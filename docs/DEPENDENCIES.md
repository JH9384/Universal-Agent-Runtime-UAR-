# Dependency Compatibility Matrix

This document describes the compatibility between different optional dependency groups in UAR.

## Overview

UAR uses a modular dependency structure where heavy integrations are optional. This allows users to install only what they need, reducing install size and complexity.

## Installation Groups

| Group | Description | Size | Dependencies |
|-------|-------------|------|-------------|
| **base** | Core runtime, document processing (basic), API server | ~100MB | fastapi, uvicorn, pydantic, pypdf, pandas, etc. |
| **advanced** | All advanced integrations combined | ~500MB | autogen, crewai, llama-index, dagster, neo4j, chromadb, qdrant, unstructured, docling |
| **doc-processing** | Advanced document processing | ~150MB | unstructured[local-inference], docling |
| **agent-orchestration** | Multi-agent workflows | ~200MB | autogen, crewai |
| **advanced-rag** | Knowledge graphs and vector databases | ~300MB | llama-index, llama-index-graph-stores-neo4j, neo4j, chromadb, qdrant |
| **pipeline-orchestration** | Dagster workflow orchestration | ~250MB | dagster, dagster-webserver |
| **graphrag** | Microsoft GraphRAG | ~100MB | graphrag |
| **autonomi** | Decentralized storage (experimental) | ~50MB | autonomi |

## Compatibility Matrix

| Group | base | doc-processing | agent-orchestration | advanced-rag | pipeline-orchestration | graphrag | autonomi |
|-------|------|----------------|---------------------|-------------|----------------------|----------|-----------|
| **base** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **doc-processing** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **agent-orchestration** | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | ✅ | ✅ |
| **advanced-rag** | ✅ | ✅ | ⚠️ | ✅ | ⚠️ | ✅ | ✅ |
| **pipeline-orchestration** | ✅ | ✅ | ⚠️ | ⚠️ | ✅ | ✅ | ✅ |
| **graphrag** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **autonomi** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

**Legend:**
- ✅ Fully compatible, no known conflicts
- ⚠️ Compatible but may have overlapping dependencies (install with care)

## Known Compatibility Notes

### agent-orchestration + advanced-rag
- Both groups may install different versions of common AI/ML libraries
- Recommended: Test thoroughly if combining these groups
- Workaround: Install both groups and let pip resolve dependencies

### advanced-rag + pipeline-orchestration
- Dagster may have specific version requirements for some dependencies
- Recommended: Use Dagster's version constraints as the source of truth
- Workaround: Install pipeline-orchestration first, then advanced-rag

## Recommended Installation Patterns

### For Document Analysis
```bash
pip install -e ".[doc-processing]"
```

### For Multi-Agent Workflows
```bash
pip install -e ".[agent-orchestration]"
```

### For Knowledge Graph Applications
```bash
pip install -e ".[advanced-rag]"
```

### For Production Pipelines
```bash
pip install -e ".[pipeline-orchestration]"
```

### For Full Feature Set
```bash
pip install -e ".[advanced]"
```

## Version Constraints

All dependencies have upper bounds to prevent breaking changes:

- Core dependencies: `<2.0` or `<3.0` depending on maturity
- Advanced integrations: `<1.0` or `<2.0` for stability

See `pyproject.toml` for exact version constraints.

## Testing Compatibility

Run the dependency compatibility tests to verify your installation:

```bash
# Test base installation
pip install -e ".[dev]"
pytest tests/test_dependency_compatibility.py::TestDependencyCompatibility::test_base_imports

# Test specific group
pip install -e ".[doc-processing]"
pytest tests/test_dependency_compatibility.py::TestDependencyCompatibility::test_doc_processing_imports
```

## Troubleshooting

### Dependency Conflicts

If you encounter version conflicts:

1. **Clear pip cache:**
   ```bash
   pip cache purge
   ```

2. **Use fresh virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[your-group]"
   ```

3. **Check for conflicting packages:**
   ```bash
   pip check
   ```

### Import Errors

If you get import errors after installation:

1. Verify the group was installed:
   ```bash
   pip show unstructured  # or other package name
   ```

2. Reinstall the group:
   ```bash
   pip install -e ".[your-group] --force-reinstall"
   ```

3. Check Python version compatibility (requires Python 3.10+)

## CI Testing

The CI matrix tests the following combinations on every PR:
- base (no optional dependencies)
- advanced (all optional dependencies)
- doc-processing
- agent-orchestration

This ensures compatibility is maintained across all installation types.

## Future Enhancements

Planned improvements:
- [ ] Add automated dependency conflict detection in CI
- [ ] Create pre-built Docker images for each installation group
- [ ] Add dependency version upgrade guide
- [ ] Create compatibility test suite for edge cases
