import hashlib
import json
import os
import re
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.sse import sse_client

_CODE_FENCE_RE = re.compile(r"```[\s\S]*?```")
_HIGH_SYMBOL_RE = re.compile(r"[{}\[\]()<>;=+\-*/|&!@#$%^~`\\]")

_KAITEN_MCP_URL = os.environ.get("KAITEN_MCP_URL", "http://kaiten-mcp:3000/sse")


@asynccontextmanager
async def kaiten_session():
    """Yields an initialized MCP ClientSession connected to kaiten-mcp over SSE."""
    async with sse_client(url=_KAITEN_MCP_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def _call(session: ClientSession, tool: str, **kwargs) -> object:
    args = {k: v for k, v in kwargs.items() if v is not None}
    result = await session.call_tool(tool, arguments=args)
    if result.content and hasattr(result.content[0], "text"):
        try:
            return json.loads(result.content[0].text)
        except json.JSONDecodeError:
            return result.content[0].text
    return None


def _is_code_chunk(text: str) -> bool:
    if _CODE_FENCE_RE.search(text):
        return True
    return len(_HIGH_SYMBOL_RE.findall(text)) / max(len(text), 1) > 0.15


def _chunk_text(text: str, size: int = 1500, overlap: int = 200) -> list[str]:
    if len(text) <= size:
        return [text] if text.strip() else []
    chunks, start = [], 0
    while start < len(text):
        chunk = text[start : start + size]
        if chunk.strip():
            chunks.append(chunk)
        start += size - overlap
    return chunks


def _prosemirror_to_text(node) -> str:
    """Recursively extract plain text from a ProseMirror/Tiptap node."""
    if not node:
        return ""
    if isinstance(node, list):
        return "\n".join(_prosemirror_to_text(n) for n in node)
    if isinstance(node, str):
        try:
            node = json.loads(node)
        except (json.JSONDecodeError, TypeError):
            return node

    block_types = {
        "doc", "paragraph", "heading", "heading1", "heading2", "heading3",
        "blockquote", "bulletList", "orderedList", "listItem",
        "codeBlock", "table", "tableRow",
    }
    text = node.get("text", "")
    children = node.get("content", [])
    parts = [text] if text else []
    if children:
        child_text = _prosemirror_to_text(children)
        if child_text:
            sep = "\n" if node.get("type") in block_types else " "
            parts.append(child_text + sep)
    return "".join(parts).strip()


async def build_points(
    domain: dict,
    embedder,
    chunk_size: int = 1500,
    chunk_overlap: int = 200,
) -> list[dict]:
    """Fetch Kaiten docs + cards via kaiten-mcp SSE, chunk, embed, return Qdrant point dicts."""
    kaiten_cfg = domain["kaiten"]
    space_ids: list[int] = kaiten_cfg.get("space_ids", [])
    group_ids: list[str] = kaiten_cfg.get("document_group_ids", [])
    board_ids: list[int] = kaiten_cfg.get("card_board_ids", [])
    points: list[dict] = []

    async with kaiten_session() as session:
        # ── Documents ──────────────────────────────────────────────────────
        raw_docs = await _call(
            session, "kaiten_list_documents",
            space_id=space_ids[0] if space_ids else None,
        )
        docs: list[dict] = raw_docs if isinstance(raw_docs, list) else []

        if group_ids:
            group_set = set(group_ids)
            docs = [d for d in docs if d.get("group_id") in group_set]

        for doc in docs:
            uid = doc.get("uid") or doc.get("id")
            full = await _call(session, "kaiten_get_document", document_id=uid)
            if not full:
                continue
            content = _prosemirror_to_text(full.get("data") or full.get("content") or "")
            if not content.strip():
                continue
            title = doc.get("title", f"Document {uid}")
            for chunk in _chunk_text(content, chunk_size, chunk_overlap):
                task = "code" if _is_code_chunk(chunk) else "document"
                vector = await embedder.embed(chunk, task)
                chunk_id = hashlib.md5(f"doc:{uid}:{chunk[:50]}".encode()).hexdigest()
                points.append({
                    "id": chunk_id,
                    "vector": vector,
                    "payload": {
                        "title": title,
                        "source": "document",
                        "kaiten_id": str(uid),
                        "text": chunk,
                        "url": doc.get("url", ""),
                    },
                })

        # ── Cards ──────────────────────────────────────────────────────────
        for board_id in (board_ids if board_ids else [None]):
            raw_cards = await _call(
                session, "kaiten_list_cards",
                board_id=board_id,
            )
            cards: list[dict] = raw_cards if isinstance(raw_cards, list) else []
            for card in cards:
                description = card.get("description", "") or ""
                title = card.get("title", f"Card {card['id']}")
                text = f"{title}\n\n{description}".strip()
                if not text:
                    continue
                task = "code" if _is_code_chunk(text) else "document"
                vector = await embedder.embed(text, task)
                card_id = hashlib.md5(f"card:{card['id']}".encode()).hexdigest()
                points.append({
                    "id": card_id,
                    "vector": vector,
                    "payload": {
                        "title": title,
                        "source": "card",
                        "kaiten_id": str(card["id"]),
                        "text": text[:1500],
                        "url": card.get("url", ""),
                    },
                })

    return points
