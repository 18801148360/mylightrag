"""LightRAG runtime bootstrap for the standalone MCP process."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from typing import Any

from lightrag.utils import logger


_WORKSPACE_PATTERN = re.compile(r"^[A-Za-z0-9_]*$")


@dataclass(frozen=True)
class MCPRuntimeSettings:
    """Settings that belong to the MCP process rather than a query."""

    workspace: str | None = None
    lightrag_argv: tuple[str, ...] = field(default_factory=tuple)


class MCPRuntime:
    """Own one fixed-workspace LightRAG instance and its storage lifecycle."""

    def __init__(self, settings: MCPRuntimeSettings):
        self.settings = settings
        self.app: Any | None = None
        self.rag: Any | None = None
        self._lifespan: Any | None = None
        self._started = False

    async def start(self) -> None:
        if self._started:
            return

        workspace = self.settings.workspace
        if workspace is not None and not _WORKSPACE_PATTERN.fullmatch(workspace):
            raise ValueError(
                "MCP workspace may contain only letters, numbers, and underscores"
            )

        original_argv = sys.argv[:]
        sys.argv = [original_argv[0], *self.settings.lightrag_argv]
        try:
            from lightrag.api.config import global_args, initialize_config

            initialize_config(force=True)
            if workspace is not None:
                global_args.workspace = workspace

            from lightrag.api.lightrag_server import create_app

            self.app = create_app(global_args)
            self.rag = self.app.state.rag
            self._lifespan = self.app.router.lifespan_context(self.app)
            await self._lifespan.__aenter__()
            self._started = True
            logger.info("LightRAG MCP runtime started for workspace=%s", self.rag.workspace)
        finally:
            sys.argv = original_argv

    async def stop(self) -> None:
        if not self._started:
            return

        lifespan = self._lifespan
        self._lifespan = None
        self._started = False
        if lifespan is not None:
            await lifespan.__aexit__(None, None, None)
        self.rag = None
        self.app = None
        logger.info("LightRAG MCP runtime stopped")
