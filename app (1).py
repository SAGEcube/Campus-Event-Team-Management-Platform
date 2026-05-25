import streamlit as st
import requests
import json
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore, auth as firebase_auth

# ---------------------------
# Firebase configuration
# ---------------------------
# You need a service account JSON file (see instructions below)
# Place it in the same directory and name it 'serviceAccountKey.json'
# Or set the environment variable FIREBASE_CREDENTIALS

firebase_config = {
    "apiKey": st.secrets["FIREBASE_API_KEY"],          # From Firebase Console
    "authDomain": st.secrets["FIREBASE_AUTH_DOMAIN"],
    "projectId": st.secrets["FIREBASE_PROJECT_ID"],
    "databaseURL": st.secrets["FIREBASE_DATABASE_URL"], # optional for Firestore
}

# Initialize Firebase Admin SDK (only once)
if not firebase_admin._apps:
    cred_path = "serviceAccountKey.json"
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ---------------------------
# Helper functions
# ---------------------------

def sign_in_with_email(email, password):
    """Sign in using Firebase Auth REST API"""
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_config['apiKey']}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    response = requests.post(url, data=payload)
    return response.json()

def sign_up_with_email(email, password):
    """Create a new user using Firebase Auth REST API"""
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={firebase_config['apiKey']}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    response = requests.post(url, data=payload)
    return response.json()

def get_user_profile(uid):
    doc = db.collection("users").document(uid).get()
    if doc.exists:
        return doc.to_dict()
    return None

def update_user_profile(uid, data):
    data["uid"] = uid
    data["updated_at"] = datetime.utcnow().isoformat()
    db.collection("users").document(uid).set(data, merge=True)

def send_notification(uid, message, notif_type, ref_id=""):
    db.collection("notifications").add({
        "uid": uid,
        "message": message,
        "type": notif_type,
        "ref_id": ref_id,
        "read": False,
        "created_at": datetime.utcnow().isoformat(),
    })

# ---------------------------
# Session state initialization
# ---------------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "user_email" not in st.session_state:
    st.session_state.user_email = None
if "id_token" not in st.session_state:
    st.session_state.id_token = None

# ---------------------------
# Authentication UI
# ---------------------------
def auth_page():
    st.title("Campus Event Management Platform")
    tab1, tab2 = st.tabs(["Sign In", "Sign Up"])

    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login"):
            resp = sign_in_with_email(email, password)
            if "idToken" in resp:
                # Verify token with Firebase Admin
                decoded = firebase_auth.verify_id_token(resp["idToken"])
                st.session_state.user_id = decoded["uid"]
                st.session_state.user_email = email
                st.session_state.id_token = resp["idToken"]
                st.session_state.authenticated = True
                # Ensure user document exists
                if not get_user_profile(decoded["uid"]):
                    update_user_profile(decoded["uid"], {
                        "email": email,
                        "name": email.split("@")[0],
                        "role": "member",
                        "created_at": datetime.utcnow().isoformat(),
                    })
                st.rerun()
            else:
                st.error("Login failed: " + resp.get("error", {}).get("message", "Unknown error"))

    with tab2:
        new_email = st.text_input("Email", key="signup_email")
        new_password = st.text_input("Password", type="password", key="signup_password")
        name = st.text_input("Full Name", key="signup_name")
        if st.button("Create Account"):
            resp = sign_up_with_email(new_email, new_password)
            if "idToken" in resp:
                uid = firebase_auth.verify_id_token(resp["idToken"])["uid"]
                update_user_profile(uid, {
                    "email": new_email,
                    "name": name,
                    "role": "member",
                    "created_at": datetime.utcnow().isoformat(),
                })
                st.success("Account created! Please sign in.")
            else:
                st.error("Signup failed: " + resp.get("error", {}).get("message", "Unknown error"))

# ---------------------------
# Main App after login
# ---------------------------
def main_app():
    st.sidebar.title(f"Welcome, {st.session_state.user_email}")
    menu = st.sidebar.radio("Navigation", ["Dashboard", "Teams", "Events", "Tasks", "Notifications", "Profile"])

    if st.sidebar.button("Logout"):
        for key in ["authenticated", "user_id", "user_email", "id_token"]:
            st.session_state[key] = None
        st.rerun()

    uid = st.session_state.user_id

    # ----- Dashboard -----
    if menu == "Dashboard":
        st.header("Dashboard")

        # Get statistics
        teams = list(db.collection("teams").where("members", "array_contains", uid).stream())
        events = [{"id": e.id, **e.to_dict()} for e in db.collection("events").stream()]
        my_events = [e for e in events if uid in e.get("registrations", [])]
        upcoming = [e for e in events if e.get("status") == "upcoming"]
        tasks = list(db.collection("tasks").where("assigned_to", "==", uid).stream())
        pending_tasks = [t for t in tasks if t.to_dict().get("status") != "done"]
        unread = list(db.collection("notifications").where("uid", "==", uid).where("read", "==", False).stream())

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Teams", len(teams))
        col2.metric("Registered Events", len(my_events))
        col3.metric("Upcoming Events", len(upcoming))
        col4.metric("Pending Tasks", len(pending_tasks))

        st.subheader("Your Teams")
        for t in teams[:5]:
            st.write(f"• {t.to_dict().get('name', 'Unnamed')}")

        st.subheader("Upcoming Events")
        for e in upcoming[:5]:
            st.write(f"• {e['title']} on {e.get('date', 'TBD')}")

        st.subheader("Pending Tasks")
        for t in pending_tasks[:5]:
            st.write(f"• {t.to_dict().get('title', 'Task')} - {t.to_dict().get('status', 'pending')}")

    # ----- Teams -----
    elif menu == "Teams":
        st.header("Manage Teams")

        with st.expander("Create New Team"):
            name = st.text_input("Team Name")
            desc = st.text_area("Description")
            if st.button("Create Team"):
                if name:
                    team = {
                        "name": name,
                        "description": desc,
                        "owner_uid": uid,
                        "members": [uid],
                        "created_at": datetime.utcnow().isoformat(),
                    }
                    db.collection("teams").add(team)
                    st.success("Team created!")
                    st.rerun()
                else:
                    st.error("Team name required")

        st.subheader("Your Teams")
        teams = db.collection("teams").where("members", "array_contains", uid).stream()
        for team in teams:
            team_data = team.to_dict()
            with st.expander(f"📌 {team_data['name']}"):
                st.write(f"Description: {team_data.get('description', '')}")
                st.write(f"Owner: {team_data.get('owner_uid')}")
                st.write(f"Members: {', '.join(team_data.get('members', []))}")

                if team_data.get("owner_uid") == uid:
                    new_member = st.text_input(f"Add member UID to {team_data['name']}", key=f"add_{team.id}")
                    if st.button("Add", key=f"btn_{team.id}"):
                        if new_member:
                            team_ref = db.collection("teams").document(team.id)
                            team_ref.update({"members": firestore.ArrayUnion([new_member])})
                            send_notification(new_member, f"You were added to team {team_data['name']}", "team_add")
                            st.success(f"Added {new_member}")
                            st.rerun()

    # ----- Events -----
    elif menu == "Events":
        st.header("Events")

        with st.expander("Create New Event"):
            title = st.text_input("Title")
            date = st.date_input("Date")
            location = st.text_input("Location")
            capacity = st.number_input("Capacity", min_value=1, value=100)
            description = st.text_area("Description")
            # Choose team from user's teams
            teams = list(db.collection("teams").where("members", "array_contains", uid).stream())
            team_options = {t.id: t.to_dict().get("name", t.id) for t in teams}
            selected_team = st.selectbox("Team", options=list(team_options.keys()), format_func=lambda x: team_options[x])
            if st.button("Create Event"):
                if title and date and location and selected_team:
                    event = {
                        "title": title,
                        "description": description,
                        "date": date.isoformat(),
                        "location": location,
                        "team_id": selected_team,
                        "created_by": uid,
                        "capacity": capacity,
                        "registrations": [],
                        "status": "upcoming",
                        "created_at": datetime.utcnow().isoformat(),
                    }
                    db.collection("events").add(event)
                    st.success("Event created!")
                    st.rerun()
                else:
                    st.error("Please fill all required fields")

        st.subheader("All Events")
        events = db.collection("events").stream()
        for ev in events:
            ev_data = ev.to_dict()
            with st.expander(f"📅 {ev_data['title']} - {ev_data.get('date', 'No date')}"):
                st.write(f"Location: {ev_data.get('location')}")
                st.write(f"Capacity: {len(ev_data.get('registrations', []))}/{ev_data.get('capacity', 100)}")
                st.write(f"Status: {ev_data.get('status')}")
                if st.button("Register", key=f"reg_{ev.id}"):
                    if uid not in ev_data.get("registrations", []):
                        if len(ev_data.get("registrations", [])) < ev_data.get("capacity", 100):
                            db.collection("events").document(ev.id).update({
                                "registrations": firestore.ArrayUnion([uid])
                            })
                            send_notification(uid, f"You registered for {ev_data['title']}", "registration", ev.id)
                            st.success("Registered!")
                            st.rerun()
                        else:
                            st.error("Event is full")
                    else:
                        st.info("Already registered")
                if st.button("Unregister", key=f"unreg_{ev.id}"):
                    db.collection("events").document(ev.id).update({
                        "registrations": firestore.ArrayRemove([uid])
                    })
                    st.success("Unregistered")
                    st.rerun()

    # ----- Tasks -----
    elif menu == "Tasks":
        st.header("Tasks")

        # Show tasks assigned to me
        st.subheader("My Tasks")
        my_tasks = db.collection("tasks").where("assigned_to", "==", uid).stream()
        for task in my_tasks:
            tdata = task.to_dict()
            with st.expander(f"📋 {tdata['title']} - {tdata.get('status', 'pending')}"):
                st.write(f"Description: {tdata.get('description', '')}")
                st.write(f"Due date: {tdata.get('due_date', 'Not set')}")
                new_status = st.selectbox("Update status", ["pending", "in_progress", "done"], index=["pending","in_progress","done"].index(tdata.get("status","pending")), key=f"status_{task.id}")
                if st.button("Update", key=f"upd_{task.id}"):
                    db.collection("tasks").document(task.id).update({"status": new_status})
                    st.success("Updated")
                    st.rerun()

        # Create task for an event (only if you are the event creator)
        st.subheader("Create Task for an Event")
        events_created = db.collection("events").where("created_by", "==", uid).stream()
        event_choices = {e.id: e.to_dict().get("title", e.id) for e in events_created}
        if event_choices:
            selected_event = st.selectbox("Event", options=list(event_choices.keys()), format_func=lambda x: event_choices[x])
            task_title = st.text_input("Task Title")
            task_desc = st.text_area("Description")
            assignee = st.text_input("Assign to (User UID)")
            due_date = st.date_input("Due date")
            if st.button("Create Task"):
                if task_title and selected_event:
                    task = {
                        "title": task_title,
                        "description": task_desc,
                        "event_id": selected_event,
                        "assigned_to": assignee,
                        "due_date": due_date.isoformat() if due_date else "",
                        "status": "pending",
                        "created_by": uid,
                        "created_at": datetime.utcnow().isoformat(),
                    }
                    db.collection("tasks").add(task)
                    if assignee:
                        send_notification(assignee, f"New task '{task_title}' assigned", "task_assigned", selected_event)
                    st.success("Task created")
                    st.rerun()
                else:
                    st.error("Task title required")
        else:
            st.info("You haven't created any events yet. Events you create can have tasks.")

    # ----- Notifications -----
    elif menu == "Notifications":
        st.header("Notifications")
        notifs = db.collection("notifications").where("uid", "==", uid).order_by("created_at", direction=firestore.Query.DESCENDING).limit(50).stream()
        for n in notifs:
            n_data = n.to_dict()
            read_status = "✅" if n_data.get("read") else "🔔"
            st.write(f"{read_status} {n_data['message']} - {n_data.get('created_at', '')}")
            if not n_data.get("read"):
                if st.button("Mark as read", key=f"read_{n.id}"):
                    db.collection("notifications").document(n.id).update({"read": True})
                    st.rerun()

    # ----- Profile -----
    elif menu == "Profile":
        st.header("Your Profile")
        profile = get_user_profile(uid) or {}
        name = st.text_input("Name", value=profile.get("name", ""))
        department = st.text_input("Department", value=profile.get("department", ""))
        role = st.selectbox("Role", ["member", "team_lead", "admin"], index=["member","team_lead","admin"].index(profile.get("role", "member")))
        if st.button("Update Profile"):
            update_user_profile(uid, {"name": name, "department": department, "role": role})
            st.success("Profile updated")
            st.rerun()

# ---------------------------
# Run the app
# ---------------------------
if not st.session_state.authenticated:
    auth_page()
else:
    main_app()
