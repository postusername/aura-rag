#!/usr/bin/env bash
set -e

SKILLS_SRC="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DEST="${HOME}/.claude/skills"

mkdir -p "$SKILLS_DEST"

for skill_dir in "$SKILLS_SRC"/*/; do
  skill_name="$(basename "$skill_dir")"
  [ "$skill_name" = "install.sh" ] && continue
  dest="$SKILLS_DEST/$skill_name"
  rm -rf "$dest"
  cp -r "$skill_dir" "$dest"
  echo "  Installed: $skill_name → $dest"
done

echo ""
echo "Skills installed. Restart Claude Code to activate them."
echo "Test with: /rag-sync, /rag-query, /rag-manage"
