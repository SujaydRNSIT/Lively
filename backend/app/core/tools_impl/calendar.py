import time
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple

from app.config import settings
from app.services.email_service import parse_slot_to_datetimes

logger = logging.getLogger("lively.tools.calendar")

_WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class CalendarService:
    """
    Task 8.2: Calendar Tool Implementation.
    Solutions-architect demo calendar with working days, demo hours and one booking per slot.
    Bookings are in-memory, so they reset when the process restarts.
    """
    def __init__(self):
        self._bookings: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------ config helpers
    @staticmethod
    def _offset() -> timedelta:
        return timedelta(hours=settings.CALENDAR_UTC_OFFSET_HOURS)

    @staticmethod
    def _working_days() -> set:
        days = set()
        for key in settings.CALENDAR_WORKING_DAYS.split(","):
            key = key.strip()[:3].lower()
            if key in _WEEKDAY_KEYS:
                days.add(_WEEKDAY_KEYS.index(key))
        return days

    @staticmethod
    def _slot_times() -> List[Tuple[int, int]]:
        times = []
        for item in settings.CALENDAR_SLOT_TIMES.split(","):
            try:
                hour, minute = item.strip().split(":")
                times.append((int(hour), int(minute)))
            except ValueError:
                continue
        return times or [(10, 0), (14, 0), (16, 0)]

    @staticmethod
    def _hour_label(hour: int) -> str:
        return f"{hour % 12 or 12} {'AM' if hour < 12 else 'PM'}"

    def label_for(self, start_utc: datetime) -> str:
        local = start_utc + self._offset()
        return f"{local:%A} {local:%b} {local.day} at {local.hour % 12 or 12}:{local.minute:02d} {'AM' if local.hour < 12 else 'PM'} {settings.CALENDAR_TZ_LABEL}"

    def meeting_link(self, meeting_id: str) -> str:
        return f"{settings.MEETING_ROOM_BASE_URL.rstrip('/')}/Lively-{meeting_id}"

    # ------------------------------------------------------------ availability
    def _conflicts(self, start_utc: datetime, end_utc: datetime, ignore_channel: Optional[str]) -> bool:
        for booking in self._bookings.values():
            if ignore_channel and booking.get("channel") == ignore_channel:
                continue
            if start_utc < booking["end_utc"] and booking["start_utc"] < end_utc:
                return True
        return False

    def _violation(self, start_utc: datetime, end_utc: datetime, ignore_channel: Optional[str] = None, now: Optional[datetime] = None) -> Optional[str]:
        now = now or datetime.now(timezone.utc)
        local_start, local_end = start_utc + self._offset(), end_utc + self._offset()
        if start_utc < now + timedelta(minutes=15):
            return "that time has already passed or is too soon"
        if local_start.weekday() not in self._working_days():
            return f"our architects don't run demos on {local_start:%A}s"
        start_h = local_start.hour + local_start.minute / 60
        end_h = local_end.hour + local_end.minute / 60
        if local_end.date() != local_start.date() or start_h < settings.BUSINESS_HOURS_START or end_h > settings.BUSINESS_HOURS_END:
            return (f"it's outside demo hours ({self._hour_label(settings.BUSINESS_HOURS_START)} to "
                    f"{self._hour_label(settings.BUSINESS_HOURS_END)} {settings.CALENDAR_TZ_LABEL})")
        if self._conflicts(start_utc, end_utc, ignore_channel):
            return "that slot is already booked"
        return None

    def next_open_slots(self, count: int = 3, after_utc: Optional[datetime] = None, duration_minutes: int = 30,
                        ignore_channel: Optional[str] = None) -> List[str]:
        now = datetime.now(timezone.utc)
        start_from = max(after_utc or now, now)
        local_today = (now + self._offset()).date()
        slots: List[str] = []
        for day_delta in range(0, 21):
            day = local_today + timedelta(days=day_delta)
            for hour, minute in self._slot_times():
                start_utc = (datetime(day.year, day.month, day.day, hour, minute) - self._offset()).replace(tzinfo=timezone.utc)
                if start_utc < start_from:
                    continue
                if self._violation(start_utc, start_utc + timedelta(minutes=duration_minutes), ignore_channel, now):
                    continue
                slots.append(self.label_for(start_utc))
                if len(slots) >= count:
                    return slots
        return slots

    def check_slot(self, slot_label: str, duration_minutes: int = 30, ignore_channel: Optional[str] = None) -> Dict[str, Any]:
        try:
            start_utc, _ = parse_slot_to_datetimes(slot_label)
        except Exception:
            return {"ok": False, "reason": "I couldn't understand that time",
                    "alternatives": self.next_open_slots(3, ignore_channel=ignore_channel)}
        end_utc = start_utc + timedelta(minutes=duration_minutes)
        reason = self._violation(start_utc, end_utc, ignore_channel)
        if reason:
            return {"ok": False, "reason": reason, "start_utc": start_utc,
                    "alternatives": self.next_open_slots(3, after_utc=start_utc, duration_minutes=duration_minutes, ignore_channel=ignore_channel)}
        return {"ok": True, "reason": None, "start_utc": start_utc, "end_utc": end_utc, "alternatives": []}

    # ------------------------------------------------------------ bookings
    def reserve(self, slot_label: str, start_utc: datetime, end_utc: datetime, channel: Optional[str],
                email: Optional[str], topic: Optional[str] = None) -> Dict[str, Any]:
        if channel:
            self.release_channel(channel)  # rescheduling replaces this conversation's previous booking
        meeting_id = f"mtg_{uuid.uuid4().hex[:10]}"
        booking = {
            "meeting_id": meeting_id,
            "channel": channel,
            "email": email,
            "topic": topic,
            "time": slot_label,
            "start_utc": start_utc,
            "end_utc": end_utc,
            "meeting_link": self.meeting_link(meeting_id),
            "booked_at": time.time(),
        }
        self._bookings[meeting_id] = booking
        logger.info(f"Calendar meeting booked: {meeting_id} at {slot_label} (channel={channel})")
        return booking

    def release_channel(self, channel: str) -> None:
        for meeting_id in [m for m, b in self._bookings.items() if b.get("channel") == channel]:
            del self._bookings[meeting_id]

    def reset(self) -> None:
        self._bookings.clear()

    async def check_availability(self, date_str: str = "tomorrow", time_preference: str = "afternoon") -> Dict[str, Any]:
        """Open demo slots with Senior Solutions Architects (next working days, demo hours only)."""
        slots = self.next_open_slots(6)
        if time_preference == "morning":
            preferred = [s for s in slots if " AM " in s]
        elif time_preference == "afternoon":
            preferred = [s for s in slots if " PM " in s]
        else:
            preferred = slots
        available = (preferred or slots)[:5]
        return {
            "status": "success",
            "action": "check_availability",
            "date": date_str,
            "available_slots": available,
            "recommended_slot": available[0] if available else None,
            "message": f"Found {len(available)} open slots." if available else "No open slots in the next three weeks.",
        }

    async def book_meeting(
        self,
        time_slot: str = "Tomorrow at 2:00 PM EST",
        email: Optional[str] = None,
        topic: str = "Agora Real-Time Voice AI Sales Deep-Dive",
        host_name: str = "Senior Solutions Architect"
    ) -> Dict[str, Any]:
        """Validates the slot against availability, then reserves it with its own meeting room."""
        check = self.check_slot(time_slot)
        if not check["ok"]:
            return {"status": "UNAVAILABLE", "time": time_slot, "reason": check["reason"], "alternatives": check["alternatives"]}
        booking = self.reserve(time_slot, check["start_utc"], check["end_utc"], None, email, topic)
        return {
            "meeting_id": booking["meeting_id"],
            "status": "CONFIRMED",
            "time": time_slot,
            "email": email,
            "topic": topic,
            "host": host_name,
            "meeting_link": booking["meeting_link"],
            "booked_at": booking["booked_at"],
            "message": f"Demo confirmed for {time_slot}.",
        }

calendar_service = CalendarService()

# Export helper functions
async def check_availability(date_str: str = "tomorrow", time_preference: str = "afternoon") -> Dict[str, Any]:
    return await calendar_service.check_availability(date_str, time_preference)

async def book_meeting(time_slot: str, email: Optional[str] = None, topic: str = "Agora Real-Time Voice AI Sales Deep-Dive") -> Dict[str, Any]:
    return await calendar_service.book_meeting(time_slot, email, topic)

async def book_calendar_slot(time_slot: str, email: Optional[str] = None, topic: str = "Agora Real-Time Voice AI Sales Deep-Dive") -> Dict[str, Any]:
    return await calendar_service.book_meeting(time_slot, email, topic)
