"""
database.py - SQLite database layer for FitBot
"""
import sqlite3
import bcrypt
import json
from datetime import date
from pathlib import Path

DB_PATH = Path(__file__).parent / "fitbot.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create all tables if they don't exist."""
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT    UNIQUE NOT NULL,
                password    TEXT    NOT NULL,
                name        TEXT,
                age         INTEGER,
                weight_kg   REAL,
                height_cm   REAL,
                goal        TEXT,       -- 'fat_loss' | 'muscle_gain' | 'maintain'
                activity_level TEXT,    -- 'sedentary' | 'light' | 'moderate' | 'active'
                tdee        REAL,       -- calculated daily calorie target
                created_at  TEXT        DEFAULT (date('now'))
            );

            CREATE TABLE IF NOT EXISTS plans (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL REFERENCES users(id),
                nutrition_plan  TEXT,   -- JSON
                exercise_plan   TEXT,   -- JSON
                created_at      TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS food_logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                log_date    TEXT    NOT NULL DEFAULT (date('now')),
                meal        TEXT,       -- breakfast / lunch / dinner / snack
                description TEXT,
                calories    REAL,
                protein_g   REAL        DEFAULT 0,
                carbs_g     REAL        DEFAULT 0,
                fat_g       REAL        DEFAULT 0,
                logged_at   TEXT        DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                role        TEXT    NOT NULL,   -- 'user' | 'assistant'
                content     TEXT    NOT NULL,
                created_at  TEXT    DEFAULT (datetime('now'))
            );
        """)
        # Migrate existing DB: add macro columns if they don't exist yet
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(food_logs)").fetchall()}
        for col in ("protein_g", "carbs_g", "fat_g"):
            if col not in existing_cols:
                conn.execute(f"ALTER TABLE food_logs ADD COLUMN {col} REAL DEFAULT 0")

        # Migrate existing DB: add activity_level to users if missing
        user_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "activity_level" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN activity_level TEXT DEFAULT 'moderate'")


# ── User auth ──────────────────────────────────────────────────────────────

def create_user(username: str, password: str) -> int:
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, hashed),
        )
        return cur.lastrowid


def verify_user(username: str, password: str):
    """Returns user row dict or None."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
    if row and bcrypt.checkpw(password.encode(), row["password"].encode()):
        return dict(row)
    return None


def get_user(username: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
    return dict(row) if row else None


def update_user_profile(user_id: int, name: str, age: int, weight_kg: float,
                        height_cm: float, goal: str, tdee: float,
                        activity_level: str = "moderate"):
    with get_conn() as conn:
        conn.execute(
            """UPDATE users SET name=?, age=?, weight_kg=?, height_cm=?,
               goal=?, tdee=?, activity_level=? WHERE id=?""",
            (name, age, weight_kg, height_cm, goal, tdee, activity_level, user_id),
        )


# ── Plans ──────────────────────────────────────────────────────────────────

def save_plan(user_id: int, nutrition_plan: dict, exercise_plan: dict) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO plans (user_id, nutrition_plan, exercise_plan) VALUES (?,?,?)",
            (user_id, json.dumps(nutrition_plan), json.dumps(exercise_plan)),
        )
        return cur.lastrowid


def get_latest_plan(user_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM plans WHERE user_id=? ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    if row:
        d = dict(row)
        d["nutrition_plan"] = json.loads(d["nutrition_plan"])
        d["exercise_plan"] = json.loads(d["exercise_plan"])
        return d
    return None


# ── Food logs ──────────────────────────────────────────────────────────────

def log_food(user_id: int, meal: str, description: str, calories: float,
             log_date: str | None = None,
             protein_g: float = 0, carbs_g: float = 0, fat_g: float = 0):
    ld = log_date or str(date.today())
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO food_logs
               (user_id, log_date, meal, description, calories, protein_g, carbs_g, fat_g)
               VALUES (?,?,?,?,?,?,?,?)""",
            (user_id, ld, meal, description, calories, protein_g, carbs_g, fat_g),
        )


def get_today_calories(user_id: int, log_date: str | None = None) -> float:
    ld = log_date or str(date.today())
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(calories),0) as total FROM food_logs WHERE user_id=? AND log_date=?",
            (user_id, ld),
        ).fetchone()
    return float(row["total"])


def get_today_macros(user_id: int, log_date: str | None = None) -> dict:
    """Return summed protein, carbs, and fat logged today."""
    ld = log_date or str(date.today())
    with get_conn() as conn:
        row = conn.execute(
            """SELECT
                 COALESCE(SUM(protein_g), 0) as protein_g,
                 COALESCE(SUM(carbs_g),  0) as carbs_g,
                 COALESCE(SUM(fat_g),    0) as fat_g
               FROM food_logs WHERE user_id=? AND log_date=?""",
            (user_id, ld),
        ).fetchone()
    return {"protein_g": float(row["protein_g"]),
            "carbs_g":   float(row["carbs_g"]),
            "fat_g":     float(row["fat_g"])}


def delete_last_food_log(user_id: int, log_date: str | None = None):
    """Delete the most recent food log entry for today. Returns the deleted row or None."""
    ld = log_date or str(date.today())
    with get_conn() as conn:
        row = conn.execute(
            """SELECT * FROM food_logs WHERE user_id=? AND log_date=?
               ORDER BY id DESC LIMIT 1""",
            (user_id, ld),
        ).fetchone()
        if row:
            conn.execute("DELETE FROM food_logs WHERE id=?", (row["id"],))
            return dict(row)
    return None


def get_today_logs(user_id: int, log_date: str | None = None):
    ld = log_date or str(date.today())
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM food_logs WHERE user_id=? AND log_date=? ORDER BY logged_at",
            (user_id, ld),
        ).fetchall()
    return [dict(r) for r in rows]


def get_meal_log(user_id: int, meal: str, log_date: str | None = None):
    """Return the most recent food log entry for a specific meal today."""
    ld = log_date or str(date.today())
    with get_conn() as conn:
        row = conn.execute(
            """SELECT * FROM food_logs WHERE user_id=? AND log_date=? AND meal=?
               ORDER BY id DESC LIMIT 1""",
            (user_id, ld, meal),
        ).fetchone()
    return dict(row) if row else None


def update_food_log(log_id: int, description: str, calories: float):
    """Update the description and calories of an existing food log entry in place."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE food_logs SET description=?, calories=? WHERE id=?",
            (description, calories, log_id),
        )


# ── Chat history ───────────────────────────────────────────────────────────

def save_message(user_id: int, role: str, content: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content) VALUES (?,?,?)",
            (user_id, role, content),
        )


def get_chat_history(user_id: int, limit: int = 20, today_only: bool = False):
    with get_conn() as conn:
        if today_only:
            rows = conn.execute(
                """SELECT role, content FROM chat_messages
                   WHERE user_id=? AND date(created_at)=date('now')
                   ORDER BY id DESC LIMIT ?""",
                (user_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT role, content FROM chat_messages
                   WHERE user_id=? ORDER BY id DESC LIMIT ?""",
                (user_id, limit),
            ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]