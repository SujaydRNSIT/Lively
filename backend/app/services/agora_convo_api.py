import httpx
import base64
import logging
from typing import Dict, Any, Optional
from app.config import settings
from app.services.agora_token import build_rtc_token

logger = logging.getLogger("lively.services.agora_convo")

class AgoraConvoAIService:
    BASE_URL = "https://api.agora.io/api/conversational-ai-agent/v2/projects"

    def __init__(self):
        self.app_id = settings.AGORA_APP_ID
        self.app_cert = settings.AGORA_APP_CERTIFICATE
        self.rest_key = settings.AGORA_REST_KEY
        self.rest_secret = settings.AGORA_REST_SECRET
        # Shared connection-pooled HTTP client — avoids TCP+TLS handshake per request
        self._http_client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )

    def _get_headers(self) -> Dict[str, str]:
        if not self.rest_key or not self.rest_secret:
            auth_str = "dummy:dummy"
        else:
            auth_str = f"{self.rest_key}:{self.rest_secret}"
        encoded_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
        return {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/json",
        }

    async def start_agent(
        self,
        channel_name: str,
        customer_uid: int | str = 1001,
        agent_rtc_uid: int = 9999,
        custom_llm_url: Optional[str] = None
    ) -> Dict[str, Any]:
        import time
        agent_token = build_rtc_token(
            self.app_id, self.app_cert, channel_name, agent_rtc_uid
        )

        llm_endpoint = custom_llm_url or f"{settings.BACKEND_PUBLIC_URL}/v1/chat/completions?channel={channel_name}"
        unique_session_name = f"Lively_{channel_name}_{int(time.time())}"

        payload = {
            "name": unique_session_name,
            "properties": {
                "channel": channel_name,
                "token": agent_token,
                "agent_rtc_uid": str(agent_rtc_uid),
                "remote_rtc_uids": ["*"],
                "idle_timeout": 600,
                "llm": {
                    "url": llm_endpoint,
                    "api_key": settings.LIVELY_LLM_SHARED_SECRET,
                    "system_messages": [
                        {
                            "role": "system",
                            "content": "You are Lively, an expert voice AI sales representative for Lively AI powered by Agora."
                        }
                    ],
                    "max_history": 32,
                    "greeting_message": "Hello! I'm Lively, your AI sales representative. How can I help you today?",
                    "failure_message": "I'm sorry, could you please repeat that?",
                    "params": {
                        "model": "lively-router"
                    }
                },
                "tts": {
                    "credential_mode": "managed",
                    "vendor": "minimax",
                    "params": {
                        "url": "wss://api.minimax.io/ws/v1/t2a_v2",
                        "model": "speech-2.6-turbo",
                        "voice_setting": {
                            "voice_id": "English_captivating_female1"
                        }
                    }
                },
                "asr": {
                    "credential_mode": "managed",
                    "vendor": "deepgram",
                    "params": {
                        "url": "wss://api.deepgram.com/v1/listen",
                        "model": "nova-3",
                        "language": "en-US"
                    }
                },
                "turn_detection": {
                    "mode": "default",
                    "config": {
                        "speech_threshold": 0.5,
                        "start_of_speech": {
                            "mode": "vad",
                            "vad_config": {
                                "interrupt_duration_ms": 240,
                                "speaking_interrupt_duration_ms": 400,
                                "prefix_padding_ms": 600
                            }
                        },
                        "end_of_speech": {
                            "mode": "semantic",
                            "semantic_config": {
                                "silence_duration_ms": 650,
                                "max_wait_ms": 3000
                            }
                        }
                    }
                }
            }
        }

        if not self.app_id or not self.rest_key:
            logger.info("Agora REST credentials not configured. Returning simulated agent session.")
            return {
                "agent_id": f"agent_sess_{channel_name}_{int(customer_uid)}",
                "status": "RUNNING",
                "channel_name": channel_name,
                "agent_rtc_uid": agent_rtc_uid,
                "customer_uid": customer_uid,
                "mock": True
            }

        endpoint = f"{self.BASE_URL}/{self.app_id}/join"
        try:
            res = await self._http_client.post(endpoint, json=payload, headers=self._get_headers())
            logger.info(f"Agora v2 join response: {res.status_code} {res.text[:500]}")
            if res.status_code in (200, 201):
                data = res.json()
                data["channel_name"] = channel_name
                data["agent_rtc_uid"] = agent_rtc_uid
                return data
            elif res.status_code == 409:
                try:
                    err_data = res.json()
                    existing_agent = err_data.get("agent_id")
                    if existing_agent:
                        logger.info(f"Stopping conflicting Agora agent {existing_agent} and retrying join...")
                        await self.stop_agent(existing_agent)
                        import asyncio
                        await asyncio.sleep(0.5)
                        payload["name"] = f"Lively_{channel_name}_{int(time.time())}_retry"
                        retry_res = await self._http_client.post(endpoint, json=payload, headers=self._get_headers())
                        if retry_res.status_code in (200, 201):
                            data = retry_res.json()
                            data["channel_name"] = channel_name
                            data["agent_rtc_uid"] = agent_rtc_uid
                            return data
                except Exception as retry_err:
                    logger.warning(f"Retry after 409 failed: {retry_err}")

            logger.warning(f"Agora Start Agent failed ({res.status_code}): {res.text[:300]}. Falling back to simulation.")
            return {
                "agent_id": f"agent_sess_{channel_name}_{int(customer_uid)}",
                "status": "RUNNING",
                "channel_name": channel_name,
                "agent_rtc_uid": agent_rtc_uid,
                "customer_uid": customer_uid,
                "api_code": res.status_code,
                "mock": True
            }
        except Exception as e:
            logger.exception(f"Agora Convo AI start agent error: {e}")
            return {
                "agent_id": f"agent_sess_{channel_name}_{int(customer_uid)}",
                "status": "RUNNING",
                "channel_name": channel_name,
                "agent_rtc_uid": agent_rtc_uid,
                "customer_uid": customer_uid,
                "error": str(e),
                "mock": True
            }

    async def stop_agent(self, agent_id: str) -> Dict[str, Any]:
        if not self.app_id or not self.rest_key or agent_id.startswith("agent_sess_"):
            return {"agent_id": agent_id, "status": "STOPPED", "mock": True}

        endpoint = f"{self.BASE_URL}/{self.app_id}/agents/{agent_id}/leave"
        try:
            res = await self._http_client.post(endpoint, headers=self._get_headers())
            return res.json() if res.status_code == 200 else {"agent_id": agent_id, "status": "STOPPED", "code": res.status_code}
        except Exception as e:
            return {"agent_id": agent_id, "status": "STOPPED", "error": str(e)}

    async def query_agent(self, agent_id: str) -> Dict[str, Any]:
        if not self.app_id or not self.rest_key or agent_id.startswith("agent_sess_"):
            return {"agent_id": agent_id, "status": "RUNNING", "channel": "active", "mock": True}

        endpoint = f"{self.BASE_URL}/{self.app_id}/agents/{agent_id}"
        try:
            res = await self._http_client.get(endpoint, headers=self._get_headers())
            return res.json() if res.status_code == 200 else {"agent_id": agent_id, "status": "UNKNOWN", "code": res.status_code}
        except Exception as e:
            return {"agent_id": agent_id, "status": "UNKNOWN", "error": str(e)}

agora_convo_service = AgoraConvoAIService()
