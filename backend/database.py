from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent / "ai_cos.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _seed_defaults(conn: sqlite3.Connection) -> None:
    history_rows = [
        ("Day 01", 412, 18),
        ("Day 02", 438, 19),
        ("Day 03", 425, 18),
        ("Day 04", 461, 20),
        ("Day 05", 449, 19),
        ("Day 06", 476, 21),
        ("Day 07", 462, 20),
        ("Day 08", 488, 22),
        ("Day 09", 470, 20),
        ("Day 10", 501, 22),
        ("Day 11", 493, 21),
        ("Day 12", 516, 23),
        ("Day 13", 505, 22),
        ("Day 14", 527, 24),
    ]

    if conn.execute("SELECT COUNT(*) FROM student_life_history").fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO student_life_history (day, dinner_diners, scheduled_sections) VALUES (?, ?, ?)",
            history_rows,
        )

    roommate_rows = [
        (
            "STU-601",
            "Aanya",
            json.dumps([5, 5, 4, 2, 5]),
            json.dumps([5, 4, 5, 2, 5]),
            "North",
        ),
        (
            "STU-602",
            "Rohan",
            json.dumps([2, 3, 2, 5, 2]),
            json.dumps([2, 3, 2, 5, 2]),
            "North",
        ),
        (
            "STU-603",
            "Meera",
            json.dumps([4, 4, 5, 3, 4]),
            json.dumps([4, 5, 4, 3, 4]),
            "North",
        ),
        (
            "STU-604",
            "Kabir",
            json.dumps([3, 2, 3, 4, 3]),
            json.dumps([3, 2, 3, 4, 2]),
            "North",
        ),
        (
            "STU-605",
            "Ira",
            json.dumps([5, 4, 5, 2, 5]),
            json.dumps([5, 5, 4, 2, 5]),
            "South",
        ),
        (
            "STU-606",
            "Dev",
            json.dumps([2, 3, 2, 5, 2]),
            json.dumps([2, 3, 2, 4, 2]),
            "South",
        ),
        (
            "STU-607",
            "Tara",
            json.dumps([4, 5, 4, 3, 4]),
            json.dumps([4, 4, 5, 3, 4]),
            "South",
        ),
        (
            "STU-608",
            "Neil",
            json.dumps([3, 2, 3, 4, 3]),
            json.dumps([3, 2, 2, 5, 3]),
            "South",
        ),
    ]

    if conn.execute("SELECT COUNT(*) FROM roommate_profiles").fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO roommate_profiles (student_id, name, preferences, profile, group_name) VALUES (?, ?, ?, ?, ?)",
            roommate_rows,
        )

    amenity_rows = [
        ("AM-101", "washing_machine", "H-A101", "A", 2, "07:00", 1),
        ("AM-102", "washing_machine", "H-B204", "B", 2, "07:00", 2),
        ("AM-103", "washing_machine", "H-C310", "C", 1, "07:00", 3),
        ("AM-104", "washing_machine", "H-A119", "A", 2, "07:00", 4),
        ("AM-105", "washing_machine", "H-D021", "D", 1, "07:00", 5),
        ("AM-201", "sports_court", "H-B101", "B", 2, "17:00", 1),
        ("AM-202", "sports_court", "H-C118", "C", 1, "17:00", 2),
        ("AM-203", "sports_court", "H-A208", "A", 2, "17:00", 3),
    ]
    if conn.execute("SELECT COUNT(*) FROM amenity_requests").fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO amenity_requests (request_id, amenity, resident, hall, priority, slot, arrival) VALUES (?, ?, ?, ?, ?, ?, ?)",
            amenity_rows,
        )

    menu_rows = [
        ("Veg rice bowl", 90),
        ("Paneer wrap", 120),
        ("Chicken meal box", 150),
        ("Fruit and yogurt cup", 65),
    ]
    if conn.execute("SELECT COUNT(*) FROM cafeteria_menu").fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO cafeteria_menu (item, regular_price) VALUES (?, ?)",
            menu_rows,
        )


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS student_life_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day TEXT UNIQUE,
                dinner_diners INTEGER NOT NULL,
                scheduled_sections INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS roommate_profiles (
                student_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                preferences TEXT NOT NULL,
                profile TEXT NOT NULL,
                group_name TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS amenity_requests (
                request_id TEXT PRIMARY KEY,
                amenity TEXT NOT NULL,
                resident TEXT NOT NULL,
                hall TEXT NOT NULL,
                priority INTEGER NOT NULL,
                slot TEXT NOT NULL,
                arrival INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cafeteria_menu (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item TEXT UNIQUE NOT NULL,
                regular_price REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS keep_alive_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pinged_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL
            )
            """
        )
        _seed_defaults(conn)
        conn.commit()


def record_keepalive(status: str) -> None:
    init_db()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO keep_alive_log (status) VALUES (?)",
            (status,),
        )
        conn.commit()


def fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]
