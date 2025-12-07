"""
Script to clear stored authentication tokens
Use this if you want to force re-login
"""
import sqlite3

DB_PATH = "options_signals.db"

def clear_tokens():
    """Clear all stored tokens"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Clear all tokens
    cursor.execute("UPDATE users SET access_token = NULL, refresh_token = NULL, token_expires_at = NULL")
    
    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()
    
    print(f"✓ Cleared tokens for {rows_affected} user(s)")
    print("You will need to log in again.")

if __name__ == "__main__":
    print("Clearing all authentication tokens...")
    clear_tokens()
    print("\nDone! Restart backend and log in again.")

