from typing import Dict

from fastmcp import FastMCP

from infrastructure.settings import get_settings

settings = get_settings()

mcp = FastMCP(name=settings.app_name)

query_mcp_app = mcp.http_app(path="/mcp")


@mcp.tool
def echo(text: str) -> Dict[str, str]:
    """Echo the input text back to the caller.

    Returns a dictionary containing the echoed text under the 'response' key.
    """
    return {"response": text}
