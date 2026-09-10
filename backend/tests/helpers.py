from typing import Dict, Tuple


async def new_session(ac) -> Tuple[str, Dict[str, str]]:
    """Create a visitor session and return (channel_name, auth headers)."""
    res = await ac.post("/api/session", json={})
    assert res.status_code == 200, res.text
    data = res.json()
    return data["channel_name"], {"X-Lively-Session": data["session_token"]}
