# Lively — User Guide & Step-by-Step Usage Instructions

> **Real-time voice AI sales agent that listens, adapts, remembers customer context, and turns conversations into actionable sales outcomes.**  
> Powered by **Agora Conversational AI Engine** + **Custom LLM Brain (Groq & NVIDIA NIM)**.

---

## 1. Quick 1-Click Startup

If you are on Windows, you can start the entire stack with a single click:

### Option A: Standard 1-Click Launch (Recommended)
Double-click **`run.bat`** in the project root folder (or run in PowerShell / CMD):
```cmd
.\run.bat
```

### Option B: Separate Console Windows (For easy log monitoring)
Double-click **`run_separate.bat`**:
```cmd
.\run_separate.bat
```

### Option C: PowerShell Launcher
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_lively.ps1
```

> **What the launcher automatically does:**
> 1. Frees ports `8000` and `5173` if anything was running from a previous session.
> 2. Starts `cloudflared.exe` tunnel to make your local backend publicly reachable by Agora's cloud servers.
> 3. Automatically updates `BACKEND_PUBLIC_URL` in `.env` and `backend/.env`.
> 4. Starts the **FastAPI Backend** on `http://localhost:8000`.
> 5. Starts the **Vite React Frontend** on `http://localhost:5173`.
> 6. Automatically opens your default web browser to the Lively Sales Cockpit!

---

## 2. Prerequisites & Environment Setup

### Required Tools
- **Python 3.10+** (Added to PATH)
- **Node.js 18+** & npm

### Configuring `.env`
Ensure `.env` in the root directory contains your Agora and API credentials:

```env
# Agora App & REST API Credentials (Required for Voice & Conversational AI)
AGORA_APP_ID=your_agora_app_id
AGORA_APP_CERTIFICATE=your_agora_app_cert
AGORA_REST_KEY=your_agora_customer_key
AGORA_REST_SECRET=your_agora_customer_secret

# LLM Providers
GROQ_API_KEY=gsk_...                       # Primary low-latency voice turns (sub-200ms TTFT)
GROQ_MODEL=llama-3.3-70b-versatile
NVIDIA_NIM_API_KEY=nvapi-...               # Secondary / complex reasoning & failover
NVIDIA_NIM_MODEL=meta/llama-3.1-70b-instruct

# Application Secrets (generate each with: python -c "import secrets; print(secrets.token_urlsafe(32))")
LIVELY_LLM_SHARED_SECRET=<random>   # Agora presents this to /v1/chat/completions
SESSION_SECRET=<random>             # signs per-visitor session tokens

# Server Port
HOST=0.0.0.0
PORT=8000
BACKEND_PUBLIC_URL=http://localhost:8000   # Auto-updated by launcher with Cloudflare URL
```

---

## 3. Manual Startup (If Running Components Separately)

If you prefer to start each service manually in separate terminal tabs:

### Terminal 1: Cloudflare Tunnel (Required for Agora webhook callbacks)
```powershell
.\cloudflared.exe tunnel --url http://localhost:8000
```
*Copy the `https://<random>.trycloudflare.com` URL and paste it into `BACKEND_PUBLIC_URL=` in `.env` and `backend/.env`.*

### Terminal 2: FastAPI Backend
```powershell
cd backend
$env:PYTHONPATH="."
py -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
*Health check URL: `http://localhost:8000/health`*

### Terminal 3: React Sales Cockpit Frontend
```powershell
cd frontend
npm run dev
```
*Open `http://localhost:5173` in your browser.*

---

## 4. How to Use the Lively Sales Cockpit

Once the web app opens at **`http://localhost:5173`**, you will see the full real-time sales intelligence cockpit:

```text
┌───────────────────────────────────────────────────────────────────────────┐
│  LIVELY SALES COCKPIT        [Latency: 142ms]  [Agora: Connected]  [📚 Docs]│
├───────────────────────────────────────────────────────────────────────────┤
│  [ OUTCOME ACHIEVED BANNER: Demo Booked / Lead Qualified / Escalated ]    │
├───────────────────────────────────────────────────────────────────────────┤
│  VOICE HUD: Channel: [lively-sales-room] [🎤 Start Call] [🔇 Mute] [Wave] │
├───────────────────────────────────────────────────────────────────────────┤
│  TABS: [1. Live Sales Cockpit] [2. Scripted Demo Harness] [3. Telemetry]  │
├───────────────────────────────────────────────────────────────────────────┤
│  PIPELINE PROGRESSION: Discovery ➔ BANT Qual ➔ Objections ➔ Demo Book     │
│  BANT SCORECARD: Users: 80 | Budget: $100k ARR | Authority: VP Product    │
├─────────────────────────────────────┬─────────────────────────────────────┤
│  LIVE DIARIZED TRANSCRIPT           │  REAL-TIME OBJECTION BATTLECARDS    │
│  👤 Buyer: How much does it cost?   │  ⚠️ Pricing Objection Detected      │
│  🤖 Lively: Starter is $199/mo...   │  💡 Rebuttal: Highlight 50% TCO ROI │
├─────────────────────────────────────┴─────────────────────────────────────┤
│  ACTION ITEMS & CRM SYNC: Lead Created (Acme) | Demo Booked (Tomorrow 2pm)│
└───────────────────────────────────────────────────────────────────────────┘
```

---

### Feature 1: Live Voice Call (Agora RTC Audio)
1. In the **Voice Call HUD** at the top, verify the Channel Name (default: `lively-sales-room`).
2. Click **"Start Voice Session"** (green button).
3. Allow browser microphone access when prompted.
4. Speak into your microphone!
   - Agora's Conversational AI engine performs real-time Voice Activity Detection (VAD) and Speech-to-Text.
   - It streams your utterance to our backend's `/v1/chat/completions`.
   - Lively generates an intelligent sales response using Groq / NVIDIA NIM, streaming audio back via ElevenLabs / Azure TTS over Agora RTC with **natural barge-in capability** (you can interrupt Lively mid-sentence at any time).
5. Click **"Mute Mic"** to temporarily pause audio capture, or **"End Call"** to stop the session.

---

### Feature 2: 4-Step Scripted Demo Scenario (Hackathon Flow)
Click the **"Scripted Demo Harness (Hackathon Flow)"** tab in the UI to run the step-by-step evaluation scenario:

1. **Step 1: Pricing Inquiry**
   - Click **"Play Step 1"**
   - *Prompt*: `"Hi, we are evaluating real-time voice AI. How much does Lively cost?"`
   - *Outcome*: Lively retrieves pricing sheets from RAG and quotes the $199 Starter and $699 Growth tiers with 40–60% TCO savings.
2. **Step 2: Competitor Interruption & Objection Handling**
   - Click **"Play Step 2"**
   - *Prompt*: `"Wait, how do you compare to OpenAI Realtime and Twilio?"`
   - *Outcome*: Lively triggers the competitor battlecard, explaining Agora SD-RTN sub-300ms transport and custom LLM sovereignty. The Objection Battlecard updates to *Resolved*.
3. **Step 3: User Scale Change (Memory & Diffing)**
   - Click **"Play Step 3"**
   - *Prompt*: `"Actually our sales team just expanded to 80 users today and our budget is $100k ARR. I'm the VP of Product."`
   - *Outcome*: Deal State updates `users` from 10 &rarr; 80, `budget` to $100k ARR, and `authority` to VP Product without losing previous conversational context.
4. **Step 4: Book Enterprise Demo (Autonomous Tool Calling)**
   - Click **"Play Step 4"**
   - *Prompt*: `"Can we schedule a 30-minute deep-dive demo tomorrow at 2:00 PM EST for our engineers?"`
   - *Outcome*: Lively emits the `chat.completion.custom_metadata` filler phrase, executes the `book_meeting` tool, and renders the **Outcome Achieved: Live Demo Booked Banner** with the calendar reservation!

---

### Feature 3: Real-Time Telemetry & Latency Dashboard
Click the **"Telemetry & Latency Observability"** tab:
- **TTFT (p50 / p95)**: Real-time Time-To-First-Token latency metrics in milliseconds.
- **Model Breakdown**: Distribution between Groq LPU turns, NVIDIA NIM reasoning turns, and built-in sales fallback.
- **Memory Diff Audit Log**: Full chronological history of extracted deal entities (e.g. `User scale changed from 20 -> 80 seats`).

---

### Feature 4: Knowledge Base / RAG Battlecards
- Click the **"Knowledge Base"** book icon in the top navigation bar.
- Inspect the embedded knowledge base documents, pricing tiers, security FAQ (HIPAA / SOC2), and competitor battlecards loaded in the vector store.

---

## 5. Troubleshooting & FAQ

### Q1: "Agora REST credentials not configured" or simulated agent warning?
- Ensure `AGORA_APP_ID`, `AGORA_APP_CERTIFICATE`, `AGORA_REST_KEY`, and `AGORA_REST_SECRET` are correctly filled in `.env`.
- Note: You must enable **Conversational AI Engine** in your Agora Console project settings.

### Q2: Port 8000 or 5173 is already in use?
- `run.bat` automatically calls `free_ports.py` to terminate stale background processes.
- You can also run: `python scripts/free_ports.py`

### Q3: Why does Agora need a public tunnel URL?
- Agora's cloud servers call our backend's `/v1/chat/completions` endpoint via HTTP POST. A public URL (provided automatically by Cloudflare tunnel) is required so Agora can reach your local machine.

---

## 6. Automated Verification Tests

To verify backend intelligence, Deal State memory, RAG retrieval, and tool execution without running the UI:

```powershell
$env:PYTHONPATH="backend"
py backend/tests/test_phase6_7_8.py
```

All tests will run and validate the complete end-to-end intelligence engine.
