from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import sqlite3
import os
from datetime import datetime, date, timedelta

app = Flask(__name__, static_folder='.')
CORS(app, resources={
    r"/*": 
    {"origins": [
        "http://localhost:8000", 
        "https://joshthinh.github.io",
        "https://joshthinh.github.io/Elen-Signin"
        ]
    }
})  # ← Make sure this is after app creation

DB_FILE = 'users.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT NOT NULL,
            room_code TEXT NOT NULL,
            desk TEXT,
            avatar TEXT,
            status TEXT DEFAULT 'none',
            role TEXT DEFAULT 'user',
            work_hours REAL DEFAULT 0,
            break_hours REAL DEFAULT 0,
            last_clock_in TEXT,
            last_break_start TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS timesheets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            date TEXT NOT NULL,
            work_hours REAL DEFAULT 0,
            break_hours REAL DEFAULT 0
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            receiver TEXT NOT NULL,
            subject TEXT,
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            is_read INTEGER DEFAULT 0
        )
    ''')
    # Add avatar column if it doesn't exist (for migration)
    try:
        c.execute('ALTER TABLE users ADD COLUMN avatar TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
    # Add deleted column to messages if it doesn't exist
    try:
        c.execute('ALTER TABLE messages ADD COLUMN deleted INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass  # Already exists
    conn.commit()
    conn.close()

init_db()


def get_all_users():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT username, password, email, room_code, desk, avatar, status, role, work_hours, break_hours FROM users')
    users = [dict(zip(['username', 'password', 'email', 'room_code', 'desk', 'avatar', 'status', 'role', 'work_hours', 'break_hours'], row)) for row in c.fetchall()]
    conn.close()
    return users

def find_user_by_username(username):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT username, password, email, room_code, desk, status, role, work_hours, break_hours FROM users WHERE username = ?', (username,))
    row = c.fetchone()
    conn.close()
    if row:
        return dict(zip(['username', 'password', 'email', 'room_code', 'desk', 'status', 'role', 'work_hours', 'break_hours'], row))
    return None

def add_user(user):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''INSERT INTO users (username, password, email, room_code, desk, avatar, status, role, work_hours, break_hours) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (user['username'], user['password'], user['email'], user['room_code'], user.get('desk'), user.get('avatar'), user.get('status', 'none'), user.get('role', 'user'), user.get('work_hours', 0), user.get('break_hours', 0)))
    conn.commit()
    conn.close()

def update_user_status(username, action):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.now().isoformat()
    
    # Fetch current user info
    c.execute('SELECT status, last_clock_in, last_break_start, work_hours, break_hours FROM users WHERE username = ?', (username,))
    row = c.fetchone()
    if not row:
        conn.close()
        return
    
    status, last_clock_in, last_break_start, work_hours, break_hours = row
    work_hours = work_hours or 0
    break_hours = break_hours or 0
    
    if action == 'clocked-in':
        if status == 'break':
            # Coming back from break - add break time and continue work
            if last_break_start:
                try:
                    start = datetime.fromisoformat(last_break_start)
                    elapsed = (datetime.now() - start).total_seconds() / 3600.0
                    break_hours += elapsed
                except ValueError:
                    # Handle invalid datetime format
                    pass
            c.execute('UPDATE users SET status = ?, last_clock_in = ?, break_hours = ?, last_break_start = NULL WHERE username = ?', 
                     ('clocked-in', now, break_hours, username))
        else:
            # Fresh clock in - just start work timer
            c.execute('UPDATE users SET status = ?, last_clock_in = ? WHERE username = ?', 
                     (action, now, username))
    
    elif action == 'break':
        if status == 'clocked-in' and last_clock_in:
            # Going on break - add work time and start break
            try:
                start = datetime.fromisoformat(last_clock_in)
                elapsed = (datetime.now() - start).total_seconds() / 3600.0
                work_hours += elapsed
            except ValueError:
                # Handle invalid datetime format
                pass
            c.execute('UPDATE users SET status = ?, last_break_start = ?, work_hours = ?, last_clock_in = NULL WHERE username = ?', 
                     (action, now, work_hours, username))
        else:
            # Just update status if not coming from work
            c.execute('UPDATE users SET status = ? WHERE username = ?', (action, username))
    
    elif action == 'clocked-out':
        # End work - add current session time and save to timesheet
        if status == 'clocked-in' and last_clock_in:
            # Add final work session
            try:
                start = datetime.fromisoformat(last_clock_in)
                elapsed = (datetime.now() - start).total_seconds() / 3600.0
                work_hours += elapsed
            except ValueError:
                # Handle invalid datetime format
                pass
        elif status == 'break' and last_break_start:
            # Add final break session
            try:
                start = datetime.fromisoformat(last_break_start)
                elapsed = (datetime.now() - start).total_seconds() / 3600.0
                break_hours += elapsed
            except ValueError:
                # Handle invalid datetime format
                pass
        
        # Save to timesheet
        today = date.today().isoformat()
        c.execute('''INSERT INTO timesheets (username, date, work_hours, break_hours) VALUES (?, ?, ?, ?)''', 
                 (username, today, work_hours, break_hours))
        
        # Reset for next day
        c.execute('UPDATE users SET status = ?, work_hours = 0, break_hours = 0, last_clock_in = NULL, last_break_start = NULL WHERE username = ?', 
                 (action, username))
    
    else:
        # Just update status for other actions
        c.execute('UPDATE users SET status = ? WHERE username = ?', (action, username))
    
    conn.commit()
    conn.close()

@app.route("/signup", methods=["POST"])
def signup():
    data = request.json
    if not isinstance(data, dict) or not all(k in data for k in ("username", "password", "email", "room_code", "role")):
        return jsonify({"error": "Missing fields"}), 400
    if find_user_by_username(data["username"]):
        return jsonify({"error": "User exists"}), 409

    if data["room_code"] == "54321" and not data.get("deskSelection"):
        return jsonify({"error": "Desk selection required for this code"}), 400
    
    role = "admin" if data.get("role") == "admin" else "user"
    if role == "admin":
        if data.get("admin_code") != "1122334455":
            return jsonify({"error": "Invalid admin code"}), 403
    
    add_user({
        "username": data["username"],
        "password": data["password"],
        "email": data["email"],
        "room_code": data["room_code"],
        "desk": data.get("deskSelection") if data.get("deskSelection") else None,
        "avatar": data.get("avatar"),  # <-- Add this line!
        "status": "none",
        "role": role,
        "work_hours": 0,
        "break_hours": 0,
        "inbox": []
    })
    
    return jsonify({"message": "User registered"}), 201

def is_admin(username):
    user = find_user_by_username(username)
    return user and user.get("role") == "admin"

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    if not isinstance(data, dict) or not all(k in data for k in ("username", "password")):
        return jsonify({"error": "Missing fields"}), 400
    user = find_user_by_username(data["username"])
    if user and user["password"] == data["password"]:
        user.pop('password', None)  # Don't send password to frontend
        return jsonify({"message": "Login successful", "user": user}), 200
    return jsonify({"error": "Unable to login"}), 401

@app.route("/status/<username>/<action>", methods=["POST"])
def update_status(username, action):
    user = find_user_by_username(username)
    if user:
        update_user_status(username, action)
        return jsonify({"message": f"Status updated to {action}"}), 200
    return jsonify({"error": "User not found"}), 404

@app.route("/update_desk", methods=["POST"])
def update_desk():
    data = request.json
    if not isinstance(data, dict):
        return jsonify({"error": "Missing fields"}), 400
    username = data.get("username")
    desk = data.get("desk")
    if not username or not desk:
        return jsonify({"error": "Missing fields"}), 400
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('UPDATE users SET desk = ? WHERE username = ?', (desk, username))
    conn.commit()
    conn.close()
    return jsonify({"message": "Desk updated"}), 200

@app.route("/update_user", methods=["POST"])
def update_user():
    data = request.json
    if not isinstance(data, dict) or not all(k in data for k in ("username", "email", "password")):
        return jsonify({"error": "Missing fields"}), 400
    username = data["username"]
    email = data["email"]
    password = data["password"]
    user = find_user_by_username(username)
    if not user:
        return jsonify({"error": "User not found"}), 404
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET email = ?, password = ? WHERE username = ?", (email, password, username))
    conn.commit()
    conn.close()
    return jsonify({"message": "Account updated successfully!"}), 200

@app.route("/status", methods=["GET"])
def get_status():
    users = get_all_users()
    return jsonify({
        "users": [
            {
                "username": u["username"],
                "desk": u.get("desk"),
                "avatar": u.get("avatar"),
                "status": u.get("status", "none"),
            }
            for u in users
        ]
    }), 200

ADMIN_PASSWORD = 552211 

@app.route("/users", methods=["GET"])
def get_users():
    users = get_all_users()
    # Remove passwords from the response
    for user in users:
        user.pop('password', None)
    return jsonify({"users": users}), 200

@app.route("/delete_user", methods=["DELETE"])
def delete_user():
    data = request.json
    if not isinstance(data, dict) or not all(k in data for k in ("username", "admin_username")):
        return jsonify({"error": "Missing fields"}), 400
    
    admin_username = data["admin_username"]
    target_username = data["username"]
    
    # Check if admin_username is actually an admin
    admin_user = find_user_by_username(admin_username)
    if not admin_user or admin_user.get("role") != "admin":
        return jsonify({"error": "Unauthorized - Admin privileges required"}), 403
    
    # Check if target user exists
    target_user = find_user_by_username(target_username)
    if not target_user:
        return jsonify({"error": "User not found"}), 404
    
    # Prevent admin from deleting themselves
    if admin_username == target_username:
        return jsonify({"error": "Cannot delete yourself"}), 400
    
    # Delete the user
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE username = ?", (target_username,))
    conn.commit()
    conn.close()
    
    return jsonify({"message": f"User '{target_username}' deleted successfully"}), 200

@app.route('/user/<username>', methods=['GET'])
def get_user(username):
    try:
        user = find_user_by_username(username)
        if user:
            user.pop('password', None)
            return jsonify(user), 200
        else:
            return jsonify({'error': 'User not found'}), 404
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/inbox', methods=['POST'])
def send_message():
    data = request.json
    required = ['sender', 'receiver', 'message']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing fields'}), 400
    subject = data.get('subject', '')
    timestamp = datetime.now().isoformat()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('INSERT INTO messages (sender, receiver, subject, message, timestamp) VALUES (?, ?, ?, ?, ?)',
              (data['sender'], data['receiver'], subject, data['message'], timestamp))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Message sent!'}), 201

@app.route('/inbox', methods=['GET'])
def get_inbox():
    username = request.args.get('username')
    if not username:
        return jsonify({'error': 'Username required'}), 400
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT id, sender, subject, message, timestamp FROM messages WHERE receiver = ? AND (deleted IS NULL OR deleted = 0) ORDER BY timestamp DESC', (username,))
    messages = [
        {'id': row[0], 'sender': row[1], 'subject': row[2], 'message': row[3], 'timestamp': row[4]}
        for row in c.fetchall()
    ]
    conn.close()
    return jsonify({'message': messages})

@app.route('/message/<int:message_id>', methods=['GET'])
def view_message(message_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT id, sender, receiver, subject, message, timestamp, is_read FROM messages WHERE id = ?', (message_id,))
    row = c.fetchone()
    if row:
        # Optionally mark as read
        c.execute('UPDATE messages SET is_read = 1 WHERE id = ?', (message_id,))
        conn.commit()
        message = dict(zip(['id', 'sender', 'receiver', 'subject', 'message', 'timestamp', 'is_read'], row))
        conn.close()
        return jsonify({'message': message}), 200
    else:
        conn.close()
        return jsonify({'error': 'Message not found'}), 404

@app.route('/message/<int:message_id>', methods=['DELETE'])
def delete_message(message_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('UPDATE messages SET deleted = 1 WHERE id = ?', (message_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Message deleted'}), 200

@app.route('/message/<int:message_id>/undo', methods=['POST'])
def undo_delete_message(message_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('UPDATE messages SET deleted = 0 WHERE id = ?', (message_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Message restored'}), 200

@app.route('/timesheets/week', methods=['GET'])
def get_week_timesheets():
    # Calculate current week's Monday and Friday
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)
    # Get all users
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT DISTINCT username FROM users')
    users = [row[0] for row in c.fetchall()]
    # Prepare result
    result = {}
    for user in users:
        # Get timesheet entries for this user for current week (Mon-Fri)
        c.execute('''SELECT date, work_hours, break_hours FROM timesheets WHERE username = ? AND date >= ? AND date <= ?''', (user, monday.isoformat(), friday.isoformat()))
        entries = c.fetchall()
        # Map date to hours
        day_map = {row[0]: {'work_hours': row[1], 'break_hours': row[2]} for row in entries}
        # Build week data (Monday to Friday)
        week_data = []
        for i in range(5):
            day = (monday + timedelta(days=i)).isoformat()
            week_data.append({
                'date': day,
                'work_hours': day_map.get(day, {}).get('work_hours', 0),
                'break_hours': day_map.get(day, {}).get('break_hours', 0)
            })
        result[user] = week_data
    conn.close()
    return jsonify(result), 200

def get_week_dates():
    today = date.today()
    # Monday is 0, Sunday is 6
    start = today - timedelta(days=today.weekday())  # Monday
    return [(start + timedelta(days=i)).isoformat() for i in range(5)]  # Mon-Fri

@app.route("/weekly_timesheets", methods=["GET"])
def weekly_timesheets():
    week_dates = get_week_dates()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Get all users
    c.execute("SELECT username FROM users")
    users = [row[0] for row in c.fetchall()]
    # Get timesheets for this week
    c.execute("SELECT username, date, work_hours, break_hours FROM timesheets WHERE date IN ({})".format(
        ",".join(["?"]*len(week_dates))
    ), week_dates)
    timesheet_rows = c.fetchall()
    conn.close()
    # Build a dict: {username: {date: {work_hours, break_hours}}}
    timesheets = {u: {d: {"work_hours": 0, "break_hours": 0} for d in week_dates} for u in users}
    for username, d, wh, bh in timesheet_rows:
        timesheets[username][d] = {"work_hours": wh, "break_hours": bh}
    return jsonify({
        "week_dates": week_dates,
        "users": [
            {
                "username": u,
                "days": [timesheets[u][d] for d in week_dates]
            }
            for u in users
        ]
    })

@app.route("/current_hours", methods=["GET"])
def get_current_hours():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT username, work_hours, break_hours, status, last_clock_in, last_break_start FROM users')
    rows = c.fetchall()
    conn.close()
    
    current_time = datetime.now()
    result = []
    
    for row in rows:
        username, work_hours, break_hours, status, last_clock_in, last_break_start = row
        work_hours = work_hours or 0
        break_hours = break_hours or 0
        
        # Add current session time if user is actively working
        if status == 'clocked-in' and last_clock_in:
            try:
                start = datetime.fromisoformat(last_clock_in)
                elapsed = (current_time - start).total_seconds() / 3600.0
                work_hours += elapsed
            except ValueError:
                # Handle invalid datetime format
                pass
        elif status == 'break' and last_break_start:
            try:
                start = datetime.fromisoformat(last_break_start)
                elapsed = (current_time - start).total_seconds() / 3600.0
                break_hours += elapsed
            except ValueError:
                # Handle invalid datetime format
                pass
            
        result.append({
            'username': username,
            'work_hours': round(work_hours, 2),
            'break_hours': round(break_hours, 2),
            'status': status
        })
    
    return jsonify(result), 200

if __name__ == '__main__':
    app.run(debug=True)

