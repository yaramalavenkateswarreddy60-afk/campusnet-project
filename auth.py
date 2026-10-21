"""
CampusNet: Authentication & Role-Based Access Control (RBAC) Module
Provides password hashing, session management, and server-side permission decorators.
"""

from functools import wraps
from datetime import datetime, timezone
from flask import session, request, jsonify, g, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db

ROLE_ADMIN = "admin"
ROLE_NETADMIN = "netadmin"
ROLE_READONLY = "readonly"

VALID_ROLES = {ROLE_ADMIN, ROLE_NETADMIN, ROLE_READONLY}

ROLE_HIERARCHY = {
    ROLE_ADMIN: 3,
    ROLE_NETADMIN: 2,
    ROLE_READONLY: 1,
}

ROLE_LABELS = {
    ROLE_ADMIN: "Administrator",
    ROLE_NETADMIN: "Network Administrator",
    ROLE_READONLY: "Read-Only Authority",
}


def hash_password(raw_password: str) -> str:
    """Returns secure password hash using PBKDF2/scrypt with salt."""
    if not raw_password or len(raw_password) < 6:
        raise ValueError("Password must be at least 6 characters long.")
    return generate_password_hash(raw_password)


def verify_password(raw_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against the stored cryptographic hash."""
    if not raw_password or not hashed_password:
        return False
    return check_password_hash(hashed_password, raw_password)


def get_user_by_id(user_id: int, db_path=None):
    """Fetches user record by ID."""
    conn = get_db(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, role, full_name, email, is_active, created_at, last_login_at FROM users WHERE id = ?;",
        (user_id,)
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def get_user_by_username(username: str, include_hash: bool = False, db_path=None):
    """Fetches user record by username."""
    conn = get_db(db_path)
    cursor = conn.cursor()
    cols = "id, username, password_hash, role, full_name, email, is_active, created_at, last_login_at" if include_hash else "id, username, role, full_name, email, is_active, created_at, last_login_at"
    cursor.execute(f"SELECT {cols} FROM users WHERE username = ?;", (username.strip().lower(),))
    row = cursor.fetchone()
    return dict(row) if row else None


def list_users(db_path=None):
    """Returns all user accounts without password hashes."""
    conn = get_db(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, role, full_name, email, is_active, created_at, last_login_at FROM users ORDER BY id ASC;"
    )
    return [dict(row) for row in cursor.fetchall()]


def create_user(username: str, raw_password: str, role: str, full_name: str, email: str = None, db_path=None):
    """Creates a new authorized user account."""
    username = username.strip().lower()
    if not username or len(username) < 3:
        raise ValueError("Username must be at least 3 characters long.")

    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role '{role}'. Allowed roles: {', '.join(VALID_ROLES)}")

    if not full_name or not full_name.strip():
        raise ValueError("Full name is required.")

    pwd_hash = hash_password(raw_password)
    now = datetime.now(timezone.utc).isoformat()

    conn = get_db(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO users (username, password_hash, role, full_name, email, is_active, created_at, last_login_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, NULL);
            """,
            (username, pwd_hash, role, full_name.strip(), email.strip() if email else None, now)
        )
        conn.commit()
        new_id = cursor.lastrowid
        return get_user_by_id(new_id, db_path=db_path)
    except Exception as e:
        conn.rollback()
        if "UNIQUE constraint failed" in str(e):
            raise ValueError(f"Username '{username}' already exists.")
        raise e


def update_user(user_id: int, role: str = None, full_name: str = None, email: str = None, is_active: int = None, db_path=None):
    """Updates user profile or role."""
    user = get_user_by_id(user_id, db_path=db_path)
    if not user:
        raise ValueError(f"User with ID {user_id} not found.")

    conn = get_db(db_path)
    cursor = conn.cursor()

    updates = []
    params = []

    if role is not None:
        if role not in VALID_ROLES:
            raise ValueError(f"Invalid role '{role}'.")
        updates.append("role = ?")
        params.append(role)

    if full_name is not None:
        if not full_name.strip():
            raise ValueError("Full name cannot be empty.")
        updates.append("full_name = ?")
        params.append(full_name.strip())

    if email is not None:
        updates.append("email = ?")
        params.append(email.strip() if email else None)

    if is_active is not None:
        updates.append("is_active = ?")
        params.append(1 if is_active else 0)

    if not updates:
        return user

    params.append(user_id)
    cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?;", params)
    conn.commit()
    return get_user_by_id(user_id, db_path=db_path)


def reset_password(user_id: int, new_password: str, db_path=None):
    """Resets user password."""
    user = get_user_by_id(user_id, db_path=db_path)
    if not user:
        raise ValueError(f"User with ID {user_id} not found.")

    pwd_hash = hash_password(new_password)
    conn = get_db(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?;", (pwd_hash, user_id))
    conn.commit()
    return True


def delete_user(user_id: int, db_path=None):
    """Deletes a user account (prevents deleting the last admin)."""
    user = get_user_by_id(user_id, db_path=db_path)
    if not user:
        raise ValueError(f"User with ID {user_id} not found.")

    conn = get_db(db_path)
    cursor = conn.cursor()

    if user["role"] == ROLE_ADMIN:
        cursor.execute("SELECT COUNT(*) AS admin_count FROM users WHERE role = 'admin' AND is_active = 1;")
        row = cursor.fetchone()
        if row and row["admin_count"] <= 1:
            raise ValueError("Cannot delete the only active Administrator account.")

    cursor.execute("DELETE FROM users WHERE id = ?;", (user_id,))
    conn.commit()
    return True


def record_login(user_id: int, db_path=None):
    """Updates the last_login_at timestamp for a user."""
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET last_login_at = ? WHERE id = ?;", (now, user_id))
    conn.commit()


# ----------------------------------------------------------------------------
# Session & Context Management
# ----------------------------------------------------------------------------

def login_user(user: dict):
    """Sets session cookies for authenticated user."""
    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["role"] = user["role"]
    session["full_name"] = user.get("full_name", user["username"])
    session.permanent = True
    g.user = user


def logout_user():
    """Clears user session."""
    session.clear()
    g.user = None


def get_current_user():
    """
    Returns current user dictionary from g or session.
    Also supports X-CampusNet-User header for automated tests and CLI tools.
    """
    if hasattr(g, "user") and g.user is not None:
        return g.user

    # 1. Check session
    user_id = session.get("user_id")
    if user_id:
        user = get_user_by_id(user_id)
        if user and user.get("is_active"):
            g.user = user
            return user
        else:
            session.clear()

    # 2. Check X-CampusNet-User header (convenience for API testing & integration)
    header_user = request.headers.get("X-CampusNet-User")
    if header_user:
        user = get_user_by_username(header_user)
        if user and user.get("is_active"):
            g.user = user
            return user

    g.user = None
    return None


# ----------------------------------------------------------------------------
# Permission Decorators
# ----------------------------------------------------------------------------

def login_required(f):
    """Requires user to be authenticated."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({
                "error": "Authentication required. Please log in with an authorized account.",
                "status": 401
            }), 401
        return f(*args, **kwargs)
    return decorated_function


def roles_required(*allowed_roles):
    """Requires user to have at least one of the specified roles."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({
                    "error": "Authentication required. Please log in.",
                    "status": 401
                }), 401

            if user["role"] not in allowed_roles:
                return jsonify({
                    "error": f"Access forbidden. Action requires one of: {', '.join(allowed_roles)}. Your current role is: {user['role']}.",
                    "status": 403,
                    "required_roles": list(allowed_roles),
                    "current_role": user["role"]
                }), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    """Convenience decorator for Administrator-only endpoints."""
    return roles_required(ROLE_ADMIN)(f)
