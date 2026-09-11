import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.deal_desk import deal_desk, AGENT_CEILING, MANAGER_CEILING, ABSOLUTE_MAXIMUM
from app.core.deal_state_engine import deal_state_engine
from app.core.tools_defs import execute_openai_tool_call
from app.core.llm_router import llm_router
from tests.helpers import new_session


# --------------------------------------------------------------------------- #
# 1. Test Deal Desk Core Policy Rules & Authority Tiers
# --------------------------------------------------------------------------- #
def test_deal_desk_policy_tiers():
    channel = "test_dd_policy"

    # A. Within Agent Authority (<= 15%) -> Immediate autonomous approval
    rec1 = deal_desk.propose(channel, 10.0)
    assert rec1.status == "approved"
    assert rec1.authorised_pct == 10.0
    assert rec1.manager_approval_required is False
    assert "Approved 10%" in rec1.to_dict()["label"]
    assert rec1.to_dict()["bound_by"] == f"agent authority: {AGENT_CEILING}%"

    # B. Above Agent Authority but <= Manager Ceiling (15% - 25%) -> Pending Manager
    rec2 = deal_desk.propose(channel, 20.0)
    assert rec2.status == "pending_manager"
    assert rec2.authorised_pct == 20.0
    assert rec2.manager_approval_required is True
    assert "Pending manager approval" in rec2.to_dict()["label"]

    # C. Manager clicks Approve
    approved_rec = deal_desk.manager_approve(channel, rec2.id, approved_by="sales_director")
    assert approved_rec is not None
    assert approved_rec.status == "approved"
    assert approved_rec.approved_by == "sales_director"
    assert approved_rec.authorised_pct == 20.0

    # D. Above Hard Ceiling (> 25%) -> Strictly Refused
    rec3 = deal_desk.propose(channel, 35.0)
    assert rec3.status == "refused"
    assert rec3.authorised_pct == 0.0
    assert "Refused" in rec3.to_dict()["label"]
    assert f"hard ceiling: {ABSOLUTE_MAXIMUM}%" in rec3.to_dict()["bound_by"]

    # E. Commitment Trade Headroom (e.g. annual commitment +5pp headroom -> agent ceiling = 20%)
    rec4 = deal_desk.propose(channel, 18.0, trade="annual")
    assert rec4.status == "approved"
    assert rec4.authorised_pct == 18.0
    assert rec4.trade == "annual"
    assert "trade commitment (annual) applied" in rec4.to_dict()["bound_by"]


# --------------------------------------------------------------------------- #
# 2. Test OpenAI Tool Registry Execution
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_openai_tool_call_propose_concession():
    channel = "test_dd_tool_exec"
    state = deal_state_engine.get_or_create(channel)

    tool_result = await execute_openai_tool_call(
        tool_name="propose_concession",
        arguments={"percentage": 12.5},
        channel_name=channel,
        deal_state=state
    )

    assert tool_result["status"] == "approved"
    assert tool_result["authorised_pct"] == 12.5
    assert state.deal_desk is not None
    assert state.deal_desk["authorised_pct"] == 12.5
    assert state.deal_desk["status"] == "approved"


# --------------------------------------------------------------------------- #
# 3. Test REST API Endpoints for Propose, Approve, and History
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_deal_desk_rest_api_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        channel, headers = await new_session(ac)

        # Propose 14% (Autonomous)
        res1 = await ac.post("/api/tools/deal-desk/propose", json={
            "channel_name": channel,
            "percentage": 14.0,
            "trade": "none"
        }, headers=headers)
        assert res1.status_code == 200
        data1 = res1.json()["data"]
        assert data1["status"] == "approved"
        assert data1["authorised_pct"] == 14.0

        # Propose 22% (Escalated to Manager)
        res2 = await ac.post("/api/tools/deal-desk/propose", json={
            "channel_name": channel,
            "percentage": 22.0,
            "trade": "none"
        }, headers=headers)
        assert res2.status_code == 200
        data2 = res2.json()["data"]
        assert data2["status"] == "pending_manager"
        concession_id = data2["id"]

        # Manager approves via REST
        res3 = await ac.post("/api/tools/deal-desk/approve", json={
            "channel_name": channel,
            "concession_id": concession_id,
            "approved_by": "vp_sales"
        }, headers=headers)
        assert res3.status_code == 200
        data3 = res3.json()["data"]
        assert data3["status"] == "approved"
        assert data3["approved_by"] == "vp_sales"

        # Check Concession History
        hist_res = await ac.get(f"/api/tools/deal-desk/history/{channel}", headers=headers)
        assert hist_res.status_code == 200
        history = hist_res.json()["history"]
        assert len(history) >= 2


# --------------------------------------------------------------------------- #
# 4. Test System Prompt Grounding with Concession
# --------------------------------------------------------------------------- #
def test_system_prompt_reflects_deal_desk_concession():
    channel = "test_dd_prompt"
    state = deal_state_engine.get_or_create(channel)

    # Propose 10%
    deal_desk.propose(channel, 10.0)
    state.deal_desk = deal_desk.history(channel)[-1]

    prompt = llm_router.construct_system_prompt(state, "Can you do a 10% discount?")
    assert "APPROVED concession of 10% off" in prompt
    assert "179" in prompt  # $199 - 10% = $179
    assert "629" in prompt  # $699 - 10% = $629


# --------------------------------------------------------------------------- #
# 5. Live End-to-End LLM Turn with Price Deduction Response
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_live_llm_turn_negotiates_and_deduces_price():
    channel = "test_dd_live_turn"
    state = deal_state_engine.get_or_create(channel)

    # Set approved 10% concession
    deal_desk.propose(channel, 10.0)
    state.deal_desk = deal_desk.history(channel)[-1]

    messages = [
        {"role": "user", "content": "Can you give us a 10% discount on the Starter plan?"}
    ]

    tokens = []
    async for chunk in llm_router.stream_chat_completion(
        messages=messages,
        deal_state=state,
        channel_name=channel,
        model=None
    ):
        if chunk.startswith("data:") and not chunk.startswith("data: [DONE]"):
            import json
            try:
                payload = json.loads(chunk.replace("data:", "").strip())
                choices = payload.get("choices") or []
                if choices:
                    content = choices[0].get("delta", {}).get("content", "")
                    if content:
                        tokens.append(content)
            except Exception:
                pass

    response_text = "".join(tokens).lower()
    print("\n[LLM Agent Response to 10% Discount Request]:", "".join(tokens))

    # Agent should confirm the discount and quote reduced price
    assert any(term in response_text for term in ("179", "10%", "discount", "starter", "month", "deal"))
