import sqlite3
import os

DB_PATH = "deathstar.db"

def get_connection():
    """Get a database connection. Caller is responsible for closing."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the Death Star database with tables and seed data."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS planets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sector TEXT NOT NULL,
            population TEXT,
            distance_parsecs REAL,
            status TEXT DEFAULT 'active'
        );

        CREATE TABLE IF NOT EXISTS laser_status (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            power_level INTEGER DEFAULT 0,
            temperature REAL DEFAULT 18.5,
            status TEXT DEFAULT 'standby',
            kyber_crystal_alignment REAL DEFAULT 100.0,
            last_fired_at TEXT
        );

        CREATE TABLE IF NOT EXISTS crew_stations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_name TEXT NOT NULL,
            operator_name TEXT,
            rank TEXT,
            access_code TEXT,
            status TEXT DEFAULT 'active'
        );

        CREATE TABLE IF NOT EXISTS firing_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_planet TEXT,
            power_used INTEGER,
            result TEXT,
            operator TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS system_config (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS systems_status (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            shields_status TEXT DEFAULT 'operational',
            shields_level INTEGER DEFAULT 85,
            targeting_computer TEXT DEFAULT 'operational',
            targeting_accuracy REAL DEFAULT 97.3,
            communications_array TEXT DEFAULT 'operational',
            signal_strength INTEGER DEFAULT 92,
            reactor_status TEXT DEFAULT 'operational',
            power_output INTEGER DEFAULT 87,
            deflector_shields TEXT DEFAULT 'operational',
            deflector_level INTEGER DEFAULT 78,
            reinforcements_available INTEGER DEFAULT 12,
            last_updated TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Seed planets
    cursor.execute("SELECT COUNT(*) FROM planets")
    if cursor.fetchone()[0] == 0:
        planets = [
            ("Alderaan", "Core Worlds", "2 billion", 12.4, "active"),
            ("Yavin IV", "Outer Rim", "1,000 (Rebel base)", 43.2, "active"),
            ("Scarif", "Outer Rim", "475,000", 38.7, "active"),
            ("Jedha", "Mid Rim", "11.3 million", 28.1, "active"),
            ("Tatooine", "Outer Rim", "200,000", 41.0, "active"),
            ("Hoth", "Outer Rim", "Unknown (Rebel activity)", 52.6, "active"),
            ("Endor", "Outer Rim", "30 million (Ewoks)", 47.3, "active"),
            ("Coruscant", "Core Worlds", "1 trillion", 5.1, "active"),
            ("Naboo", "Mid Rim", "4.5 billion", 19.8, "active"),
            ("Kashyyyk", "Mid Rim", "56 million (Wookiees)", 31.5, "active"),
            ("Mustafar", "Outer Rim", "20,000", 44.9, "active"),
            ("Dagobah", "Outer Rim", "Unknown", 49.2, "active"),
        ]
        cursor.executemany(
            "INSERT INTO planets (name, sector, population, distance_parsecs, status) VALUES (?, ?, ?, ?, ?)",
            planets
        )

    # Seed laser status
    cursor.execute("SELECT COUNT(*) FROM laser_status")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO laser_status (id, power_level, temperature, status) VALUES (1, 0, 18.5, 'standby')"
        )

    # Seed crew stations with access codes (BUG: storing plaintext sensitive credentials)
    cursor.execute("SELECT COUNT(*) FROM crew_stations")
    if cursor.fetchone()[0] == 0:
        crew = [
            ("Primary Fire Control", "Moff Tarkin", "Grand Moff", "IMPERIAL-7740-ALPHA", "active"),
            ("Targeting Array", "Lt. Tanbris", "Lieutenant", "TARGET-9921-BETA", "active"),
            ("Power Regulation", "Cmdr. Jhared", "Commander", "POWER-5531-GAMMA", "active"),
            ("Shield Modulation", "Cpt. Lennox", "Captain", "SHIELD-8812-DELTA", "active"),
            ("Reactor Core", "Dr. Kornell", "Chief Engineer", "REACTOR-2245-OMEGA", "active"),
            ("Communications", "Lt. Childsen", "Lieutenant", "COMMS-6637-SIGMA", "active"),
        ]
        cursor.executemany(
            "INSERT INTO crew_stations (station_name, operator_name, rank, access_code, status) VALUES (?, ?, ?, ?, ?)",
            crew
        )

    # Seed systems status
    cursor.execute("SELECT COUNT(*) FROM systems_status")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO systems_status (id) VALUES (1)"
        )

    # Seed system config
    cursor.execute("SELECT COUNT(*) FROM system_config")
    if cursor.fetchone()[0] == 0:
        config = [
            ("max_power", "100"),
            ("min_safe_temp", "15.0"),
            ("max_safe_temp", "85.0"),
            ("cooldown_seconds", "30"),
            ("master_override_code", "palpatine-order-66"),
            ("encryption_key", "aes256-imperial-KSDF8234mzx"),
            ("admin_password", "deathstar_admin_2024!"),
            ("api_secret", "sk-imperial-82hf92h3f9823hf98"),
        ]
        cursor.executemany(
            "INSERT OR IGNORE INTO system_config (key, value) VALUES (?, ?)",
            config
        )

    conn.commit()
    conn.close()


def query_db(query, args=(), one=False):
    """Execute a query and return results."""
    conn = get_connection()
    cursor = conn.execute(query, args)
    results = cursor.fetchall()
    conn.close()
    if one:
        return results[0] if results else None
    return results
