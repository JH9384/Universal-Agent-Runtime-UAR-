"""Multi-language code analysis skill.

Performs static analysis on source code for common languages:
Python, JavaScript, TypeScript, Go, Rust, Java, C, C++.

Reports: lines of code, function/class counts, import/module counts,
cyclomatic complexity estimate, TODO/FIXME comments, and
potential issues.

Goal Metadata:
    code_source      — Source code string to analyze (required)
    code_language    — Language: 'python', 'javascript', 'typescript',
                       'go', 'rust', 'java', 'c', 'cpp' (default: auto-detect)
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext

logger = logging.getLogger(__name__)

# Language detection hints
_LANG_HINTS = {
    "python": [
        r"^def\s+", r"^class\s+", r"^import\s+", r"^from\s+\S+\s+import",
    ],
    "javascript": [
        r"\bconst\s+", r"\bfunction\s+", r"\bvar\s+",
        r"=>", r"console\.log",
    ],
    "typescript": [
        r":\s+(string|number|boolean|any|void|interface|type\s+)",
        r"\binterface\s+", r"\btype\s+", r"\benum\s+",
    ],
    "go": [
        r"^package\s+", r"^func\s+", r":=", r"^import\s+\(",
    ],
    "rust": [
        r"\bfn\s+", r"\blet\s+mut\s+", r"\bimpl\s+", r"\buse\s+",
    ],
    "java": [
        r"\bpublic\s+class\s+", r"\bprivate\s+", r"\bSystem\.out",
    ],
    "c": [
        r"^#include\s+", r"\bint\s+main\s*\(", r"\bprintf\s*\(",
    ],
    "cpp": [
        r"^#include\s+", r"\bstd::", r"\bclass\s+", r"\bpublic:\s*$",
    ],
}


def _detect_language(source: str) -> str:
    """Auto-detect programming language from source."""
    scores: Dict[str, int] = {}
    for lang, patterns in _LANG_HINTS.items():
        score = 0
        for pat in patterns:
            if re.search(pat, source, re.MULTILINE):
                score += 1
        if score > 0:
            scores[lang] = score
    if scores:
        return max(scores, key=lambda k: scores[k])
    return "unknown"


def _has_real_comment(line: str, marker: str) -> bool:
    """Return True if *marker* appears outside string literals.

    Handles both single (') and double (") quoted strings.
    """
    in_single = False
    in_double = False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line):
            i += 2
            continue
        if not in_single and ch == '"' and not in_double:
            in_double = True
            i += 1
            continue
        if not in_double and ch == "'" and not in_single:
            in_single = True
            i += 1
            continue
        if in_double and ch == '"':
            in_double = False
            i += 1
            continue
        if in_single and ch == "'":
            in_single = False
            i += 1
            continue
        if not in_single and not in_double:
            if line.startswith(marker, i):
                return True
        i += 1
    return False


def _count_lines(source: str) -> Dict[str, int]:
    """Count total, blank, and comment lines."""
    lines = source.splitlines()
    total = len(lines)
    blank = sum(1 for ln in lines if not ln.strip())
    comment = 0
    in_block = False
    for line in lines:
        stripped = line.strip()
        # Detect block comment boundaries (outside strings)
        if _has_real_comment(stripped, "/*"):
            in_block = True
        if in_block:
            comment += 1
            if _has_real_comment(stripped, "*/"):
                in_block = False
            continue
        # Single-line comments (including inline) — outside strings only
        if _has_real_comment(stripped, "//") or _has_real_comment(
            stripped, "#"
        ):
            comment += 1
    code = total - blank - comment
    return {"total": total, "blank": blank, "comment": comment, "code": code}


def _extract_functions(source: str, lang: str) -> List[str]:
    """Extract function names from source."""
    names: List[str] = []

    if lang == "python":
        for m in re.finditer(r"^def\s+(\w+)\s*\(", source, re.MULTILINE):
            names.append(m.group(1))
    elif lang in ("javascript", "typescript"):
        for m in re.finditer(r"\bfunction\s+(\w+)\s*\(", source):
            names.append(m.group(1))
        for m in re.finditer(r"\bconst\s+(\w+)\s*=\s*\([^)]*\)\s*=>", source):
            names.append(m.group(1))
    elif lang == "go":
        pattern = r"^func\s+(?:\([^)]*\)\s+)?(\w+)\s*\("
        for m in re.finditer(pattern, source, re.MULTILINE):
            names.append(m.group(1))
    elif lang == "rust":
        for m in re.finditer(r"\bfn\s+(\w+)\s*\(", source):
            names.append(m.group(1))
    elif lang in ("java", "cpp", "c"):
        # Match method/function declarations
        func_pat = (
            r"\b(?:public|private|protected|static|final)?\s*"
            r"(?:\w+[\s*&]+)+(\w+)\s*\([^)]*\)\s*\{"
        )
        for m in re.finditer(func_pat, source):
            names.append(m.group(1))

    return names


def _extract_classes(source: str, lang: str) -> List[str]:
    """Extract class/struct names."""
    names: List[str] = []

    if lang == "python":
        for m in re.finditer(r"^class\s+(\w+)\s*[\(:]", source, re.MULTILINE):
            names.append(m.group(1))
    elif lang in ("javascript", "typescript", "java", "cpp"):
        for m in re.finditer(r"\bclass\s+(\w+)", source):
            names.append(m.group(1))
    elif lang == "go":
        for m in re.finditer(r"^type\s+(\w+)\s+struct\s*\{", source, re.MULTILINE):
            names.append(m.group(1))
    elif lang == "rust":
        for m in re.finditer(r"\bstruct\s+(\w+)", source):
            names.append(m.group(1))
        for m in re.finditer(r"\benum\s+(\w+)", source):
            names.append(m.group(1))

    return names


def _extract_imports(source: str, lang: str) -> List[str]:
    """Extract import/module names."""
    imports: List[str] = []

    if lang == "python":
        for m in re.finditer(r"^import\s+(\w+)", source, re.MULTILINE):
            imports.append(m.group(1))
        for m in re.finditer(r"^from\s+(\S+)\s+import", source, re.MULTILINE):
            imports.append(m.group(1))
    elif lang in ("javascript", "typescript"):
        for m in re.finditer(r"import\s+.*?\s+from\s+['\"](.+?)['\"]", source):
            imports.append(m.group(1))
        for m in re.finditer(r"require\s*\(\s*['\"](.+?)['\"]\s*\)", source):
            imports.append(m.group(1))
    elif lang == "go":
        for m in re.finditer(r'["\'](\S+?)["\']', source):
            imports.append(m.group(1))
    elif lang == "rust":
        for m in re.finditer(r"\buse\s+([\w:]+)", source):
            imports.append(m.group(1))
    elif lang in ("java", "cpp", "c"):
        for m in re.finditer(r'#include\s+[<\"](.+?)[>\"]', source):
            imports.append(m.group(1))

    return imports


def _find_todos(source: str) -> List[Dict[str, Any]]:
    """Find TODO, FIXME, HACK comments."""
    todos = []
    for m in re.finditer(
        r"(TODO|FIXME|HACK|XXX|BUG|NOTE)[\s:]?[\s]*(.*)",
        source,
        re.IGNORECASE,
    ):
        todos.append({
            "type": m.group(1).upper(),
            "text": m.group(2).strip()[:100],
            "line": source[:m.start()].count("\n") + 1,
        })
    return todos


def _estimate_complexity(source: str, lang: str) -> Dict[str, Any]:
    """Estimate cyclomatic complexity."""
    # Count decision points
    decisions = 0
    patterns = [
        r"\bif\b", r"\belse\b", r"\bwhile\b",
        r"\bfor\b", r"\bforeach\b",
        r"\bmatch\b", r"\bcase\b", r"\bdefault\b",
        r"\bswitch\b", r"\btry\b", r"\bcatch\b",
        r"\band\b", r"\bor\b", r"&&", r"\|\|",
        r"\bthen\b", r"\bwhen\b",
    ]
    for pat in patterns:
        decisions += len(re.findall(pat, source, re.IGNORECASE))

    funcs = _extract_functions(source, lang)
    n_funcs = max(len(funcs), 1)

    return {
        "decision_points": decisions,
        "function_count": len(funcs),
        "estimated_complexity": round(decisions / n_funcs, 2),
    }


def _find_issues(source: str, lang: str) -> List[Dict[str, Any]]:
    """Find potential issues."""
    issues = []

    # Check for empty catch blocks
    catch_pat = r"catch\s*\([^)]*\)\s*\{\s*\}"
    for m in re.finditer(catch_pat, source, re.DOTALL):
        issues.append({
            "type": "empty_catch",
            "message": "Empty catch block detected",
            "line": source[:m.start()].count("\n") + 1,
        })

    # Check for TODO/FIXME
    todos = _find_todos(source)
    for todo in todos:
        issues.append({
            "type": todo["type"].lower(),
            "message": todo["text"],
            "line": todo.get("line", 0),
        })

    # Long lines
    for i, line in enumerate(source.splitlines(), 1):
        if len(line) > 120:
            issues.append({
                "type": "long_line",
                "message": f"Line {i} exceeds 120 characters",
                "line": i,
            })

    # Python-specific
    if lang == "python":
        bare_match = re.search(r"except\s*:\s*$", source, re.MULTILINE)
        if bare_match:
            issues.append({
                "type": "bare_except",
                "message": "Bare except clause found",
                "line": source[:bare_match.start()].count("\n") + 1,
            })

    return issues


@register_skill("code_analysis")
def code_analysis(ctx: PipelineContext) -> Dict[str, Any]:
    """Analyze source code for metrics and potential issues.

    Supports: Python, JavaScript, TypeScript, Go, Rust, Java, C, C++.
    Auto-detects language if not specified.

    Metadata:
        code_source     — Source code string (required)
        code_language   — Language hint (optional, auto-detected)
    """
    meta = ctx.goal.metadata or {}
    source = str(meta.get("code_source", ""))

    if not source.strip():
        return {
            "status": "failed",
            "error": "code_source is required in goal metadata",
        }

    lang = str(meta.get("code_language", "")).lower().strip()
    if not lang or lang == "auto":
        lang = _detect_language(source)

    lines = _count_lines(source)
    functions = _extract_functions(source, lang)
    classes = _extract_classes(source, lang)
    imports = _extract_imports(source, lang)
    complexity = _estimate_complexity(source, lang)
    issues = _find_issues(source, lang)

    return {
        "status": "completed",
        "goal": ctx.goal.user_intent,
        "result": {
            "language": lang,
            "lines": lines,
            "functions": functions,
            "classes": classes,
            "imports": imports,
            "complexity": complexity,
            "issues": issues,
        },
        "metrics": {
            "total_lines": lines["total"],
            "code_lines": lines["code"],
            "function_count": len(functions),
            "class_count": len(classes),
            "import_count": len(imports),
            "issue_count": len(issues),
        },
    }
