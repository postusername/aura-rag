import hashlib
import os
import re
from typing import AsyncIterator

import httpx

KAITEN_BASE = "https://{domain}.kaiten.ru/api/v1"
_CODE_FENCE_RE = re.compile(r"```[\s\S]*?```")
_HIGH_SYMBOL_RE = re.compile(r"[{}\[\]()<>;=+\-*/|&!@#$%^~`\\]")


def _kaiten_headers() -> dict:
    token = os.environ.get("KAITEN_TOKEN", "")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _kaiten_url(path: str) -> str:
    domain = os.environ.get("KAITEN_DOMAIN", "")
    return KAITEN_BASE.format(domain=domain) + path


def _is_code_chunk(text: str) -> bool:
    if _CODE_FENCE_RE.search(text):
        return True
    symbols = len(_HIGH_SYMBOL_RE.findall(text))
    return symbols / max(len(text), 1) > 0.15


def _chunk_text(text: str, size: int = 1500, overlap: int = 200) -> list[str]:
    if len(text) <= size:
        return [text] if text.strip() else []
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        start = end - overlap
    return chunks


async def _get_all_documents(space_ids: list[int], group_ids: list[int]) -> list[dict]:
    docs = []
    async with httpx.AsyncClient(timeout=30) as client:
        if space_ids:
            for space_id in space_ids:
                resp = await client.get(
                    _kaiten_url(f"/spaces/{space_id}/documents"),
                    headers=_kaiten_headers(),
                )
                if resp.status_code == 200:
                    docs.extend(resp.json())
        if group_ids:
            for group_id in group_ids:
                resp = await client.get(
                    _kaiten_url(f"/document-groups/{group_id}/documents"),
                    headers=_kaiten_headers(),
                )
                if resp.status_code == 200:
                    docs.extend(resp.json())
        if not space_ids and not group_ids:
            resp = await client.get(_kaiten_url("/documents"), headers=_kaiten_headers())
            if resp.status_code == 200:
                docs.extend(resp.json())
    seen = set()
    unique = []
    for d in docs:
        if d["id"] not in seen:
            seen.add(d["id"])
            unique.append(d)
    return unique


async def _get_document_content(doc_id: int) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(_kaiten_url(f"/documents/{doc_id}"), headers=_kaiten_headers())
        if resp.status_code == 200:
            return resp.json().get("content", "")
    return ""


async def _get_cards(board_ids: list[int]) -> list[dict]:
    cards = []
    async with httpx.AsyncClient(timeout=30) as client:
        if board_ids:
            for board_id in board_ids:
                resp = await client.get(
                    _kaiten_url(f"/boards/{board_id}/cards"),
                    headers=_kaiten_headers(),
                )
                if resp.status_code == 200:
                    cards.extend(resp.json())
        else:
            resp = await client.get(_kaiten_url("/cards"), headers=_kaiten_headers())
            if resp.status_code == 200:
                cards.extend(resp.json())
    return cards


async def build_points(
    domain: dict,
    embedder,
    chunk_size: int = 1500,
    chunk_overlap: int = 200,
) -> list[dict]:
    """Fetch Kaiten docs + cards, chunk, embed, return Qdrant point dicts."""
    kaiten_cfg = domain["kaiten"]
    points = []

    docs = await _get_all_documents(
        kaiten_cfg.get("space_ids", []),
        kaiten_cfg.get("document_group_ids", []),
    )

    for doc in docs:
        content = await _get_document_content(doc["id"])
        if not content.strip():
            continue
        title = doc.get("title", f"Document {doc['id']}")
        for chunk in _chunk_text(content, chunk_size, chunk_overlap):
            task = "code" if _is_code_chunk(chunk) else "document"
            vector = await embedder.embed(chunk, task)
            chunk_id = hashlib.md5(f"doc:{doc['id']}:{chunk[:50]}".encode()).hexdigest()
            points.append(
                {
                    "id": chunk_id,
                    "vector": vector,
                    "payload": {
                        "title": title,
                        "source": "document",
                        "kaiten_id": doc["id"],
                        "text": chunk,
                        "url": doc.get("url", ""),
                    },
                }
            )

    cards = await _get_cards(kaiten_cfg.get("card_board_ids", []))
    for card in cards:
        description = card.get("description", "") or ""
        title = card.get("title", f"Card {card['id']}")
        text = f"{title}\n\n{description}".strip()
        if not text:
            continue
        task = "code" if _is_code_chunk(text) else "document"
        vector = await embedder.embed(text, task)
        card_id = hashlib.md5(f"card:{card['id']}".encode()).hexdigest()
        points.append(
            {
                "id": card_id,
                "vector": vector,
                "payload": {
                    "title": title,
                    "source": "card",
                    "kaiten_id": card["id"],
                    "text": text[:1500],
                    "url": card.get("url", ""),
                },
            }
        )

    return points
