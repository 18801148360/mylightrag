"""Protocol-independent read-only query service for LightRAG MCP tools."""

from __future__ import annotations

import time
import uuid
from typing import Any

from lightrag.utils import logger

from .models import MCPQueryRequest


class MCPQueryService:
    """Translate MCP requests into stable, agent-facing query results."""

    def __init__(self, runtime: Any):
        self.runtime = runtime

    @property
    def rag(self) -> Any:
        rag = self.runtime.rag
        if rag is None:
            raise RuntimeError("LightRAG runtime is not initialized")
        return rag

    async def query(self, request: MCPQueryRequest) -> dict[str, Any]:
        validated = request.to_query_request()
        param = validated.to_query_params(False)
        param.stream = False

        started_at = time.perf_counter()
        try:
            result = await self.rag.aquery_llm(validated.query, param=param)
        except Exception as exc:
            error_id = uuid.uuid4().hex[:12]
            logger.error(
                "MCP RAG query failed [error_id=%s]: %s",
                error_id,
                exc,
                exc_info=True,
            )
            raise RuntimeError(f"RAG query failed (error_id: {error_id})") from exc

        llm_response = result.get("llm_response", {})
        data = result.get("data", {}) or {}
        answer = llm_response.get("content", "") or (
            "No relevant context found for the query."
        )
        llm_generated = bool(
            llm_response.get("llm_generated", bool(llm_response.get("content")))
        )
        references = data.get("references", []) or []

        if validated.include_references and validated.include_chunk_content:
            references = _enrich_references(references, data.get("chunks", []))
        elif not validated.include_references:
            references = []

        return {
            "answer": answer,
            "references": references,
            "metadata": {
                **(result.get("metadata", {}) or {}),
                "mode": validated.mode,
                "response_time": round(time.perf_counter() - started_at, 3),
                "llm_generated": llm_generated,
            },
        }

    async def retrieve(self, request: MCPQueryRequest) -> dict[str, Any]:
        validated = request.to_query_request(force_references=True)
        param = validated.to_query_params(False)
        param.stream = False

        started_at = time.perf_counter()
        try:
            result = await self.rag.aquery_data(validated.query, param=param)
        except Exception as exc:
            error_id = uuid.uuid4().hex[:12]
            logger.error(
                "MCP RAG retrieval failed [error_id=%s]: %s",
                error_id,
                exc,
                exc_info=True,
            )
            raise RuntimeError(f"RAG retrieval failed (error_id: {error_id})") from exc

        if not isinstance(result, dict):
            raise RuntimeError("RAG retrieval returned an invalid result")

        data = result.get("data", {}) or {}
        if validated.include_chunk_content:
            data = dict(data)
            data["references"] = _enrich_references(
                data.get("references", []) or [], data.get("chunks", []) or []
            )

        return {
            "status": result.get("status", "success"),
            "message": result.get("message", "Query executed successfully"),
            "data": data,
            "metadata": {
                **(result.get("metadata", {}) or {}),
                "mode": validated.mode,
                "response_time": round(time.perf_counter() - started_at, 3),
            },
        }

    async def health(self) -> dict[str, Any]:
        rag = self.rag
        storage_status = getattr(rag, "_storages_status", None)
        return {
            "status": "ok",
            "workspace": rag.workspace,
            "storage_initialized": getattr(storage_status, "name", "")
            == "INITIALIZED",
            "supported_modes": ["local", "global", "hybrid", "naive", "mix"],
            "read_only": True,
        }


def _enrich_references(
    references: list[dict[str, Any]], chunks: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    content_by_reference: dict[str, list[str]] = {}
    for chunk in chunks:
        reference_id = chunk.get("reference_id", "")
        content = chunk.get("content", "")
        if reference_id and content:
            content_by_reference.setdefault(reference_id, []).append(content)

    enriched = []
    for reference in references:
        reference_copy = dict(reference)
        reference_id = reference.get("reference_id", "")
        if reference_id in content_by_reference:
            reference_copy["content"] = content_by_reference[reference_id]
        enriched.append(reference_copy)
    return enriched
