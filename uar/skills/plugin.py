"""Plugin ABI for loading external UAR skills.

Skills can be loaded from:
- ``~/.uar/skills/`` — user-local skill directories
- PyPI packages named ``uar-skills-*`` — community skill packages
- Any Python module that exposes a ``uar_skills`` entry-point group

Usage:
    from uar.skills.plugin import load_plugins
    load_plugins()  # discovers and registers all external skills
"""

import importlib
import importlib.metadata as imd
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from uar.core.registry import registry

logger = logging.getLogger(__name__)

# Default search paths
_USER_SKILL_DIR = Path.home() / ".uar" / "skills"
_PLUGIN_ENTRY_GROUP = "uar.skills"


def _load_module_from_path(module_name: str, file_path: Path) -> Any:
    """Load a Python module from an arbitrary file path."""
    spec = importlib.util.spec_from_file_location(
        module_name, file_path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create spec for {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _discover_user_skills() -> List[Path]:
    """Find all ``.py`` files under ``~/.uar/skills/``."""
    if not _USER_SKILL_DIR.exists():
        return []
    return [
        p
        for p in _USER_SKILL_DIR.rglob("*.py")
        if p.name != "__init__.py" and not p.name.startswith("_")
    ]


def _discover_pypi_plugins() -> List[Any]:
    """Find modules registered via the ``uar.skills`` entry point group."""
    modules = []
    try:
        eps = imd.entry_points()
        if hasattr(eps, "select"):
            # importlib.metadata >= 3.9 (Python 3.10+)
            group = eps.select(group=_PLUGIN_ENTRY_GROUP)
        else:
            # Legacy API
            group = eps.get(_PLUGIN_ENTRY_GROUP) or []  # type: ignore
        for ep in group:
            try:
                modules.append(ep.load())
            except Exception:
                logger.exception("Failed to load plugin %s", ep.name)
    except Exception:
        logger.exception("Plugin discovery failed")
    return modules


def _register_skills_from_module(module: Any) -> int:
    """Import a module and count how many skills were registered."""
    # The module's top-level execution should have triggered
    # @register_skill decorators, but we double-check by looking for
    # a convention-based ``register_skills`` function as well.
    count = 0
    if hasattr(module, "register_skills"):
        try:
            result = module.register_skills(registry)
            if isinstance(result, int):
                count += result
        except Exception:
            logger.exception("register_skills() failed in %s", module)

    # Also accept a module-level ``__uar_skills__`` dict:
    #   __uar_skills__ = {"my_skill": my_skill_fn}
    skill_dict = getattr(module, "__uar_skills__", {})
    for name, fn in skill_dict.items():
        try:
            registry.register(name, fn)
            count += 1
        except Exception:
            logger.exception("Failed to register skill %s", name)

    return count


def load_plugins(
    *,
    user_dir: Optional[Path] = None,
    pypi: bool = True,
) -> Dict[str, int]:
    """Discover and register all external skills.

    Args:
        user_dir: Override the default ``~/.uar/skills/`` path.
        pypi: Whether to scan PyPI entry points.

    Returns:
        Mapping of source name → number of skills registered.
    """
    results: Dict[str, int] = {}

    # 1. User-local skills
    skill_dir = user_dir or _USER_SKILL_DIR
    for path in _discover_user_skills():
        module_name = f"uar.user_skill.{path.stem}"
        try:
            mod = _load_module_from_path(module_name, path)
            count = _register_skills_from_module(mod)
            if count:
                results[str(path.relative_to(skill_dir))] = count
        except Exception:
            logger.exception("Failed to load user skill %s", path)

    # 2. PyPI packages
    if pypi:
        for mod in _discover_pypi_plugins():
            try:
                count = _register_skills_from_module(mod)
                if count:
                    name = getattr(mod, "__name__", str(mod))
                    results[name] = count
            except Exception:
                logger.exception("Failed to load PyPI plugin %s", mod)

    total = sum(results.values())
    if total:
        logger.info(
            "Loaded %s external skill(s) from %s source(s)",
            total,
            len(results),
        )
    return results


def init_user_skill_dir() -> Path:
    """Create ``~/.uar/skills/`` and seed it with a README and example."""
    skill_dir = _USER_SKILL_DIR
    skill_dir.mkdir(parents=True, exist_ok=True)

    readme = skill_dir / "README.md"
    if not readme.exists():
        readme.write_text(
            "# UAR User Skills\n\n"
            "Drop ``.py`` files here or create sub-packages.\n\n"
            "Each module can use ``@register_skill`` decorators or "  # noqa: E501
            "expose a ``register_skills(registry)`` function.\n"
        )

    example = skill_dir / "example_plugin.py"
    if not example.exists():
        example.write_text(
            '"""Example user skill plugin."""\n'
            "\n"
            "from uar.core.registry import register_skill\n"
            "\n"
            "@register_skill('hello_user')\n"
            "def hello_user(ctx):\n"
            "    return {\n"
            "        'status': 'completed',\n"
            "        'message': 'Hello from user plugin!',\n"
            "    }\n"
        )

    return skill_dir
