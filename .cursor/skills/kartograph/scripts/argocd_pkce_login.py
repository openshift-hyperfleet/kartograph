#!/usr/bin/env python3
"""Manual OAuth2/PKCE login against ArgoCD's Dex, bypassing the broken `argocd login --sso` CLI.

Usage:
    /usr/bin/python3 argocd_pkce_login.py [--server SERVER] [--out TOKEN_FILE]

Prints an authorization URL to open in a browser, waits for the local
callback, exchanges the code for tokens, and writes the id_token (the same
value the argocd CLI stores as its auth token) to TOKEN_FILE.

Use /usr/bin/python3 explicitly - a shadowed/wrapped `python3` in some shells
has been observed to fail silently here.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import json
import secrets
import urllib.parse
import urllib.request

DEFAULT_SERVER = (
    "argocd-server-argocd-tenant-control-plane.apps.rosa.appsres09ue1.24ep.p3.openshiftapps.com"
)
CLIENT_ID = "argo-cd-cli"
CALLBACK_PORT = 8085
# Must be exactly this path - Dex rejects any other redirect_uri as unregistered
# even though the argocd CLI's own local server also listens on /callback for
# other flows.
CALLBACK_PATH = "/auth/callback"


def build_pkce_pair() -> tuple[str, str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    state = secrets.token_urlsafe(16)
    return verifier, challenge, state


def wait_for_callback() -> dict[str, str | None]:
    result: dict[str, str | None] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != CALLBACK_PATH:
                self.send_response(404)
                self.end_headers()
                return
            qs = urllib.parse.parse_qs(parsed.query)
            result["code"] = qs.get("code", [None])[0]
            result["state"] = qs.get("state", [None])[0]
            result["error"] = qs.get("error", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body>Login captured, you can close this tab.</body></html>")

        def log_message(self, *_args: object) -> None:
            pass

    server = http.server.HTTPServer(("127.0.0.1", CALLBACK_PORT), Handler)
    server.timeout = 180
    while "code" not in result and "error" not in result:
        server.handle_request()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default=DEFAULT_SERVER)
    parser.add_argument("--out", default="/tmp/argocd_token.txt")
    args = parser.parse_args()

    verifier, challenge, state = build_pkce_pair()
    redirect_uri = f"http://localhost:{CALLBACK_PORT}{CALLBACK_PATH}"
    auth_params = {
        "client_id": CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid profile email groups offline_access",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    auth_url = f"https://{args.server}/api/dex/auth?{urllib.parse.urlencode(auth_params)}"
    print(f"Open this URL in a browser and complete SSO login:\n\n{auth_url}\n")
    print("Waiting for callback on 127.0.0.1:8085 ...")

    result = wait_for_callback()
    if result.get("error"):
        raise SystemExit(f"Dex returned an error: {result}")
    if result.get("state") != state:
        raise SystemExit("State mismatch - possible CSRF, aborting")

    token_params = {
        "grant_type": "authorization_code",
        "code": result["code"],
        "redirect_uri": redirect_uri,
        "client_id": CLIENT_ID,
        "code_verifier": verifier,
    }
    req = urllib.request.Request(
        f"https://{args.server}/api/dex/token",
        data=urllib.parse.urlencode(token_params).encode(),
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        tokens = json.load(resp)

    id_token = tokens["id_token"]
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(id_token)
    print(f"id_token written to {args.out} ({len(id_token)} chars)")
    print(
        "\nUse it against the REST API, e.g.:\n"
        f'  curl -s -H "Authorization: Bearer $(cat {args.out})" '
        f'"https://{args.server}/api/v1/applications"'
    )


if __name__ == "__main__":
    main()
