import os
import re
import time
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple
from urllib.parse import quote

from app.config import settings

logger = logging.getLogger("lively.services.email")

WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6
}


MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}


def parse_slot_to_datetimes(slot_str: str, now: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    """
    Parses strings like 'Thursday at 2:00 PM EST', 'Tomorrow at 10:00 AM', 'Monday Sep 14 at 10:00 AM EST'
    or 'Friday 3 PM' into UTC start and end datetimes. Relative days are resolved in the slot's timezone.
    """
    now = now or datetime.now(timezone.utc)
    lower = slot_str.lower()

    # Timezone: explicit label (whole words only, so "latest" isn't EST) or the calendar default
    if re.search(r"\b(?:pst|pdt|pacific)\b", lower):
        utc_offset = -8
    elif re.search(r"\b(?:cst|cdt|central)\b", lower):
        utc_offset = -6
    elif re.search(r"\b(?:est|edt|et|eastern)\b", lower):
        utc_offset = -5
    elif re.search(r"\b(?:utc|gmt)\b", lower):
        utc_offset = 0
    else:
        utc_offset = settings.CALENDAR_UTC_OFFSET_HOURS

    local_today = (now + timedelta(hours=utc_offset)).date()
    target_date = local_today
    month_day = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b", lower)
    if month_day:
        candidate = datetime(local_today.year, MONTHS[month_day.group(1)], int(month_day.group(2))).date()
        target_date = candidate if candidate >= local_today else candidate.replace(year=candidate.year + 1)
    elif "day after tomorrow" in lower:
        target_date = local_today + timedelta(days=2)
    elif re.search(r"\btomorrow\b", lower):
        target_date = local_today + timedelta(days=1)
    elif not re.search(r"\b(?:today|tonight)\b", lower):
        for day_name, day_idx in WEEKDAYS.items():
            if day_name in lower:
                days_ahead = (day_idx - local_today.weekday()) % 7 or 7  # same weekday means next week
                target_date = local_today + timedelta(days=days_ahead)
                break

    # Time: prefer an explicit AM/PM, then HH:MM, then "at 2", else 2 PM
    hour, minute = 14, 0
    m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)", lower)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2) or 0)
        is_pm = m.group(3).startswith("p")
        if is_pm and hour < 12:
            hour += 12
        elif not is_pm and hour == 12:
            hour = 0
    else:
        m = re.search(r"\b(\d{1,2}):(\d{2})\b", lower) or re.search(r"\bat\s+(\d{1,2})\b(?!\s*(?:mins?|minutes|hours?|users|seats))", lower)
        if m:
            hour = int(m.group(1))
            minute = int(m.group(2)) if m.lastindex and m.lastindex >= 2 else 0
            if hour < 8:
                hour += 12  # business hours: "at 2" means 2 PM

    duration = 30
    dur_match = re.search(r"(\d+)\s*-?\s*(?:minute|min)", lower)
    if dur_match:
        duration = int(dur_match.group(1))

    naive_local = datetime(target_date.year, target_date.month, target_date.day, hour, minute)
    start_utc = (naive_local - timedelta(hours=utc_offset)).replace(tzinfo=timezone.utc)
    return start_utc, start_utc + timedelta(minutes=duration)


def build_google_calendar_url(
    title: str,
    start_dt: datetime,
    end_dt: datetime,
    details: str,
    location: str
) -> str:
    """
    Builds a Google Calendar web blocking URL that pre-fills the exact date, time, title, Meet link, and agenda.
    Format: https://calendar.google.com/calendar/render?action=TEMPLATE&text=...&dates=START/END&details=...&location=...
    """
    fmt = "%Y%m%dT%H%M%SZ"
    start_str = start_dt.strftime(fmt)
    end_str = end_dt.strftime(fmt)
    dates_param = f"{start_str}/{end_str}"

    base_url = "https://calendar.google.com/calendar/render"
    params = [
        ("action", "TEMPLATE"),
        ("text", title),
        ("dates", dates_param),
        ("details", details),
        ("location", location),
        ("trp", "true")
    ]
    query_str = "&".join(f"{k}={quote(v)}" for k, v in params)
    return f"{base_url}?{query_str}"


def generate_ics_calendar(
    uid: str,
    title: str,
    start_dt: datetime,
    end_dt: datetime,
    details: str,
    location: str,
    attendee_email: str
) -> str:
    """
    Generates an RFC 5545 compliant iCalendar string for universal calendar blocking.
    """
    now_fmt = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    fmt = "%Y%m%dT%H%M%SZ"
    dtstart = start_dt.strftime(fmt)
    dtend = end_dt.strftime(fmt)

    # Clean description for ICS (escape newlines)
    clean_details = details.replace("\r\n", "\\n").replace("\n", "\\n")

    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Lively AI//Sales Engine//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:REQUEST",
        "BEGIN:VEVENT",
        f"UID:{uid}@lively.ai",
        f"DTSTAMP:{now_fmt}",
        f"DTSTART:{dtstart}",
        f"DTEND:{dtend}",
        f"SUMMARY:{title}",
        f"DESCRIPTION:{clean_details}",
        f"LOCATION:{location}",
        "STATUS:CONFIRMED",
        *([f"ATTENDEE;ROLE=REQ-PARTICIPANT;PARTSTAT=ACCEPTED;CN={attendee_email}:mailto:{attendee_email}"] if attendee_email else []),
        "ORGANIZER;CN=Lively AI:mailto:notifications@lively.ai",
        "BEGIN:VALARM",
        "TRIGGER:-PT15M",
        "ACTION:DISPLAY",
        "DESCRIPTION:Reminder: Lively AI Demo Walkthrough in 15 minutes",
        "END:VALARM",
        "END:VEVENT",
        "END:VCALENDAR"
    ]
    return "\r\n".join(ics_lines) + "\r\n"


def render_html_email(
    recipient_email: str,
    meeting_time: str,
    meet_link: str,
    calendar_link: str,
    topic: str = "Lively Real-Time Voice AI Sales Deep-Dive",
    host: str = "Senior Solutions Architect"
) -> str:
    """
    Renders an editorial, high-end HTML email with Lively's palette,
    featuring the meeting details, direct Google Meet button, and Add to Calendar block.
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Your Lively AI Demo is Confirmed</title>
  <style>
    body {{
      margin: 0;
      padding: 0;
      background-color: #f7f6f2;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      color: #20201e;
      -webkit-font-smoothing: antialiased;
    }}
    .wrapper {{
      max-width: 600px;
      margin: 40px auto;
      background: #ffffff;
      border: 1px solid #e5e3dc;
      border-radius: 16px;
      overflow: hidden;
      box-shadow: 0 4px 24px rgba(0, 0, 0, 0.04);
    }}
    .header {{
      padding: 36px 40px 24px;
      border-bottom: 1px solid #f0eee6;
      background: #ffffff;
    }}
    .tag {{
      display: inline-block;
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      color: #6166cf;
      background: #f0f1fa;
      padding: 4px 12px;
      border-radius: 9999px;
      margin-bottom: 14px;
    }}
    .title {{
      font-family: "Newsreader", Georgia, serif;
      font-size: 28px;
      font-weight: 500;
      line-height: 1.25;
      color: #1a1a18;
      margin: 0 0 8px;
    }}
    .subtitle {{
      font-size: 14px;
      color: #696862;
      margin: 0;
      line-height: 1.5;
    }}
    .content {{
      padding: 32px 40px;
    }}
    .card {{
      background: #faf9f5;
      border: 1px solid #ebe8de;
      border-radius: 12px;
      padding: 24px;
      margin-bottom: 28px;
    }}
    .card-row {{
      display: flex;
      margin-bottom: 12px;
      font-size: 14px;
    }}
    .card-row:last-child {{
      margin-bottom: 0;
    }}
    .card-label {{
      width: 110px;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: #8c8a82;
      padding-top: 2px;
    }}
    .card-value {{
      font-weight: 600;
      color: #20201e;
      flex: 1;
    }}
    .button-group {{
      margin: 32px 0 24px;
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
    }}
    .btn-primary {{
      display: inline-block;
      background: #6166cf;
      color: #ffffff !important;
      text-decoration: none;
      padding: 14px 28px;
      border-radius: 10px;
      font-size: 13px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      text-align: center;
    }}
    .btn-secondary {{
      display: inline-block;
      background: #ffffff;
      color: #20201e !important;
      text-decoration: none;
      padding: 13px 24px;
      border-radius: 10px;
      border: 1px solid #d5d2c7;
      font-size: 13px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      text-align: center;
    }}
    .agenda {{
      border-top: 1px solid #f0eee6;
      padding-top: 24px;
      margin-top: 24px;
    }}
    .agenda h4 {{
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: #20201e;
      margin: 0 0 12px;
    }}
    .agenda ul {{
      margin: 0;
      padding-left: 20px;
      font-size: 13px;
      color: #55544e;
      line-height: 1.6;
    }}
    .footer {{
      padding: 24px 40px;
      background: #f7f6f2;
      border-top: 1px solid #ebe8de;
      text-align: center;
      font-size: 11px;
      color: #8c8a82;
      line-height: 1.5;
    }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <div class="tag">Reservation Confirmed</div>
      <h1 class="title">Your Product Walkthrough is Locked In</h1>
      <p class="subtitle">Thank you for connecting with Lively. A dedicated technical sales architect has been assigned to your session.</p>
    </div>

    <div class="content">
      <div class="card">
        <div class="card-row">
          <div class="card-label">Date & Time</div>
          <div class="card-value" style="color: #6166cf; font-size: 16px;">{meeting_time}</div>
        </div>
        <div class="card-row">
          <div class="card-label">Format</div>
          <div class="card-value">30-Minute Video Consultation & Technical Deep-Dive</div>
        </div>
        <div class="card-row">
          <div class="card-label">Host</div>
          <div class="card-value">{host}</div>
        </div>
        <div class="card-row">
          <div class="card-label">Topic</div>
          <div class="card-value">{topic}</div>
        </div>
        <div class="card-row">
          <div class="card-label">Attendee</div>
          <div class="card-value">{recipient_email}</div>
        </div>
      </div>

      <div style="text-align: center; margin: 28px 0;">
        <a href="{meet_link}" class="btn-primary" target="_blank" style="margin-right: 8px;">
          Join video room
        </a>
        <a href="{calendar_link}" class="btn-secondary" target="_blank">
          Add to Google Calendar
        </a>
      </div>

      <div class="agenda">
        <h4>Discussion Agenda</h4>
        <ul>
          <li><strong>Real-time conversational voice</strong>: live latency and interruption handling on your own scenarios.</li>
          <li><strong>Autonomous Objection Handling</strong>: Real-time RAG & programmatic battlecards.</li>
          <li><strong>Enterprise Integration</strong>: CRM synchronization, lead routing, and telemetry APIs.</li>
        </ul>
      </div>
    </div>

    <div class="footer">
      Lively AI Sales Agent Platform &bull; Real-Time Voice Infrastructure<br />
      Need to reschedule? Reply to this email or re-enter the session at any time.
    </div>
  </div>
</body>
</html>
"""


def _smtp_send(msg: Any, to_email: str) -> Tuple[bool, Optional[str]]:
    """Blocking SMTP delivery. Callers run it in a worker thread (see app.core.background)."""
    user = settings.SMTP_USER.strip() if settings.SMTP_USER else None
    password = settings.SMTP_PASSWORD.replace(" ", "").strip() if settings.SMTP_PASSWORD else None
    if not (settings.SMTP_HOST and user and password):
        return False, "SMTP credentials (SMTP_USER / SMTP_PASSWORD) not configured in environment."
    try:
        if settings.SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
            if settings.SMTP_USE_TLS:
                server.starttls()
        server.login(user, password)
        sender = user if "gmail" in settings.SMTP_HOST.lower() else (settings.SMTP_FROM_EMAIL or user)
        server.sendmail(sender, [to_email], msg.as_string())
        server.quit()
        logger.info(f"Email delivered via SMTP to {to_email}")
        return True, None
    except Exception as e:
        logger.error(f"SMTP delivery failed: {e}. Falling back to preview recording.")
        return False, str(e)


class EmailService:
    def __init__(self):
        self.previews_dir = os.path.join(os.path.dirname(__file__), "..", "email_previews")
        os.makedirs(self.previews_dir, exist_ok=True)

    def prepare_demo_confirmation(
        self,
        to_email: str,
        meeting_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Prepares meeting times, Google Calendar blocking URL, ICS invitation, and rendered HTML.
        """
        time_slot = meeting_data.get("time", "Tomorrow at 2:00 PM EST")
        topic = meeting_data.get("topic", "Lively Real-Time Voice AI Sales Deep-Dive")
        host = meeting_data.get("host", "Senior Solutions Architect")
        meet_link = meeting_data.get("meeting_link") or ""
        meeting_id = meeting_data.get("meeting_id", f"mtg_{int(time.time())}")

        # Parse start and end times for Google Calendar and ICS
        start_dt, end_dt = parse_slot_to_datetimes(time_slot)

        details = (
            f"Lively Voice AI Product Walkthrough\n"
            f"Topic: {topic}\n"
            f"Host: {host}\n"
            f"Attendee: {to_email}\n"
            f"Video room: {meet_link}\n\n"
            f"Agenda:\n"
            f"1. Live real-time voice demo\n"
            f"2. Objection Handling & RAG Architecture\n"
            f"3. Enterprise CRM & Live Handoffs"
        )

        # 1. Google Calendar URL
        gcal_url = build_google_calendar_url(
            title=f"Lively AI Demo: {topic}",
            start_dt=start_dt,
            end_dt=end_dt,
            details=details,
            location=meet_link
        )

        # 2. ICS calendar content
        ics_content = generate_ics_calendar(
            uid=meeting_id,
            title=f"Lively AI Demo: {topic}",
            start_dt=start_dt,
            end_dt=end_dt,
            details=details,
            location=meet_link,
            attendee_email=to_email
        )

        # 3. HTML email content
        html_content = render_html_email(
            recipient_email=to_email,
            meeting_time=time_slot,
            meet_link=meet_link,
            calendar_link=gcal_url,
            topic=topic,
            host=host
        )

        # 4. Plaintext email content
        plain_content = (
            f"Lively AI - Demo Confirmed\n\n"
            f"Hello,\n"
            f"Your product walkthrough has been scheduled for {time_slot}.\n\n"
            f"Video room: {meet_link}\n"
            f"Add to Google Calendar: {gcal_url}\n\n"
            f"Host: {host}\n"
            f"Topic: {topic}\n\n"
            f"We look forward to speaking with you.\n"
            f"- The Lively AI Team"
        )

        return {
            "to_email": to_email,
            "meeting_id": meeting_id,
            "time_slot": time_slot,
            "start_dt": start_dt.isoformat(),
            "end_dt": end_dt.isoformat(),
            "google_calendar_url": gcal_url,
            "ics_content": ics_content,
            "html_content": html_content,
            "plain_content": plain_content,
            "meet_link": meet_link
        }

    def send_demo_confirmation(
        self,
        to_email: str,
        meeting_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Sends the confirmation email with the Google Meet link and attached .ics calendar block.
        If SMTP is unconfigured or unavailable, stores the rendered email and .ics artifact to disk.
        """
        clean_email = to_email.strip()
        if not clean_email or "@" not in clean_email:
            logger.warning(f"Invalid email recipient: '{to_email}'. Skipping email dispatch.")
            return {"status": "error", "message": "Invalid recipient email address"}

        prep = self.prepare_demo_confirmation(clean_email, meeting_data)
        subject = f"Confirmed: Lively AI Demo on {prep['time_slot']}"

        clean_user = settings.SMTP_USER.strip() if settings.SMTP_USER else None
        from_header = f"{settings.SMTP_FROM_NAME or 'Lively AI'} <{clean_user}>" if clean_user else settings.SMTP_FROM

        # Create multipart message
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = from_header
        msg["To"] = clean_email

        # Message body (alternative plain + html)
        alt_body = MIMEMultipart("alternative")
        alt_body.attach(MIMEText(prep["plain_content"], "plain", "utf-8"))
        alt_body.attach(MIMEText(prep["html_content"], "html", "utf-8"))
        msg.attach(alt_body)

        # Attach .ics calendar invite
        try:
            ics_attachment = MIMEBase("text", "calendar", method="REQUEST", name="invite.ics")
            ics_attachment.set_payload(prep["ics_content"].encode("utf-8"))
            encoders.encode_base64(ics_attachment)
            ics_attachment.add_header("Content-Disposition", "attachment; filename=invite.ics")
            ics_attachment.add_header("Content-Class", "urn:content-classes:calendarmessage")
            msg.attach(ics_attachment)
        except Exception as e:
            logger.warning(f"Failed to attach ICS payload: {e}")

        smtp_success, smtp_error = _smtp_send(msg, clean_email)

        # Always save local preview files for inspection and robust testing
        preview_id = f"{int(time.time())}_{re.sub(r'[^a-zA-Z0-9]', '_', clean_email)}"
        html_file = os.path.join(self.previews_dir, f"email_{preview_id}.html")
        ics_file = os.path.join(self.previews_dir, f"invite_{preview_id}.ics")

        with open(html_file, "w", encoding="utf-8") as f:
            f.write(prep["html_content"])

        with open(ics_file, "w", encoding="utf-8") as f:
            f.write(prep["ics_content"])

        logger.info(f"Saved email preview to {html_file} and calendar invite to {ics_file}")

        return {
            "status": "success",
            "delivered": smtp_success,
            "mode": "smtp" if smtp_success else "preview_saved",
            "error": smtp_error,
            "recipient": clean_email,
            "google_calendar_url": prep["google_calendar_url"],
            "google_meet_link": prep["meet_link"],
            "preview_html": html_file,
            "preview_ics": ics_file
        }


    def send_handoff_notification(self, to_email: str, record: Dict[str, Any]) -> Dict[str, Any]:
        """Emails the AE desk the handoff context so the human can join without re-asking anything."""
        s = record.get("summary", {})
        objections = ", ".join(f"{o['type']} (\"{o['utterance'][:60]}\")" for o in s.get("open_objections", [])) or "none"
        lines = [
            f"Reason: {record['reason']} (urgency: {record['urgency']})",
            f"Join the buyer: {record['bridge_url']}",
            "",
            f"Company: {s.get('company')}",
            f"Contact: {s.get('contact_name')} <{s.get('contact_email') or 'no email yet'}>",
            f"Qualification: {s.get('qualification_score')}/100{' (qualified)' if s.get('lead_qualified') else ''}",
            f"Budget: {s.get('budget') or 'unknown'} | Authority: {s.get('authority') or 'unknown'} | Timeline: {s.get('timeline') or 'unknown'}",
            f"Need: {'; '.join(s.get('need') or []) or 'unknown'} | Seats: {s.get('seats') or 'unknown'}",
            f"Open objections: {objections}",
            f"Demo: {s.get('scheduled_demo') or 'not booked'}",
            "",
            "Recent conversation:",
        ] + [f"{t['role'].title()}: {t['content']}" for t in record.get("recent_turns", [])]
        msg = MIMEText("\n".join(lines), "plain", "utf-8")
        msg["Subject"] = f"[Lively handoff] {s.get('company')}: {record['reason']}"
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_USER}>" if settings.SMTP_USER else settings.SMTP_FROM
        msg["To"] = to_email
        delivered, error = _smtp_send(msg, to_email)
        return {"delivered": delivered, "error": error}


# Global singleton instance
email_service = EmailService()
