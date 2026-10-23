"""SQLite access: sessions, sub_questions, sources, notes, reports."""
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY, question TEXT, depth TEXT, status TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS sub_questions (id INTEGER PRIMARY KEY, session_id INTEGER, text TEXT, status TEXT);
CREATE TABLE IF NOT EXISTS sources (id INTEGER PRIMARY KEY, session_id INTEGER, url TEXT, title TEXT, fetched_at TEXT, content_hash TEXT, status TEXT, reason TEXT);
CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, source_id INTEGER, sub_question_id INTEGER, facts TEXT, evidence TEXT, relevance REAL);
CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY, session_id INTEGER, markdown TEXT, claims_checked INTEGER, created_at TEXT);
"""


def connect(path: str = "pra.sqlite") -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn
