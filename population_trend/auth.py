from __future__ import annotations

from functools import wraps

from flask import flash, g, redirect, request, session, url_for

from .database import execute, query_one
from .security import hash_password


def current_user():
    username = session.get("username")
    if not username:
        return None
    return query_one("SELECT * FROM users WHERE username = ?", (username,))


def authenticate(username: str, password: str):
    user = query_one("SELECT * FROM users WHERE username = ?", (username,))
    if user and user["password_hash"] == hash_password(password):
        return user
    return None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("请先登录系统。", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("请先登录系统。", "warning")
            return redirect(url_for("login"))
        if g.user["role"] != "admin":
            flash("该操作需要管理员权限。", "error")
            return redirect(request.referrer or url_for("dashboard"))
        return view(*args, **kwargs)

    return wrapped


def log_action(action: str, detail: str = "") -> None:
    username = g.user["username"] if g.get("user") else "system"
    execute(
        "INSERT INTO operation_logs (username, action, detail) VALUES (?, ?, ?)",
        (username, action, detail),
    )
