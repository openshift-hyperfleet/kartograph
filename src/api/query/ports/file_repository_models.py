from pydantic import BaseModel


class RemoteFileRepositoryResponse(BaseModel):
    success: bool
    error: str | None = None
    content: str | None = None
    source_url: str | None = None
    raw_url: str | None = None
