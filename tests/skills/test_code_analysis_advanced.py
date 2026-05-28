"""Extended tests for code_analysis skill.

Covers previously untested languages (javascript, typescript, java,
c, cpp) and edge cases in comment detection and complexity estimation.
"""

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.code_analysis import (
    code_analysis,
    _detect_language,
    _has_real_comment,
)


def _ctx(metadata: dict) -> PipelineContext:
    goal = GoalSpec(
        id="test-id",
        user_intent="test",
        objective="test",
        metadata=metadata,
    )
    return PipelineContext(goal=goal, data={})


JS_SAMPLE = """
const x = 10;
function greet(name) {
    console.log("Hello " + name);
    return name.toUpperCase();
}
const arrow = (a, b) => a + b;
"""

TS_SAMPLE = """
interface User {
    name: string;
    age: number;
}
type ID = string | number;
function getUser(id: ID): User {
    return { name: "test", age: 30 };
}
"""

JAVA_SAMPLE = """
public class Main {
    private int value;
    public static void main(String[] args) {
        System.out.println("Hello");
    }
}
"""

C_SAMPLE = """
#include <stdio.h>
int main() {
    printf("Hello\\n");
    return 0;
}
"""

CPP_SAMPLE = """
#include <iostream>
class Box {
public:
    int width;
};
int main() {
    std::cout << "Hello" << std::endl;
    return 0;
}
"""


class TestLanguageDetection:
    """Auto-detection for all supported languages."""

    def test_detect_python(self):
        assert _detect_language("def foo():\n  pass") == "python"

    def test_detect_javascript(self):
        assert _detect_language(JS_SAMPLE) == "javascript"

    def test_detect_typescript(self):
        assert _detect_language(TS_SAMPLE) == "typescript"

    def test_detect_go(self):
        assert _detect_language("package main\nfunc main() {}") == "go"

    def test_detect_rust(self):
        assert _detect_language("fn main() {\n  let x = 1;\n}") == "rust"

    def test_detect_java(self):
        assert _detect_language(JAVA_SAMPLE) == "java"

    def test_detect_c(self):
        assert _detect_language(C_SAMPLE) == "c"

    def test_detect_cpp(self):
        assert _detect_language(CPP_SAMPLE) == "cpp"

    def test_detect_unknown(self):
        assert _detect_language("random text without hints") == "unknown"


class TestCodeAnalysisLanguages:
    """Analysis results for each language."""

    def test_javascript_analysis(self):
        result = code_analysis(_ctx({"code_source": JS_SAMPLE}))
        assert result["status"] == "completed"
        res = result["result"]
        assert res["language"] == "javascript"
        assert res["lines"]["total"] >= 5
        assert len(res["functions"]) >= 2

    def test_typescript_analysis(self):
        result = code_analysis(_ctx({"code_source": TS_SAMPLE}))
        assert result["status"] == "completed"
        res = result["result"]
        assert res["language"] == "typescript"
        assert len(res["functions"]) >= 1

    def test_java_analysis(self):
        result = code_analysis(_ctx({"code_source": JAVA_SAMPLE}))
        assert result["status"] == "completed"
        res = result["result"]
        assert res["language"] == "java"
        assert len(res["classes"]) >= 1

    def test_c_analysis(self):
        result = code_analysis(_ctx({"code_source": C_SAMPLE}))
        assert result["status"] == "completed"
        res = result["result"]
        assert res["language"] == "c"
        assert len(res["functions"]) >= 1
        assert any("stdio" in imp for imp in res["imports"])

    def test_cpp_analysis(self):
        result = code_analysis(_ctx({"code_source": CPP_SAMPLE}))
        assert result["status"] == "completed"
        res = result["result"]
        assert res["language"] == "cpp"
        assert len(res["classes"]) >= 1
        assert "iostream" in res["imports"]


class TestRealCommentDetection:
    """_has_real_comment handles strings and escapes correctly."""

    def test_comment_outside_string(self):
        assert _has_real_comment("x = 1 # TODO", "TODO") is True

    def test_comment_in_single_quoted_string(self):
        assert _has_real_comment("x = 'TODO: fix'", "TODO") is False

    def test_comment_in_double_quoted_string(self):
        assert _has_real_comment('x = "TODO: fix"', "TODO") is False

    def test_escaped_quote(self):
        # The escaped quote prevents entering string mode, so TODO
        # is found outside any string literal.
        # x = \"TODO"  ->  backslash escapes quote, then TODO" is
        # in a string, so TODO is inside the string -> False
        assert _has_real_comment('x = "\\"TODO"', "TODO") is False

    def test_comment_after_string(self):
        assert _has_real_comment('x = "ok" # TODO', "TODO") is True


class TestComplexityEstimation:
    """Cyclomatic complexity estimation edge cases."""

    def test_simple_function_low_complexity(self):
        source = "def f():\n    return 1\n"
        result = code_analysis(_ctx({
            "code_source": source, "code_language": "python"
        }))
        assert result["result"]["complexity"]["estimated_complexity"] == 0.0

    def test_multiple_branches(self):
        source = (
            "def f(x):\n"
            "    if x:\n        return 1\n"
            "    elif y:\n        return 2\n"
            "    else:\n        return 3\n"
        )
        result = code_analysis(_ctx({
            "code_source": source, "code_language": "python"
        }))
        comp = result["result"]["complexity"]["estimated_complexity"]
        # if (1) + else (1) = 2; elif does not match \bif\b
        assert comp >= 2

    def test_loops_add_complexity(self):
        source = (
            "def f():\n"
            "    for i in range(10):\n"
            "        if i % 2:\n            pass\n"
        )
        result = code_analysis(_ctx({
            "code_source": source, "code_language": "python"
        }))
        comp = result["result"]["complexity"]["estimated_complexity"]
        assert comp >= 2

    def test_try_except_adds_complexity(self):
        source = (
            "def f():\n"
            "    try:\n        pass\n"
            "    except ValueError:\n        pass\n"
        )
        result = code_analysis(_ctx({
            "code_source": source, "code_language": "python"
        }))
        comp = result["result"]["complexity"]["estimated_complexity"]
        # 'try' matches (1), 'except' is not in pattern list
        assert comp >= 1
