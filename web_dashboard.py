from flask import Flask, jsonify, request, render_template, session, Response
from datetime import datetime
import yaml, json
from flask import Flask, jsonify, request, render_template, session, Response

app = Flask(__name__)
app.secret_key = "super-secret-key"  # replace with secure key in production

# Use the project's Neo4jConnector which already handles availability and env vars
from neo4j_connector import Neo4jConnector

neo = Neo4jConnector()


# API: DB status
@app.route('/api/db_status')
def api_db_status():
    return jsonify({"available": getattr(neo, "_available", False)})

# === Simple Auth Middleware ===
def admin_required(func):
    def wrapper(*args, **kwargs):
        session["user"] = "admin"  # placeholder demo auth
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

# === Dashboard Route ===
@app.route("/dashboard")
@admin_required
def dashboard():
    return render_template("dashboard.html")

# === Decision Endpoints ===
@app.route("/decisions/pending")
@admin_required
def pending_decisions():
    q = """
    MATCH (d:Decision {status:'pending'})
    RETURN d.id as id, d.agent as agent, d.step as step,
           d.recommendation as recommendation,
           d.tools as tools, d.stats as stats,
           d.explanations as explanations, d.severity as severity
    LIMIT 50
    """
    if not getattr(neo, "_available", False):
        return jsonify([]), 503
    with neo.driver.session() as session:
        results = [dict(r) for r in session.run(q)]
    for r in results:
        r["tools"] = json.loads(r["tools"])
        r["stats"] = json.loads(r["stats"])
        r["explanations"] = json.loads(r["explanations"])
    return jsonify(results)

@app.route("/decisions/<decision_id>/approve", methods=["POST"])
@admin_required
def approve_decision(decision_id):
    choice = request.json.get("choice")
    if not getattr(neo, "_available", False):
        return jsonify({"error": "database unavailable"}), 503
    with neo.driver.session() as session:
        session.run("""
            MATCH (d:Decision {id:$id})
            SET d.status='approved', d.choice=$choice, d.resolved_at=datetime()
        """, id=decision_id, choice=choice)
    return jsonify({"status": "approved", "choice": choice})

# === Policy Endpoints ===
POLICY_FILE = "config/severity_policy.yaml"

@app.route("/policy", methods=["GET"])
@admin_required
def get_policy():
    with open(POLICY_FILE, "r") as f:
        policy = yaml.safe_load(f)
    return jsonify(policy)

@app.route("/policy", methods=["POST"])
@admin_required
def update_policy():
    data = request.json
    with open(POLICY_FILE, "w") as f:
        yaml.safe_dump(data, f)
    neo.reload_policy()
    # (Optionally: log changes into Neo4j as PolicyChange nodes)
    return jsonify({"status": "updated"})

@app.route("/policy/history")
@admin_required
def policy_history():
    # placeholder demo history
    return jsonify([
        {"user":"admin","timestamp":str(datetime.utcnow()),"diff":"Initial policy setup"}
    ])

# === Metrics Endpoints ===
@app.route("/metrics/live")
@admin_required
def live_metrics():
    q = """
    MATCH (d:Decision)
    WHERE d.created_at >= datetime() - duration('P1D')
    RETURN d.choice as choice, d.status as status, d.recommendation as rec
    """
    if not getattr(neo, "_available", False):
        return jsonify({
            "total": 0,
            "api_count": 0,
            "rpa_count": 0,
            "approved": 0,
            "overridden": 0,
            "api_pct": 0,
            "rpa_pct": 0
        }), 503
    with neo.driver.session() as session:
        results = [dict(r) for r in session.run(q)]
    total = len(results)
    api_count = sum(1 for r in results if r.get("choice") == "API_Tool")
    rpa_count = sum(1 for r in results if r.get("choice") == "RPA_Tool")
    approved = sum(1 for r in results if r.get("status") == "approved")
    overridden = sum(1 for r in results if r.get("choice") and r["choice"] != r.get("rec"))
    return jsonify({
        "total": total,
        "api_count": api_count,
        "rpa_count": rpa_count,
        "approved": approved,
        "overridden": overridden,
        "api_pct": (api_count/total*100) if total else 0,
        "rpa_pct": (rpa_count/total*100) if total else 0
    })

@app.route("/metrics/trends")
@admin_required
def metrics_trends():
    agent = request.args.get("agent")
    days = int(request.args.get("days", 1))
    q = """
    MATCH (d:Decision)
    WHERE d.created_at >= datetime() - duration({days:$days})
    """
    params = {"days": f"P{days}D"}
    if agent and agent.lower() != "all":
        q += " AND d.agent=$agent"
        params["agent"] = agent
    q += """
    WITH d, apoc.date.truncate(toInteger(apoc.date.toEpochMillis(d.created_at)), 'hour') AS hour
    RETURN hour,
           count(*) as total,
           sum(CASE WHEN d.choice='API_Tool' THEN 1 ELSE 0 END) as api_count,
           sum(CASE WHEN d.choice='RPA_Tool' THEN 1 ELSE 0 END) as rpa_count,
           sum(CASE WHEN d.status='approved' THEN 1 ELSE 0 END) as approved_count,
           sum(CASE WHEN d.choice<>d.recommendation AND d.status='approved' THEN 1 ELSE 0 END) as overridden_count
    ORDER BY hour ASC
    """
    if not getattr(neo, "_available", False):
        return jsonify([]), 503
    with neo.driver.session() as session:
        results = [dict(r) for r in session.run(q, **params)]
    for r in results:
        r["timestamp"] = r["hour"]
        r["success_rate"] = (r["approved_count"]/r["total"]*100) if r["total"] else 0
    return jsonify(results)

@app.route("/metrics/export")
@admin_required
def export_metrics():
    agent = request.args.get("agent", "All")
    days = int(request.args.get("days", 1))
    q = """
    MATCH (d:Decision)
    WHERE d.created_at >= datetime() - duration({days:$days})
    """
    params = {"days": f"P{days}D"}
    if agent and agent.lower() != "all":
        q += " AND d.agent=$agent"
        params["agent"] = agent
    q += """
    WITH d, apoc.date.truncate(toInteger(apoc.date.toEpochMillis(d.created_at)), 'hour') AS hour
    RETURN hour,
           count(*) as total,
           sum(CASE WHEN d.choice='API_Tool' THEN 1 ELSE 0 END) as api_count,
           sum(CASE WHEN d.choice='RPA_Tool' THEN 1 ELSE 0 END) as rpa_count,
           sum(CASE WHEN d.status='approved' THEN 1 ELSE 0 END) as approved_count,
           sum(CASE WHEN d.choice<>d.recommendation AND d.status='approved' THEN 1 ELSE 0 END) as overridden_count
    ORDER BY hour ASC
    """
    if not getattr(neo, "_available", False):
        return Response(
            ",".join(["timestamp","total","api_count","rpa_count","approved_count","overridden_count","success_rate"]) + "\n",
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=metrics.csv"}
        )
    with neo.driver.session() as session:
        results = [dict(r) for r in session.run(q, **params)]
    def generate():
        header = ["timestamp","total","api_count","rpa_count","approved_count","overridden_count","success_rate"]
        yield ",".join(header) + "\n"
        for r in results:
            success_rate = (r["approved_count"]/r["total"]*100) if r["total"] else 0
            row = [str(r["hour"]), str(r["total"]), str(r["api_count"]), str(r["rpa_count"]),
                   str(r["approved_count"]), str(r["overridden_count"]), f"{success_rate:.2f}"]
            yield ",".join(row) + "\n"
    return Response(generate(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=metrics.csv"})

# === Entrypoint ===
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
