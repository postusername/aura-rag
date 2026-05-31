import os
import uuid

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)


def _client() -> AsyncQdrantClient:
    url = os.environ.get("QDRANT_URL", "http://localhost:6333")
    return AsyncQdrantClient(url=url)


def _collection_name(domain_id: str) -> str:
    return f"domain_{domain_id}"


async def ensure_collection(domain_id: str, dimensions: int) -> None:
    async with _client() as client:
        name = _collection_name(domain_id)
        existing = [c.name for c in (await client.get_collections()).collections]
        if name not in existing:
            await client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=dimensions, distance=Distance.COSINE),
            )


async def upsert_points(domain_id: str, points: list[dict]) -> int:
    """points: list of {id?, vector, payload}. Returns count upserted."""
    async with _client() as client:
        name = _collection_name(domain_id)
        qdrant_points = [
            PointStruct(
                id=p.get("id") or str(uuid.uuid4()),
                vector=p["vector"],
                payload=p.get("payload", {}),
            )
            for p in points
        ]
        await client.upsert(collection_name=name, points=qdrant_points)
        return len(qdrant_points)


async def search(
    domain_id: str,
    query_vector: list[float],
    limit: int = 5,
    score_threshold: float = 0.5,
) -> list[dict]:
    async with _client() as client:
        name = _collection_name(domain_id)
        results = await client.search(
            collection_name=name,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            with_payload=True,
        )
    return [
        {
            "id": str(r.id),
            "score": r.score,
            "title": r.payload.get("title", ""),
            "source": r.payload.get("source", ""),
            "kaiten_id": r.payload.get("kaiten_id"),
            "excerpt": r.payload.get("text", "")[:500],
            "url": r.payload.get("url", ""),
        }
        for r in results
    ]


async def search_all_domains(
    domain_ids: list[str],
    query_vector: list[float],
    limit: int = 5,
    score_threshold: float = 0.5,
) -> list[dict]:
    all_results = []
    for domain_id in domain_ids:
        try:
            results = await search(domain_id, query_vector, limit, score_threshold)
            for r in results:
                r["domain_id"] = domain_id
            all_results.extend(results)
        except Exception:
            pass
    all_results.sort(key=lambda x: x["score"], reverse=True)
    return all_results[:limit]


async def delete_collection(domain_id: str) -> bool:
    async with _client() as client:
        name = _collection_name(domain_id)
        try:
            await client.delete_collection(collection_name=name)
            return True
        except Exception:
            return False


async def get_collection_count(domain_id: str) -> int:
    async with _client() as client:
        name = _collection_name(domain_id)
        try:
            info = await client.get_collection(collection_name=name)
            return info.points_count or 0
        except Exception:
            return 0


async def clear_collection(domain_id: str, dimensions: int) -> None:
    await delete_collection(domain_id)
    await ensure_collection(domain_id, dimensions)
