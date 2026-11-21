import json
from typing import Any

__all__ = [
    "CLAUDE_DOCUMENT",
    "CLAUDE_ID",
    "CLAUDE_RETURN",
    "VSCODE_DOCUMENT",
    "VSCODE_ID",
    "document_bytes",
]

CLAUDE_ID = "https://claude.ai/oauth/mcp-oauth-client-metadata"
CLAUDE_RETURN = "https://claude.ai/api/mcp/auth_callback"
CLAUDE_DOCUMENT: dict[str, Any] = {
    "client_id": CLAUDE_ID,
    "client_name": "Claude",
    "client_uri": "https://claude.ai",
    "redirect_uris": [CLAUDE_RETURN],
    "grant_types": ["authorization_code", "refresh_token", "urn:ietf:params:oauth:grant-type:jwt-bearer"],
    "response_types": ["code"],
    "token_endpoint_auth_method": "none",
}
VSCODE_ID = "https://vscode.dev/oauth/client-metadata.json"
VSCODE_DOCUMENT: dict[str, Any] = {
    "client_name": "Visual Studio Code",
    "logo_uri": "https://code.visualstudio.com/assets/branding/code-stable.png",
    "grant_types": ["authorization_code", "refresh_token", "urn:ietf:params:oauth:grant-type:device_code"],
    "response_types": ["code"],
    "token_endpoint_auth_method": "none",
    "application_type": "native",
    "client_id": VSCODE_ID,
    "client_uri": "https://vscode.dev/product",
    "redirect_uris": ["http://127.0.0.1:33418/", "https://vscode.dev/redirect"],
}


def document_bytes(document: dict[str, Any], **changes: Any) -> bytes:
    return json.dumps(document | changes).encode("utf-8")
