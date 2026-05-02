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

## Step 1 — Install basics

You need:

- Python (3.10+)
- Node (for UI, optional)
- Ollama (for local AI)

Install Ollama:
https://ollama.com

Then run:

```bash
ollama pull llama3.2:3b
```

---

## Step 2 — Start Ollama

```bash
ollama serve
```

Leave this running.

---

## Step 3 — Start UAR

From the project folder:

```bash
make up
```

You should see a server start on:

```text
http://127.0.0.1:8000
```

---

## Step 4 — Run your first task

Open a new terminal and run:

```bash
curl http://localhost:8000/api/uar/run \
  -H "Content-Type: application/json" \
  -d '{"goal":"Explain gravity simply","skills":["ollama_generate"]}'
```

---

## What just happened

- You gave the system a goal
- It used a skill (ollama_generate)
- It called your local AI (Ollama)
- It returned a response

---

## Step 5 — (Optional) UI

```bash
make up-full
```

Open browser:

http://localhost:5173

---

## Mental model

You don’t need to understand the code.

Just know:

- Goal → what you want
- Skills → how it does it
- Output → result

---

## Common issues

### Nothing happens

Check:

```bash
ollama serve
```

### Error about model

Run:

```bash
ollama pull llama3.2:3b
```

---

## That’s it

If you can run one goal successfully, you’re onboarded.

Everything else is just expansion.
