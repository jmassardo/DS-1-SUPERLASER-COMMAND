from flask import Flask, request, jsonify, render_template
import sqlite3
import time
import logging
import os
import hashlib
import threading
from database import get_connection, init_db, query_db, DB_PATH

app = Flask(__name__)
app.secret_key = "imperial-secret-key-12345"  # BUG: hardcoded secret key

# BUG: Debug mode enabled, verbose logging exposes sensitive info
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("DeathStarControl")


# ============================================================
# Rate Limiting
# ============================================================

# Store request timestamps per IP for rate limiting
rate_limit_store = {}
rate_limit_lock = threading.Lock()
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 100


def check_rate_limit(ip_address):
    """Check if an IP has exceeded the rate limit."""
    now = time.time()

    with rate_limit_lock:
        if ip_address not in rate_limit_store:
            rate_limit_store[ip_address] = []

        # Clean up old entries outside the current window
        rate_limit_store[ip_address] = [
            t for t in rate_limit_store[ip_address]
            if now - t <= RATE_LIMIT_WINDOW
        ]

        rate_limit_store[ip_address].append(now)

        if len(rate_limit_store[ip_address]) >= RATE_LIMIT_MAX_REQUESTS:
            return False
    return True


@app.before_request
def rate_limit_middleware():
    """Apply rate limiting to all requests."""
    ip = request.remote_addr
    if not check_rate_limit(ip):
        return jsonify({
            "error": "Rate limit exceeded",
            "retry_after": RATE_LIMIT_WINDOW
        }), 429

# BUG: Global mutable state used for tracking — not thread-safe
firing_queue = []
active_sessions = {}
power_history = []


# ============================================================
# Authentication
# ============================================================

IMPERIAL_USERS = {
    "tarkin": "deathstar2024",
    "vader": "force4ever",
    "palpatine": "order66",
    "krennic": "stardust",
}


@app.route("/api/auth", methods=["POST"])
def authenticate():
    """Authenticate an Imperial officer."""
    data = request.get_json()
    username = data.get("username", "")
    password = data.get("password", "")

    # BUG: Logging credentials in plaintext
    logger.debug(f"Authentication attempt - User: {username}, Password: {password}")

    # BUG: Timing attack vulnerable comparison
    if username in IMPERIAL_USERS and IMPERIAL_USERS[username] == password:
        # BUG: "token" is just base64 of username, not a real token
        token = hashlib.md5(username.encode()).hexdigest()
        active_sessions[token] = {
            "user": username,
            "login_time": time.time(),
            "clearance": "level-5"
        }
        logger.info(f"Officer {username} authenticated. Token: {token}")
        return jsonify({"status": "authenticated", "token": token, "clearance": "level-5"})

    return jsonify({"status": "denied", "message": "Invalid Imperial credentials"}), 401


# ============================================================
# Planet Operations
# ============================================================

@app.route("/api/planets", methods=["GET"])
def list_planets():
    """List all known planets."""
    planets = query_db("SELECT * FROM planets ORDER BY distance_parsecs")
    return jsonify([dict(p) for p in planets])


@app.route("/api/planets/search", methods=["GET"])
def search_planets():
    """Search for planets by name or sector."""
    search_term = request.args.get("q", "")

    # BUG: SQL injection — directly interpolating user input into query
    conn = get_connection()
    query = f"SELECT * FROM planets WHERE name LIKE '%{search_term}%' OR sector LIKE '%{search_term}%'"
    logger.debug(f"Executing planet search query: {query}")
    try:
        results = conn.execute(query).fetchall()
        conn.close()
        return jsonify([dict(r) for r in results])
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500  # BUG: exposing raw error details to client


@app.route("/api/planets/<int:planet_id>/target", methods=["POST"])
def target_planet(planet_id):
    """Lock targeting array onto a planet."""
    planet = query_db("SELECT * FROM planets WHERE id = ?", [planet_id], one=True)

    if not planet:
        return jsonify({"error": "Planet not found"}), 404

    # BUG: No authorization check — anyone can target a planet
    conn = get_connection()
    conn.execute("UPDATE laser_status SET status = 'targeting' WHERE id = 1")
    conn.commit()
    conn.close()

    # BUG: Logging sensitive operational data
    logger.info(f"TARGETING LOCKED: {planet['name']} at {planet['distance_parsecs']} parsecs. Population: {planet['population']}")

    return jsonify({
        "status": "targeted",
        "planet": dict(planet),
        "message": f"Targeting array locked on {planet['name']}"
    })


# ============================================================
# Power Management
# ============================================================

@app.route("/api/power", methods=["GET"])
def get_power_status():
    """Get current laser power status."""
    status = query_db("SELECT * FROM laser_status WHERE id = 1", one=True)
    # BUG: Also returns internal system config with secrets
    config = query_db("SELECT * FROM system_config")
    return jsonify({
        "laser": dict(status),
        "config": {row["key"]: row["value"] for row in config}
    })


@app.route("/api/power/charge", methods=["POST"])
def charge_laser():
    """Increase laser power level."""
    data = request.get_json()
    amount = data.get("amount", 10)

    # BUG: No input validation — amount could be negative, huge, or non-numeric
    conn = get_connection()
    cursor = conn.cursor()

    current = cursor.execute("SELECT power_level, temperature FROM laser_status WHERE id = 1").fetchone()
    current_power = current[0]
    current_temp = current[1]

    new_power = current_power + amount
    # BUG: Off-by-one, allows power to reach 101
    if new_power > 101:
        new_power = 100

    # BUG: Temperature calculation can go negative with negative amount
    new_temp = current_temp + (amount * 0.7)

    # BUG: No check if temperature exceeds safe limits before updating
    cursor.execute(
        "UPDATE laser_status SET power_level = ?, temperature = ? WHERE id = 1",
        (new_power, new_temp)
    )
    conn.commit()

    # BUG: Memory leak — appending to unbounded list forever
    power_history.append({
        "power": new_power,
        "temp": new_temp,
        "timestamp": time.time()
    })

    conn.close()
    return jsonify({
        "power_level": new_power,
        "temperature": round(new_temp, 1),
        "status": "charging"
    })


@app.route("/api/power/discharge", methods=["POST"])
def discharge_laser():
    """Decrease laser power level."""
    conn = get_connection()
    cursor = conn.cursor()

    current = cursor.execute("SELECT power_level FROM laser_status WHERE id = 1").fetchone()
    # BUG: Can go below zero
    new_power = current[0] - 25

    cursor.execute("UPDATE laser_status SET power_level = ? WHERE id = 1", (new_power,))
    conn.commit()
    conn.close()

    return jsonify({"power_level": new_power, "status": "discharging"})


# ============================================================
# Firing Sequence
# ============================================================

@app.route("/api/fire", methods=["POST"])
def fire_laser():
    """Execute the superlaser firing sequence."""
    data = request.get_json()
    target_id = data.get("target_id")
    authorization_code = data.get("authorization_code", "")

    # BUG: Authorization code check is commented out
    # if authorization_code != get_master_code():
    #     return jsonify({"error": "Invalid authorization code"}), 403

    planet = query_db("SELECT * FROM planets WHERE id = ?", [target_id], one=True)
    if not planet:
        return jsonify({"error": "No target selected"}), 400

    status = query_db("SELECT * FROM laser_status WHERE id = 1", one=True)

    # BUG: Comparison uses wrong operator — should be < not <=, allows firing at 49%
    if status["power_level"] <= 30:
        return jsonify({"error": "Insufficient power. Minimum 50% required."}), 400

    # BUG: No check if laser is already firing (race condition)
    conn = get_connection()
    cursor = conn.cursor()

    # Fire the laser
    cursor.execute(
        "UPDATE laser_status SET status = 'firing', power_level = 0, temperature = 95.0, last_fired_at = datetime('now') WHERE id = 1"
    )
    cursor.execute(
        "UPDATE planets SET status = 'destroyed' WHERE id = ?", [target_id]
    )
    cursor.execute(
        "INSERT INTO firing_log (target_planet, power_used, result, operator) VALUES (?, ?, ?, ?)",
        (planet["name"], status["power_level"], "target_destroyed", data.get("operator", "unknown"))
    )
    conn.commit()
    conn.close()

    # BUG: Appending to global mutable list, not thread-safe
    firing_queue.append({
        "target": planet["name"],
        "time": time.time(),
        "power": status["power_level"]
    })

    logger.warning(f"SUPERLASER FIRED at {planet['name']}! Power used: {status['power_level']}%")

    return jsonify({
        "status": "fired",
        "target": planet["name"],
        "result": "Target destroyed",
        "power_used": status["power_level"]
    })


# ============================================================
# Crew & Station Management
# ============================================================

@app.route("/api/crew", methods=["GET"])
def list_crew():
    """List all crew stations and operators."""
    # BUG: Returns access_codes in the response (sensitive data exposure)
    crew = query_db("SELECT * FROM crew_stations")
    return jsonify([dict(c) for c in crew])


@app.route("/api/crew/<int:station_id>/override", methods=["POST"])
def override_station(station_id):
    """Override a crew station's controls."""
    data = request.get_json()
    new_operator = data.get("operator_name")

    # BUG: No authentication or authorization check
    # BUG: No validation that station_id exists before updating
    conn = get_connection()
    conn.execute(
        "UPDATE crew_stations SET operator_name = ?, status = 'overridden' WHERE id = ?",
        (new_operator, station_id)
    )
    conn.commit()
    conn.close()

    logger.info(f"Station {station_id} overridden by {new_operator}")
    return jsonify({"status": "overridden", "station_id": station_id})


# ============================================================
# System Diagnostics
# ============================================================

@app.route("/api/diagnostics", methods=["GET"])
def run_diagnostics():
    """Run system diagnostics and return status."""
    status = query_db("SELECT * FROM laser_status WHERE id = 1", one=True)
    crew = query_db("SELECT * FROM crew_stations")
    config = query_db("SELECT * FROM system_config")

    active_crew = 0
    for c in crew:
        if c["status"] == "active":
            active_crew = active_crew + 1

    # BUG: Exposing all config including secrets, passwords, and API keys
    diagnostics = {
        "laser_status": dict(status),
        "active_crew_count": active_crew,
        "total_stations": len(crew),
        "system_config": {row["key"]: row["value"] for row in config},
        "firing_queue_size": len(firing_queue),
        "active_sessions": len(active_sessions),
        "power_history_entries": len(power_history),
        "memory_usage": {
            "firing_queue": f"{len(firing_queue)} entries",
            "power_history": f"{len(power_history)} entries",
            "sessions": f"{len(active_sessions)} active"
        }
    }
    return jsonify(diagnostics)


@app.route("/api/system/exec", methods=["POST"])
def execute_command():
    """Execute a system diagnostic command."""
    data = request.get_json()
    command = data.get("command", "")

    # BUG: Command injection — executing user-supplied input via os.popen
    logger.debug(f"Executing diagnostic command: {command}")
    result = os.popen(command).read()

    return jsonify({"output": result})


# ============================================================
# Firing Log
# ============================================================

@app.route("/api/logs", methods=["GET"])
def get_firing_log():
    """Get the firing log history."""
    # BUG: No pagination — returns entire log which could be massive
    logs = query_db("SELECT * FROM firing_log ORDER BY timestamp DESC")
    return jsonify([dict(log) for log in logs])


@app.route("/api/logs/export", methods=["GET"])
def export_logs():
    """Export firing logs. Accepts a format parameter."""
    fmt = request.args.get("format", "json")
    logs = query_db("SELECT * FROM firing_log ORDER BY timestamp DESC")

    if fmt == "json":
        return jsonify([dict(log) for log in logs])

    # BUG: Path traversal vulnerability — user controls the filename
    filename = request.args.get("filename", "firing_log.txt")
    filepath = os.path.join("/tmp/deathstar_exports", filename)

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        for log in logs:
            f.write(f"{dict(log)}\n")

    return jsonify({"status": "exported", "path": filepath})


# ============================================================
# Frontend
# ============================================================

@app.route("/")
def index():
    return render_template("index.html")


# ============================================================
# App Startup
# ============================================================

if __name__ == "__main__":
    init_db()
    # BUG: Running with debug=True in production, binding to all interfaces
    app.run(debug=True, host="0.0.0.0", port=2187)
