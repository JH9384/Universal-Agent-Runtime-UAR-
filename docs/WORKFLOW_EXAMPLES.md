# Common Workflow Examples

This guide provides copy-paste examples for common UAR workflows.

For a user-focused cookbook with visualization, metrics, recipe timeline,
and UOR workflow examples, see [User Examples and Common Needs](USER_EXAMPLES.md).

## Quick Start Examples

### 1. Analyze a Codebase
**Use case**: Understand the structure and dependencies of a Python project

**Goal**: "Analyze the codebase structure and dependencies"
**Skills**: `doc_ingest`, `dependency_map`, `sum_review`

**Expected output**: Dependency graph showing file relationships and a summary

---

### 2. Review Documentation with AI
**Use case**: Get an AI-powered review of your documentation

**Goal**: "Review the documentation and identify gaps"
**Skills**: `doc_ingest`, `ollama_generate`

**Expected output**: AI-generated analysis of documentation quality and completeness

---

### 3. Build Knowledge Graph
**Use case**: Create a searchable knowledge graph for a document set

**Goal**: "Index all documentation for semantic search"
**Skills**: `graphrag_index`

**Expected output**: GraphRAG knowledge graph (slow, one-time operation)

**Note**: After indexing, use `graphrag_query` to search

---

### 4. Query Knowledge Graph
**Use case**: Ask questions about indexed documents

**Goal**: "What are the main themes in the documentation?"
**Skills**: `graphrag_query`

**Metadata**: `graphrag_method=local` (or `global` for thematic analysis)

**Expected output**: Relevant document excerpts with sources

---

### 5. Full Pipeline: Index and Query
**Use case**: Build a knowledge graph and immediately query it

**Goal**: "Index the codebase and find all references to authentication"
**Skills**: `graphrag_index`, `graphrag_query`

**Expected output**: Complete indexing followed by query results

**Note**: This is very slow for large codebases

---

## Advanced Workflows

### 6. Backup to Decentralized Storage
**Use case**: Permanently store important files on Autonomi

**Goal**: "Backup the source code to Autonomi"
**Skills**: `autonomi_upload`

**Expected output**: Autonomi address for retrieving files later

**Prerequisites**: Autonomi package installed, wallet configured

---

### 7. Retrieve from Decentralized Storage
**Use case**: Download files previously stored on Autonomi

**Goal**: "Download backup from Autonomi"
**Skills**: `autonomi_download`

**Metadata**: `autonomi_address=<your-address>`

**Expected output**: Downloaded files to local system

---

### 8. Analyze Formal Grammar
**Use case**: Verify a BNF grammar specification is correct

**Goal**: "Analyze this grammar for correctness"
**Skills**: `alm_analyze`

**Input**: Grammar specification in goal or via doc_ingest

**Expected output**: Analysis results with status

**Prerequisites**: ALM service running

---

## API Examples

### Using cURL

**Basic run**:
```bash
curl http://localhost:8000/api/uar/run \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Summarize the project",
    "skills": ["doc_ingest", "section_sum"],
    "input_path": "./docs"
  }'
```

**With streaming events**:
```bash
curl http://localhost:8000/api/uar/stream \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Analyze code structure",
    "skills": ["doc_ingest", "dependency_map"],
    "input_path": "./src"
  }'
```

**With GraphRAG query**:
```bash
curl http://localhost:8000/api/uar/run \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "What are the main components?",
    "skills": ["graphrag_query"],
    "metadata": {"graphrag_method": "local"}
  }'
```

### Using Python

```python
import requests

# Basic run
response = requests.post('http://localhost:8000/api/uar/run', json={
    'goal': 'Summarize the project',
    'skills': ['doc_ingest', 'section_sum'],
    'input_path': './docs'
})

print(response.json())

# Streaming
response = requests.post('http://localhost:8000/api/uar/stream', json={
    'goal': 'Analyze code structure',
    'skills': ['doc_ingest', 'dependency_map'],
    'input_path': './src'
}, stream=True)

for line in response.iter_lines():
    if line.startswith(b'data: '):
        event = json.loads(line.decode()[6:])
        print(event)
```

## Web UI Recipes

The web UI includes pre-configured recipes for common workflows:

1. **🦙 Ollama review** - Quick LLM review of library docs
   - Skills: `doc_ingest`, `ollama_generate`

2. **🕸️ Dep map** - Build a dependency graph
   - Skills: `doc_ingest`, `dependency_map`, `sum_review`

3. **📚 GraphRAG index** - Build the knowledge graph (slow, one-time)
   - Skills: `graphrag_index`

4. **🔎 GraphRAG query** - Query an existing graph
   - Skills: `graphrag_query`

5. **⚡ Full pipeline** - Index then query (very slow)
   - Skills: `graphrag_index`, `graphrag_query`

6. **☁️ Autonomi upload** - Upload current input_path to Autonomi
   - Skills: `autonomi_upload`

7. **☁️ Autonomi download** - Download from Autonomi address
   - Skills: `autonomi_download`

8. **☁️ Autonomi status** - Check Autonomi connectivity
   - Skills: `autonomi_status`

## Tips for Success

### Start Simple
- Begin with `doc_ingest` + `section_sum` to understand your data
- Progress to `dependency_map` for code analysis
- Add AI features (`ollama_generate`) when you need insights

### Understand Skill Prerequisites
- `dependency_map` requires `doc_ingest` results
- `graphrag_query` requires `graphrag_index` to run first
- `ollama_generate` benefits from `doc_ingest` for context

### Use the Web UI for Exploration
- The file picker helps you safely select directories
- Recipes provide one-click workflows
- Real-time event streaming shows progress

### Optimize for Your Use Case
- For quick analysis: Use `doc_ingest` + `ollama_generate`
- For code understanding: Use `doc_ingest` + `dependency_map`
- For semantic search: Use `graphrag_index` + `graphrag_query`
- For permanent storage: Use Autonomi skills

### Troubleshooting
- Check the [Error Guide](ERROR_GUIDE.md) for common issues
- Use `python scripts/validate_config.py` to check configuration
- View the Skill Guide in the web UI for skill details
