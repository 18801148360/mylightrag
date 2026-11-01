"""Standalone FastMCP server exposing read-only LightRAG queries."""

from __future__ import annotations

import argparse
import os
import sys
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv


def create_mcp_server(settings: MCPServerSettings | None = None) -> Any:
    """Create a FastMCP server without starting its transport."""

    settings = settings or MCPServerSettings.from_env()
    original_argv = sys.argv[:]
    sys.argv = [original_argv[0], *settings.lightrag_argv]
    try:
        from .auth import verify_api_key
        from .models import MCPQueryRequest
        from .runtime import MCPRuntime, MCPRuntimeSettings
        from .service import MCPQueryService
    finally:
        sys.argv = original_argv

    try:
        from fastmcp import Context, FastMCP
    except ImportError as exc:  # pragma: no cover - exercised without the extra
        raise RuntimeError(
            "FastMCP is not installed. Install the MCP extra with "
            "`pip install -e '.[mcp]'`."
        ) from exc

    globals()["Context"] = Context
    globals()["MCPQueryRequest"] = MCPQueryRequest

    runtime = MCPRuntime(
        MCPRuntimeSettings(
            workspace=settings.workspace,
            lightrag_argv=settings.lightrag_argv,
        )
    )
    service = MCPQueryService(runtime)

    @asynccontextmanager
    async def lifespan(_server: Any):
        await runtime.start()
        try:
            yield {"runtime": runtime}
        finally:
            await runtime.stop()

    mcp = FastMCP("LightRAG", lifespan=lifespan)

    @mcp.tool(
        name="rag_query",
        description=(
            "Query the fixed-workspace LightRAG knowledge base and return a "
            "non-streaming answer with source references. This is read-only."
        ),
    )
    async def rag_query(request: MCPQueryRequest, ctx: Context) -> dict[str, Any]:
        verify_api_key(ctx, settings.api_key)
        return await service.query(request)

    @mcp.tool(
        name="rag_retrieve",
        description=(
            "Retrieve structured entities, relationships, chunks, and references "
            "from the fixed-workspace LightRAG knowledge base. This is read-only."
        ),
    )
    async def rag_retrieve(request: MCPQueryRequest, ctx: Context) -> dict[str, Any]:
        verify_api_key(ctx, settings.api_key)
        return await service.retrieve(request)

    @mcp.tool(
        name="rag_health",
        description="Return LightRAG MCP runtime health and fixed-workspace status.",
    )
    async def rag_health(ctx: Context) -> dict[str, Any]:
        verify_api_key(ctx, settings.api_key)
        return await service.health()

    return mcp


class MCPServerSettings:
    """Transport and authentication settings for the MCP process."""

    def __init__(
        self,
        *,
        transport: str = "stdio",
        host: str = "127.0.0.1",
        port: int = 8001,
        workspace: str | None = None,
        api_key: str | None = None,
        lightrag_argv: tuple[str, ...] = (),
    ):
        self.transport = transport
        self.host = host
        self.port = port
        self.workspace = workspace
        self.api_key = api_key
        self.lightrag_argv = lightrag_argv

    @classmethod
    def from_env(cls) -> "MCPServerSettings":
        load_dotenv(dotenv_path=".env", override=False)
        workspace = os.getenv("MCP_WORKSPACE")
        if workspace is None:
            workspace = os.getenv("WORKSPACE")
        api_key = os.getenv("MCP_API_KEY") or os.getenv("LIGHTRAG_API_KEY")
        return cls(
            transport=os.getenv("MCP_TRANSPORT", "stdio").strip().lower(),
            host=os.getenv("MCP_HOST", "127.0.0.1"),
            port=int(os.getenv("MCP_PORT", "8001")),
            workspace=workspace,
            api_key=api_key,
        )


def _parse_args() -> MCPServerSettings:
    load_dotenv(dotenv_path=".env", override=False)
    parser = argparse.ArgumentParser(description="LightRAG FastMCP server")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default=os.getenv("MCP_TRANSPORT", "stdio"),
    )
    parser.add_argument("--host", default=os.getenv("MCP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MCP_PORT", "8001")))
    parser.add_argument("--workspace", default=os.getenv("MCP_WORKSPACE"))
    parser.add_argument("--api-key", default=os.getenv("MCP_API_KEY"))
    args, lightrag_argv = parser.parse_known_args()
    workspace = args.workspace if args.workspace is not None else os.getenv("WORKSPACE")
    api_key = args.api_key or os.getenv("LIGHTRAG_API_KEY")
    return MCPServerSettings(
        transport=args.transport,
        host=args.host,
        port=args.port,
        workspace=workspace,
        api_key=api_key,
        lightrag_argv=tuple(lightrag_argv),
    )


def main() -> None:
    settings = _parse_args()
    server = create_mcp_server(settings)
    if settings.transport == "stdio":
        server.run(transport="stdio")
        return

    server.run(
        transport="http",
        host=settings.host,
        port=settings.port,
    )


if __name__ == "__main__":
    main()
