"""PlatformIO embedded development skill.

A lightweight PlatformIO project metadata generator.
"""

from __future__ import annotations

import shutil
from typing import Any, Dict

from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext


def _check_platformio() -> bool:
    return shutil.which("pio") is not None


def platformio(ctx: PipelineContext) -> Dict[str, Any]:
    """Check PlatformIO availability and generate project metadata.

    Parameters (from ctx.goal.metadata):
        board: str - Target board (default: esp32dev)
        framework: str - Framework (default: arduino)
    """
    params = ctx.goal.metadata or {}
    board = str(params.get("board", "esp32dev"))
    framework = str(params.get("framework", "arduino"))

    available = _check_platformio()

    project_config = f"""[env:{board}]
platform = espressif32
board = {board}
framework = {framework}
monitor_speed = 115200
"""

    return {
        "status": "completed",
        "goal": ctx.goal.user_intent,
        "result": {
            "platformio_available": available,
            "board": board,
            "framework": framework,
            "project_config": project_config,
            "build_command": f"pio run -e {board}",
            "upload_command": f"pio run -e {board} --target upload",
        },
        "metrics": {
            "available": available,
        },
    }


register_skill("platformio")(platformio)
