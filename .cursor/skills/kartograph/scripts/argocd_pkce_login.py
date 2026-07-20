#!/usr/bin/env python3
"""Log in to an ArgoCD instance's Dex/OpenShift SSO via OAuth2 Authorization
Code + PKCE, without depending on the `argocd` CLI's gRPC(-web) transport
(which is unreliable in this environment - it fails with "gRPC connection
not ready: context deadline exceeded" even though the ArgoCD REST/HTTP API
and Dex are both reachable over plain HTTPS).

Usage:
    python3 argocd_pkce_login.py <argocd-server-hostname>

Opens the SSO login URL in the local browser (same machine as this script),
runs a short-lived local HTTP listener to catch the redirect, exchanges the
code for tokens, and prints:
  - the id_token (bearer token for the ArgoCD REST API)
  - a ready-to-use `curl`/`Authorization` header example

It does NOT write to ~/.config/argocd/config, since the `argocd` CLI itself
cannot use this connection anyway. Use the printed bearer token directly
against the ArgoCD REST API, e.g.:

    curl -sS -H "Authorization: Bearer $TOKEN" \\
      "https://<server>/api/v1/applications/kartograph-stage"
"""

import base64
import hashlib
import http.server
import json
import os
import secrets
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser

CLIENT_ID = "argo-cd-cli"
CALLBACK_PATH = "/auth/callback"
PORT = 8085
SCOPE = "openid profile email groups offline_access"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    result = {}

    def do_GET(self):  # noqa: N802 (stdlib method name)
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != CALLBACK_PATH:
            self.send_response(404)
            self.end_headers()
            return
        params = urllib.parse.parse_qs(parsed.query)
        _CallbackHandler.result["code"] = params.get("code", [None])[0]
        _CallbackHandler.result["state"] = params.get("state", [None])[0]
        _CallbackHandler.result["error"] = params.get("error_description", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        body = "Login successful, you can close this tab." if _CallbackHandler.result.get("code") else "Login failed - check the terminal."
        self.wfile.write(f"<html><body><h3>{body}</h3></body></html>".encode())

    def log_message(self, *_args):
        pass  # keep stdout clean; caller reports progress explicitly


def login(server_host: str, timeout_seconds: int = 180) -> dict:
    verifier = _b64url(os.urandom(32))
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    state = secrets.token_urlsafe(16)
    redirect_uri = f"http://localhost:{PORT}{CALLBACK_PATH}"
    base = f"https://{server_host}/api/dex"

    auth_url = f"{base}/auth?" + urllib.parse.urlencode(
        {
            "client_id": CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SCOPE,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
    )

    httpd = http.server.HTTPServer(("127.0.0.1", PORT), _CallbackHandler)
    httpd.timeout = timeout_seconds
    server_thread = threading.Thread(target=httpd.handle_request, daemon=True)
    server_thread.start()

    print(f"Open this URL in your browser to log in via OpenShift SSO:\n\n  {auth_url}\n")
    webbrowser.open(auth_url)
    print(f"Waiting up to {timeout_seconds}s for you to complete the login...")

    server_thread.join(timeout=timeout_seconds)
    result = _CallbackHandler.result
    if not result.get("code"):
        raise RuntimeError(f"Login did not complete: {result.get('error') or 'timed out waiting for callback'}")
    if result.get("state") != state:
        raise RuntimeError("State mismatch - possible CSRF, aborting.")

    token_req = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "code": result["code"],
            "redirect_uri": redirect_uri,
            "client_id": CLIENT_ID,
            "code_verifier": verifier,
        }
    ).encode()
    req = urllib.request.Request(
        f"{base}/token",
        data=token_req,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        tokens = json.loads(resp.read())

    print("Login successful.")
    return tokens


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <argocd-server-hostname>", file=sys.stderr)
        sys.exit(1)

    tokens = login(sys.argv[1])
    print(f"\nid_token (use as Bearer token against the ArgoCD REST API):\n\n{tokens['id_token']}\n")
