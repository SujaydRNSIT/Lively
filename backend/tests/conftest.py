import os

import pytest

# Tests must never reach real email, LLM, CRM or Agora services, whatever is in the developer's .env.
for _key in ("SMTP_USER", "SMTP_PASSWORD", "GROQ_API_KEY", "NVIDIA_NIM_API_KEY", "HUBSPOT_ACCESS_TOKEN",
             "ESCALATION_NOTIFY_EMAIL", "PINECONE_API_KEY", "AGORA_APP_ID", "AGORA_REST_KEY", "REDIS_URL", "DATABASE_URL"):
    os.environ[_key] = ""
# Legacy tests book fixed relative days ("tomorrow at 3 PM"); keep them independent of the weekday they run on.
os.environ["CALENDAR_WORKING_DAYS"] = "mon,tue,wed,thu,fri,sat,sun"


@pytest.fixture(autouse=True)
def _isolate_shared_state():
    from app.core.tools_impl.calendar import calendar_service
    from app.core.security import rate_limiter
    calendar_service.reset()
    rate_limiter.reset()
    yield
