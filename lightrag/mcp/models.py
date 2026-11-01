"""Input models for the read-only LightRAG MCP tools."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from lightrag.api.routers.query_routes import QueryRequest


class MCPQueryRequest(BaseModel):
    """Public query options exposed to MCP clients.

    Validation that is shared with the REST API is delegated to
    ``QueryRequest`` before a query reaches ``LightRAG``. Streaming and
    server-only prompt controls are intentionally not exposed here.
    """

    query: str = Field(description="Question or search phrase for the knowledge base")
    mode: Literal["local", "global", "hybrid", "naive", "mix"] = Field(
        default="mix",
        description="Retrieval mode; mix is recommended for most questions",
    )
    response_type: Optional[str] = Field(
        default=None,
        description="Requested answer shape, for example 'Bullet Points'",
    )
    top_k: Optional[int] = Field(default=None, ge=1)
    chunk_top_k: Optional[int] = Field(default=None, ge=1)
    max_entity_tokens: Optional[int] = Field(default=None, ge=1)
    max_relation_tokens: Optional[int] = Field(default=None, ge=1)
    max_total_tokens: Optional[int] = Field(default=None, ge=1)
    hl_keywords: List[str] = Field(default_factory=list)
    ll_keywords: List[str] = Field(default_factory=list)
    conversation_history: Optional[List[Dict[str, Any]]] = None
    user_prompt: Optional[str] = None
    disable_user_prompt_prefix: Optional[bool] = None
    enable_rerank: Optional[bool] = None
    include_references: bool = True
    include_chunk_content: bool = False

    def to_query_request(self, *, force_references: bool = False) -> QueryRequest:
        """Convert to the REST query model so both protocols share validation."""

        payload = self.model_dump(exclude_none=True)
        if force_references:
            payload["include_references"] = True
        return QueryRequest.model_validate(payload)
