import hashlib
import os
import re

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


async def _get_documents(
    space_ids: list[int],
    document_group_ids: list[str],
) -> list[dict]:
    """Fetch all documents, optionally scoped to spaces and filtered by group UIDs."""
    all_docs: list[dict] = []

    async with httpx.AsyncClient(timeout=30) as client:
        if space_ids:
            for space_id in space_ids:
                resp = await client.get(
                    _kaiten_url(f"/spaces/{space_id}/documents"),
                    headers=_kaiten_headers(),
                )
                if resp.status_code == 200:
                    all_docs.extend(resp.json())
        else:
            # No space filter — fetch all documents
            resp = await client.get(_kaiten_url("/documents"), headers=_kaiten_headers())
            if resp.status_code == 200:
                all_docs.extend(resp.json())

    # Deduplicate
    seen: set[str] = set()
    unique: list[dict] = []
    for d in all_docs:
        uid = d.get("uid") or d.get("id")
        if uid and uid not in seen:
            seen.add(uid)
            unique.append(d)

    # Filter by document group if specified (group_id is a UUID string)
    if document_group_ids:
        group_set = set(document_group_ids)
        unique = [d for d in unique if d.get("group_id") in group_set]

    return unique


async def _get_document_content(doc_uid: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(_kaiten_url(f"/documents/{doc_uid}"), headers=_kaiten_headers())
        if resp.status_code == 200:
            return resp.json().get("content", "")
    return ""


async def _get_cards(board_ids: list[int]) -> list[dict]:
    cards: list[dict] = []
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
    """Fetch Kaiten docs + cards for a domain, chunk, embed, return Qdrant point dicts."""
    kaiten_cfg = domain["kaiten"]
    space_ids: list[int] = kaiten_cfg.get("space_ids", [])
    group_ids: list[str] = kaiten_cfg.get("document_group_ids", [])
    board_ids: list[int] = kaiten_cfg.get("card_board_ids", [])
    points: list[dict] = []

    docs = await _get_documents(space_ids, group_ids)

    for doc in docs:
        doc_uid = doc.get("uid") or doc.get("id")
        content = await _get_document_content(doc_uid)
        if not content.strip():
            continue
        title = doc.get("title", f"Document {doc_uid}")
        for chunk in _chunk_text(content, chunk_size, chunk_overlap):
            task = "code" if _is_code_chunk(chunk) else "document"
            vector = await embedder.embed(chunk, task)
            chunk_id = hashlib.md5(f"doc:{doc_uid}:{chunk[:50]}".encode()).hexdigest()
            points.append(
                {
                    "id": chunk_id,
                    "vector": vector,
                    "payload": {
                        "title": title,
                        "source": "document",
                        "kaiten_id": doc_uid,
                        "text": chunk,
                        "url": doc.get("url", ""),
                    },
                }
            )

    cards = await _get_cards(board_ids)
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
                    "kaiten_id": str(card["id"]),
                    "text": text[:1500],
                    "url": card.get("url", ""),
                },
            }
        )

    return points
