from lightrag.mcp.models import MCPQueryRequest


def test_mcp_query_request_reuses_rest_validation_and_forces_non_streaming():
    request = MCPQueryRequest(query="What is retrieval augmented generation?")

    query_request = request.to_query_request()
    query_params = query_request.to_query_params(False)

    assert query_request.mode == "mix"
    assert query_params.stream is False


def test_mcp_retrieve_always_includes_references():
    request = MCPQueryRequest(
        query="Explain the knowledge graph",
        include_references=False,
    )

    query_request = request.to_query_request(force_references=True)

    assert query_request.include_references is True
