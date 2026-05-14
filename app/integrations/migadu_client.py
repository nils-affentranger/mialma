import httpx
from typing import List, Dict, Any
from app.core.config import settings

class MigaduClient:
    def __init__(self):
        self.base_url = "https://api.migadu.com/v1"
        self.auth = (settings.MIGADU_USER, settings.MIGADU_TOKEN)

    async def get_domains(self) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/domains",
                auth=self.auth,
                headers={"Content-type": "application/json"}
            )
            response.raise_for_status()
            return response.json().get("domains", [])

    async def get_aliases(self, domain: str) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/domains/{domain}/aliases",
                auth=self.auth
            )
            response.raise_for_status()
            return response.json().get("address_aliases", [])

    async def create_alias(self, domain: str, local_part: str, destinations: List[str], is_internal: bool = False) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            data = {
                "local_part": local_part,
                "destinations": ",".join(destinations),
                "is_internal": str(is_internal).lower()
            }
            response = await client.post(
                f"{self.base_url}/domains/{domain}/aliases",
                auth=self.auth,
                json=data
            )
            response.raise_for_status()
            return response.json()

    async def update_alias(self, domain: str, local_part: str, destinations: List[str] = None, is_internal: bool = None, new_local_part: str = None) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            data = {}
            if destinations is not None:
                data["destinations"] = ",".join(destinations)
            if is_internal is not None:
                data["is_internal"] = str(is_internal).lower()
            if new_local_part is not None:
                data["local_part"] = new_local_part
            
            response = await client.put(
                f"{self.base_url}/domains/{domain}/aliases/{local_part}",
                auth=self.auth,
                json=data
            )
            response.raise_for_status()
            return response.json()

    async def delete_alias(self, domain: str, local_part: str) -> None:
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/domains/{domain}/aliases/{local_part}",
                auth=self.auth
            )
            response.raise_for_status()

migadu_client = MigaduClient()
