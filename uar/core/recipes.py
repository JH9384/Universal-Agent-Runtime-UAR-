"""Shared recipe definitions for UAR.

This module contains the canonical recipe definitions used by both
the executor and the API server to avoid duplication.
"""

import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

# Recipe definitions matching frontend RECIPES
DEFAULT_RECIPES: Dict[str, Dict[str, Any]] = {
    'review': {
        'id': 'review',
        'label': '🦙 Ollama review',
        'skills': ['doc_ingest', 'ollama_generate'],
        'hint': 'Quick LLM review of library docs'
    },
    'deps': {
        'id': 'deps',
        'label': '🕸️ Dep map',
        'skills': ['doc_ingest', 'dependency_map', 'sum_review'],
        'hint': 'Build a dependency graph'
    },
    'gr_index': {
        'id': 'gr_index',
        'label': '📚 GraphRAG index',
        'skills': ['graphrag_index'],
        'hint': 'Build the knowledge graph (slow, one-time)'
    },
    'gr_query': {
        'id': 'gr_query',
        'label': '🔎 GraphRAG query',
        'skills': ['graphrag_query'],
        'hint': 'Query an existing graph'
    },
    'gr_full': {
        'id': 'gr_full',
        'label': '⚡ Full pipeline',
        'skills': ['graphrag_index', 'graphrag_query'],
        'hint': 'Index then query (very slow)'
    },
    'auto_up': {
        'id': 'auto_up',
        'label': '☁️ Autonomi upload',
        'skills': ['autonomi_upload'],
        'hint': 'Upload current input_path to Autonomi'
    },
    'auto_down': {
        'id': 'auto_down',
        'label': '☁️ Autonomi download',
        'skills': ['autonomi_download'],
        'hint': 'Download from Autonomi address'
    },
    'auto_status': {
        'id': 'auto_status',
        'label': '☁️ Autonomi status',
        'skills': ['autonomi_status'],
        'hint': 'Check Autonomi connectivity'
    },
}

# Create RECIPE_MAP for quick lookup of skill lists by recipe ID
RECIPE_MAP: Dict[str, List[str]] = {
    recipe_id: recipe['skills']
    for recipe_id, recipe in DEFAULT_RECIPES.items()
    if 'skills' in recipe
}


def validate_recipes() -> None:
    """Validate that all skills in recipes are registered.

    This function is called at module load time to catch invalid
    skill references early rather than at runtime.
    """
    try:
        from .registry import registry

        all_valid = True
        for recipe_id, recipe in DEFAULT_RECIPES.items():
            skills = recipe.get('skills', [])
            for skill in skills:
                if not registry.is_registered(skill):
                    logger.warning(
                        f"Recipe '{recipe_id}' references unregistered "
                        f"skill: {skill}"
                    )
                    all_valid = False

        if all_valid:
            logger.info("All recipe skills validated successfully")
    except ImportError:
        # Registry might not be available during import
        logger.warning(
            "Could not validate recipes against registry - "
            "registry not available"
        )


# Validate recipes at module load time
validate_recipes()
