"""
Database module for AI Medical Report Analyser.
Handles SQLite database initialization and connection management.
"""

import sqlite3
import os

IS_VERCEL = os.environ.get('VERCEL', False)

if IS_VERCEL:
    DATABASE = '/tmp/medreport.db'
else:
    DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'medreport.db')


def get_db():
    """
    Get a database connection with Row factory and foreign keys enabled.
    
    Returns:
        sqlite3.Connection: A configured database connection.
    """
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """
    Initialize the database by creating required tables if they don't exist.
    
    Creates:
        - users: Stores user accounts with hashed passwords.
        - analyses: Stores medical report analysis results linked to users.
    """
    conn = get_db()
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
