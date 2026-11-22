import json
from typing import Any

__all__ = [
    "CHATGPT_DOCUMENT",
    "CHATGPT_ID",
    "CHATGPT_RETURN",
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
CHATGPT_ID = "https://chatgpt.com/oauth/client.json"
CHATGPT_RETURN = "https://chatgpt.com/connector_platform_oauth_redirect"
CHATGPT_DOCUMENT: dict[str, Any] = {
    "client_id": CHATGPT_ID,
    "client_uri": "https://chatgpt.com/",
    "redirect_uris": [CHATGPT_RETURN],
    "token_endpoint_auth_method": "private_key_jwt",
    "token_endpoint_auth_methods_supported": ["none", "private_key_jwt"],
    "grant_types": ["authorization_code", "refresh_token", "urn:ietf:params:oauth:grant-type:jwt-bearer"],
    "response_types": ["code"],
    "client_name": "ChatGPT",
    "logo_uri": "https://persistent.oaistatic.com/sonic/misc/openai-logo.png",
    "token_endpoint_auth_signing_alg": "RS256",
    "jwks_uri": "https://chatgpt.com/oauth/jwks.json",
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
