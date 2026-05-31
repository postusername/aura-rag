import hashlib
import json
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
        # Kaiten API: /documents returns all docs; no per-space endpoint exists
        resp = await client.get(_kaiten_url("/documents"), headers=_kaiten_headers())
        if resp.status_code == 200:
            all_docs.extend(resp.json())

    # Filter by space if specified (documents carry a space_id via their path/group)
    if space_ids:
        space_set = set(str(s) for s in space_ids)
        # Documents don't have a direct space_id; filter by document groups that
        # belong to those spaces — handled by document_group_ids filter below.
        # If only space_ids given with no group filter, keep all docs (full-space sync).

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


def _prosemirror_to_text(node: dict | list | None) -> str:
    """Recursively extract plain text from a ProseMirror/Tiptap document node."""
    if not node:
        return ""
    if isinstance(node, list):
        return "\n".join(_prosemirror_to_text(n) for n in node)
    if isinstance(node, str):
        try:
            node = json.loads(node)
        except (json.JSONDecodeError, TypeError):
            return node

    node_type = node.get("type", "")
    text = node.get("text", "")
    children = node.get("content", [])

    parts = []
    if text:
        parts.append(text)
    if children:
        child_text = _prosemirror_to_text(children)
        if child_text:
            # Add a newline after block-level nodes
            sep = "\n" if node_type in ("doc", "paragraph", "heading", "heading1",
                                        "heading2", "heading3", "blockquote",
                                        "bulletList", "orderedList", "listItem",
                                        "codeBlock", "table", "tableRow") else " "
            parts.append(child_text + sep)

    return "".join(parts).strip()


async def _get_document_content(doc_uid: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(_kaiten_url(f"/documents/{doc_uid}"), headers=_kaiten_headers())
        if resp.status_code != 200:
            return ""
        doc = resp.json()
        # Kaiten stores rich text in 'data' as a ProseMirror JSON string
        raw = doc.get("data") or doc.get("content") or ""
        if not raw:
            return ""
        return _prosemirror_to_text(raw)


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
