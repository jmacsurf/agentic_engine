from flask import Flask, jsonify, request, session, Response
from functools import wraps
from neo4j_connector import Neo4jConnector
from prometheus_client import Counter, Gauge, generate_latest

app = Flask(__name__, static_folder="static")
app.secret_key = "super-secret-key"
neo = Neo4jConnector(password="testpassword123")

USERS = {
    "admin": {"password": "admin123", "role": "admin"},
    "viewer": {"password": "viewer123", "role": "viewer"}
}

# Prometheus metrics
agent_successes = Counter("agent_successes", "Agent success count", ["agent"])
agent_failures = Counter("agent_failures", "Agent failure count", ["agent"])
kg_nodes = Gauge("kg_nodes", "Number of KG nodes")
kg_edges = Gauge("kg_edges", "Number of KG edges")

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return jsonify({"error": "unauthorized"}), 401
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session or session.get("role") != "admin":
            return jsonify({"error": "forbidden"}), 403
        return f(*args, **kwargs)
    return wrapper

@app.route("/")
def index():
    return jsonify({"message": "Agentic Choreography Engine Dashboard", "status": "running"})

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    user, pwd = data.get("username"), data.get("password")
    if user in USERS and USERS[user]["password"] == pwd:
        session["user"] = user
        session["role"] = USERS[user]["role"]
        return jsonify({"status":"ok", "role":session["role"]})
    return jsonify({"error":"invalid credentials"}), 401

@app.route("/metrics")
def metrics():
    return Response(generate_latest(), mimetype="text/plain")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
