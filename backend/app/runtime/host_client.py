import httpx

from app.runtime.schemas import HostAgentStatus


class HostManagerClient:
    def __init__(self, base_url: str, api_key: str, timeout_s: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_s = timeout_s

    async def _request(
        self,
        method: str,
        path: str,
        json: dict | None = None,
    ) -> HostAgentStatus:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(
            headers={"x-api-key": self.api_key},
            timeout=self.timeout_s,
        ) as client:
            response = await client.request(method, url, json=json)
            response.raise_for_status()
        return HostAgentStatus.model_validate(response.json())

    async def ensure(self, agent_id: str) -> HostAgentStatus:
        return await self._request("POST", f"/agents/{agent_id}/ensure")

    async def stop(self, agent_id: str) -> HostAgentStatus:
        return await self._request("POST", f"/agents/{agent_id}/stop")

    async def status(self, agent_id: str) -> HostAgentStatus:
        return await self._request("GET", f"/agents/{agent_id}/status")
