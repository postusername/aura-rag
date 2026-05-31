import asyncio
import logging
import os
import sys

import mcp.types as types
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.server.stdio import stdio_server
from starlette.applications import Starlette
from starlette.routing import Mount, Route
import uvicorn

import config_manager
import vector_store
from classifier import DomainClassifier
from embedder import create_embedder
from indexer import build_points

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

server = Server("aura-rag")
_embedder = None
_classifier = None


async def _get_embedder():
    global _embedder
    if _embedder is None:
        cfg = config_manager.get_embedding_config()
        _embedder = create_embedder(cfg)
    return _embedder


async def _get_classifier(reload: bool = False):
    global _classifier
    if _classifier is None or reload:
        emb = await _get_embedder()
        _classifier = DomainClassifier(emb)
        domains = config_manager.list_domains()
        await _classifier.load_domains(domains)
    return _classifier


def _format_context(results: list[dict]) -> str:
    if not results:
        return ""
    lines = ["## Retrieved Knowledge Base Context\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"### [{i}] {r['title']} (score: {r['score']:.2f})")
        if r.get("url"):
            lines.append(f"Source: {r['url']}")
        lines.append(f"\n{r['excerpt']}\n")
    return "\n".join(lines)


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="rag_query",
            description="Search the company knowledge base to answer questions. Classifies the query domain automatically, retrieves semantically relevant documents and cards from Kaiten.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The question or topic to search for"},
                    "domain": {"type": "string", "description": "Force a specific domain ID (optional; auto-detected if omitted)"},
                    "max_results": {"type": "integer", "description": "Max results to return (default: 5)", "default": 5},
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="rag_sync",
            description="Fetch documents and cards from Kaiten and store their embeddings in the vector database. Run after adding/updating domains or when knowledge base content has changed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "Sync a specific domain ID (optional; syncs all if omitted)"},
                    "force": {"type": "boolean", "description": "Force full re-index (clears existing vectors)", "default": False},
                },
            },
        ),
        types.Tool(
            name="rag_list_domains",
            description="List all configured knowledge base domains with their document counts and sync status.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="rag_add_domain",
            description="Add a new knowledge base domain. After adding, run rag_sync to index its content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Unique domain ID (lowercase, hyphens OK)"},
                    "label": {"type": "string", "description": "Human-readable domain name"},
                    "description": {"type": "string", "description": "Natural language description of what this domain covers. Used for automatic query classification."},
                    "space_ids": {"type": "array", "items": {"type": "integer"}, "description": "Kaiten space IDs (integers) to include"},
                    "document_group_ids": {"type": "array", "items": {"type": "string"}, "description": "Kaiten document group UIDs (strings, e.g. 'ac94385f-7366-4a88-b996-867729861838')"},
                    "card_board_ids": {"type": "array", "items": {"type": "integer"}, "description": "Kaiten board IDs (integers) whose cards to include"},
                },
                "required": ["id", "label", "description"],
            },
        ),
        types.Tool(
            name="rag_update_domain",
            description="Update an existing knowledge base domain configuration. Re-sync the domain after updating.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Domain ID to update"},
                    "label": {"type": "string"},
                    "description": {"type": "string"},
                    "space_ids": {"type": "array", "items": {"type": "integer"}},
                    "document_group_ids": {"type": "array", "items": {"type": "string"}, "description": "Kaiten document group UIDs (strings)"},
                    "card_board_ids": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["id"],
            },
        ),
        types.Tool(
            name="rag_remove_domain",
            description="Remove a knowledge base domain and delete its vector index.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Domain ID to remove"},
                },
                "required": ["id"],
            },
        ),
        types.Tool(
            name="rag_get_embedding_config",
            description="Show the current embedding provider and model configuration.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="rag_set_embedding_provider",
            description="Switch the embedding provider or model. After switching, run rag_sync with force=true to re-embed all documents.",
            inputSchema={
                "type": "object",
                "properties": {
                    "provider": {"type": "string", "enum": ["google", "ollama"], "description": "Embedding provider"},
                    "model": {"type": "string", "description": "Model name (e.g. 'gemini-embedding-2', 'nomic-embed-text', 'bge-m3')"},
                    "dimensions": {"type": "integer", "description": "Output vector dimensions (default: 768)"},
                },
                "required": ["provider", "model"],
            },
        ),
        types.Tool(
            name="rag_embedding_status",
            description="Test connectivity to the configured embedding provider and report status.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        result = await _dispatch(name, arguments)
        return [types.TextContent(type="text", text=str(result))]
    except Exception as e:
        log.exception(f"Tool {name} failed")
        return [types.TextContent(type="text", text=f"Error: {e}")]


async def _dispatch(name: str, args: dict) -> object:
    if name == "rag_query":
        return await _rag_query(args)
    if name == "rag_sync":
        return await _rag_sync(args)
    if name == "rag_list_domains":
        return await _rag_list_domains()
    if name == "rag_add_domain":
        return await _rag_add_domain(args)
    if name == "rag_update_domain":
        return await _rag_update_domain(args)
    if name == "rag_remove_domain":
        return await _rag_remove_domain(args)
    if name == "rag_get_embedding_config":
        return config_manager.get_embedding_config()
    if name == "rag_set_embedding_provider":
        return await _rag_set_embedding_provider(args)
    if name == "rag_embedding_status":
        return await _rag_embedding_status()
    raise ValueError(f"Unknown tool: {name}")


async def _rag_query(args: dict) -> dict:
    query = args["query"]
    forced_domain = args.get("domain")
    max_results = args.get("max_results", 5)

    emb = await _get_embedder()
    retrieval_cfg = config_manager.get_retrieval_config()
    min_score = retrieval_cfg.get("min_score", 0.5)

    if forced_domain:
        domain_id = forced_domain
        confidence = 1.0
        scores = {domain_id: 1.0}
    else:
        classifier = await _get_classifier()
        classification = await classifier.classify(query)
        domain_id = classification["domain_id"]
        confidence = classification["confidence"]
        scores = classification["scores"]

    query_vector = await emb.embed(query, task="query")
    results = await vector_store.search(domain_id, query_vector, max_results, min_score)

    return {
        "domain": domain_id,
        "confidence": confidence,
        "all_scores": scores,
        "results": results,
        "context": _format_context(results),
    }


async def _rag_sync(args: dict) -> dict:
    target_domain = args.get("domain")
    force = args.get("force", False)

    emb = await _get_embedder()
    cfg = config_manager.get_embedding_config()
    dimensions = cfg.get("dimensions", 768)
    retrieval_cfg = config_manager.get_retrieval_config()
    chunk_size = retrieval_cfg.get("chunk_size_chars", 1500)
    chunk_overlap = retrieval_cfg.get("chunk_overlap_chars", 200)

    domains = config_manager.list_domains()
    if target_domain:
        domain = config_manager.get_domain(target_domain)
        if not domain:
            raise ValueError(f"Domain '{target_domain}' not found")
        domains = [domain]

    total_synced = 0
    updated_domains = []

    for domain in domains:
        domain_id = domain["id"]
        log.info(f"Syncing domain: {domain_id}")

        if force:
            await vector_store.clear_collection(domain_id, dimensions)
        else:
            await vector_store.ensure_collection(domain_id, dimensions)

        points = await build_points(domain, emb, chunk_size, chunk_overlap)
        if points:
            await vector_store.upsert_points(domain_id, points)
        config_manager.mark_synced(domain_id, len(points))
        total_synced += len(points)
        updated_domains.append(domain_id)
        log.info(f"Domain {domain_id}: {len(points)} chunks indexed")

    await _get_classifier(reload=True)

    return {
        "synced_chunks": total_synced,
        "domains_updated": updated_domains,
    }


async def _rag_list_domains() -> list[dict]:
    domains = config_manager.list_domains()
    result = []
    for d in domains:
        count = await vector_store.get_collection_count(d["id"])
        result.append({
            "id": d["id"],
            "label": d["label"],
            "description": d["description"][:100] + "..." if len(d["description"]) > 100 else d["description"],
            "kaiten_sources": d["kaiten"],
            "synced_at": d.get("synced_at"),
            "vector_count": count,
        })
    return result


async def _rag_add_domain(args: dict) -> dict:
    domain = config_manager.add_domain(
        domain_id=args["id"],
        label=args["label"],
        description=args["description"],
        space_ids=args.get("space_ids"),
        document_group_ids=args.get("document_group_ids"),
        card_board_ids=args.get("card_board_ids"),
    )
    await _get_classifier(reload=True)
    return {"added": domain, "next_step": "Run rag_sync to index this domain's content."}


async def _rag_update_domain(args: dict) -> dict:
    domain_id = args.pop("id")
    domain = config_manager.update_domain(domain_id, **args)
    await _get_classifier(reload=True)
    return {"updated": domain, "next_step": "Run rag_sync to re-index this domain's content."}


async def _rag_remove_domain(args: dict) -> dict:
    domain_id = args["id"]
    config_manager.remove_domain(domain_id)
    await vector_store.delete_collection(domain_id)
    await _get_classifier(reload=True)
    return {"removed": domain_id}


async def _rag_set_embedding_provider(args: dict) -> dict:
    global _embedder
    provider = args["provider"]
    model = args["model"]
    dimensions = args.get("dimensions", 768)
    config = config_manager.set_embedding_provider(provider, model, dimensions)
    _embedder = None  # force recreation
    return {
        "embedding": config,
        "warning": "Embedding provider changed. Run rag_sync with force=true to re-embed all documents.",
    }


async def _rag_embedding_status() -> dict:
    try:
        emb = await _get_embedder()
        cfg = config_manager.get_embedding_config()
        ok = await emb.ping()
        return {
            "provider": cfg["provider"],
            "model": cfg["model"],
            "dimensions": cfg["dimensions"],
            "status": "ok" if ok else "unreachable",
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def create_app() -> Starlette:
    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            await server.run(streams[0], streams[1], server.create_initialization_options())

    return Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ]
    )


async def _run_stdio():
    log.info("Starting Aura RAG MCP server (stdio mode)")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    if "--stdio" in sys.argv:
        asyncio.run(_run_stdio())
    else:
        port = int(os.environ.get("PORT", 8080))
        log.info(f"Starting Aura RAG MCP server on :{port} (SSE mode)")
        app = create_app()
        uvicorn.run(app, host="0.0.0.0", port=port)
