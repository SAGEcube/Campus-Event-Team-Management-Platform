# 🎓 Campus Event Management Platform

A full-stack platform for managing campus events — built with **React** (frontend) and **Flask + Firebase** (backend). Supports team creation, event registration, task assignment, real-time notifications, and a personal dashboard.

---

## 📐 Architecture

```
┌────────────────────┐        REST API         ┌──────────────────────┐
│  React Frontend    │  ◄──────────────────►   │  Flask Backend       │
│  (Firebase Auth)   │                         │  (app.py)            │
└────────────────────┘                         └──────────┬───────────┘
                                                          │ Firebase Admin SDK
                                                          ▼
                                               ┌──────────────────────┐
                                               │  Firebase            │
                                               │  ├─ Firestore (DB)   │
                                               │  └─ Authentication   │
                                               └──────────────────────┘
```

---

## 🗂️ Project Structure

```
campus-event-platform/
├── backend/
│   ├── app.py                  # Flask API — all routes
│   ├── requirements.txt        # Python dependencies
│   └── serviceAccountKey.json  # Firebase service account (DO NOT COMMIT)
│
├── frontend/
│   ├── public/
│   └── src/
│       ├── components/
│       │   ├── Dashboard.jsx
│       │   ├── Events/
│       │   │   ├── EventList.jsx
│       │   │   ├── EventCard.jsx
│       │   │   └── EventForm.jsx
│       │   ├── Teams/
│       │   │   ├── TeamList.jsx
│       │   │   └── TeamForm.jsx
│       │   ├── Tasks/
│       │   │   ├── TaskList.jsx
│       │   │   └── TaskCard.jsx
│       │   └── Notifications/
│       │       └── NotificationBell.jsx
│       ├── firebase.js         # Firebase client config
│       ├── App.jsx
│       └── index.js
│
└── README.md
```

---

## ⚙️ Backend Setup (Flask)

### Prerequisites
- Python 3.10+
- A Firebase project with **Firestore** and **Authentication** enabled

### 1. Clone & install dependencies
```bash
git clone https://github.com/your-org/campus-event-platform.git
cd campus-event-platform/backend
pip install -r requirements.txt
```

### 2. Configure Firebase
1. Go to **Firebase Console → Project Settings → Service Accounts**
2. Click **Generate new private key** — download `serviceAccountKey.json`
3. Place it in the `backend/` folder

Or use an environment variable:
```bash
export FIREBASE_CREDENTIALS=/path/to/serviceAccountKey.json
```

### 3. Run the server
```bash
# Development
python app.py

# Production (Gunicorn)
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

The API will be available at `http://localhost:5000`.

---

## 🔥 Frontend Setup (React + Firebase)

### 1. Install dependencies
```bash
cd frontend
npm install
```

### 2. Firebase client config
Create `src/firebase.js`:
```javascript
import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";

const firebaseConfig = {
  apiKey: "YOUR_API_KEY",
  authDomain: "YOUR_PROJECT.firebaseapp.com",
  projectId: "YOUR_PROJECT_ID",
  storageBucket: "YOUR_PROJECT.appspot.com",
  messagingSenderId: "YOUR_SENDER_ID",
  appId: "YOUR_APP_ID"
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
```

### 3. Start the app
```bash
npm start
```

---

## 🔌 API Reference

All endpoints (except `/`) require a Firebase ID token:
```
Authorization: Bearer <FIREBASE_ID_TOKEN>
```

### Auth & User
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/users/me` | Get my profile |
| PUT | `/api/users/me` | Create / update profile |

### Teams
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/teams` | Create a team |
| GET | `/api/teams` | List my teams |
| GET | `/api/teams/:id` | Get team details |
| POST | `/api/teams/:id/members` | Add a member (owner only) |

### Events
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/events` | Create an event |
| GET | `/api/events` | List all events (`?status=upcoming`) |
| GET | `/api/events/:id` | Get event details |
| PUT | `/api/events/:id` | Update event (creator only) |
| POST | `/api/events/:id/register` | Register for event |
| POST | `/api/events/:id/unregister` | Cancel registration |

### Tasks
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/events/:id/tasks` | Create a task |
| GET | `/api/events/:id/tasks` | List tasks for event |
| PUT | `/api/tasks/:id` | Update task |
| GET | `/api/tasks/mine` | My assigned tasks |

### Notifications
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/notifications` | Get my notifications |
| POST | `/api/notifications/:id/read` | Mark as read |

### Dashboard
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboard` | Aggregated summary |

---

## 🗄️ Firestore Collections

| Collection | Description |
|------------|-------------|
| `users` | User profiles (uid, name, department, role) |
| `teams` | Teams with member lists |
| `events` | Campus events with registrations array |
| `tasks` | Tasks linked to events, assigned to users |
| `notifications` | User notification feed |

---

## 🚀 Deployment

### Backend — Google Cloud Run
```bash
gcloud run deploy campus-event-api \
  --source . \
  --region us-central1 \
  --allow-unauthenticated
```

### Frontend — Firebase Hosting
```bash
npm run build
firebase deploy --only hosting
```

---

## 🔐 Security Notes

- `serviceAccountKey.json` must **never** be committed to version control. Add it to `.gitignore`.
- All Firestore write rules should be enforced at the **Firebase Security Rules** level in addition to the API layer.
- Use HTTPS in production; set `FLASK_DEBUG=false`.

---

## 🛣️ Roadmap

- [ ] Real-time notifications via Firebase Cloud Messaging (FCM)
- [ ] Calendar view integration
- [ ] Event photo gallery (Firebase Storage)
- [ ] CSV export of registrations
- [ ] Role-based access (Admin / Organizer / Attendee)
- [ ] Email reminders via SendGrid

---

## 📄 License

MIT License — feel free to use, modify, and distribute.
