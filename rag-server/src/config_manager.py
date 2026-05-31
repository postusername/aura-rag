import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(os.environ.get("RAG_CONFIG_PATH", "/app/config/settings.json"))

DEFAULT_EMBEDDING = {
    "provider": os.environ.get("RAG_DEFAULT_EMBEDDING_PROVIDER", "google"),
    "model": os.environ.get("RAG_DEFAULT_EMBEDDING_MODEL", "gemini-embedding-2"),
    "dimensions": int(os.environ.get("RAG_DEFAULT_EMBEDDING_DIMENSIONS", "768")),
}

DEFAULT_RETRIEVAL = {
    "max_results": 5,
    "min_score": 0.5,
    "chunk_size_chars": 1500,
    "chunk_overlap_chars": 200,
    "include_cards": True,
}


def _to_domain_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "domain"


def _to_label(name: str) -> str:
    return " ".join(part.capitalize() for part in re.split(r"[-_\s]+", name.strip()) if part)


def _make_domain(name: str) -> dict:
    domain_id = _to_domain_id(name)
    label = _to_label(name)
    return {
        "id": domain_id,
        "label": label,
        "description": f"Knowledge and documents related to {label.lower()}",
        "kaiten": {
            "space_ids": [],
            "document_group_ids": [],
            "card_board_ids": [],
        },
        "synced_at": None,
        "doc_count": 0,
    }


def _build_domains_from_env() -> list[dict]:
    raw = os.environ.get("RAG_INIT_DOMAINS", "").strip()
    if not raw:
        return []
    # Format: "engineering:Engineering,hr:HR & People" or "engineering,hr"
    items = [item.strip() for item in raw.split(",") if item.strip()]
    seen: set[str] = set()
    domains: list[dict] = []
    for item in items:
        if ":" in item:
            domain_id_raw, label_raw = item.split(":", 1)
            domain_id = _to_domain_id(domain_id_raw.strip())
            label = label_raw.strip() or _to_label(domain_id)
            domain = _make_domain(domain_id)
            domain["id"] = domain_id
            domain["label"] = label
            domain["description"] = f"Knowledge and documents related to {label.lower()}"
        else:
            domain = _make_domain(item)
        if domain["id"] in seen:
            continue
        seen.add(domain["id"])
        domains.append(domain)
    return domains


def _build_domains_from_prompt() -> list[dict]:
    if not sys.stdin.isatty():
        return []
    if os.environ.get("RAG_INTERACTIVE_INIT", "1") == "0":
        return []

    raw = input(
        "settings.json не найден. Введите домены через запятую "
        "(например: engineering, hr, product). Пусто = дефолт: "
    ).strip()
    if not raw:
        return []

    names = [item.strip() for item in raw.split(",") if item.strip()]
    seen: set[str] = set()
    domains: list[dict] = []
    for name in names:
        domain = _make_domain(name)
        if domain["id"] in seen:
            continue
        seen.add(domain["id"])
        domains.append(domain)
    return domains


def _default_config() -> dict:
    domains = _build_domains_from_env()
    if not domains:
        domains = _build_domains_from_prompt()

    return {
        "embedding": DEFAULT_EMBEDDING,
        "domains": domains,
        "retrieval": DEFAULT_RETRIEVAL,
    }


def _ensure_config_exists() -> None:
    if CONFIG_PATH.exists():
        return
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(_default_config(), f, indent=2, ensure_ascii=False)


def _load() -> dict:
    _ensure_config_exists()
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
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
