import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, List

DB_PATH = "options_signals.db"


def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database tables"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Users table for OAuth tokens
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            access_token TEXT,
            refresh_token TEXT,
            token_expires_at INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # User settings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            username TEXT PRIMARY KEY,
            delta_threshold REAL DEFAULT 0.20,
            vega_threshold REAL DEFAULT 0.10,
            theta_threshold REAL DEFAULT 0.02,
            gamma_threshold REAL DEFAULT 0.01,
            consecutive_confirmations INTEGER DEFAULT 2,
            FOREIGN KEY (username) REFERENCES users(username)
        )
    """)
    
    # Trade logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trade_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            username TEXT,
            detected_position TEXT,
            strike_price REAL,
            strike_ltp REAL,
            delta REAL,
            vega REAL,
            theta REAL,
            gamma REAL,
            raw_option_chain TEXT,
            FOREIGN KEY (username) REFERENCES users(username)
        )
    """)
    
    # Initialize default settings for known users
    for user in ["samarth", "prajwal"]:
        cursor.execute("""
            INSERT OR IGNORE INTO user_settings (username)
            VALUES (?)
        """, (user,))
    
    conn.commit()

    # Market data log table for ML training data
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_data_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            underlying_price REAL NOT NULL,
            atm_strike REAL NOT NULL,
            aggregated_greeks TEXT,
            signals TEXT
        )
    """)
    
    conn.commit()
    conn.close()


def store_tokens(username: str, access_token: str, refresh_token: str, expires_at: int):
    """Store OAuth tokens for a user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO users (username, access_token, refresh_token, token_expires_at)
        VALUES (?, ?, ?, ?)
    """, (username, access_token, refresh_token, expires_at))
    conn.commit()
    conn.close()


def get_user_tokens(username: str) -> Optional[Dict]:
    """Get stored tokens for a user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT access_token, refresh_token, token_expires_at
        FROM users
        WHERE username = ?
    """, (username,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "access_token": row["access_token"],
            "refresh_token": row["refresh_token"],
            "token_expires_at": row["token_expires_at"]
        }
    return None


def get_user_settings(username: str) -> Optional[Dict]:
    """Get user settings"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT delta_threshold, vega_threshold, theta_threshold,
               gamma_threshold, consecutive_confirmations
        FROM user_settings
        WHERE username = ?
    """, (username,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "delta_threshold": row["delta_threshold"],
            "vega_threshold": row["vega_threshold"],
            "theta_threshold": row["theta_threshold"],
            "gamma_threshold": row["gamma_threshold"],
            "consecutive_confirmations": row["consecutive_confirmations"]
        }
    return None


def update_user_settings(username: str, settings: Dict) -> Optional[Dict]:
    """Update user settings"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE user_settings
        SET delta_threshold = ?,
            vega_threshold = ?,
            theta_threshold = ?,
            gamma_threshold = ?,
            consecutive_confirmations = ?
        WHERE username = ?
    """, (
        settings.get("delta_threshold", 0.20),
        settings.get("vega_threshold", 0.10),
        settings.get("theta_threshold", 0.02),
        settings.get("gamma_threshold", 0.01),
        settings.get("consecutive_confirmations", 2),
        username
    ))
    conn.commit()
    conn.close()
    
    if cursor.rowcount > 0:
        return get_user_settings(username)
    return None


def log_signal(username: str, position: str, strike_price: float, strike_ltp: float,
               delta: float, vega: float, theta: float, gamma: float, raw_chain: dict):
    """Log a detected signal"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO trade_logs (
            username, detected_position, strike_price, strike_ltp,
            delta, vega, theta, gamma, raw_option_chain
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        username, position, strike_price, strike_ltp,
        delta, vega, theta, gamma, json.dumps(raw_chain)
    ))
    conn.commit()
    conn.close()


def get_trade_logs(username: str, limit: int = 100) -> List[Dict]:
    """Get trade logs for a user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT timestamp, detected_position, strike_price, strike_ltp,
               delta, vega, theta, gamma, raw_option_chain
        FROM trade_logs
        WHERE username = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """, (username, limit))
    
    rows = cursor.fetchall()
    conn.close()
    
    logs = []
    for row in rows:
        logs.append({
            "timestamp": row["timestamp"],
            "detected_position": row["detected_position"],
            "strike_price": row["strike_price"],
            "strike_ltp": row["strike_ltp"],
            "delta": row["delta"],
            "vega": row["vega"],
            "theta": row["theta"],
            "gamma": row["gamma"],
            "raw_option_chain": json.loads(row["raw_option_chain"]) if row["raw_option_chain"] else None
        })
    
    return logs
