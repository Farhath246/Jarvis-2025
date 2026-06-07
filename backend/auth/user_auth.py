"""
user_auth.py — Traditional (Username/Password) authentication for Jarvis.
Exposes eel functions for registering and logging in users.
"""

import eel
import sqlite3
import hashlib
import os
import logging
from backend.config import DB_PATH

logger = logging.getLogger(__name__)

def hash_password(password: str, salt: bytes = None) -> tuple[bytes, bytes]:
    """Hash a password with PBKDF2 HMAC."""
    if salt is None:
        salt = os.urandom(16)
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt, hashed

def verify_password(stored_password_hash: str, provided_password: str) -> bool:
    """Verify a provided password against a stored hash."""
    try:
        salt_hex, hash_hex = stored_password_hash.split(':')
        salt = bytes.fromhex(salt_hex)
        hashed = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), salt, 100000)
        return hashed.hex() == hash_hex
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False

@eel.expose
def register_user(username, email, password):
    """
    Register a new user with username, email, and password.
    Returns {"success": True/False, "message": str}
    """
    try:
        salt, hashed = hash_password(password)
        stored_hash = f"{salt.hex()}:{hashed.hex()}"
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email))
        if cursor.fetchone():
            conn.close()
            return {"success": False, "message": "Username or email already exists."}
            
        cursor.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, stored_hash)
        )
        conn.commit()
        conn.close()
        logger.info(f"Registered new user: {username}")
        return {"success": True, "message": "Registration successful."}
    except Exception as e:
        logger.error(f"Error registering user: {e}")
        return {"success": False, "message": f"An error occurred: {e}"}

@eel.expose
def login_user(username, password):
    """
    Authenticate an existing user.
    Returns {"success": True/False, "message": str}
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            stored_hash = row[0]
            if verify_password(stored_hash, password):
                logger.info(f"User {username} logged in successfully.")
                return {"success": True, "message": "Login successful."}
                
        return {"success": False, "message": "Invalid username or password."}
    except Exception as e:
        logger.error(f"Error logging in user: {e}")
        return {"success": False, "message": f"An error occurred: {e}"}

