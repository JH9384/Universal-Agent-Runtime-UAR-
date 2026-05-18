# UAR Onboarding Guide (Zero to Running)

## Who this is for

Someone who:
- has never seen this system
- may not be technical
- just wants to run it and see something happen

---

## What this system is (simple)

UAR = a system that:
- takes a goal
- runs steps (skills)
- produces results

Think of it like:
"I give it a task → it runs tools → I get an answer"

---

## Choose Your Setup Path

Pick the setup that matches your needs:

### 🚀 Quick Start (5 minutes)
**Best for**: Try it out, minimal features
- Python 3.10+ only
- No external dependencies
- Core skills only (no AI, no GraphRAG)

### ⚡ Standard Setup (10 minutes)
**Best for**: Full experience, local AI
- Python 3.10+
- Ollama (for AI features)
- All core skills + AI generation

### 🎯 Full Setup (15 minutes)
**Best for**: Complete feature set
- Python 3.10+
- Node.js 18+ (for web UI)
- Ollama (for AI)
- All 14 skills + web interface

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
- Skill selector with 14 skills
- Pre-configured recipes
- Real-time event streaming

---

## Mental Model

You don't need to understand the code.

Just know:

- **Goal** → what you want
- **Skills** → how it does it
- **Output** → result

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
