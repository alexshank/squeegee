"""Build hook: a wheel must never ship a UI that 404s.

Builds the frontend when the sources and npm are both present, then refuses to
produce a wheel without the assets.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

STATIC = Path("src/squeegee/ui/static")
FRONTEND = Path("frontend")


class UiBuildHook(BuildHookInterface):  # type: ignore[type-arg] # hatchling ships no stubs
    """Builds frontend/ into src/squeegee/ui/static before a wheel is packed."""

    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        """Build the assets if possible, and fail the build if they are absent."""
        root = Path(self.root)
        if self.target_name != "wheel":
            return
        if (root / FRONTEND / "package.json").is_file() and shutil.which("npm"):
            self._build(root)
        if not (root / STATIC / "index.html").is_file():
            raise RuntimeError(
                f"{STATIC}/index.html is missing, so this wheel would serve a broken UI. "
                "Run `make ui` (which needs Node) before building, or build from a source "
                "tree where the assets are already present."
            )

    def _build(self, root: Path) -> None:
        install = "ci" if (root / FRONTEND / "package-lock.json").is_file() else "install"
        for command in (["npm", install], ["npm", "run", "build"]):
            subprocess.run(command, cwd=root / FRONTEND, check=True)
