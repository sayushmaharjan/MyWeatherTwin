"""
email_service.py — Send OTP emails via Gmail SMTP.
"""

import os
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


def generate_otp() -> str:
    """Generate a 6-digit OTP."""
    return str(random.randint(100000, 999999))


def send_otp_email(to_email: str, otp: str, purpose: str = "verify your account") -> dict:
    """
    Send an OTP email via Gmail SMTP.
    Returns {'success': True} or {'success': False, 'error': '...'}.
    """
    smtp_email = os.getenv("SMTP_EMAIL", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")

    if not smtp_email or not smtp_password:
        return {"success": False, "error": "SMTP credentials not configured"}

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"WeatherTwin — Your OTP Code: {otp}"
        msg["From"] = smtp_email
        msg["To"] = to_email

        html = f"""
        <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:480px;margin:0 auto;padding:32px;background:#0f172a;border-radius:20px;border:1px solid rgba(148,163,184,0.15);">
            <div style="text-align:center;margin-bottom:24px;">
                <div style="font-size:2.5rem;">🌤️</div>
                <div style="font-size:1.5rem;font-weight:700;background:linear-gradient(135deg,#3b82f6,#8b5cf6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">WeatherTwin</div>
            </div>
            <div style="text-align:center;color:#94a3b8;font-size:0.9rem;margin-bottom:24px;">
                Use this code to {purpose}
            </div>
            <div style="text-align:center;background:rgba(59,130,246,0.1);border:1px solid rgba(59,130,246,0.3);border-radius:12px;padding:20px;margin-bottom:24px;">
                <div style="font-size:2.5rem;font-weight:800;letter-spacing:8px;color:#3b82f6;">{otp}</div>
            </div>
            <div style="text-align:center;color:#64748b;font-size:0.75rem;">
                This code expires in 10 minutes. Do not share it with anyone.
            </div>
        </div>
        """

        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, to_email, msg.as_string())

        return {"success": True}

    except Exception as e:
        return {"success": False, "error": str(e)}


def send_reminder_confirmation_email(to_email: str, description: str, event_time_str: str, notify_time_str: str, location: str) -> dict:
    """Send an email confirming a scheduled reminder."""
    smtp_email = os.getenv("SMTP_EMAIL", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")

    if not smtp_email or not smtp_password:
        return {"success": False, "error": "SMTP credentials not configured"}

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "WeatherTwin — Reminder Scheduled"
        msg["From"] = smtp_email
        msg["To"] = to_email

        html = f"""
        <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:480px;margin:0 auto;padding:32px;background:#0f172a;border-radius:20px;border:1px solid rgba(148,163,184,0.15);color:#f8fafc;">
            <div style="text-align:center;margin-bottom:24px;">
                <div style="font-size:2.5rem;">⏰</div>
                <div style="font-size:1.5rem;font-weight:700;background:linear-gradient(135deg,#3b82f6,#8b5cf6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">Reminder Saved</div>
            </div>
            <div style="color:#94a3b8;font-size:0.95rem;margin-bottom:24px;text-align:center;">
                We have successfully scheduled your reminder.
            </div>
            <div style="background:rgba(255,255,255,0.05);border-radius:12px;padding:20px;margin-bottom:24px;font-size:0.9rem;">
                <div style="margin-bottom:8px;"><strong>Event:</strong> {description}</div>
                <div style="margin-bottom:8px;"><strong>Location:</strong> {location}</div>
                <div style="margin-bottom:8px;"><strong>Event Time:</strong> {event_time_str}</div>
                <div><strong>Notification Time:</strong> {notify_time_str}</div>
            </div>
            <div style="text-align:center;color:#64748b;font-size:0.75rem;">
                We'll email you a weather update around {notify_time_str}. Stay tuned!
            </div>
        </div>
        """

        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, to_email, msg.as_string())

        return {"success": True}

    except Exception as e:
        return {"success": False, "error": str(e)}


def send_scheduled_notification_email(to_email: str, description: str, event_time_str: str, location: str, weather_insight: str) -> dict:
    """Send the scheduled notification email with the current weather advisory."""
    smtp_email = os.getenv("SMTP_EMAIL", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")

    if not smtp_email or not smtp_password:
        return {"success": False, "error": "SMTP credentials not configured"}

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"WeatherTwin Advisory: Upcoming Event '{description}'"
        msg["From"] = smtp_email
        msg["To"] = to_email

        html = f"""
        <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:550px;margin:0 auto;padding:32px;background:#0f172a;border-radius:20px;border:1px solid rgba(148,163,184,0.15);color:#f8fafc;">
            <div style="text-align:center;margin-bottom:20px;">
                <div style="font-size:2.5rem;">🌎🌤️</div>
                <div style="font-size:1.5rem;font-weight:700;background:linear-gradient(135deg,#3b82f6,#8b5cf6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">Notification Event</div>
            </div>
            
            <div style="background:rgba(59,130,246,0.1);border-left:4px solid #3b82f6;border-radius:8px;padding:16px;margin-bottom:24px;">
                <div style="font-size:1.1rem;font-weight:600;margin-bottom:4px;color:#f1f5f9;">{description}</div>
                <div style="font-size:0.85rem;color:#94a3b8;">{location} • {event_time_str}</div>
            </div>

            <div style="font-size:0.95rem;line-height:1.6;color:#e2e8f0;margin-bottom:24px;">
                {weather_insight}
            </div>
            
            <div style="text-align:center;color:#64748b;font-size:0.75rem;">
                Stay safe! Sent proactively by WeatherTwin.
            </div>
        </div>
        """

        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, to_email, msg.as_string())

        return {"success": True}

    except Exception as e:
        return {"success": False, "error": str(e)}
