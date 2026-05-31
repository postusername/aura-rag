---
name: rag-query
description: Search the company knowledge base in Kaiten to answer internal questions. Use when the user asks about internal documentation, company processes, technical decisions, HR policies, project details — any question better answered from internal knowledge than general training data. Also triggers on phrases like "what do our docs say", "что в базе знаний", "check the docs", "наша документация", "внутри компании".
---

# RAG Query — Company Knowledge Base

Retrieves semantically relevant documents and cards from the Kaiten knowledge base.

## Workflow

1. Call `rag_query(query=<user's question verbatim>)`.
   - The query domain is detected automatically.
   - If `confidence` < 0.3, tell the user which domain was guessed and offer to specify one from `rag_list_domains()`.

2. Present the retrieved context:
   - Answer the user's question using the `context` field.
   - Cite each source by its `title` (not internal IDs).
   - Quote relevant excerpts.

3. If `results` is empty:
   - Suggest running `/rag-sync` to refresh the index.
   - Offer to answer from general knowledge if appropriate.

## Output format

Answer the user's question directly. Append a sources section:

**Sources:**
- [Document Title] — relevance: 0.85
- [Card Title] — relevance: 0.71
