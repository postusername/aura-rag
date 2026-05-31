import asyncio
import math
from typing import TypedDict


class ClassificationResult(TypedDict):
    domain_id: str
    confidence: float
    scores: dict[str, float]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class DomainClassifier:
    def __init__(self, embedder):
        self._embedder = embedder
        self._domain_vectors: dict[str, list[float]] = {}
        self._domains: list[dict] = []

    async def load_domains(self, domains: list[dict]) -> None:
        self._domains = domains
        self._domain_vectors = {}
        for domain in domains:
            vector = await self._embedder.embed(domain["description"], task="document")
            self._domain_vectors[domain["id"]] = vector

    async def classify(self, query: str) -> ClassificationResult:
        if not self._domain_vectors:
            raise RuntimeError("No domains loaded. Call load_domains() first.")

        query_vector = await self._embedder.embed(query, task="query")

        scores: dict[str, float] = {}
        for domain_id, domain_vector in self._domain_vectors.items():
            scores[domain_id] = max(0.0, _cosine(query_vector, domain_vector))

        total = sum(scores.values())
        best_id = max(scores, key=lambda k: scores[k])
        confidence = scores[best_id] / total if total > 0 else 0.0

        return ClassificationResult(
            domain_id=best_id,
            confidence=round(confidence, 3),
            scores={k: round(v, 3) for k, v in scores.items()},
        )

    def is_ready(self) -> bool:
        return bool(self._domain_vectors)
