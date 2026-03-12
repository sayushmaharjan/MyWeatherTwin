"""
Authentication — user registration, login, OTP verification.
"""

import os
import csv
import hashlib
import random
import string
import smtplib
import streamlit as st
from email.message import EmailMessage

from config import USERS_FILE, SMTP_EMAIL, SMTP_PASSWORD


# ── Helpers ────────────────────────────────────────────

def init_users_file():
    """Create users.csv with header row if it doesn't exist."""
    if not os.path.exists(USERS_FILE):
        USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(USERS_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["gmail", "username", "hashed_password"])


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def send_otp(email: str, otp: str):
    """Send a 6-digit OTP via Gmail SMTP."""
    msg = EmailMessage()
    msg["Subject"] = "Your WeatherTwin Verification Code"
    msg["From"] = SMTP_EMAIL
    msg["To"] = email
    msg.set_content(f"Your OTP for WeatherTwin registration is: {otp}")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(SMTP_EMAIL, SMTP_PASSWORD)
        smtp.send_message(msg)


def user_exists(email):
    with open(USERS_FILE, "r") as f:
        reader = csv.DictReader(f)
        return any(row["gmail"] == email for row in reader)


# ── UI ─────────────────────────────────────────────────

def register_user():
    st.subheader("📝 Register")

    username = st.text_input("Username")
    email = st.text_input("Gmail")
    password = st.text_input("Password", type="password")

    if st.button("Send OTP"):
        if not username or not email or not password:
            st.warning("⚠️ All fields are required")
            return

        if user_exists(email):
            st.error("❌ User already exists")
            return

        otp = "".join(random.choices(string.digits, k=6))
        st.session_state["otp"] = otp
        st.session_state["reg_email"] = email
        st.session_state["reg_username"] = username
        st.session_state["reg_password"] = password

        send_otp(email, otp)
        st.success("📧 OTP sent to your Gmail")

    otp_input = st.text_input("Enter OTP")

    if st.button("Verify & Register"):
        if otp_input == st.session_state.get("otp"):
            hashed_pw = hash_password(st.session_state["reg_password"])

            with open(USERS_FILE, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    st.session_state["reg_email"],
                    st.session_state["reg_username"],
                    hashed_pw,
                ])

            st.success("✅ Registration successful! Please log in.")
            st.session_state.clear()
        else:
            st.error("❌ Incorrect OTP")


def login_user():
    st.subheader("🔑 Login")

    email = st.text_input("Gmail")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        hashed_pw = hash_password(password)

        with open(USERS_FILE, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["gmail"] == email and row["hashed_password"] == hashed_pw:
                    st.session_state["user"] = email
                    st.session_state["username"] = row["username"]
                    st.success(f"✅ Logged in as {row['username']}")
                    st.rerun()
                    return

        st.error("❌ Invalid Gmail or password")


def auth_ui():
    """Top-level auth form: Login / Register toggle."""
    mode = st.radio("Select mode:", ["Login", "Register"])
    if mode == "Login":
        login_user()
    else:
        register_user()


# Ensure file exists on import
init_users_file()
