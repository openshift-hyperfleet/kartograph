from fastmcp import FastMCP
from infrastructure.settings import get_settings

settings = get_settings()

mcp = FastMCP(name=settings.app_name)

query_mcp_app = mcp.http_app(path="/mcp")


@mcp.tool
def echo(input: str):
    return {"response": input}
