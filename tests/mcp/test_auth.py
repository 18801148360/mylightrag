import pytest

from lightrag.mcp.auth import MCPAuthenticationError, verify_api_key


class _Request:
    def __init__(self, headers):
        self.headers = headers


class _Context:
    def __init__(self, headers):
        self.request = _Request(headers)

    def get_http_request(self):
        return self.request


def test_api_key_accepts_bearer_header():
    verify_api_key(_Context({"authorization": "Bearer secret"}), "secret")


def test_api_key_accepts_x_api_key_header():
    verify_api_key(_Context({"x-api-key": "secret"}), "secret")


def test_api_key_rejects_invalid_key():
    with pytest.raises(MCPAuthenticationError):
        verify_api_key(_Context({"x-api-key": "wrong"}), "secret")
