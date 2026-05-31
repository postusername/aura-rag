import os
from abc import ABC, abstractmethod

import httpx


class BaseEmbedder(ABC):
    @abstractmethod
    async def embed(self, text: str, task: str = "document") -> list[float]:
        """Embed a single text. task: 'document', 'query', or 'code'."""

    async def embed_batch(self, texts: list[str], task: str = "document") -> list[list[float]]:
        results = []
        for text in texts:
            results.append(await self.embed(text, task))
        return results


class GoogleEmbedder(BaseEmbedder):
    # Official endpoint: https://ai.google.dev/api/embeddings
    _BASE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent"

    _TASK_MAP = {
        "document": "RETRIEVAL_DOCUMENT",
        "query": "RETRIEVAL_QUERY",
        "code": "CODE_RETRIEVAL_QUERY",
    }

    def __init__(self, model: str, api_key: str, dimensions: int = 768):
        self.model = model
        self.api_key = api_key
        self.dimensions = dimensions
        self._url = self._BASE.format(model=model)

    async def embed(self, text: str, task: str = "document") -> list[float]:
        task_type = self._TASK_MAP.get(task, "RETRIEVAL_DOCUMENT")
        payload = {
            "content": {"parts": [{"text": text}]},
            "embedContentConfig": {
                "taskType": task_type,
                "outputDimensionality": self.dimensions,
            },
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                self._url,
                json=payload,
                headers={"x-goog-api-key": self.api_key},
            )
            resp.raise_for_status()
        return resp.json()["embedding"]["values"]

    async def embed_batch(self, texts: list[str], task: str = "document") -> list[list[float]]:
        # Google doesn't have a batch endpoint for embedContent; call sequentially
        results = []
        for text in texts:
            results.append(await self.embed(text, task))
        return results

    async def ping(self) -> bool:
        try:
            await self.embed("test", "query")
            return True
        except Exception:
            return False


class OllamaEmbedder(BaseEmbedder):
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def embed(self, text: str, task: str = "document") -> list[float]:
        payload = {"model": self.model, "input": text}
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{self.base_url}/api/embed", json=payload)
            resp.raise_for_status()
        return resp.json()["embeddings"][0]

    async def ping(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False


def create_embedder(config: dict) -> BaseEmbedder:
    provider = config.get("provider", "google")
    model = config.get("model", "gemini-embedding-2")
    dimensions = config.get("dimensions", 768)

    if provider == "google":
        api_key = os.environ.get("GOOGLE_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY environment variable is not set. "
                "Get a free key at https://aistudio.google.com/apikey"
            )
        return GoogleEmbedder(model=model, api_key=api_key, dimensions=dimensions)

    if provider == "ollama":
        ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        return OllamaEmbedder(base_url=ollama_url, model=model)

    raise ValueError(f"Unknown embedding provider: '{provider}'. Supported: 'google', 'ollama'")
