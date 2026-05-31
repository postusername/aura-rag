import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(os.environ.get("RAG_CONFIG_PATH", "/app/config/settings.json"))


def _load() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


def _save(data: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_settings() -> dict:
    return _load()


def get_embedding_config() -> dict:
    return _load()["embedding"]


def set_embedding_provider(provider: str, model: str, dimensions: int | None = None) -> dict:
    data = _load()
    data["embedding"]["provider"] = provider
    data["embedding"]["model"] = model
    if dimensions is not None:
        data["embedding"]["dimensions"] = dimensions
    _save(data)
    return data["embedding"]


def list_domains() -> list[dict]:
    return _load()["domains"]


def get_domain(domain_id: str) -> dict | None:
    for d in _load()["domains"]:
        if d["id"] == domain_id:
            return d
    return None


def add_domain(
    domain_id: str,
    label: str,
    description: str,
    space_ids: list[int] | None = None,
    document_group_ids: list[int] | None = None,
    card_board_ids: list[int] | None = None,
) -> dict:
    data = _load()
    if any(d["id"] == domain_id for d in data["domains"]):
        raise ValueError(f"Domain '{domain_id}' already exists")
    domain = {
        "id": domain_id,
        "label": label,
        "description": description,
        "kaiten": {
            "space_ids": space_ids or [],
            "document_group_ids": document_group_ids or [],
            "card_board_ids": card_board_ids or [],
        },
        "synced_at": None,
        "doc_count": 0,
    }
    data["domains"].append(domain)
    _save(data)
    return domain


def update_domain(domain_id: str, **kwargs: Any) -> dict:
    data = _load()
    for d in data["domains"]:
        if d["id"] == domain_id:
            if "label" in kwargs:
                d["label"] = kwargs["label"]
            if "description" in kwargs:
                d["description"] = kwargs["description"]
            if "space_ids" in kwargs:
                d["kaiten"]["space_ids"] = kwargs["space_ids"]
            if "document_group_ids" in kwargs:
                d["kaiten"]["document_group_ids"] = kwargs["document_group_ids"]
            if "card_board_ids" in kwargs:
                d["kaiten"]["card_board_ids"] = kwargs["card_board_ids"]
            _save(data)
            return d
    raise ValueError(f"Domain '{domain_id}' not found")


def remove_domain(domain_id: str) -> None:
    data = _load()
    original = len(data["domains"])
    data["domains"] = [d for d in data["domains"] if d["id"] != domain_id]
    if len(data["domains"]) == original:
        raise ValueError(f"Domain '{domain_id}' not found")
    _save(data)


def mark_synced(domain_id: str, doc_count: int) -> None:
    data = _load()
    for d in data["domains"]:
        if d["id"] == domain_id:
            d["synced_at"] = datetime.now(timezone.utc).isoformat()
            d["doc_count"] = doc_count
            _save(data)
            return
    raise ValueError(f"Domain '{domain_id}' not found")


def get_retrieval_config() -> dict:
    return _load()["retrieval"]
