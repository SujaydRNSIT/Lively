"""
Phase 7 — Task 7.1: Document Ingestion and Chunking Script for Lively RAG Knowledge Base.
Ingests product specifications, pricing matrices, architectural battlecards, and customer case studies.
"""

import logging
from typing import List, Dict, Any
from app.db.vector_store import vector_store

logger = logging.getLogger("lively.rag.ingest")

DOCUMENTS_SOURCE = [
    {
        "doc_id": "prod_agora_rtc_core",
        "title": "Agora Real-Time Conversational AI Engine Architecture",
        "category": "product",
        "content": (
            "Agora's Conversational AI Engine is built on top of the Software-Defined Real-time Network (SD-RTN), "
            "providing ultra-low latency voice streaming across 200+ countries with sub-80ms packet delivery. "
            "It manages native Voice Activity Detection (VAD), acoustic echo cancellation (AEC), automatic gain control (AGC), "
            "background noise suppression (ANS), and adaptive turn-taking with instant barge-in interruption. "
            "The engine orchestrates streaming STT (ARES, Deepgram, Azure) -> Custom LLM endpoint -> streaming TTS (ElevenLabs, Azure)."
        ),
        "keywords": ["agora", "architecture", "sd-rtn", "vad", "aec", "ans", "barge-in", "interruption", "turn-taking", "stt", "tts"]
    },
    {
        "doc_id": "pricing_tiers_2026",
        "title": "Lively Pricing Sheets & Volume Discounts",
        "category": "pricing",
        "content": (
            "Lively Pricing Structure:\n"
            "- Starter Tier: $199/month includes 2,000 voice minutes, full Agora SD-RTN network access, and Groq LPU routing.\n"
            "- Growth Tier: $699/month includes 10,000 voice minutes, automated CRM sync (Salesforce/HubSpot), custom battlecards, and calendar booking.\n"
            "- Enterprise Tier: Volume-based custom pricing with dedicated SD-RTN routing, private NVIDIA NIM model options and a dedicated SLA.\n"
            "- Seats do not change the plan price; plans are priced by voice minutes, so larger teams usually move from Starter to Growth for volume."
        ),
        "keywords": ["pricing", "price", "cost", "starter", "growth", "enterprise", "discount", "tier", "plan", "budget", "roi", "tco"]
    },
    {
        "doc_id": "battlecard_openai_realtime",
        "title": "Competitive Battlecard: Agora vs OpenAI Realtime API",
        "category": "battlecard",
        "content": (
            "Why Lively + Agora outperforms OpenAI Realtime API:\n"
            "1. Network Quality: Agora operates a telecom-grade global SD-RTN network, preventing packet loss and jitter common with public WebSockets.\n"
            "2. Model Sovereignty: OpenAI locks customers into GPT-4o voice. Lively allows complete freedom to route conversational turns to Groq (sub-200ms TTFT LPU) or private NVIDIA NIM enterprise models.\n"
            "3. Audio Processing: Agora's native acoustic echo cancellation prevents self-interruption and feedback loops.\n"
            "4. Cost control: pick the model per turn instead of paying one vendor's per-token voice pricing."
        ),
        "keywords": ["openai", "openai realtime", "gpt-4o", "gpt4o", "chatgpt", "competitor", "comparison"]
    },
    {
        "doc_id": "battlecard_twilio_sip",
        "title": "Competitive Battlecard: Agora vs Twilio Media Streams",
        "category": "battlecard",
        "content": (
            "Why Lively + Agora outperforms Twilio / Vapi:\n"
            "1. Latency: SIP media bridges add transport hops; Agora carries audio over its own real-time WebRTC network end to end.\n"
            "2. Native Turn-Taking: Agora handles barge-in at the edge, cutting speech transmission immediately when user speaks.\n"
            "3. Direct Custom LLM Brain: Zero middleman markup on tokens."
        ),
        "keywords": ["twilio", "vapi", "bland", "retell", "elevenlabs", "sip", "telephony", "competitor"]
    },
    {
        "doc_id": "integrations_onboarding",
        "title": "Integrations, Scheduling & Human Handoff",
        "category": "product",
        "content": (
            "Integrations: call notes, qualification details and booked meetings sync to the CRM (HubSpot supported; Salesforce on Enterprise). "
            "Scheduling: the agent offers open demo slots during the call and sends a calendar invite with a video room link. "
            "Human handoff: when a buyer asks for a person, raises contract or legal terms, or stays frustrated, the call is handed to an account executive "
            "with the full conversation and qualification summary, so the buyer never repeats themselves. "
            "Guardrails: answers come only from approved documentation; anything uncertain is routed to a human."
        ),
        "keywords": ["integration", "integrations", "crm", "hubspot", "salesforce", "calendar", "handoff", "human", "onboarding", "trust", "accuracy", "hallucination"]
    },
    {
        "doc_id": "faq_security_hipaa",
        "title": "Security, Privacy & HIPAA Compliance FAQ",
        "category": "security",
        "content": (
            "Security & Compliance Standards:\n"
            "- End-to-end encrypted WebRTC audio streams (AES-256).\n"
            "- SOC2 Type II certified and HIPAA compliant with signed Business Associate Agreements (BAA).\n"
            "- Zero data retention options for sensitive healthcare and financial interactions.\n"
            "- Sovereign on-premise model execution available via NVIDIA NIM."
        ),
        "keywords": ["security", "hipaa", "soc2", "gdpr", "compliance", "encryption", "privacy", "baa"]
    }
]

def run_ingestion() -> int:
    """
    Embeds and upserts knowledge base documents into Pinecone.
    """
    vector_store.upsert_documents(DOCUMENTS_SOURCE)
    logger.info(f"Ingested {len(DOCUMENTS_SOURCE)} RAG knowledge base documents into Pinecone.")
    return len(DOCUMENTS_SOURCE)

if __name__ == "__main__":
    c = run_ingestion()
    print(f" Successfully ingested {c} RAG documents into vector store!")
