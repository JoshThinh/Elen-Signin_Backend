from flask import Flask, request, jsonify
from flask_cors import CORS
import json

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:8000"}})  # ← Make sure this is after app creation

DATA_FILE = 'users.json'

def read_data():
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def write_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

@app.route("/signup", methods=["POST"])
def signup():
    data = request.json
    users = read_data()
    for user in users:
        if user["username"] == data["username"]:
            return jsonify({"error": "User exists"}), 409
    users.append({
        "username": data["username"],
        "password": data["password"],
        "email": data["email"],
        "code": data["code"],
        "status": "none"
    })
    write_data(users)
    return jsonify({"message": "User registered"}), 201

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    if not all(k in data for k in ("username", "password", "code")):
        return jsonify({"error": "Missing fields"}), 400

    users = read_data()
    for user in users:
        if (
            user["username"] == data["username"]
            and user["password"] == data["password"]
            and user.get("code") == data["code"]
        ):
            return jsonify({"message": "Login successful"}), 200
    return jsonify({"error": "Invalid credentials or group code"}), 401

@app.route("/status/<username>/<action>", methods=["POST"])
def update_status(username, action):
    users = read_data()
    for user in users:
        if user["username"] == username:
            user["status"] = action
            write_data(users)
            return jsonify({"message": f"Status updated to {action}"}), 200
    return jsonify({"error": "User not found"}), 404

@app.route("/status", methods=["GET"])
def get_status():
    users = read_data()
    clocked_in = [u["username"] for u in users if u["status"] == "clocked-in"]
    on_break = [u["username"] for u in users if u["status"] == "break"]
    return jsonify({"clockedIn": clocked_in, "onBreak": on_break}), 200

if __name__ == '__main__':
    app.run(debug=True)
