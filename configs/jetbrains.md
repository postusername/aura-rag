# JetBrains IDEs — Aura RAG Setup

JetBrains IDEs (IntelliJ IDEA, PyCharm, WebStorm, etc.) support MCP servers since version 2025.2.

## Setup

1. Start the RAG Docker services:
   ```bash
   docker compose up -d
   ```

2. Open your JetBrains IDE (2025.2+).

3. Go to **Settings → Tools → AI Assistant → MCP Servers**.

4. Click **+** and add:
   - **Name**: `rag`
   - **Type**: `SSE`
   - **URL**: `http://localhost:8080/sse`

5. Click **Apply** and restart the AI Assistant.

## Usage

In the AI Assistant chat panel, you can now use all RAG tools:
- "Search our knowledge base for API authentication guidelines"
- "Sync the knowledge base from Kaiten"
- "Add a domain for Legal documentation"

The IDE will show which MCP tools are being called in the conversation.
