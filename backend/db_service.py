"""
db_service.py — PostgreSQL (Supabase) database service for user authentication.
Handles user registration, login, OTP storage, and table creation.
"""

import os
import time
import bcrypt
import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


def _get_connection():
    """Create a PostgreSQL connection using DATABASE_URL."""
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        raise ConnectionError("DATABASE_URL not set in .env")
    return psycopg2.connect(database_url)


def init_tables():
    """Create users and otp tables if they don't exist."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS weathertwin_users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                residence_type VARCHAR(50),
                commute_type VARCHAR(50),
                health_issues TEXT
            )
        """)
        
        # Add columns if they don't exist (for existing users table)
        try:
            cur.execute("ALTER TABLE weathertwin_users ADD COLUMN IF NOT EXISTS residence_type VARCHAR(50)")
            cur.execute("ALTER TABLE weathertwin_users ADD COLUMN IF NOT EXISTS commute_type VARCHAR(50)")
            cur.execute("ALTER TABLE weathertwin_users ADD COLUMN IF NOT EXISTS health_issues TEXT")
            cur.execute("ALTER TABLE weathertwin_users ADD COLUMN IF NOT EXISTS remember_token VARCHAR(255)")
            cur.execute("ALTER TABLE weathertwin_users ADD COLUMN IF NOT EXISTS remember_token_expires TIMESTAMP")
            cur.execute("ALTER TABLE weathertwin_users ADD COLUMN IF NOT EXISTS home_address VARCHAR(255)")
        except psycopg2.Error:
            conn.rollback()
            pass # Columns might already exist, though IF NOT EXISTS should handle it in PG 9.6+
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS weathertwin_otp (
                id SERIAL PRIMARY KEY,
                email VARCHAR(100) NOT NULL,
                otp_code VARCHAR(6) NOT NULL,
                purpose VARCHAR(20) DEFAULT 'register',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                used BOOLEAN DEFAULT FALSE
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS weathertwin_favorites (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES weathertwin_users(id) ON DELETE CASCADE,
                location_name VARCHAR(255) NOT NULL,
                lat FLOAT NOT NULL,
                lon FLOAT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, lat, lon)
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS weathertwin_reminders (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES weathertwin_users(id) ON DELETE CASCADE,
                description TEXT NOT NULL,
                event_datetime TIMESTAMP NOT NULL,
                notification_datetime TIMESTAMP NOT NULL,
                location_name VARCHAR(255) NOT NULL,
                lat FLOAT NOT NULL,
                lon FLOAT NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Drop the now-unused profiles table if it exists
        cur.execute("DROP TABLE IF EXISTS weathertwin_profiles")
        
        conn.commit()
    finally:
        conn.close()


def store_otp(email: str, otp_code: str, purpose: str = "register") -> dict:
    """Store an OTP in the database with 10-minute expiry."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        # Invalidate any existing unused OTPs for this email + purpose
        cur.execute(
            "UPDATE weathertwin_otp SET used = TRUE WHERE email = %s AND purpose = %s AND used = FALSE",
            (email, purpose),
        )
        # Insert new OTP
        cur.execute(
            "INSERT INTO weathertwin_otp (email, otp_code, purpose, expires_at) VALUES (%s, %s, %s, CURRENT_TIMESTAMP + INTERVAL '10 minutes')",
            (email, otp_code, purpose),
        )
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def verify_otp(email: str, otp_code: str, purpose: str = "register") -> dict:
    """Verify an OTP. Returns {'success': True} or {'success': False, 'error': '...'}."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT id FROM weathertwin_otp
               WHERE email = %s AND otp_code = %s AND purpose = %s
               AND used = FALSE AND expires_at > CURRENT_TIMESTAMP
               ORDER BY created_at DESC LIMIT 1""",
            (email, otp_code, purpose),
        )
        row = cur.fetchone()
        if not row:
            return {"success": False, "error": "Invalid or expired OTP"}

        # Mark OTP as used
        cur.execute("UPDATE weathertwin_otp SET used = TRUE WHERE id = %s", (row[0],))
        conn.commit()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def register_user(username: str, email: str, password: str) -> dict:
    """
    Register a new user. Returns {'success': True} or {'success': False, 'error': '...'}.
    Password is hashed with bcrypt before storage.
    """
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    conn = _get_connection()
    try:
        cur = conn.cursor()

        # Check if username exists
        cur.execute("SELECT COUNT(*) FROM weathertwin_users WHERE username = %s", (username,))
        if cur.fetchone()[0] > 0:
            return {"success": False, "error": "Username already taken"}

        # Check if email exists
        cur.execute("SELECT COUNT(*) FROM weathertwin_users WHERE email = %s", (email,))
        if cur.fetchone()[0] > 0:
            return {"success": False, "error": "Email already registered"}

        # Insert new user
        cur.execute(
            "INSERT INTO weathertwin_users (username, email, password_hash) VALUES (%s, %s, %s)",
            (username, email, password_hash),
        )
        conn.commit()
        return {"success": True}

    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def authenticate_by_password(email: str, password: str) -> dict:
    """Authenticate with email + password."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, email, password_hash FROM weathertwin_users WHERE email = %s",
            (email,),
        )
        row = cur.fetchone()

        if not row:
            return {"success": False, "error": "Invalid email or password"}

        user_id, user_name, user_email, stored_hash = row

        if bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8")):
            return {
                "success": True,
                "user": {"id": user_id, "username": user_name, "email": user_email},
            }
        else:
            return {"success": False, "error": "Invalid email or password"}

    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def authenticate_by_otp(username: str) -> dict:
    """
    Look up a user by username and return their email (for OTP sending).
    Does NOT authenticate — the OTP verification step does that.
    """
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, email FROM weathertwin_users WHERE username = %s",
            (username,),
        )
        row = cur.fetchone()
        if not row:
            return {"success": False, "error": "Username not found"}
        return {
            "success": True,
            "user": {"id": row[0], "username": row[1], "email": row[2]},
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def get_user_by_email_or_username(identifier: str) -> dict:
    """Get user info by email or username."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, email FROM weathertwin_users WHERE email = %s OR username = %s",
            (identifier, identifier),
        )
        row = cur.fetchone()
        if not row:
            return {"success": False, "error": "User not found"}
        return {
            "success": True,
            "user": {"id": row[0], "username": row[1], "email": row[2]},
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def check_user_has_active_token(identifier: str) -> dict:
    """Check if the user has an unexpired remember_token.
    Identifier can be email or username.
    Returns the user dictionary if valid, else success: False.
    """
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, username, email FROM weathertwin_users
            WHERE (email = %s OR username = %s)
            AND remember_token IS NOT NULL
            AND remember_token_expires > CURRENT_TIMESTAMP
            """,
            (identifier, identifier),
        )
        row = cur.fetchone()
        if not row:
            return {"success": False, "error": "No active token found"}
        return {
            "success": True,
            "user": {"id": row[0], "username": row[1], "email": row[2]},
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def get_user_profile(user_id: int) -> dict:
    """Fetch user profile settings from the users table."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT residence_type, commute_type, health_issues, home_address, work_address FROM weathertwin_users WHERE id = %s",
            (user_id,),
        )
        row = cur.fetchone()
        if not row:
            return {"success": True, "profile": {}}
        return {
            "success": True,
            "profile": {
                "residence_type": row[0],
                "commute_type": row[1],
                "health_issues": row[2],
                "home_address": row[3]
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def update_user_profile(user_id: int, residence: str, commute: str, health: str, home_address: str) -> dict:
    """Update user profile settings in the users table."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE weathertwin_users 
            SET residence_type = %s,
                commute_type = %s,
                health_issues = %s,
                home_address = %s
            WHERE id = %s
            """,
            (residence, commute, health, home_address, user_id)
        )
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def test_connection() -> dict:
    """Test if database connection works."""
    try:
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute("SELECT version()")
        version = cur.fetchone()[0]
        conn.close()
        return {"success": True, "version": version}
    except Exception as e:
        return {"success": False, "error": str(e)}

def set_remember_token(user_id: int, token: str, expires_at) -> dict:
    """Sets a remember me token for a specific user with an expiration date."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE weathertwin_users 
            SET remember_token = %s,
                remember_token_expires = %s
            WHERE id = %s
            """,
            (token, expires_at, user_id)
        )
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def verify_remember_token(token: str) -> dict:
    """Verifies a remember token and returns the user if it is valid and not expired."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, username, email 
            FROM weathertwin_users 
            WHERE remember_token = %s AND remember_token_expires > CURRENT_TIMESTAMP
            """,
            (token,)
        )
        row = cur.fetchone()
        if not row:
            return {"success": False, "error": "Invalid or expired token"}
            
        return {
            "success": True,
            "user": {"id": row[0], "username": row[1], "email": row[2]}
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def get_favorites(user_id: int) -> dict:
    """Get a list of favorite locations for the user."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT location_name, lat, lon 
            FROM weathertwin_favorites 
            WHERE user_id = %s 
            ORDER BY created_at ASC
            """,
            (user_id,),
        )
        rows = cur.fetchall()
        favorites = [{"name": r[0], "lat": r[1], "lon": r[2]} for r in rows]
        return {"success": True, "favorites": favorites}
    except Exception as e:
        return {"success": False, "error": str(e), "favorites": []}
    finally:
        conn.close()


def add_favorite(user_id: int, location_name: str, lat: float, lon: float) -> dict:
    """Add a location to the user's favorites."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO weathertwin_favorites (user_id, location_name, lat, lon)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id, lat, lon) DO NOTHING
            """,
            (user_id, location_name, lat, lon),
        )
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def remove_favorite(user_id: int, lat: float, lon: float) -> dict:
    """Remove a location from the user's favorites by coordinates."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM weathertwin_favorites 
            WHERE user_id = %s AND abs(lat - %s) < 0.001 AND abs(lon - %s) < 0.001
            """,
            (user_id, lat, lon),
        )
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


# ─── REMINDERS ──────────────────────────────────────

def add_reminder(user_id: int, description: str, event_datetime: str, notification_datetime: str, location_name: str, lat: float, lon: float) -> dict:
    """Schedule a new reminder."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO weathertwin_reminders (user_id, description, event_datetime, notification_datetime, location_name, lat, lon)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, description, event_datetime, notification_datetime, location_name, lat, lon),
        )
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def get_reminders_by_user(user_id: int) -> dict:
    """Fetch all reminders for a specific user."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, description, event_datetime, notification_datetime, location_name, lat, lon, status
            FROM weathertwin_reminders
            WHERE user_id = %s
            ORDER BY notification_datetime ASC
            """,
            (user_id,),
        )
        rows = cur.fetchall()
        reminders = [
            {
                "id": r[0],
                "description": r[1],
                "event_datetime": r[2],
                "notification_datetime": r[3],
                "location_name": r[4],
                "lat": r[5],
                "lon": r[6],
                "status": r[7]
            }
            for r in rows
        ]
        return {"success": True, "reminders": reminders}
    except Exception as e:
        return {"success": False, "error": str(e), "reminders": []}
    finally:
        conn.close()


def delete_reminder(reminder_id: int) -> dict:
    """Delete a reminder by ID."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM weathertwin_reminders WHERE id = %s", (reminder_id,))
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def get_pending_reminders() -> dict:
    """Fetch all pending reminders where the notification time has passed."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT r.id, r.user_id, r.description, r.event_datetime, r.location_name, r.lat, r.lon, u.email
            FROM weathertwin_reminders r
            JOIN weathertwin_users u ON r.user_id = u.id
            WHERE r.status = 'pending' AND r.notification_datetime <= CURRENT_TIMESTAMP
            """
        )
        rows = cur.fetchall()
        reminders = [
            {
                "id": r[0],
                "user_id": r[1],
                "description": r[2],
                "event_datetime": r[3],
                "location_name": r[4],
                "lat": r[5],
                "lon": r[6],
                "email": r[7]
            }
            for r in rows
        ]
        return {"success": True, "reminders": reminders}
    except Exception as e:
        return {"success": False, "error": str(e), "reminders": []}
    finally:
        conn.close()


def mark_reminder_sent(reminder_id: int) -> dict:
    """Mark a reminder as sent."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE weathertwin_reminders
            SET status = 'sent'
            WHERE id = %s
            """,
            (reminder_id,),
        )
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

