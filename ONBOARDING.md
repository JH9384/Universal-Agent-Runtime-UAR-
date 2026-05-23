# UAR Onboarding Guide (Zero to Running)

## Who this is for

Someone who:
- has never seen this system
- may not be technical
- just wants to run it and see something happen

---

## What this system is (simple)

UAR is **two things at once**:

**Agent Runtime**: Give it a goal → it picks skills → executes → streams results back.

**Scientific Sandbox**: No toolchains to install. Send a JSON goal, get 3D molecular coordinates, quantum circuit layouts, RISC-V emulation traces, or Verilog testbenches back.

Think of it like:
"I send a JSON goal → it runs computation or AI tools → I get structured, reproducible results."

---

## Choose Your Setup Path

Pick the setup that matches your needs:

### 🚀 Quick Start — STEM Sandbox (5 minutes)
**Best for**: Try quantum circuits, molecular models, RISC-V emulation
- Python 3.10+ only
- No external dependencies
- 30+ STEM skills work out of the box

### ⚡ Standard Setup — Agent + AI (10 minutes)
**Best for**: Document processing, local AI, knowledge graphs
- Python 3.10+
- Ollama (for AI features)
- Core skills + AI generation

### 🎯 Full Setup — Everything (15 minutes)
**Best for**: Complete feature set with web UI
- Python 3.10+
- Node.js 18+ (for web UI)
- Ollama (for AI)
- All 124 skills + web interface

---

## 🚀 Quick Start (Minimal)

### Step 1 — Install Python

You need Python 3.10 or newer.

Check your version:

```bash
python --version
```

### Step 2 — Setup Configuration

Copy the minimal configuration:

```bash
cp .env.minimal .env
```

### Step 3 — Start UAR

From the project folder:

```bash
make up
```

You should see a server start on:

```text
http://127.0.0.1:8000
```

### Step 4 — Run Your First Task

Open a new terminal and run:

```bash
curl http://localhost:8000/api/uar/run \
  -H "Content-Type: application/json" \
  -d '{"goal":"Summarize this project","skills":["doc_ingest","section_sum"]}'
```

**What just happened:**
- You gave the system a goal
- It used skills to read files and summarize
- It returned a response

### Try a STEM skill (no extra setup)

```bash
curl http://localhost:8000/api/uar/run \
  -H "Content-Type: application/json" \
  -d '{"goal":"Visualize a water molecule","skills":["molecular_visualization"],"metadata":{"molecule":"water"}}'
```

**What just happened:**
- You asked for a molecular visualization
- It returned 3D atomic coordinates, bond topology, and centered positions
- No RDKit, no PyMOL, no Jupyter — just a JSON request and a structured response

That's it! You're running UAR with minimal setup.

---

## ⚡ Standard Setup (with Ollama AI)

### Step 1 — Install Ollama

Download from: https://ollama.com

Then pull a model:

```bash
ollama pull llama3.2:3b
```

### Step 2 — Start Ollama

```bash
ollama serve
```

Leave this running.

### Step 3 — Setup Configuration

Copy the minimal configuration:

```bash
cp .env.minimal .env
```

Add Ollama settings to `.env`:

```bash
echo "OLLAMA_HOST=http://127.0.0.1:11434" >> .env
echo "OLLAMA_MODEL=llama3.2:3b" >> .env
```

### Step 4 — Start UAR

```bash
make up
```

### Step 5 — Run AI-Powered Task

```bash
curl http://localhost:8000/api/uar/run \
  -H "Content-Type: application/json" \
  -d '{"goal":"Explain gravity simply","skills":["ollama_generate"]}'
```

**What just happened:**
- You gave the system a goal
- It used Ollama to generate an AI response
- It returned the answer

---

## 🎯 Full Setup (with Web UI)

### Step 1 — Install Node.js

You need Node.js 18+ for the web interface.

Check: `node --version`

### Step 2 — Install Ollama (for AI)

Download from: https://ollama.com

```bash
ollama pull llama3.2:3b
ollama serve
```

### Step 3 — Setup Configuration

```bash
cp .env.minimal .env
echo "OLLAMA_HOST=http://127.0.0.1:11434" >> .env
echo "OLLAMA_MODEL=llama3.2:3b" >> .env
```

### Step 4 — Start Everything

```bash
make up-full
```

This starts both the API server and web UI.

### Step 5 — Open Web Interface

Open your browser to:

```text
http://localhost:5173
```

You'll see:
- File picker for documents
- Skill selector with 124 skills across 9 categories
- 10 pre-configured recipes (drag-and-drop with skills)
- Real-time event streaming with per-skill timing

---

## Mental Model

You don't need to understand the code.

Just know:

- **Goal** → what you want
- **Skills** → how it does it
- **Output** → result

And one more thing — every run is **observable**:

- The WebSocket stream tells you exactly when each skill starts and completes
- Per-skill timing appears in the metrics panel
- The full event log is saved to disk — you can replay any run later
- Recipes (bundles of skills) show up as nested blocks with their own timing

This means you can debug a slow run by looking at which skill took time, or replay a failed run by reading its event log. Nothing is a black box.

---

## Common Issues

### Nothing happens

Check the server is running:

```bash
curl http://localhost:8000/api/health
```

### Error about model

Run:

```bash
ollama pull llama3.2:3b
```

### Configuration errors

Validate your setup:

```bash
python scripts/validate_config.py
```

This will check your `.env` file and provide helpful guidance.

### Want more features?

See `.env.example` for all optional features:
- GraphRAG (knowledge graphs)
- Autonomi (decentralized storage)
- ALM (formal language analysis)

---

## That's It

If you can run one goal successfully, you're onboarded.

Everything else is just expansion.

**Next steps:**
- Try different skills
- Explore the web UI recipes
- Add optional features from `.env.example`
