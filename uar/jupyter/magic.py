"""IPython magic commands for UAR.

Usage in Jupyter:
    %load_ext uar.jupyter.magic
    %%uar run
    Summarize the codebase
"""

import json
import os
from typing import Any, Dict, Optional

from IPython.core.magic import Magics, cell_magic, line_magic, magics_class
from IPython.core.magic_arguments import (
    argument,
    magic_arguments,
    parse_argstring,
)

from uar.core.contracts import GoalSpec
from uar.core.planner import SimplePlanner
from uar.core.executor import Executor
from uar.core.registry import registry

# Ensure core skills are registered
import uar.skills.section_sum  # noqa: F401
import uar.skills.doc_ingest  # noqa: F401
import uar.skills.dependency_map  # noqa: F401
import uar.skills.sum_review  # noqa: F401
import uar.skills.ollama_generate  # noqa: F401
import uar.skills.math_compute  # noqa: F401
import uar.skills.math_plot  # noqa: F401
import uar.skills.cipher_ops  # noqa: F401
import uar.skills.stem_extended  # noqa: F401
import uar.skills.physics_compute  # noqa: F401


@magics_class
class UARMagics(Magics):
    """IPython magic for UAR skill execution."""

    def __init__(self, shell: Any) -> None:
        super().__init__(shell)
        self._last_result: Optional[Dict[str, Any]] = None
        self._server_url = os.getenv(
            "UAR_SERVER_URL", "http://localhost:8000"
        )

    @line_magic
    @magic_arguments()
    @argument(
        "--server", "-S",
        help="UAR API server URL",
    )
    @argument(
        "--api-key", "-k",
        help="API key for remote server",
    )
    def uar_config(self, parameter_s: str) -> None:
        """Configure UAR magic defaults."""
        args = parse_argstring(self.uar_config, parameter_s)
        if args.server:
            self._server_url = args.server
            print(f"Server set to: {args.server}")
        if args.api_key:
            os.environ["UAR_API_KEY"] = args.api_key
            print("API key stored in environment")

    @cell_magic("uar")
    @magic_arguments()
    @argument(
        "--skills", "-s",
        default="",
        help="Comma-separated skill list",
    )
    @argument(
        "--input", "-i",
        default="",
        help="Input path for doc ingestion",
    )
    @argument(
        "--json", "-j",
        action="store_true",
        help="Output raw JSON",
    )
    @argument(
        "--remote", "-r",
        action="store_true",
        help="Send to remote server instead of local",
    )
    def uar_magic(self, line: str, cell: str) -> Optional[Dict[str, Any]]:
        """Execute a UAR goal from a Jupyter cell.

        Example:
            %%uar --skills math_compute
            Solve x^2 + 2x + 1 = 0
        """
        args = parse_argstring(self.uar_magic, line)
        goal_text = cell.strip()

        if not goal_text:
            print("Error: Empty goal. Provide text in the cell.")
            return None

        skills = [s.strip() for s in args.skills.split(",") if s.strip()]

        if args.remote:
            return self._run_remote(goal_text, skills, args)
        return self._run_local(goal_text, skills, args)

    def _run_local(
        self,
        goal: str,
        skills: list,
        args: Any,
    ) -> Dict[str, Any]:
        """Execute locally using the UAR engine."""
        goal_spec = GoalSpec(
            id="jupyter-cell",
            user_intent=goal,
            objective=goal,
            required_skills=skills,
            metadata={"input_path": args.input} if args.input else {},
        )

        planner = SimplePlanner()
        strategy = planner.plan(goal_spec)

        executor = Executor()
        result = executor.run(strategy, goal_spec)

        self._last_result = result  # type: ignore[assignment]

        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"Status: {result.status}")
            if result.outputs:
                print("Outputs:")
                for key, val in result.outputs.items():  # type: ignore[attr-defined]
                    print(f"  {key}: {val}")
            if hasattr(result, "events") and result.events:
                print(f"Events: {len(result.events)}")

        return result  # type: ignore[return-value]

    def _run_remote(
        self,
        goal: str,
        skills: list,
        args: Any,
    ) -> Optional[Dict[str, Any]]:
        """Execute via remote UAR API."""
        import httpx

        payload = {
            "goal": goal,
            "skills": skills,
        }

        headers: Dict[str, str] = {"Content-Type": "application/json"}
        api_key = os.getenv("UAR_API_KEY")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            with httpx.Client(timeout=120.0) as client:
                r = client.post(
                    f"{self._server_url}/api/uar/run",
                    json=payload,
                    headers=headers,
                )
            r.raise_for_status()
            data = r.json()
            self._last_result = data

            if args.json:
                print(json.dumps(data, indent=2))
            else:
                print(f"Status: {data.get('status', 'unknown')}")
                if "outputs" in data:
                    print("Outputs:", data["outputs"])

            return data
        except Exception as exc:
            print(f"Remote execution failed: {exc}")
            return None

    @line_magic
    def uar_skills(self, parameter_s: str = "") -> None:
        """List all registered UAR skills."""
        names = registry.list()
        print(f"Registered skills: {len(names)}")
        for name in names:
            print(f"  • {name}")

    @line_magic
    def uar_last(self, parameter_s: str = "") -> Optional[Dict[str, Any]]:
        """Show the result of the last UAR execution."""
        if self._last_result is None:
            print("No previous execution.")
            return None
        print(json.dumps(self._last_result, indent=2, default=str))
        return self._last_result


def load_ipython_extension(ipython: Any) -> None:
    """Register the UAR magics with IPython."""
    ipython.register_magics(UARMagics)
