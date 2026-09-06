<div align="center">

<img src="frontend/public/logo.png" alt="Lively Logo" width="280" />

### **LISTEN. ADAPT. REMEMBER. ACT.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://reactjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Agora](https://img.shields.io/badge/Agora-Conversational%20AI-099DFD?style=for-the-badge&logo=agora&logoColor=white)](https://www.agora.io)
[![Groq](https://img.shields.io/badge/Groq-LPU%20Inference-F55036?style=for-the-badge&logo=groq&logoColor=white)](https://groq.com)
[![NVIDIA NIM](https://img.shields.io/badge/NVIDIA-NIM-76B900?style=for-the-badge&logo=nvidia&logoColor=white)](https://build.nvidia.com)

---

**A real-time voice AI sales agent that listens to every word, adapts its strategy on the fly, remembers full deal context across turns, and acts — booking demos, updating CRMs, and escalating to humans — all while the buyer is still on the line.**

*Powered by the Agora Conversational AI Engine with a custom multi-LLM brain (Groq LPU + NVIDIA NIM).*

[Features](#core-features) · [Architecture](#system-architecture) · [Quick Start](#quick-start) · [Manual Setup](#manual-setup-alternative) · [Demo](#demo-walkthrough) · [Project Structure](#project-structure)

---

</div>

<br/>

## Core Features

| Capability | What It Does |
|:---|:---|
| **Real-Time Voice Conversations** | Sub-300ms round-trip latency with Agora's telecom-grade RTC — natural turn-taking, barge-in, echo cancellation, and noise suppression out of the box. |
| **Adaptive Sales Brain** | Every utterance is analyzed for buyer intent, scale, budget, timeline, competitor mentions, and authority level. The agent adapts its pitch in real time. |
| **Persistent Deal Memory** | Additive & mergeable deal state across all turns — nothing is forgotten. Budget changes? User scale updates? Lively merges them with a full change-log. |
| **RAG-Grounded Responses** | Battlecards, pricing sheets, and competitive intelligence are retrieved in real time so every claim is grounded in facts, not hallucinations. |
| **Live Tool Calling** | `book_meeting()`, `create_or_update_crm_lead()`, `escalate_to_human()` — the agent takes action while the conversation is still happening. |
| **Multi-LLM Router** | Groq LPU for ultra-low-latency voice turns, NVIDIA NIM for complex reasoning, and a built-in sales specialist brain as a zero-downtime fallback. |
| **Dark / Light Theme** | Full dark mode with a one-click Sun/Moon toggle in the cockpit navbar. |
| **Live Telemetry** | Real-time TTFT, response latency, model distribution, memory diffs, and deal stage tracking — all streamed via WebSocket. |

<br/>

---

## System Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                 BROWSER  (React / TypeScript)                  │
│                                                                │
│  Sales Cockpit UI       Agora RTC Web SDK       WebSocket      │
│  ┌──────────────┐      ┌──────────────────┐   ┌────────────┐   │
│  │ Transcript   │      │ Publish Mic Audio│   │ Telemetry  │   │
│  │ Deal Stage   │      │ Subscribe Agent  │   │ Stream     │   │
│  │ Battlecards  │      │ Speech           │   │ /ws/{ch}   │   │
│  │ Telemetry    │      └────────┬─────────┘   └─────┬──────┘   │
│  └──────────────┘                │                   │         │
└──────────────────────────────────┼───────────────────┼─────────┘
                                   │                   │
                                   ▼                   ▼
┌────────────────────────────────────────────────────────────────┐
│            AGORA CONVERSATIONAL AI ENGINE                      │
│                                                                │
│  ● Turn-Taking & VAD       ● Barge-In Handling                 │
│  ● Echo Cancellation       ● Noise Suppression                 │
│  ● Streaming STT ──► [Custom LLM Endpoint] ──► TTS             │
└───────────────────────────────┬────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────┐
│            LIVELY INTELLIGENCE CORE  (FastAPI)                 │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │               /v1/chat/completions                       │  │
│  │  OpenAI-compatible streaming endpoint called by Agora    │  │
│  │                                                          │  │
│  │  1. LISTEN    → Extract intent, budget, competitors      │  │
│  │  2. ADAPT     → RAG retrieval + next-best-action         │  │
│  │  3. REMEMBER  → Additive deal state merge + change-log   │  │
│  │  4. ACT       → Tool-calling (book, CRM, escalate)       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                │
│  ┌────────────────┐  ┌──────────────┐  ┌───────────────────┐   │
│  │  LLM Router    │  │  Tool Layer  │  │ Telemetry Engine  │   │
│  │                │  │              │  │                   │   │
│  │  Groq LPU      │  │ book_meeting │  │ TTFT / p50 / p95  │   │
│  │  (sub-200ms)   │  │ update_crm   │  │ Model distrib.    │   │
│  │                │  │ escalate     │  │ Memory diffs      │   │
│  │  NVIDIA NIM    │  │              │  │ Stage tracking    │   │
│  │  (reasoning)   │  └──────────────┘  └───────────────────┘   │
│  │                │                                            │
│  │  Built-in      │                                            │
│  │  (fallback)    │                                            │
│  └────────────────┘                                            │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   Storage Layer                          │  │
│  │  SQLite (local dev) / Postgres (production)              │  │
│  │  DealStateTable · EscalationQueue · Analytics            │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

<br/>

---

## Quick Start

> **This is the recommended way to run Lively.** Two `.bat` files handle everything — dependencies, tunneling, port management, and launching all services in one terminal.

### Prerequisites

| Requirement | Version | Download |
|:---|:---|:---|
| **Python** | 3.11+ | [python.org/downloads](https://www.python.org/downloads/windows/) — check **"Add Python to PATH"** |
| **Node.js** | 18+ | [nodejs.org](https://nodejs.org/) |
| **Git** | Any | [git-scm.com](https://git-scm.com/) |

### Step 1 — Clone the Repository

```cmd
git clone https://github.com/your-org/Lively.git
cd Lively
```

### Step 2 — Install Everything

Double-click **`install.bat`** or run it from a terminal:

```cmd
install.bat
```

This single script automatically:

| # | What it does |
|:---|:---|
| 1 | Detects your Python installation and creates a `.venv` virtual environment |
| 2 | Installs all backend Python packages from `backend/requirements.txt` |
| 3 | Installs all frontend npm packages via `npm ci` |
| 4 | Creates `.env` from `.env.example` if it doesn't exist |
| 5 | Downloads `cloudflared.exe` for the Agora webhook tunnel |

### Step 3 — Configure API Keys

Open `.env` in any editor and fill in your credentials:

```env
# ── Required ─────────────────────────────────────
AGORA_APP_ID=your_agora_app_id
AGORA_APP_CERTIFICATE=your_agora_app_certificate
AGORA_REST_KEY=your_agora_rest_key
AGORA_REST_SECRET=your_agora_rest_secret

# ── At least one LLM provider ────────────────────
GROQ_API_KEY=gsk_...                      # Primary — low-latency voice turns
NVIDIA_NIM_API_KEY=nvapi-...              # Secondary — complex reasoning

# ── Optional ─────────────────────────────────────
PINECONE_API_KEY=                          # Leave blank for built-in in-memory RAG
```

### Step 4 — Launch Lively

Double-click **`run.bat`** or run from a terminal:

```cmd
run.bat
```

**`run.bat` handles everything for you:**

```
 ✓  Frees any stale ports (8000, 5173)
 ✓  Starts the Cloudflare tunnel for Agora webhooks
 ✓  Auto-updates BACKEND_PUBLIC_URL in your .env
 ✓  Launches the FastAPI backend on port 8000
 ✓  Launches the Vite dev server on port 5173
 ✓  Opens http://localhost:5173 in your browser
```

> **Want separate terminal windows?** Run `run_separate.bat` instead — it opens the tunnel, backend, and frontend in three distinct CMD windows for easier debugging.

<br/>

---

## Manual Setup (Alternative)

> Use this approach if you're on **macOS / Linux**, prefer full control, or need to debug individual services.

### Prerequisites

- Python 3.11+
- Node.js 18+ / npm
- A Cloudflare tunnel (or ngrok) for Agora webhook callbacks

### 1. Clone & Configure Environment

```bash
git clone https://github.com/your-org/Lively.git
cd Lively
cp .env.example .env
```

Edit `.env` and insert your API keys (same as Step 3 above).

### 2. Set Up the Python Virtual Environment

```bash
python -m venv .venv

# Activate the virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1

# Windows (CMD):
.venv\Scripts\activate.bat

# macOS / Linux:
source .venv/bin/activate
```

### 3. Install Backend Dependencies

```bash
pip install --upgrade pip
pip install -r backend/requirements.txt
```

### 4. Install Frontend Dependencies

```bash
cd frontend
npm ci
cd ..
```

### 5. Start the Cloudflare Tunnel

Agora's Conversational AI Engine needs a publicly reachable URL to call your custom LLM endpoint. In a **new terminal**:

```bash
cloudflared tunnel --url http://localhost:8000
```

Copy the generated `https://....trycloudflare.com` URL and set it in your `.env`:

```env
BACKEND_PUBLIC_URL=https://your-tunnel-url.trycloudflare.com
```

> Also copy `.env` into the `backend/` directory so FastAPI can read it:
> ```bash
> cp .env backend/.env
> ```

### 6. Start the FastAPI Backend

```bash
# Windows (PowerShell)
$env:PYTHONPATH="backend"
py -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# macOS / Linux
PYTHONPATH=backend python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 7. Start the React Frontend

In a **new terminal**:

```bash
cd frontend
npm run dev
```

### 8. Open in Browser

Navigate to **http://localhost:5173** — the Lively Sales Cockpit is ready.

<br/>

---

## Demo Walkthrough

Use the built-in **Scripted Demo Harness** tab or speak live into your microphone.

<table>
<tr>
<th width="60">Turn</th>
<th width="220">Buyer Says</th>
<th>Lively Responds</th>
<th width="180">System Action</th>
</tr>
<tr>
<td align="center"><strong>1</strong></td>
<td><em>"Hi, we're evaluating real-time voice AI. How much does Lively cost?"</em></td>
<td>Quotes Starter ($199/mo) and Growth ($699/mo) tiers with 40–60% TCO advantage over alternatives.</td>
<td>RAG retrieval → pricing battlecard</td>
</tr>
<tr>
<td align="center"><strong>2</strong></td>
<td><em>"Wait, how do you compare to OpenAI Realtime and Twilio?"</em> (barge-in)</td>
<td>Triggers competitive battlecard — highlights Agora SD-RTN (&lt;300ms latency) and freedom to swap custom LLM brains.</td>
<td>Competitor detection → battlecard</td>
</tr>
<tr>
<td align="center"><strong>3</strong></td>
<td><em>"Actually our team expanded to 80 users and our budget is $100k ARR. I'm the VP of Product."</em></td>
<td>Acknowledges the updates smoothly without repeating old context.</td>
<td>Additive memory merge → deal state diff</td>
</tr>
<tr>
<td align="center"><strong>4</strong></td>
<td><em>"Can we schedule a live technical walkthrough tomorrow at 2 PM EST?"</em></td>
<td>Confirms the booking with date/time and displays the <strong>Outcome Achieved</strong> banner.</td>
<td><code>book_meeting()</code> tool call → CRM update</td>
</tr>
</table>

<br/>

---

## Project Structure

```
Lively/
│
├── install.bat                 # One-click dependency setup (Python venv, npm, cloudflared)
├── run.bat                     # One-click full system launcher (tunnel + backend + frontend)
├── run_separate.bat            # Launch each service in its own CMD window
├── .env.example                # Environment template with all configurable keys
├── .env                        # Your actual API keys (private, tracked in repo)
│
├── backend/                     # FastAPI — Lively Intelligence Core
│   ├── app/
│   │   ├── main.py             # FastAPI application entry point & route registration
│   │   ├── config.py           # Pydantic settings — env var loading & validation
│   │   ├── api/                # REST & WebSocket route handlers
│   │   ├── core/               # The brain
│   │   │   ├── deal_state_engine.py   # Additive deal memory — merge, diff, change-log
│   │   │   ├── decision.py            # Next-best-action decision engine
│   │   │   ├── llm_router.py          # Multi-provider LLM routing (Groq → NIM → fallback)
│   │   │   ├── prompts.py            # System prompt templates & persona
│   │   │   ├── rag.py                # RAG retrieval interface
│   │   │   ├── tools_defs.py         # OpenAI-format tool/function definitions
│   │   │   └── tools_impl/           # Tool implementations (booking, CRM, escalation)
│   │   ├── db/                 # Database models & session management (SQLite / Postgres)
│   │   ├── models/             # Pydantic request/response schemas
│   │   ├── routers/            # API route modules
│   │   └── services/           # Service layer
│   │       ├── agora_convo_api.py    # Agora Conversational AI agent lifecycle
│   │       ├── agora_token.py        # RTC token generation
│   │       ├── deal_state.py         # Deal state persistence & retrieval
│   │       ├── llm_router.py         # LLM service orchestration
│   │       ├── rag_service.py        # RAG service (in-memory or Pinecone)
│   │       └── tools.py             # Tool execution service
│   ├── requirements.txt        # Core Python dependencies
│   └── requirements-pinecone.txt  # Optional Pinecone semantic RAG packages
│
├── frontend/                    # React Sales Cockpit — Vite + TypeScript + Tailwind
│   ├── src/
│   │   ├── App.tsx             # Root component — layout, state management, theme
│   │   ├── index.css           # Global styles, dark/light theme, CSS variables
│   │   ├── main.tsx            # React DOM entry point
│   │   ├── components/
│   │   │   ├── Navbar.tsx              # Top nav — logo, motto, playbook, theme toggle
│   │   │   ├── LiveTranscriptStream.tsx # Real-time conversation transcript
│   │   │   ├── ObjectionBattlecards.tsx # Objection detection & response cards
│   │   │   ├── DealStagePipeline.tsx    # Visual deal stage tracker (5 stages)
│   │   │   ├── ActionItemsPanel.tsx     # Telemetry, latency, model stats, actions
│   │   │   ├── AgentExpression.tsx      # Pixel-art agent face with emotion states
│   │   │   ├── VoiceCallHud.tsx         # Voice call controls & status HUD
│   │   │   ├── ScriptedDemoHarness.tsx  # Pre-scripted demo conversation runner
│   │   │   ├── OutcomeBanner.tsx        # Success banner on deal outcomes
│   │   │   ├── KnowledgeBaseModal.tsx   # RAG knowledge base viewer/editor
│   │   │   ├── SandboxTester.tsx        # API sandbox testing panel
│   │   │   └── AnalyticsDashboard.tsx   # Analytics & reporting dashboard
│   │   ├── services/           # API client & WebSocket connection logic
│   │   └── types/              # TypeScript interfaces & type definitions
│   └── public/
│       └── logo.png            # Lively logo asset
│
├── scripts/
│   ├── launcher.py             # Orchestrates tunnel + backend + frontend processes
│   └── free_ports.py           # Kills stale processes on ports 8000 & 5173
│
└── LIMITATIONS.md              # Known constraints & trade-offs
```

<br/>

---

## Testing

Run the automated test suite to verify memory, RAG, and tool execution:

```bash
# Activate virtual environment first
.venv\Scripts\activate.bat

# Run tests
py backend/tests/test_phase6_7_8.py
```

<br/>

---

## Environment Variables Reference

| Variable | Required | Description |
|:---|:---:|:---|
| `AGORA_APP_ID` | Yes | Your Agora project App ID |
| `AGORA_APP_CERTIFICATE` | Yes | Your Agora project App Certificate |
| `AGORA_REST_KEY` | Yes | Agora RESTful API key |
| `AGORA_REST_SECRET` | Yes | Agora RESTful API secret |
| `GROQ_API_KEY` | * | Groq LPU API key — primary low-latency provider |
| `GROQ_MODEL` | — | Model name (default: `llama-3.3-70b-versatile`) |
| `NVIDIA_NIM_API_KEY` | — | NVIDIA NIM API key — complex reasoning fallback |
| `NVIDIA_NIM_BASE_URL` | — | NIM endpoint (default: `https://integrate.api.nvidia.com/v1`) |
| `NVIDIA_NIM_MODEL` | — | NIM model (default: `meta/llama-3.1-70b-instruct`) |
| `PINECONE_API_KEY` | — | Optional — enables semantic vector RAG |
| `PINECONE_INDEX_NAME` | — | Pinecone index (default: `lively-rag`) |
| `BACKEND_PUBLIC_URL` | Auto | Auto-set by `run.bat` — your Cloudflare tunnel URL |
| `AGORA_AGENT_VOICE` | — | TTS voice (default: `en-US-JennyNeural`) |
| `DEBUG` | — | Enable debug logging (default: `true`) |

> * = At least one LLM provider key is required (Groq recommended).  
> Auto = Automatically managed by `run.bat`.

<br/>

---

## Future Works

- **ASR accuracy** may degrade in extremely noisy multi-speaker environments
- **Cold-start latency** of ~100–150ms on the very first turn (TLS handshake overhead)
- **RAG scope** is limited to indexed documents — unindexed queries are gracefully deflected
- **Tool integrations** use high-fidelity mock stores in dev mode (production OAuth is a one-line swap)
- **Language support** is English (en-US) in v1

<br/>

---

<div align="center">

**Built for the [Agora Conversational AI Hackathon](https://www.agora.io)**

Made by the Lively team

</div>
