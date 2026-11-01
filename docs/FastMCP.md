# LightRAG FastMCP Server

The optional `mcp` extra provides a standalone, read-only MCP server. It uses
one fixed LightRAG workspace and exposes `rag_query`, `rag_retrieve`, and
`rag_health` tools.

## Install

```powershell
uv sync --extra mcp
```

## Configuration

The server reads the normal LightRAG `.env` configuration and these MCP-specific
variables:

```text
MCP_TRANSPORT=stdio
MCP_WORKSPACE=default
MCP_API_KEY=
MCP_HOST=127.0.0.1
MCP_PORT=8001
```

`MCP_API_KEY` protects HTTP tool calls. `LIGHTRAG_API_KEY` is used as a
fallback. stdio is intended for local clients and does not have HTTP headers;
therefore, configure the API key only when using Streamable HTTP.

## Start

stdio:

```powershell
lightrag-mcp --transport stdio
```

Streamable HTTP:

```powershell
lightrag-mcp --transport streamable-http --host 127.0.0.1 --port 8001
```

FastMCP's `http` transport is used internally for the Streamable HTTP mode.

The process initializes and finalizes the LightRAG storages with the same
lifecycle as the existing API server. MCP only exposes read-only query tools;
document ingestion, deletion, graph editing, and `bypass` mode are not
available.
