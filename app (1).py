"""
Campus Event Management Platform
Backend API built with Flask + Firebase Admin SDK
"""

import os
import json
from datetime import datetime
from functools import wraps

from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore, auth as firebase_auth

# ──────────────────────────────────────────────
# App Initialization
# ──────────────────────────────────────────────

app = Flask(__name__)
CORS(app)

# Initialize Firebase Admin SDK
# Set GOOGLE_APPLICATION_CREDENTIALS env var OR place serviceAccountKey.json in root
cred_path = os.environ.get("FIREBASE_CREDENTIALS", "serviceAccountKey.json")
if not firebase_admin._apps:
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ──────────────────────────────────────────────
# Auth Middleware
# ──────────────────────────────────────────────

def require_auth(f):
    """Verify Firebase ID token from Authorization header."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        id_token = auth_header.split("Bearer ")[1]
        try:
            decoded = firebase_auth.verify_id_token(id_token)
            request.uid = decoded["uid"]
            request.user_email = decoded.get("email", "")
        except Exception as e:
            return jsonify({"error": f"Unauthorized: {str(e)}"}), 401
        return f(*args, **kwargs)
    return decorated


# ──────────────────────────────────────────────
# Health Check
# ──────────────────────────────────────────────

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "Campus Event Platform API is running", "version": "1.0.0"})


# ──────────────────────────────────────────────
# USER PROFILE
# ──────────────────────────────────────────────

@app.route("/api/users/me", methods=["GET"])
@require_auth
def get_profile():
    """Fetch the authenticated user's profile."""
    doc = db.collection("users").document(request.uid).get()
    if not doc.exists:
        return jsonify({"error": "User profile not found"}), 404
    return jsonify(doc.to_dict()), 200


@app.route("/api/users/me", methods=["PUT"])
@require_auth
def update_profile():
    """Create or update user profile."""
    data = request.get_json()
    allowed = {"name", "department", "role", "avatar_url"}
    update = {k: v for k, v in data.items() if k in allowed}
    update["updated_at"] = datetime.utcnow().isoformat()
    update["uid"] = request.uid
    update["email"] = request.user_email
    db.collection("users").document(request.uid).set(update, merge=True)
    return jsonify({"message": "Profile updated", "data": update}), 200


# ──────────────────────────────────────────────
# TEAMS
# ──────────────────────────────────────────────

@app.route("/api/teams", methods=["POST"])
@require_auth
def create_team():
    """Create a new team."""
    data = request.get_json()
    if not data.get("name"):
        return jsonify({"error": "Team name is required"}), 400

    team = {
        "name": data["name"],
        "description": data.get("description", ""),
        "owner_uid": request.uid,
        "members": [request.uid],
        "created_at": datetime.utcnow().isoformat(),
    }
    ref = db.collection("teams").add(team)
    team["id"] = ref[1].id
    return jsonify({"message": "Team created", "data": team}), 201


@app.route("/api/teams", methods=["GET"])
@require_auth
def list_teams():
    """List all teams the authenticated user belongs to."""
    teams = (
        db.collection("teams")
        .where("members", "array_contains", request.uid)
        .stream()
    )
    result = [{"id": t.id, **t.to_dict()} for t in teams]
    return jsonify(result), 200


@app.route("/api/teams/<team_id>", methods=["GET"])
@require_auth
def get_team(team_id):
    doc = db.collection("teams").document(team_id).get()
    if not doc.exists:
        return jsonify({"error": "Team not found"}), 404
    return jsonify({"id": doc.id, **doc.to_dict()}), 200


@app.route("/api/teams/<team_id>/members", methods=["POST"])
@require_auth
def add_member(team_id):
    """Add a member to a team (owner only)."""
    team_ref = db.collection("teams").document(team_id)
    team = team_ref.get()
    if not team.exists:
        return jsonify({"error": "Team not found"}), 404
    if team.to_dict().get("owner_uid") != request.uid:
        return jsonify({"error": "Only team owner can add members"}), 403

    data = request.get_json()
    new_uid = data.get("uid")
    if not new_uid:
        return jsonify({"error": "Member UID is required"}), 400

    team_ref.update({"members": firestore.ArrayUnion([new_uid])})
    return jsonify({"message": f"Member {new_uid} added"}), 200


# ──────────────────────────────────────────────
# EVENTS
# ──────────────────────────────────────────────

@app.route("/api/events", methods=["POST"])
@require_auth
def create_event():
    """Create a new campus event."""
    data = request.get_json()
    required = ["title", "date", "location", "team_id"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"'{field}' is required"}), 400

    event = {
        "title": data["title"],
        "description": data.get("description", ""),
        "date": data["date"],
        "location": data["location"],
        "team_id": data["team_id"],
        "created_by": request.uid,
        "capacity": data.get("capacity", 100),
        "registrations": [],
        "status": "upcoming",          # upcoming | ongoing | completed | cancelled
        "created_at": datetime.utcnow().isoformat(),
    }
    ref = db.collection("events").add(event)
    event["id"] = ref[1].id
    return jsonify({"message": "Event created", "data": event}), 201


@app.route("/api/events", methods=["GET"])
@require_auth
def list_events():
    """List all events (optional ?status= filter)."""
    status = request.args.get("status")
    query = db.collection("events")
    if status:
        query = query.where("status", "==", status)
    events = [{"id": e.id, **e.to_dict()} for e in query.stream()]
    return jsonify(events), 200


@app.route("/api/events/<event_id>", methods=["GET"])
@require_auth
def get_event(event_id):
    doc = db.collection("events").document(event_id).get()
    if not doc.exists:
        return jsonify({"error": "Event not found"}), 404
    return jsonify({"id": doc.id, **doc.to_dict()}), 200


@app.route("/api/events/<event_id>", methods=["PUT"])
@require_auth
def update_event(event_id):
    """Update event details (creator only)."""
    event_ref = db.collection("events").document(event_id)
    event = event_ref.get()
    if not event.exists:
        return jsonify({"error": "Event not found"}), 404
    if event.to_dict().get("created_by") != request.uid:
        return jsonify({"error": "Only the event creator can edit it"}), 403

    data = request.get_json()
    editable = {"title", "description", "date", "location", "capacity", "status"}
    update = {k: v for k, v in data.items() if k in editable}
    update["updated_at"] = datetime.utcnow().isoformat()
    event_ref.update(update)
    return jsonify({"message": "Event updated"}), 200


@app.route("/api/events/<event_id>/register", methods=["POST"])
@require_auth
def register_for_event(event_id):
    """Register the authenticated user for an event."""
    event_ref = db.collection("events").document(event_id)
    event = event_ref.get()
    if not event.exists:
        return jsonify({"error": "Event not found"}), 404

    edata = event.to_dict()
    if request.uid in edata.get("registrations", []):
        return jsonify({"message": "Already registered"}), 200
    if len(edata.get("registrations", [])) >= edata.get("capacity", 100):
        return jsonify({"error": "Event is at full capacity"}), 409

    event_ref.update({"registrations": firestore.ArrayUnion([request.uid])})
    _send_notification(
        request.uid,
        f"You have successfully registered for '{edata['title']}'",
        "registration",
        event_id,
    )
    return jsonify({"message": "Registered successfully"}), 200


@app.route("/api/events/<event_id>/unregister", methods=["POST"])
@require_auth
def unregister_from_event(event_id):
    """Cancel registration."""
    event_ref = db.collection("events").document(event_id)
    event = event_ref.get()
    if not event.exists:
        return jsonify({"error": "Event not found"}), 404

    event_ref.update({"registrations": firestore.ArrayRemove([request.uid])})
    return jsonify({"message": "Unregistered successfully"}), 200


# ──────────────────────────────────────────────
# TASKS
# ──────────────────────────────────────────────

@app.route("/api/events/<event_id>/tasks", methods=["POST"])
@require_auth
def create_task(event_id):
    """Create a task under an event."""
    data = request.get_json()
    if not data.get("title"):
        return jsonify({"error": "Task title is required"}), 400

    task = {
        "title": data["title"],
        "description": data.get("description", ""),
        "event_id": event_id,
        "assigned_to": data.get("assigned_to", ""),    # UID of assignee
        "due_date": data.get("due_date", ""),
        "status": "pending",                            # pending | in_progress | done
        "created_by": request.uid,
        "created_at": datetime.utcnow().isoformat(),
    }
    ref = db.collection("tasks").add(task)
    task["id"] = ref[1].id

    # Notify assignee
    if task["assigned_to"]:
        event_doc = db.collection("events").document(event_id).get()
        event_title = event_doc.to_dict().get("title", "an event") if event_doc.exists else "an event"
        _send_notification(
            task["assigned_to"],
            f"You have been assigned a new task '{task['title']}' for '{event_title}'",
            "task_assigned",
            event_id,
        )

    return jsonify({"message": "Task created", "data": task}), 201


@app.route("/api/events/<event_id>/tasks", methods=["GET"])
@require_auth
def list_tasks(event_id):
    tasks = db.collection("tasks").where("event_id", "==", event_id).stream()
    return jsonify([{"id": t.id, **t.to_dict()} for t in tasks]), 200


@app.route("/api/tasks/<task_id>", methods=["PUT"])
@require_auth
def update_task(task_id):
    """Update task status or details."""
    task_ref = db.collection("tasks").document(task_id)
    task = task_ref.get()
    if not task.exists:
        return jsonify({"error": "Task not found"}), 404

    data = request.get_json()
    editable = {"title", "description", "assigned_to", "due_date", "status"}
    update = {k: v for k, v in data.items() if k in editable}
    update["updated_at"] = datetime.utcnow().isoformat()
    task_ref.update(update)
    return jsonify({"message": "Task updated"}), 200


@app.route("/api/tasks/mine", methods=["GET"])
@require_auth
def my_tasks():
    """Get all tasks assigned to the current user."""
    tasks = db.collection("tasks").where("assigned_to", "==", request.uid).stream()
    return jsonify([{"id": t.id, **t.to_dict()} for t in tasks]), 200


# ──────────────────────────────────────────────
# NOTIFICATIONS
# ──────────────────────────────────────────────

def _send_notification(uid: str, message: str, notif_type: str, ref_id: str = ""):
    """Internal helper to write a notification to Firestore."""
    db.collection("notifications").add({
        "uid": uid,
        "message": message,
        "type": notif_type,
        "ref_id": ref_id,
        "read": False,
        "created_at": datetime.utcnow().isoformat(),
    })


@app.route("/api/notifications", methods=["GET"])
@require_auth
def get_notifications():
    """Get all notifications for the current user."""
    notifs = (
        db.collection("notifications")
        .where("uid", "==", request.uid)
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .limit(50)
        .stream()
    )
    return jsonify([{"id": n.id, **n.to_dict()} for n in notifs]), 200


@app.route("/api/notifications/<notif_id>/read", methods=["POST"])
@require_auth
def mark_notification_read(notif_id):
    db.collection("notifications").document(notif_id).update({"read": True})
    return jsonify({"message": "Marked as read"}), 200


# ──────────────────────────────────────────────
# DASHBOARD
# ──────────────────────────────────────────────

@app.route("/api/dashboard", methods=["GET"])
@require_auth
def dashboard():
    """Aggregate summary for the authenticated user's dashboard."""
    uid = request.uid

    # My teams
    teams = list(
        db.collection("teams").where("members", "array_contains", uid).stream()
    )
    team_ids = [t.id for t in teams]

    # All events
    all_events = [{"id": e.id, **e.to_dict()} for e in db.collection("events").stream()]

    # Events I'm registered for
    my_registrations = [e for e in all_events if uid in e.get("registrations", [])]

    # Upcoming events (status == upcoming)
    upcoming = [e for e in all_events if e.get("status") == "upcoming"]

    # My tasks
    my_tasks_query = list(
        db.collection("tasks").where("assigned_to", "==", uid).stream()
    )
    pending_tasks = [t for t in my_tasks_query if t.to_dict().get("status") != "done"]

    # Unread notifications
    unread = list(
        db.collection("notifications")
        .where("uid", "==", uid)
        .where("read", "==", False)
        .stream()
    )

    return jsonify({
        "summary": {
            "teams_count": len(teams),
            "registered_events": len(my_registrations),
            "upcoming_events": len(upcoming),
            "pending_tasks": len(pending_tasks),
            "unread_notifications": len(unread),
        },
        "my_teams": [{"id": t.id, "name": t.to_dict().get("name")} for t in teams],
        "registered_events": my_registrations[:5],
        "upcoming_events": upcoming[:5],
        "my_pending_tasks": [{"id": t.id, **t.to_dict()} for t in pending_tasks[:5]],
    }), 200


# ──────────────────────────────────────────────
# Entry Point
# ──────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
