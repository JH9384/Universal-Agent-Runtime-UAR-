from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "apps" / "api-python" / "main.py"

IMPORT = "from run_memory import query_runs, summarize_runtime_success\n"
ENDPOINT = '''

@app.get("/memory/query")
def memory_query(goal: str | None = None, runtime: str | None = None, limit: int = 50):
    return query_runs(goal=goal, chosen_runtime=runtime, limit=limit)

@app.get("/memory/summary")
def memory_summary(goal: str | None = None):
    return summarize_runtime_success(goal=goal)
'''

text = MAIN.read_text()

if IMPORT not in text:
    text = text.replace("from fastapi import FastAPI, HTTPException\n", "from fastapi import FastAPI, HTTPException\n" + IMPORT)

if "/memory/query" not in text:
    text += ENDPOINT

MAIN.write_text(text)
print("Memory endpoints wired safely")
