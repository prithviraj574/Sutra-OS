from pydantic import BaseModel

from fastapi import APIRouter, Depends

from api.deps import get_config
from config import Config

router = APIRouter(prefix="/v1/config", tags=["config"])


class OpenApiTsConfig(BaseModel):
    input: str
    output: str
    client: str


@router.get("/openapi-ts", response_model=OpenApiTsConfig)
async def get_openapi_ts_config(config: Config = Depends(get_config)) -> OpenApiTsConfig:
    return OpenApiTsConfig(
        input=config.app.openapi_url,
        output="./src/api/generated",
        client="@hey-api/client-fetch",
    )
