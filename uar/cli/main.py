"""UAR CLI — developer-facing command-line interface."""

import json
import os
from typing import Dict, Optional

import httpx
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from uar.core.contracts import GoalSpec
from uar.core.planner import SimplePlanner
from uar.core.executor import Executor
from uar.core.exceptions import SkillNotFoundError
from uar.core.registry import registry
from uar.core.recipes import DEFAULT_RECIPES
from uar.memory.base_store import get_store, run_record_from_dict
from uar.core.replay import replay_summary
from uar.core.timeline import timeline_from_record

# Ensure all skills are registered
import uar.skills.section_sum  # noqa: F401
import uar.skills.doc_ingest  # noqa: F401
import uar.skills.dependency_map  # noqa: F401
import uar.skills.sum_review  # noqa: F401
import uar.skills.ollama_generate  # noqa: F401
import uar.skills.graphrag_skills  # noqa: F401
import uar.skills.autonomi_storage  # noqa: F401
import uar.skills.atomic_lang_model  # noqa: F401
import uar.skills.advanced_integrations  # noqa: F401
import uar.skills.math_compute  # noqa: F401
import uar.skills.math_plot  # noqa: F401
import uar.skills.cipher_ops  # noqa: F401
import uar.skills.stem_extended  # noqa: F401
import uar.skills.physics_compute  # noqa: F401
import uar.skills.uor_ecosystem_skills  # noqa: F401
import uar.skills.quantum_ml  # noqa: F401
import uar.skills.math_plot_3d  # noqa: F401
import uar.skills.code_analysis  # noqa: F401
import uar.skills.myhdl_design  # noqa: F401

app = typer.Typer(
    name="uar",
    help="Universal Agent Runtime CLI",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()

# ── shared options ──────────────────────────────────────────────────────────


def _server_url() -> str:
    return os.getenv("UAR_SERVER_URL", "http://localhost:8000")


# ── skill commands ──────────────────────────────────────────────────────────

skill_app = typer.Typer(help="Discover and inspect skills")
app.add_typer(skill_app, name="skill")


@skill_app.command("list")
def skill_list(
    available: bool = typer.Option(
        False, "--available", "-a",
        help="Only show skills whose dependencies are installed",
    ),
) -> None:
    """List all registered skills."""
    names = registry.list()
    if not names:
        console.print("[yellow]No skills registered.[/yellow]")
        return

    table = Table(
        title="Registered Skills",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("#", justify="right", style="dim")
    table.add_column("Skill Name", style="bold cyan")
    table.add_column("Status", style="green")

    for i, name in enumerate(names, 1):
        table.add_row(str(i), name, "registered")

    console.print(table)
    console.print(f"\nTotal: [bold]{len(names)}[/bold] skills")


@skill_app.command("show")
def skill_show(name: str) -> None:
    """Show details for a single skill."""
    try:
        fn = registry.get(name)
    except SkillNotFoundError:
        console.print(f"[red]Skill '{name}' not found.[/red]")
        raise typer.Exit(1) from None

    doc = (fn.__doc__ or "").strip()
    panel = Panel(
        f"[bold cyan]{name}[/bold cyan]\n\n{doc}",
        title="Skill Details",
        box=box.ROUNDED,
    )
    console.print(panel)


# ── recipe commands ─────────────────────────────────────────────────────────

recipe_app = typer.Typer(help="Inspect built-in recipes")
app.add_typer(recipe_app, name="recipe")


@recipe_app.command("list")
def recipe_list() -> None:
    """List all built-in recipes."""
    if not DEFAULT_RECIPES:
        console.print("[yellow]No recipes defined.[/yellow]")
        return

    table = Table(
        title="Built-in Recipes",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("#", justify="right", style="dim")
    table.add_column("Recipe ID", style="bold cyan")
    table.add_column("Skills", style="green")

    for i, (rid, recipe) in enumerate(DEFAULT_RECIPES.items(), 1):
        skills = ", ".join(recipe.get("skills", []))
        table.add_row(str(i), rid, skills)

    console.print(table)
    console.print(f"\nTotal: [bold]{len(DEFAULT_RECIPES)}[/bold] recipes")


@recipe_app.command("show")
def recipe_show(recipe_id: str) -> None:
    """Show a single recipe definition."""
    recipe = DEFAULT_RECIPES.get(recipe_id)
    if not recipe:
        console.print(f"[red]Recipe '{recipe_id}' not found.[/red]")
        raise typer.Exit(1)

    console.print_json(data=recipe)


# ── run commands ────────────────────────────────────────────────────────────

run_app = typer.Typer(help="Execute goals and pipelines")
app.add_typer(run_app, name="run")


@run_app.command("goal")
def run_goal(
    goal: str = typer.Argument(..., help="Objective text"),
    skills: Optional[str] = typer.Option(
        None, "--skills", "-s",
        help="Comma-separated skill list",
    ),
    input_path: Optional[str] = typer.Option(
        None, "--input", "-i",
        help="Path for doc ingestion",
    ),
    json_output: bool = typer.Option(
        False, "--json", "-j",
        help="Output raw JSON",
    ),
) -> None:
    """Run a UAR goal locally."""
    required = skills.split(",") if skills else []

    goal_spec = GoalSpec(
        id=f"cli-{typer.get_text_stream('stdin').name}",
        user_intent=goal,
        objective=goal,
        required_skills=required,
        metadata={"input_path": input_path} if input_path else {},
    )

    planner = SimplePlanner()
    strategy = planner.plan(goal_spec)

    executor = Executor()
    result = executor.run(strategy, goal_spec)

    store = get_store()
    store.append(result)
    store.flush()

    if json_output:
        console.print_json(data={
            "status": result.status,
            "outputs": result.outputs,
            "events": len(result.events) if hasattr(result, "events") else 0,
        })
    else:
        st = "green" if result.status == "completed" else "red"
        console.print(f"Status: [bold {st}]{result.status}[/bold]")
        console.print(f"Outputs: {result.outputs}")


@run_app.command("server")
def run_server_goal(
    goal: str = typer.Argument(..., help="Objective text"),
    skills: Optional[str] = typer.Option(
        None, "--skills", "-s",
        help="Comma-separated skill list",
    ),
    server: str = typer.Option(
        "http://localhost:8000", "--server", "-S",
        help="UAR API server URL",
    ),
    api_key: Optional[str] = typer.Option(
        None, "--api-key", "-k",
        help="API key for authentication",
    ),
) -> None:
    """Send a goal to a remote UAR server."""
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "goal": goal,
        "skills": skills.split(",") if skills else [],
    }
    url = f"{server}/api/uar/run"

    try:
        with httpx.Client(timeout=60.0) as client:
            r = client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
        console.print_json(data=data)
    except httpx.ConnectError:
        console.print(f"[red]Cannot connect to {server}[/red]")
        raise typer.Exit(1) from None
    except httpx.HTTPStatusError as exc:
        console.print(f"[red]HTTP {exc.response.status_code}[/red]")
        console.print_json(data=exc.response.json())
        raise typer.Exit(1) from exc


# ── history commands ────────────────────────────────────────────────────────

history_app = typer.Typer(help="Inspect past runs")
app.add_typer(history_app, name="history")


@history_app.command("list")
def history_list(
    limit: int = typer.Option(20, "--limit", "-n", help="Max records"),
) -> None:
    """List stored run records."""
    store = get_store()
    records = store.list_all()

    if not records:
        console.print("[yellow]No stored runs found.[/yellow]")
        return

    table = Table(
        title=f"Recent Runs (last {min(limit, len(records))})",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("#", justify="right", style="dim")
    table.add_column("Run ID", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Skills", style="green")
    table.add_column("Events", justify="right")

    for i, rec in enumerate(records[:limit], 1):
        summary = replay_summary(run_record_from_dict(rec))
        status_style = "green" if summary["status"] == "completed" else "red"
        table.add_row(
            str(i),
            summary["run_id"][:16] + "…",
            f"[{status_style}]{summary['status']}[/{status_style}]",
            ", ".join(summary["skills"]) or "—",
            str(summary["event_count"]),
        )

    console.print(table)


@history_app.command("show")
def history_show(
    index: int = typer.Argument(..., help="Run index (from history list)"),
    timeline: bool = typer.Option(
        False, "--timeline", "-t", help="Show timeline",
    ),
) -> None:
    """Show details for a stored run."""
    store = get_store()
    records = store.list_all()

    if index < 1 or index > len(records):
        console.print(f"[red]Invalid index. 1–{len(records)}[/red]")
        raise typer.Exit(1)

    run_record = run_record_from_dict(records[index - 1])
    summary = replay_summary(run_record)

    console.print(Panel(
        f"Run ID: [cyan]{summary['run_id']}[/cyan]\n"
        f"Status: [bold {'green' if summary['status'] == 'completed' else 'red'}]"  # noqa: E501
        f"{summary['status']}[/bold]\n"
        f"Skills: {', '.join(summary['skills']) or '—'}\n"
        f"Events: {summary['event_count']}\n"
        f"Errors: {', '.join(summary['errors']) or 'none'}",
        title=f"Run #{index}",
        box=box.ROUNDED,
    ))

    if timeline:
        tl = timeline_from_record(run_record)  # noqa: E501
        console.print_json(data=tl)


# ── health commands ─────────────────────────────────────────────────────────

health_app = typer.Typer(help="Check system health")
app.add_typer(health_app, name="health")


@health_app.command("local")
def health_local() -> None:
    """Check local skill availability."""
    names = registry.list()

    table = Table(title="Local Skill Health", box=box.ROUNDED)
    table.add_column("Skill", style="cyan")
    table.add_column("Registered", justify="center")
    table.add_column("Callable", justify="center")

    for name in names:
        try:
            registry.get(name)
            table.add_row(name, "[green]✓[/green]", "[green]✓[/green]")
        except Exception:
            table.add_row(name, "[green]✓[/green]", "[red]✗[/red]")

    console.print(table)
    console.print(f"\n[bold]{len(names)}[/bold] skills available")


@health_app.command("server")
def health_server(
    server: str = typer.Option(
        "http://localhost:8000", "--server", "-S",
        help="UAR API server URL",
    ),
) -> None:
    """Check remote server health."""
    endpoints = {
        "Health": "/api/health",
        "Live": "/api/health/live",
        "Ready": "/api/health/ready",
        "Metrics": "/api/metrics",
    }

    table = Table(title=f"Server Health — {server}", box=box.ROUNDED)
    table.add_column("Endpoint", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Response", style="dim")

    with httpx.Client(timeout=10.0) as client:
        for label, path in endpoints.items():
            try:
                r = client.get(f"{server}{path}")
                if r.status_code == 200:
                    table.add_row(
                        label,
                        "[green]✓[/green]",
                        f"{r.status_code} OK",
                    )
                else:
                    table.add_row(
                        label,
                        "[yellow]![/yellow]",
                        f"{r.status_code}",
                    )
            except Exception:
                table.add_row(label, "[red]✗[/red]", "Error")

    console.print(table)


# ── openapi command ─────────────────────────────────────────────────────────

@app.command("openapi")
def openapi_export(
    output: Optional[str] = typer.Option(
        None, "--output", "-o",
        help="Write to file instead of stdout",
    ),
    server: str = typer.Option(
        "http://localhost:8000", "--server", "-S",
        help="UAR API server URL",
    ),
) -> None:
    """Fetch and display the OpenAPI spec from a running UAR server."""
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(f"{server}/openapi.json")
        r.raise_for_status()
        spec = r.json()
    except httpx.ConnectError:
        console.print(f"[red]Cannot connect to {server}[/red]")
        raise typer.Exit(1) from None
    except httpx.HTTPStatusError as exc:
        console.print(f"[red]HTTP {exc.response.status_code}[/red]")
        raise typer.Exit(1) from exc

    pretty = json.dumps(spec, indent=2)
    if output:
        with open(output, "w") as f:
            f.write(pretty)
        console.print(f"[green]Wrote OpenAPI spec to {output}[/green]")
    else:
        console.print(pretty)


# ── entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
