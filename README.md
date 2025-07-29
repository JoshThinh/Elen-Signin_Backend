# ELEN Sign-In Backend API

This is a Flask-based backend API for the ELEN Sign-In system, designed to handle user registration, authentication, status tracking (clock in/out and breaks), messaging, desk assignments, and timesheet tracking.

---

## Features

- **User Management**
  - User signup with validation and role-based registration (user/admin)
  - User login with password verification
  - Update user email and password
  - Delete users (admin-only)
  - Fetch user details and user list (without passwords)

- **Status Tracking**
  - Clock in, break, clock out actions with automatic calculation of work and break hours
  - Real-time status updates and current hours calculation
  - Weekly timesheet aggregation

- **Messaging System**
  - Send messages between users with subject and timestamp
  - Retrieve inbox messages for a user
  - View individual messages and mark them as read
  - Soft delete and restore messages

- **Desk Management**
  - Assign and update desk location for users

- **Database**
  - Uses SQLite (`users.db`) with tables for users, timesheets, and messages
  - Automatic table creation and schema migrations on startup

- **CORS**
  - Allows requests from localhost and the deployed GitHub Pages frontend at `https://joshthinh.github.io/Elen-Signin/`

---

## Technologies

- Python 3.x
- Flask
- Flask-CORS
- SQLite3

---

## API Endpoints

### Authentication & User

| Method | Endpoint             | Description                                  | Payload / Params                                                |
|--------|----------------------|----------------------------------------------|----------------------------------------------------------------|
| POST   | `/signup`            | Register a new user                           | JSON: `username`, `password`, `email`, `room_code`, `role` (optional), `deskSelection` (optional), `avatar` (optional), `admin_code` (if role is admin) |
| POST   | `/login`             | Login user                                   | JSON: `username`, `password`                                   |
| POST   | `/update_user`       | Update user's email and password             | JSON: `username`, `email`, `password`                          |
| DELETE | `/delete_user`       | Delete a user (admin only)                    | JSON: `username`, `admin_username`                             |
| GET    | `/users`             | Get list of all users (no passwords)         | -                                                              |
| GET    | `/user/<username>`   | Get details for a specific user (no password)| URL param: `username`                                          |

### Status & Desk

| Method | Endpoint               | Description                                  | Payload / Params                             |
|--------|------------------------|----------------------------------------------|---------------------------------------------|
| POST   | `/status/<username>/<action>` | Update user's status (`clocked-in`, `break`, `clocked-out`, etc.) | URL params: `username`, `action`             |
| GET    | `/status`              | Get status summary for all users             | -                                           |
| POST   | `/update_desk`         | Update a user's desk assignment               | JSON: `username`, `desk`                     |
| GET    | `/current_hours`       | Get current work and break hours per user    | -                                           |

### Messaging

| Method | Endpoint              | Description                                  | Payload / Params                             |
|--------|-----------------------|----------------------------------------------|---------------------------------------------|
| POST   | `/inbox`              | Send a message                              | JSON: `sender`, `receiver`, `message`, `subject` (optional) |
| GET    | `/inbox`              | Get inbox messages for a user                | Query param: `username`                      |
| GET    | `/message/<id>`       | Get a single message by ID                    | URL param: message ID                        |
| DELETE | `/message/<id>`       | Soft delete a message by ID                   | URL param: message ID                        |
| POST   | `/message/<id>/undo`  | Undo delete (restore) a message               | URL param: message ID                        |

### Timesheets

| Method | Endpoint              | Description                                  | Payload / Params                             |
|--------|-----------------------|----------------------------------------------|---------------------------------------------|
| GET    | `/timesheets/week`    | Get timesheets for the current week (Mon-Fri)| -                                           |
| GET    | `/weekly_timesheets`  | Get weekly timesheet summary for all users   | -                                           |

---

## Setup & Run

1. **Clone the repo:**
   ```bash
   git clone <repository-url>
   cd <repository-folder>
