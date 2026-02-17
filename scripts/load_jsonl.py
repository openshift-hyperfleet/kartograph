#!/usr/bin/env python3
"""Load JSONL file to Kartograph with Keycloak OAuth authentication.

This script:
- Loads config from env/api.env
- Caches Keycloak tokens in ~/.kartograph/token.json
- Prompts for credentials only when token expires
- Fetches available tenants and presents an interactive picker
- Posts JSONL file to graph mutations endpoint with X-Tenant-ID header

Usage:
    ./scripts/load_jsonl.py <file.jsonl>
    ./scripts/load_jsonl.py <file.jsonl> --force-auth  # Ignore cached token
    ./scripts/load_jsonl.py <file.jsonl> --tenant-id <ULID>  # Skip tenant picker
    ./scripts/load_jsonl.py <file.jsonl> --api-url http://staging:8000
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from getpass import getpass
from pathlib import Path

import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

# Load environment from env/api.env
env_file = Path(__file__).parent.parent / "env" / "api.env"
load_dotenv(env_file)

TOKEN_CACHE = Path.home() / ".kartograph" / "token.json"


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Load JSONL file to Kartograph with OAuth authentication",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s data.jsonl
  %(prog)s data.jsonl --force-auth
  %(prog)s data.jsonl --tenant-id 01HXYZ...
  %(prog)s data.jsonl --api-url http://staging:8000
  %(prog)s data.jsonl --keycloak-url http://keycloak:8080/realms/prod
        """,
    )

    parser.add_argument("file", type=Path, help="JSONL file to load")

    # Config overrides
    parser.add_argument(
        "--api-url",
        default=os.getenv("KARTOGRAPH_API_URL", "http://localhost:8000"),
        help="Kartograph API base URL (default: from env or http://localhost:8000)",
    )
    parser.add_argument(
        "--keycloak-url",
        default=os.getenv(
            "KARTOGRAPH_OIDC_ISSUER_URL", "http://localhost:8080/realms/kartograph"
        ),
        help="Keycloak issuer URL (default: from env or http://localhost:8080/realms/kartograph)",
    )
    parser.add_argument(
        "--client-id",
        default=os.getenv("KARTOGRAPH_OIDC_CLIENT_ID", "kartograph-api"),
        help="OIDC client ID (default: from env or kartograph-api)",
    )
    parser.add_argument(
        "--client-secret",
        default=os.getenv("KARTOGRAPH_OIDC_CLIENT_SECRET", "kartograph-api-secret"),
        help="OIDC client secret (default: from env or kartograph-api-secret)",
    )

    # Tenant selection
    parser.add_argument(
        "--tenant-id",
        default=None,
        help="Tenant ID to use (skips interactive picker)",
    )

    # Auth options
    parser.add_argument(
        "--force-auth",
        action="store_true",
        help="Force re-authentication (ignore cached token)",
    )

    return parser.parse_args()


def get_cached_token(force_auth: bool = False) -> str | None:
    """Get cached token if still valid."""
    if force_auth:
        console.print("[yellow]Ignoring cached token (--force-auth)[/yellow]")
        return None

    if not TOKEN_CACHE.exists():
        return None

    try:
        data = json.loads(TOKEN_CACHE.read_text())
        expires_at = datetime.fromisoformat(data["expires_at"])
        if datetime.now() < expires_at:
            return data["access_token"]
    except (json.JSONDecodeError, KeyError, ValueError):
        pass

    return None


def fetch_new_token(keycloak_url: str, client_id: str, client_secret: str) -> str:
    """Fetch new token using password grant flow."""
    console.print("\n[bold cyan]Authentication Required[/bold cyan]")
    username = console.input("[bold]Username:[/bold] ")
    password = getpass("Password: ")

    token_url = f"{keycloak_url}/protocol/openid-connect/token"

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Authenticating with Keycloak...", total=None)

        response = requests.post(
            token_url,
            data={
                "grant_type": "password",
                "client_id": client_id,
                "client_secret": client_secret,
                "username": username,
                "password": password,
            },
            timeout=10,
        )

    if response.status_code != 200:
        console.print(
            f"[bold red]Authentication failed:[/bold red] {response.status_code}"
        )
        console.print(response.text)
        sys.exit(1)

    token_data = response.json()

    # Cache token (with 60s safety margin before expiry)
    TOKEN_CACHE.parent.mkdir(parents=True, exist_ok=True)
    expires_in = token_data.get("expires_in", 300)
    cache_data = {
        "access_token": token_data["access_token"],
        "expires_at": (datetime.now() + timedelta(seconds=expires_in - 60)).isoformat(),
    }
    TOKEN_CACHE.write_text(json.dumps(cache_data, indent=2))
    console.print(f"[green]✓[/green] Token cached to {TOKEN_CACHE}")

    return token_data["access_token"]


def get_token(
    keycloak_url: str, client_id: str, client_secret: str, force_auth: bool = False
) -> str:
    """Get valid token (from cache or new auth)."""
    token = get_cached_token(force_auth)
    if token:
        console.print("[green]✓[/green] Using cached token")
        return token

    return fetch_new_token(keycloak_url, client_id, client_secret)


def fetch_tenants(token: str, api_url: str) -> list[dict]:
    """Fetch tenants the authenticated user has access to."""
    endpoint = f"{api_url}/iam/tenants"

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Fetching tenants...", total=None)

        response = requests.get(
            endpoint,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )

    if response.status_code >= 400:
        console.print(
            f"[bold red]Failed to fetch tenants:[/bold red] {response.status_code}"
        )
        console.print(response.text)
        sys.exit(1)

    return response.json()


def pick_tenant(tenants: list[dict], tenant_id_override: str | None) -> str:
    """Select a tenant, either from CLI arg or interactive picker.

    Returns the selected tenant ID.
    """
    if not tenants:
        console.print("[bold red]Error:[/bold red] No tenants available for your user")
        sys.exit(1)

    # If --tenant-id was provided, validate it exists in the user's tenants
    if tenant_id_override:
        matching = [t for t in tenants if t["id"] == tenant_id_override]
        if not matching:
            console.print(
                f"[bold red]Error:[/bold red] Tenant '{tenant_id_override}' "
                "not found or you don't have access"
            )
            sys.exit(1)
        tenant = matching[0]
        console.print(
            f"[green]✓[/green] Using tenant: [bold]{tenant['name']}[/bold] ({tenant['id']})"
        )
        return tenant["id"]

    # Single tenant — auto-select
    if len(tenants) == 1:
        tenant = tenants[0]
        console.print(
            f"[green]✓[/green] Using tenant: [bold]{tenant['name']}[/bold] ({tenant['id']})"
        )
        return tenant["id"]

    # Multiple tenants — interactive picker
    console.print("\n[bold cyan]Select a Tenant[/bold cyan]")
    for i, tenant in enumerate(tenants, 1):
        console.print(
            f"  [bold]{i}.[/bold] {tenant['name']} [dim]({tenant['id']})[/dim]"
        )

    while True:
        choice = console.input(f"\n[bold]Tenant [1-{len(tenants)}]:[/bold] ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(tenants):
                selected = tenants[idx]
                console.print(
                    f"[green]✓[/green] Selected: [bold]{selected['name']}[/bold] ({selected['id']})"
                )
                return selected["id"]
        except ValueError:
            pass
        console.print(
            f"[yellow]Please enter a number between 1 and {len(tenants)}[/yellow]"
        )


def post_jsonl(file_path: Path, token: str, api_url: str, tenant_id: str) -> None:
    """Post JSONL file to graph mutations endpoint."""
    if not file_path.exists():
        console.print(f"[bold red]Error:[/bold red] File not found: {file_path}")
        sys.exit(1)

    endpoint = f"{api_url}/graph/mutations"
    file_size = file_path.stat().st_size
    console.print(
        f"\n[bold]Posting[/bold] {file_path.name} ({file_size:,} bytes) to {endpoint}"
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Uploading...", total=None)

        with open(file_path, "rb") as f:
            response = requests.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/jsonlines",
                    "X-Tenant-ID": tenant_id,
                },
                data=f,
                timeout=300,
            )

    if response.status_code >= 400:
        console.print(f"\n[bold red]Request failed:[/bold red] {response.status_code}")
        console.print(response.text)
        sys.exit(1)
    else:
        console.print(
            f"\n[bold green]Success![/bold green] Status: {response.status_code}"
        )
        if response.text:
            console.print(response.text)


def main():
    """Main entry point."""
    args = parse_args()

    console.print("[bold cyan]Kartograph JSONL Loader[/bold cyan]")
    console.print(f"[dim]API: {args.api_url}[/dim]")
    console.print(f"[dim]Keycloak: {args.keycloak_url}[/dim]\n")

    token = get_token(
        keycloak_url=args.keycloak_url,
        client_id=args.client_id,
        client_secret=args.client_secret,
        force_auth=args.force_auth,
    )

    tenants = fetch_tenants(token, args.api_url)
    tenant_id = pick_tenant(tenants, args.tenant_id)
    post_jsonl(args.file, token, args.api_url, tenant_id)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Interrupted by user[/yellow]")
        sys.exit(130)  # Standard exit code for Ctrl+C
