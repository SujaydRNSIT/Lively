import smtplib
import ssl
import logging
import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any
from app.config import settings

logger = logging.getLogger("lively.email")

def _send_smtp_sync(to_email: str, subject: str, html_content: str, text_content: str) -> Dict[str, Any]:
    """
    Synchronous SMTP delivery function executed in a background thread.
    """
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.info("SMTP credentials (SMTP_USER/SMTP_PASSWORD) are not set in .env. Email dispatch simulated.")
        return {
            "delivered": False,
            "simulated": True,
            "reason": "SMTP_USER or SMTP_PASSWORD not configured in .env."
        }
    
    sender_email = settings.SMTP_FROM_EMAIL or settings.SMTP_USER
    sender_name = settings.SMTP_FROM_NAME or "Lively AI Solutions"
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{sender_name} <{sender_email}>"
    msg["To"] = to_email
    
    part1 = MIMEText(text_content, "plain")
    part2 = MIMEText(html_content, "html")
    msg.attach(part1)
    msg.attach(part2)
    
    clean_user = settings.SMTP_USER.strip()
    clean_password = settings.SMTP_PASSWORD.replace(" ", "").strip()

    try:
        context = ssl.create_default_context()
        if settings.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=context, timeout=15) as server:
                server.login(clean_user, clean_password)
                server.sendmail(sender_email, to_email, msg.as_string())
        else:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
                server.starttls(context=context)
                server.login(clean_user, clean_password)
                server.sendmail(sender_email, to_email, msg.as_string())
                
        logger.info(f"Email successfully delivered to {to_email} via SMTP ({settings.SMTP_HOST}:{settings.SMTP_PORT})")
        return {"delivered": True, "recipient": to_email}
    except Exception as e:
        logger.error(f"Failed to deliver email to {to_email} via SMTP: {e}")
        return {"delivered": False, "simulated": False, "reason": str(e)}

async def send_meeting_invite_email(
    to_email: str,
    topic: str,
    time_slot: str,
    meeting_link: str,
    host: str = "Senior Solutions Architect"
) -> Dict[str, Any]:
    """
    Asynchronously delivers a professional Google Meet invitation email to the recipient.
    """
    clean_topic = topic or "Agora Real-Time Voice AI Sales Deep-Dive"
    clean_time = time_slot or "Tomorrow at 2:00 PM EST"
    clean_link = meeting_link or "https://meet.google.com/new"
    
    subject = f"Confirmed: {clean_topic} — {clean_time}"
    
    text_content = (
        f"Hello,\n\n"
        f"Your product walkthrough has been reserved!\n\n"
        f"Topic: {clean_topic}\n"
        f"Time: {clean_time}\n"
        f"Host: {host}\n"
        f"Google Meet Link: {clean_link}\n\n"
        f"We look forward to speaking with you.\n\n"
        f"— Lively AI Solutions Team"
    )
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{clean_topic}</title>
</head>
<body style="margin: 0; padding: 24px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f7f6f0; color: #20201e;">
  <div style="max-width: 560px; margin: 0 auto; background: #ffffff; border-radius: 14px; border: 1px solid #e7e5dc; padding: 32px; box-shadow: 0 4px 16px rgba(0,0,0,0.06);">
    <div style="display: inline-block; background-color: #edeefb; color: #6166cf; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.2px; padding: 4px 12px; border-radius: 20px;">
      Confirmed Demonstration
    </div>
    <h1 style="font-size: 22px; color: #121623; margin: 16px 0 8px; font-weight: 700;">{clean_topic}</h1>
    <p style="font-size: 14px; line-height: 1.6; color: #4c4b46; margin-top: 0;">
      Your session with our solutions architecture team is confirmed. Here are your meeting details:
    </p>

    <div style="background-color: #faf9f5; border: 1px solid #ebe8df; border-radius: 10px; padding: 16px; margin: 20px 0;">
      <p style="margin: 6px 0; font-size: 13px; color: #20201e;"><strong>Date & Time:</strong> {clean_time}</p>
      <p style="margin: 6px 0; font-size: 13px; color: #20201e;"><strong>Format:</strong> 30-min Real-Time Video Walkthrough</p>
      <p style="margin: 6px 0; font-size: 13px; color: #20201e;"><strong>Host:</strong> {host}</p>
    </div>

    <div style="text-align: center; margin: 28px 0 20px;">
      <a href="{clean_link}" target="_blank" style="display: inline-block; background-color: #6166cf; color: #ffffff; font-size: 14px; font-weight: 600; text-decoration: none; padding: 13px 28px; border-radius: 8px; box-shadow: 0 2px 8px rgba(97, 102, 207, 0.3);">
        Join Google Meet Video Bridge
      </a>
    </div>

    <p style="font-size: 12px; color: #8c8a82; text-align: center; margin-top: 24px; border-top: 1px solid #f0eee6; pt-4;">
      Agora Conversational AI Engine &bull; Lively Real-Time Voice Intelligence
    </p>
  </div>
</body>
</html>"""

    return await asyncio.to_thread(_send_smtp_sync, to_email, subject, html_content, text_content)
