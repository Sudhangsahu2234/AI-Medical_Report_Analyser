"""
Database module for AI Medical Report Analyser.
Handles SQLite database initialization and connection management.
Uses Flask's g object for per-request connection lifecycle.
"""

import sqlite3
import os
from flask import g

IS_VERCEL = os.environ.get('VERCEL', False)

if IS_VERCEL:
    DATABASE = '/tmp/medreport.db'
else:
    DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'medreport.db')


def get_db():
    """
    Get a database connection for the current request.
    Reuses the same connection within a single request via Flask's g object.
    Creates a new connection only if one doesn't exist yet.

    Returns:
        sqlite3.Connection: A configured database connection.
    """
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE, timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA journal_mode = WAL")
        g.db.execute("PRAGMA busy_timeout = 5000")
    return g.db


def close_db(e=None):
    """
    Close the database connection at the end of each request.
    Called automatically by Flask's teardown_appcontext.
    """
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """
    Initialize the database by creating required tables if they don't exist.

    Creates:
        - users: Stores user accounts with hashed passwords.
        - analyses: Stores medical report analysis results linked to users.
    """
    conn = sqlite3.connect(DATABASE, timeout=10)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            result_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    conn.commit()
    conn.close()
