#!/bin/bash
# Generate llms-full.txt: concatenated content of all skills + wiki for LLM ingestion
# Pattern: Hermes Atlas (https://hermesatlas.com/llms-full.txt)

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT="$REPO_ROOT/llms-full.txt"

{
  echo "# MimirAether — Full Context Bundle"
  echo "# Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "# Format: concatenated markdown for direct LLM ingestion"
  echo

  echo "---"
  echo "## llms.txt (curated index)"
  echo
  cat "$REPO_ROOT/llms.txt"
  echo
  echo "---"

  echo
  echo "## SOUL.md"
  echo
  cat "$REPO_ROOT/SOUL.md"
  echo
  echo "---"

  echo
  echo "## Wiki"
  for f in "$HOME"/wiki/*.md; do
    echo
    echo "### wiki/$(basename "$f")"
    echo
    cat "$f"
  done
  echo
  echo "---"

  echo
  echo "## Skills (mimiraether/)"
  for d in "$REPO_ROOT"/skills/mimiraether/*/; do
    skill_name="$(basename "$d")"
    skill_file="$d/SKILL.md"
    if [ -f "$skill_file" ]; then
      echo
      echo "### $skill_name"
      echo
      cat "$skill_file"
      echo
      echo "---"
    fi
  done
} > "$OUTPUT"

echo "Generated: $OUTPUT ($(wc -c < "$OUTPUT") bytes, $(wc -l < "$OUTPUT") lines)"
