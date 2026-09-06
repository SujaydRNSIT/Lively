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
            "- Enterprise Tier: Blended volume pricing starting at $0.05/minute with dedicated SD-RTN routing, private sovereign NVIDIA NIM models, 99.99% uptime SLA, and SOC2/HIPAA compliance.\n"
            "- TCO comparison: Customers achieve 40% to 60% lower total cost of ownership compared to assembling individual point solutions."
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
            "4. Cost: 50% lower cost per minute compared to OpenAI Realtime token pricing."
        ),
        "keywords": ["openai", "openai realtime", "gpt-4o", "gpt4o", "chatgpt", "competitor", "comparison"]
    },
    {
        "doc_id": "battlecard_twilio_sip",
        "title": "Competitive Battlecard: Agora vs Twilio Media Streams",
        "category": "battlecard",
        "content": (
            "Why Lively + Agora outperforms Twilio / Vapi:\n"
            "1. Latency: Twilio SIP media bridges introduce 400-800ms transport latency. Agora WebRTC provides sub-200ms glass-to-glass latency.\n"
            "2. Native Turn-Taking: Agora handles barge-in at the edge, cutting speech transmission immediately when user speaks.\n"
            "3. Direct Custom LLM Brain: Zero middleman markup on tokens."
        ),
        "keywords": ["twilio", "vapi", "bland", "retell", "elevenlabs", "sip", "telephony", "competitor"]
    },
    {
        "doc_id": "case_study_fintech",
        "title": "Case Study: Global FinTech Increases Demo Conversion by 3.2x",
        "category": "case_study",
        "content": (
            "A global financial services provider deployed Lively Voice AI for inbound demo qualification. "
            "By delivering sub-350ms response times and instant calendar booking over Agora's HIPAA-compliant voice layer, "
            "the customer achieved a 3.2x increase in qualified demo bookings and reduced CAC by 44%."
        ),
        "keywords": ["case study", "fintech", "conversion", "roi", "roi proof", "results", "metrics", "customer story"]
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
