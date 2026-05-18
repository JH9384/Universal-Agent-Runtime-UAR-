# Advanced Frameworks Integration

This document describes the advanced AI frameworks and libraries that have been integrated into the Universal Agent Runtime (UAR) system.

## Overview

The UAR system has been enhanced with comprehensive integrations from the following open-source frameworks:

- **Microsoft Agent Framework** (AutoGen + Semantic Kernel)
- **Unstructured** - Advanced document processing
- **CrewAI** - Role-based multi-agent patterns
- **LlamaIndex** - Advanced RAG capabilities
- **Dagster** - Pipeline orchestration
- **Docling** - Advanced PDF understanding
- **Network-AI** - Guardrails and governance
- **Flexible GraphRAG** - Knowledge graph RAG

## Integration Details

### 1. Microsoft Agent Framework

**File:** `uar/core/agent_framework.py`

**Features:**
- Agent-to-agent (A2A) communication protocol
- Message passing between agents
- Agent lifecycle management
- Multi-provider model support
- Cross-runtime interoperability via MCP

**Key Classes:**
- `Agent` - Base agent with message handling
- `AgentOrchestrator` - Orchestrates multi-agent workflows
- `AgentMessage` - Message structure for agent communication
- `AutoGenAdapter` - Adapter for AutoGen agents

**Usage Example:**
```python
from uar.core.agent_framework import Agent, AgentOrchestrator, execute_agent_workflow

orchestrator = AgentOrchestrator()
agent = Agent(agent_id="my_agent", name="My Agent")
orchestrator.register_agent(agent)

result = execute_agent_workflow(
    workflow_id="my_workflow",
    agent_sequence=["agent1", "agent2"],
    initial_message="Start processing"
)
```

### 2. Unstructured Document Processing

**File:** `uar/skills/doc_ingest_enhanced.py`

**Features:**
- Advanced document parsing for PDF, DOCX, images, tables
- Multiple processing strategies (Unstructured, Docling, fallback)
- Structured element extraction
- Fallback mechanisms for robustness

**Processing Strategies:**
- `UNSTRUCTURED` - Use Unstructured library for parsing
- `DOCLING` - Use Docling for advanced PDF understanding
- `FALLBACK` - Use basic parsing as fallback

**Usage Example:**
```python
from uar.skills.doc_ingest_enhanced import doc_ingest_enhanced

result = doc_ingest_enhanced(ctx)
# Returns documents with structured elements, metadata, and processing stats
```

### 3. CrewAI Role-Based Multi-Agent Patterns

**File:** `uar/core/crewai_integration.py`

**Features:**
- Role-based agent design (researcher, analyst, writer, etc.)
- Task delegation and collaboration patterns
- Hierarchical task execution
- Agent specialization patterns

**Predefined Roles:**
- `RESEARCHER` - Researches and gathers information
- `ANALYST` - Analyzes data and provides insights
- `WRITER` - Writes and edits content
- `REVIEWER` - Reviews and validates work
- `CODER` - Writes and reviews code
- `PLANNER` - Plans and organizes work
- `EXECUTOR` - Executes tasks efficiently
- `COORDINATOR` - Coordinates work between agents

**Usage Example:**
```python
from uar.core.crewai_integration import (
    TaskOrchestrator,
    create_standard_agent,
    execute_standard_workflow
)

orchestrator = TaskOrchestrator()
agent = create_standard_agent(role=AgentRole.RESEARCHER)
orchestrator.register_agent(agent)

result = execute_standard_workflow(
    workflow_type="research_analyze_write",
    input_data={"topic": "AI research"}
)
```

### 4. LlamaIndex Advanced RAG

**File:** `uar/core/llamaindex_rag.py`

**Features:**
- Hierarchical chunking and indexing
- Knowledge graph RAG query engine
- Query-focused summarization (QFS)
- Advanced retrieval strategies (hybrid, reranking, fusion)
- Multiple vector database backends

**Retrieval Strategies:**
- `VECTOR` - Vector similarity search
- `BM25` - Keyword-based search
- `HYBRID` - Combined vector and keyword search
- `AUTO_MERGING` - Hierarchical context merging
- `KNOWLEDGE_GRAPH` - Knowledge graph-based retrieval

**Usage Example:**
```python
from uar.core.llamaindex_rag import (
    LlamaIndexRAG,
    RAGConfig,
    ChunkingStrategy,
    RetrievalStrategy
)

config = RAGConfig(
    chunking_strategy=ChunkingStrategy.HIERARCHICAL,
    retrieval_strategy=RetrievalStrategy.HYBRID,
)

rag = LlamaIndexRAG(config)
rag.load_documents(input_path="./docs")
rag.create_index()

result = rag.query("What is the main topic?")
```

### 5. Dagster Pipeline Orchestration

**File:** `uar/core/dagster_orchestration.py`

**Features:**
- Declarative programming model for data pipelines
- Asset-based orchestration (track data dependencies)
- Type-safe pipeline definitions
- Built-in observability and monitoring
- Job scheduling and backfilling

**Asset Types:**
- `DOCUMENT` - Raw ingested documents
- `VECTOR_INDEX` - Vector embeddings index
- `KNOWLEDGE_GRAPH` - Knowledge graph from documents
- `RAG_RESULT` - RAG query results
- `AGENT_OUTPUT` - Agent execution outputs

**Usage Example:**
```python
from uar.core.dagster_orchestration import (
    UARPipelineOrchestrator,
    AssetType,
    create_standard_pipelines
)

orchestrator = UARPipelineOrchestrator()
create_standard_pipelines()

execution = orchestrator.execute_pipeline("rag_pipeline")
```

### 6. Network-AI Guardrails and Governance

**File:** `uar/core/guardrails.py`

**Features:**
- Shared blackboard with atomic propose → validate → commit
- Guardrails for agent behavior
- Budget and resource limits
- Safety checks and validation
- Governance policies

**Guardrail Types:**
- `CONTENT_SAFETY` - Content safety checks
- `RATE_LIMIT` - Rate limiting
- `BUDGET` - Budget enforcement
- `PERMISSION` - Permission checks
- `COMPLIANCE` - Compliance validation
- `OUTPUT_VALIDATION` - Output validation

**Usage Example:**
```python
from uar.core.guardrails import (
    GovernanceSystem,
    setup_default_guardrails
)

governance = GovernanceSystem()
setup_default_guardrails()

# Create budget for an agent
governance.create_budget(
    agent_id="my_agent",
    max_tokens=100000,
    max_cost_usd=10.0
)

# Check guardrails
violations = governance.guardrails.check(
    agent_id="my_agent",
    guardrail_type=GuardrailType.CONTENT_SAFETY,
    data="content to check"
)
```

### 7. Flexible GraphRAG

**File:** `uar/core/flexible_graphrag.py`

**Features:**
- Knowledge graph auto-building from documents
- Ontology and schema support
- Multiple LLM provider support
- Hybrid semantic search (fulltext, vector, property graph, RDF/SPARQL)
- AI query capabilities
- Flexible backend support (Neo4j, Memgraph, etc.)

**Graph Backends:**
- `NEO4J` - Neo4j graph database
- `MEMGRAPH` - Memgraph graph database
- `RDF` - RDF triple store
- `IN_MEMORY` - In-memory graph

**Search Strategies:**
- `VECTOR` - Vector similarity search
- `FULLTEXT` - Fulltext matching
- `PROPERTY_GRAPH` - Property graph queries
- `RDF_SPARQL` - RDF/SPARQL queries
- `HYBRID` - Combined search strategies

**Usage Example:**
```python
from uar.core.flexible_graphrag import (
    FlexibleGraphRAG,
    GraphBackend,
    SearchStrategy,
    create_standard_ontology
)

ontology = create_standard_ontology()
graphrag = FlexibleGraphRAG(
    backend=GraphBackend.IN_MEMORY,
    ontology=ontology
)

# Build graph from documents
graphrag.build_graph_from_documents(documents)

# Query the graph
result = graphrag.query_graph(
    query="Python programming",
    strategy=SearchStrategy.HYBRID
)
```

## UI/UX Updates

The UAR Panel UI has been updated with new skill groups:

- **Multi-Agent** - Agent workflow and CrewAI patterns
- **Advanced RAG** - LlamaIndex RAG capabilities
- **Pipeline Orchestration** - Dagster pipelines
- **Governance** - Guardrails and budget management
- **Enhanced Document Processing** - Unstructured and Docling

## Dependencies

All new dependencies have been added to `pyproject.toml`:

```toml
dependencies = [
    # Document Processing
    "unstructured[local-inference]",
    "docling",
    
    # Agent Frameworks
    "autogen>=0.4",
    "crewai>=0.80",
    
    # RAG
    "llama-index>=0.10",
    "llama-index-graph-stores-neo4j",
    
    # Pipeline Orchestration
    "dagster>=1.7",
    "dagster-webserver",
    
    # Knowledge Graph
    "neo4j>=5.0",
    
    # Vector Databases
    "chromadb",
    "qdrant-client",
    
    # Utilities
    "tenacity",
    "rich",
    "typer",
]
```

## Testing

Comprehensive tests have been added for all new integrations:

- `tests/test_agent_framework.py` - Microsoft Agent Framework tests
- `tests/test_guardrails.py` - Guardrails and governance tests
- `tests/test_flexible_graphrag.py` - Flexible GraphRAG tests
- `tests/test_crewai_integration.py` - CrewAI integration tests

## Installation

To use the new integrations, install the required dependencies:

```bash
pip install -e ".[graphrag,advanced]"
```

Or install specific packages:

```bash
pip install unstructured[local-inference] docling
pip install autogen crewai
pip install llama-index llama-index-graph-stores-neo4j
pip install dagster dagster-webserver
pip install neo4j chromadb qdrant-client
```

## Configuration

### Environment Variables

Add the following to your `.env` file as needed:

```bash
# Neo4j (for Flexible GraphRAG)
NEO4J_CONNECTION_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password

# OpenAI (for LlamaIndex embeddings)
OPENAI_API_KEY=your_api_key

# Agent budgets (default values can be overridden)
DEFAULT_MAX_TOKENS=100000
DEFAULT_MAX_API_CALLS=1000
DEFAULT_MAX_COST_USD=10.0
```

## Best Practices

### Multi-Agent Workflows

1. **Define clear roles** - Use predefined roles or create custom ones
2. **Set appropriate budgets** - Prevent runaway agent execution
3. **Use guardrails** - Ensure agent outputs are safe and compliant
4. **Monitor violations** - Track guardrail violations for debugging

### Document Processing

1. **Choose appropriate strategy** - Use Unstructured for general docs, Docling for PDFs
2. **Set size limits** - Prevent resource exhaustion
3. **Handle errors gracefully** - Use fallback mechanisms
4. **Validate outputs** - Check for proper extraction

### RAG Systems

1. **Use hierarchical chunking** - Better for large documents
2. **Enable hybrid search** - Combines vector and keyword search
3. **Configure chunk size** - Balance between context and precision
4. **Monitor retrieval quality** - Track confidence scores

### Pipeline Orchestration

1. **Define assets clearly** - Track data dependencies
2. **Use standard pipelines** - Leverage pre-defined patterns
3. **Monitor execution** - Check pipeline status regularly
4. **Handle failures** - Implement retry logic

## Troubleshooting

### Import Errors

If you see import errors for new modules:
- Ensure dependencies are installed: `pip install -e ".[graphrag,advanced]"`
- Check Python version compatibility
- Verify package versions in `pyproject.toml`

### Lint Errors

Lint errors are expected for new integrations because:
- Type stubs may not be available for all packages
- Line length warnings can be ignored (will be addressed)
- Unused imports are for optional dependencies

### Runtime Errors

If you encounter runtime errors:
- Check that required services are running (e.g., Neo4j, Ollama)
- Verify API keys are set correctly
- Check budget limits if agents are failing
- Review guardrail violations for safety issues

## Future Enhancements

Potential future improvements:

1. **Additional backends** - Support for more vector databases (Pinecone, Weaviate)
2. **Enhanced ontologies** - More predefined ontologies for different domains
3. **Advanced guardrails** - More sophisticated safety checks
4. **Visual tools** - Graph visualization for knowledge graphs
5. **Performance optimization** - Caching, parallel processing
6. **More LLM providers** - Support for additional LLM backends

## References

- [Microsoft Agent Framework](https://github.com/microsoft/autogen)
- [Unstructured](https://github.com/Unstructured-IO/unstructured)
- [CrewAI](https://github.com/joaomdmoura/crewAI)
- [LlamaIndex](https://github.com/run-llama/llama_index)
- [Dagster](https://github.com/dagster-io/dagster)
- [Docling](https://github.com/DS4SD/docling)
- [Network-AI](https://github.com/network-ai/network-ai)
- [Flexible GraphRAG](https://github.com/goldfelix/flexible-graphrag)
