# Vibe Coding Repositories — Curated for UAR

A curated list of GitHub repositories that embody the "vibe coding" philosophy
popularized by Andrej Karpathy: describe what you want in natural language,
let AI handle the implementation details.

## Karpathy's Own Repositories

### 1. karpathy/autoresearch
- **URL**: https://github.com/karpathy/autoresearch
- **Description**: AI agents running research on single-GPU nanochat training automatically.
- **Vibe coding angle**: Agents iterate on code autonomously — the "code" becomes a self-modifying binary.
- **Stars**: ~2.5k
- **License**: MIT
- **UAR relevance**: Could be integrated as a `research_loop` skill that autonomously runs experiments.

### 2. karpathy/llm-council
- **URL**: https://github.com/karpathy/llm-council
- **Description**: LLM Council — multiple models debate and compile a final answer.
- **Vibe coding angle**: 99% vibe coded in a single Saturday hack.
- **Stars**: ~3k
- **License**: MIT
- **UAR relevance**: Could become a `llm_council` skill for multi-model consensus in UAR pipelines.

### 3. karpathy/llm.c
- **URL**: https://github.com/karpathy/llm.c
- **Description**: LLM training in simple, raw C/CUDA (~1000 lines).
- **Vibe coding angle**: Educational minimalism — "vibe" understanding of how LLMs work under the hood.
- **Stars**: ~25k
- **License**: MIT
- **UAR relevance**: Could be a `train_gpt2` skill for custom model training from scratch.

---

## Top Vibe Coding Tools (Open Source)

### 4. openai/codex
- **URL**: https://github.com/openai/codex
- **Description**: Lightweight coding agent that runs in your terminal.
- **Vibe coding angle**: CLI tool where you describe features and it edits files directly.
- **Stars**: ~10k+
- **License**: Apache 2.0
- **UAR relevance**: Could integrate as a `codex_agent` skill for automated code generation.

### 5. Aider-AI/aider
- **URL**: https://github.com/Aider-AI/aider
- **Description**: AI pair programming in your terminal — edits files in git repos.
- **Vibe coding angle**: Best for existing codebases; uses repo maps for context.
- **Stars**: ~25k
- **License**: Apache 2.0
- **UAR relevance**: Ideal for UAR's `code_analysis` skill chain — aider could be the execution engine.

### 6. filipecalegario/awesome-vibe-coding
- **URL**: https://github.com/filipecalegario/awesome-vibe-coding
- **Description**: Curated list of vibe coding resources, tools, and techniques.
- **Vibe coding angle**: The definitive index of everything vibe coding.
- **Stars**: ~5k
- **License**: CC0
- **UAR relevance**: Reference material for expanding UAR's coding agent capabilities.

### 7. taskade/awesome-vibe-coding
- **URL**: https://github.com/taskade/awesome-vibe-coding
- **Description**: Complete guide to vibe coding with tools, prompts, and workflows.
- **Vibe coding angle**: Strategic blueprint for 2026.
- **Stars**: ~3k
- **License**: MIT
- **UAR relevance**: Prompt engineering patterns for UAR's natural language goal parser.

---

## Claude Code & Agent Ecosystem

### 8. alirezarezvani/claude-skills
- **URL**: https://github.com/alirezarezvani/claude-skills
- **Description**: 337 Claude Code skills, agent skills, and plugins.
- **Vibe coding angle**: Pre-built skills for engineering, marketing, product, compliance.
- **Stars**: ~1k
- **License**: MIT
- **UAR relevance**: Could adapt skill definitions to UAR's `execution_order` format.

### 9. wjgoarxiv/autoresearch-skill
- **URL**: https://github.com/wjgoarxiv/autoresearch-skill
- **Description**: Autonomous research loop inspired by Karpathy's autoresearch.
- **Vibe coding angle**: Natural-language research goals → autonomous experiment loops.
- **Stars**: ~200
- **License**: MIT
- **UAR relevance**: Directly pluggable as a UAR recipe skill.

### 10. bradAGI/awesome-cli-coding-agents
- **URL**: https://github.com/bradAGI/awesome-cli-coding-agents
- **Description**: Curated directory of CLI coding agents (Claude Code, Codex, Aider, etc.).
- **Vibe coding angle**: Comparative analysis of all major coding agents.
- **Stars**: ~500
- **License**: MIT
- **UAR relevance**: Benchmarking reference for UAR's agent framework.

---

## Integration Ideas for UAR

```python
# Potential new UAR skills based on these repos:

@vibe_coding_skill("codex_agent")
def codex_agent(ctx: PipelineContext) -> dict:
    """Use OpenAI Codex CLI to implement features from natural language."""
    ...

@vibe_coding_skill("aider_pair")
def aider_pair(ctx: PipelineContext) -> dict:
    """Pair program with Aider in a git repo context."""
    ...

@vibe_coding_skill("llm_council")
def llm_council(ctx: PipelineContext) -> dict:
    """Query multiple LLMs and synthesize consensus (Karpathy pattern)."""
    ...

@vibe_coding_skill("autoresearch")
def autoresearch(ctx: PipelineContext) -> dict:
    """Run autonomous research loops with experiment-evaluate-iterate."""
    ...
```

---

## Karpathy's Vibe Coding Philosophy (Summary)

From his X posts and talks:

1. **Don't write code, describe it** — Use natural language to specify intent
2. **Let the AI handle implementation** — Trust the model to generate working code
3. **Iterate in conversation** — Chat with the agent, don't edit files manually
4. **Review, don't write** — Human role shifts from author to editor/verifier
5. **Use the right tool** — Cursor for IDE, Claude Code for terminal, Aider for git repos

> "I just vibe coded an entire feature in 20 minutes. I didn't write a single line of code myself." — Andrej Karpathy
