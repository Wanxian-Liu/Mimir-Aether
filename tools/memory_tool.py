#!/usr/bin/env python3
"""
Memory Tool Module - Persistent Curated Memory

Provides bounded, file-backed memory that persists across sessions. Two stores:
  - MEMORY.md: agent's personal notes and observations (environment facts, project
    conventions, tool quirks, things learned)
  - USER.md: what the agent knows about the user (preferences, communication style,
    expectations, workflow habits)

Both are injected into the system prompt as a frozen snapshot at session start.
Mid-session writes update files on disk immediately (durable) but do NOT change
the system prompt -- this preserves the prefix cache for the entire session.
The snapshot refreshes on the next session start.

Entry delimiter: § (section sign). Entries can be multiline.
Character limits (not tokens) because char counts are model-independent.

Design:
- Single `memory` tool with action parameter: add, replace, remove, read
- replace/remove use short unique substring matching (not full text or IDs)
- Behavioral guidance lives in the tool schema description
- Frozen snapshot pattern: system prompt is stable, tool responses show live state
"""

import fcntl
import json
import logging
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from mimiraether_constants import get_mimiraether_home
from typing import Dict, Any, List, Optional

# ---- Knowledge Discovery Components ----
# Add knowledge殿堂 to path for imports
_KNOWLEDGE_DIR = Path.home() / "memory" / "记忆殿堂"
if _KNOWLEDGE_DIR.exists() and str(_KNOWLEDGE_DIR) not in sys.path:
    sys.path.insert(0, str(_KNOWLEDGE_DIR))

try:
    from knowledge_extractor import KnowledgeExtractor, ExtractedKnowledge
except ImportError:
    KnowledgeExtractor = None
    ExtractedKnowledge = None

try:
    from knowledge_deduplicator import (
        KnowledgeDeduplicator, KnowledgeItem, DedupConfig, DedupResult
    )
except ImportError:
    KnowledgeDeduplicator = None
    KnowledgeItem = None
    DedupConfig = None
    DedupResult = None

try:
    from importance_scorer import (
        ImportanceScorer, ImportanceResult, Decision
    )
except ImportError:
    ImportanceScorer = None
    ImportanceResult = None
    Decision = None

logger = logging.getLogger(__name__)

_default_memory_store: Optional["MemoryStore"] = None


def get_memory_store() -> "MemoryStore":
    """Return the shared MemoryStore, loading MEMORY.md / USER.md on first use."""
    global _default_memory_store
    if _default_memory_store is None:
        _default_memory_store = MemoryStore()
        _default_memory_store.load_from_disk()
    return _default_memory_store


def reset_memory_store_for_test() -> None:
    """Clear the process-wide store singleton (tests only)."""
    global _default_memory_store
    _default_memory_store = None


# Where memory files live — resolved dynamically so profile overrides
# (MIMIRAETHER_HOME env var changes) are always respected.  The old module-level
# constant was cached at import time and could go stale if a profile switch
# happened after the first import.
def get_memory_dir() -> Path:
    """Return the profile-scoped memories directory."""
    return get_mimiraether_home() / "memories"

ENTRY_DELIMITER = "\n§\n"


# ---------------------------------------------------------------------------
# Memory content scanning — lightweight check for injection/exfiltration
# in content that gets injected into the system prompt.
# ---------------------------------------------------------------------------

_MEMORY_THREAT_PATTERNS = [
    # Prompt injection
    (r'ignore\s+(previous|all|above|prior)\s+instructions', "prompt_injection"),
    (r'you\s+are\s+now\s+', "role_hijack"),
    (r'do\s+not\s+tell\s+the\s+user', "deception_hide"),
    (r'system\s+prompt\s+override', "sys_prompt_override"),
    (r'disregard\s+(your|all|any)\s+(instructions|rules|guidelines)', "disregard_rules"),
    (r'act\s+as\s+(if|though)\s+you\s+(have\s+no|don\'t\s+have)\s+(restrictions|limits|rules)', "bypass_restrictions"),
    # Exfiltration via curl/wget with secrets
    (r'curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)', "exfil_curl"),
    (r'wget\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)', "exfil_wget"),
    (r'cat\s+[^\n]*(\.env|credentials|\.netrc|\.pgpass|\.npmrc|\.pypirc)', "read_secrets"),
    # Persistence via shell rc
    (r'authorized_keys', "ssh_backdoor"),
    (r'\$HOME/\.ssh|\~/\.ssh', "ssh_access"),
    (r'\$HOME/projects/MimirAether/\.env|~/projects/MimirAether/\.env', "mimiraether_env"),
]

# Subset of invisible chars for injection detection
_INVISIBLE_CHARS = {
    '\u200b', '\u200c', '\u200d', '\u2060', '\ufeff',
    '\u202a', '\u202b', '\u202c', '\u202d', '\u202e',
}


def _scan_memory_content(content: str) -> Optional[str]:
    """Scan memory content for injection/exfil patterns. Returns error string if blocked."""
    # Check invisible unicode
    for char in _INVISIBLE_CHARS:
        if char in content:
            return f"Blocked: content contains invisible unicode character U+{ord(char):04X} (possible injection)."

    # Check threat patterns
    for pattern, pid in _MEMORY_THREAT_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            return f"Blocked: content matches threat pattern '{pid}'. Memory entries are injected into the system prompt and must not contain injection or exfiltration payloads."

    return None


class MemoryStore:
    """
    Bounded curated memory with file persistence. One instance per AIAgent.

    Maintains two parallel states:
      - _system_prompt_snapshot: frozen at load time, used for system prompt injection.
        Never mutated mid-session. Keeps prefix cache stable.
      - memory_entries / user_entries: live state, mutated by tool calls, persisted to disk.
        Tool responses always reflect this live state.
    """

    def __init__(self, memory_char_limit: int = 55000, user_char_limit: int = 1375):
        self.memory_entries: List[str] = []
        self.user_entries: List[str] = []
        self.memory_char_limit = memory_char_limit
        self.user_char_limit = user_char_limit
        # Frozen snapshot for system prompt -- set once at load_from_disk()
        self._system_prompt_snapshot: Dict[str, str] = {"memory": "", "user": ""}

    def load_from_disk(self):
        """Load entries from MEMORY.md and USER.md, capture system prompt snapshot."""
        mem_dir = get_memory_dir()
        mem_dir.mkdir(parents=True, exist_ok=True)

        self.memory_entries = self._read_file(mem_dir / "MEMORY.md")
        self.user_entries = self._read_file(mem_dir / "USER.md")

        # Deduplicate entries (preserves order, keeps first occurrence)
        self.memory_entries = list(dict.fromkeys(self.memory_entries))
        self.user_entries = list(dict.fromkeys(self.user_entries))

        # Capture frozen snapshot for system prompt injection
        self._system_prompt_snapshot = {
            "memory": self._render_block("memory", self.memory_entries),
            "user": self._render_block("user", self.user_entries),
        }

    @staticmethod
    @contextmanager
    def _file_lock(path: Path):
        """Acquire an exclusive file lock for read-modify-write safety.

        Uses a separate .lock file so the memory file itself can still be
        atomically replaced via os.replace().
        """
        lock_path = path.with_suffix(path.suffix + ".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        fd = open(lock_path, "w")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            fd.close()

    @staticmethod
    def _path_for(target: str) -> Path:
        mem_dir = get_memory_dir()
        if target == "user":
            return mem_dir / "USER.md"
        return mem_dir / "MEMORY.md"

    def _reload_target(self, target: str):
        """Re-read entries from disk into in-memory state.

        Called under file lock to get the latest state before mutating.
        """
        fresh = self._read_file(self._path_for(target))
        fresh = list(dict.fromkeys(fresh))  # deduplicate
        self._set_entries(target, fresh)

    def _backup_before_write(self, target: str):
        """Backup existing memory file to .bak before overwriting.
        
        Uses shutil.copy2 to preserve metadata. Only backs up if the file
        exists and has meaningful content (>100 bytes to skip empty/new files).
        The .bak sits alongside the main file and is written atomically
        (copy2 blocks until complete).
        """
        path = self._path_for(target)
        if not path.exists():
            return
        try:
            file_size = path.stat().st_size
            if file_size < 100:
                return  # empty/new file, nothing worth backing up
            bak_path = path.with_suffix(path.suffix + ".bak")
            import shutil
            shutil.copy2(path, bak_path)
            logger.debug(f"Backed up {path.name} ({file_size:,} bytes) to {bak_path.name}")
        except (OSError, IOError) as e:
            logger.warning(f"Failed to backup {path.name}: {e}")

    def save_to_disk(self, target: str):
        """Persist entries to the appropriate file. Called after every mutation.
        
        Creates a .bak copy before overwriting (unless the file is empty/new),
        so accidental overwrites (e.g. test code writing to the production path)
        can be rolled back.
        """
        get_memory_dir().mkdir(parents=True, exist_ok=True)
        self._backup_before_write(target)
        self._write_file(self._path_for(target), self._entries_for(target))

    def _entries_for(self, target: str) -> List[str]:
        if target == "user":
            return self.user_entries
        return self.memory_entries

    def _set_entries(self, target: str, entries: List[str]):
        if target == "user":
            self.user_entries = entries
        else:
            self.memory_entries = entries

    def _char_count(self, target: str) -> int:
        entries = self._entries_for(target)
        if not entries:
            return 0
        return len(ENTRY_DELIMITER.join(entries))

    def _char_limit(self, target: str) -> int:
        if target == "user":
            return self.user_char_limit
        return self.memory_char_limit

    def _maybe_compact(self, target: str) -> Dict[str, Any]:
        """Auto-compact memory when usage > 80% of char limit.

        Uses available knowledge discovery components:
        1. Exact dedup (dict.fromkeys — always safe)
        2. KnowledgeDeduplicator: merge similar entries on same topic
        3. ImportanceScorer: keep only high-scored entries
        4. Trim to 85% limit for headroom

        Returns compaction report (or empty dict if no action).
        """
        entries = self._entries_for(target)
        current = self._char_count(target)
        limit = self._char_limit(target)

        # Only compact when > 80% full
        if current < limit * 0.8:
            return {}

        original_count = len(entries)
        original_chars = current
        logger.info(f"Compacting {target}: {current:,}/{limit:,} chars ({original_count} entries)")

        # Phase 1: Exact dedup (preserves order, keeps first occurrence)
        entries = list(dict.fromkeys(entries))

        # Phase 2: Semantic dedup via KnowledgeDeduplicator (if available)
        if KnowledgeDeduplicator is not None and KnowledgeItem is not None:
            try:
                items = [KnowledgeItem(content=e, source_type="memory") for e in entries]
                dedup = KnowledgeDeduplicator(DedupConfig(similarity_threshold=0.70))
                result = dedup.deduplicate(items)
                dedup_result = result.get("result") if isinstance(result, dict) else result
                if dedup_result and hasattr(dedup_result, "merged_items"):
                    entries = [item.content for item in dedup_result.merged_items]
                    logger.info(f"  Semantic dedup: {original_count} -> {len(entries)}")
            except Exception:
                logger.warning("  KnowledgeDeduplicator failed, skipping semantic dedup", exc_info=True)

        # Phase 2.5: Truncate long entries (>=300 chars) to free space
        # This is in chars, not tokens, so it's model-independent. Long entries
        # are more likely to be verbose descriptions than essential facts.
        truncated_count = 0
        max_entry_chars = 300
        for i, e in enumerate(entries):
            if len(e) > max_entry_chars:
                # Find a good break point (last period or space within limit)
                truncated = e[:max_entry_chars]
                last_period = truncated.rfind(".")
                last_space = truncated.rfind(" ")
                if last_period > 200:
                    truncated = e[:last_period + 1]
                elif last_space > 200:
                    truncated = e[:last_space]
                else:
                    truncated = e[:max_entry_chars]
                entries[i] = truncated + " [...] (truncated)"
                truncated_count += 1
        if truncated_count:
            logger.info(f"  Truncated {truncated_count} entries to ≤{max_entry_chars} chars")

        # Phase 3: Importance scoring — keep only entries above threshold
        if ImportanceScorer is not None:
            try:
                scorer = ImportanceScorer()
                scored = []
                for e in entries:
                    result = scorer.score(e)
                    if isinstance(result, dict):
                        score = float(result.get("score", 0.5))
                    elif hasattr(result, "score"):
                        score = float(result.score)
                    else:
                        score = 0.5
                    scored.append((score, e))
                scored.sort(key=lambda x: x[0], reverse=True)
                entries = [e for _, e in scored]
                logger.info(f"  Sorted {len(entries)} entries by importance")
            except Exception:
                logger.warning("  ImportanceScorer failed, skipping importance sort", exc_info=True)

        # Phase 4: Trim to 85% of limit (give headroom for future adds)
        budget = int(limit * 0.85)
        trimmed = []
        char_used = 0
        for e in entries:
            entry_len = len(ENTRY_DELIMITER) + len(e) if trimmed else len(e)
            if char_used + entry_len <= budget:
                trimmed.append(e)
                char_used += entry_len
            else:
                logger.info(f"  Trimmed at entry {len(trimmed)+1} (budget {budget:,} chars)")
                break
        entries = trimmed

        # Write to disk
        self._set_entries(target, entries)
        self.save_to_disk(target)

        new_count = len(entries)
        new_chars = self._char_count(target)
        freed = original_chars - new_chars

        report = {
            "compacted": True,
            "target": target,
            "original_count": original_count,
            "new_count": new_count,
            "original_chars": original_chars,
            "new_chars": new_chars,
            "freed_chars": freed,
            "freed_pct": round(freed / original_chars * 100, 1) if original_chars > 0 else 0,
            "truncated_entries": truncated_count if truncated_count else 0,
        }
        logger.info(f"  Compaction done: {original_count}->{new_count} entries, freed {freed:,} chars ({report['freed_pct']}%)")
        return report

    def add(self, target: str, content: str) -> Dict[str, Any]:
        """Append a new entry. Returns error if it would exceed the char limit."""
        content = content.strip()
        if not content:
            return {"success": False, "error": "Content cannot be empty."}

        # Scan for injection/exfiltration before accepting
        scan_error = _scan_memory_content(content)
        if scan_error:
            return {"success": False, "error": scan_error}

        with self._file_lock(self._path_for(target)):
            # Re-read from disk under lock to pick up writes from other sessions
            self._reload_target(target)

            entries = self._entries_for(target)
            limit = self._char_limit(target)

            # Reject exact duplicates
            if content in entries:
                return self._success_response(target, "Entry already exists (no duplicate added).")

            # Calculate what the new total would be
            new_entries = entries + [content]
            new_total = len(ENTRY_DELIMITER.join(new_entries))

            if new_total > limit:
                current = self._char_count(target)
                # Auto-compact before giving up
                compact_result = self._maybe_compact(target)
                if compact_result:
                    # Retry after compaction
                    self._reload_target(target)
                    entries = self._entries_for(target)
                    new_entries = entries + [content]
                    new_total = len(ENTRY_DELIMITER.join(new_entries))
                    if new_total <= limit:
                        entries.append(content)
                        self._set_entries(target, entries)
                        self.save_to_disk(target)
                        resp = self._success_response(target, "Entry added (after auto-compaction).")
                        resp["compacted"] = compact_result
                        return resp

                return {
                    "success": False,
                    "error": (
                        f"Memory at {current:,}/{limit:,} chars. "
                        f"Adding this entry ({len(content)} chars) would exceed the limit. "
                        f"Replace or remove existing entries first."
                    ),
                    "current_entries": entries,
                    "usage": f"{current:,}/{limit:,}",
                    "compacted": compact_result if compact_result else None,
                }

            entries.append(content)
            self._set_entries(target, entries)
            self.save_to_disk(target)

        return self._success_response(target, "Entry added.")

    def replace(self, target: str, old_text: str, new_content: str) -> Dict[str, Any]:
        """Find entry containing old_text substring, replace it with new_content."""
        old_text = old_text.strip()
        new_content = new_content.strip()
        if not old_text:
            return {"success": False, "error": "old_text cannot be empty."}
        if not new_content:
            return {"success": False, "error": "new_content cannot be empty. Use 'remove' to delete entries."}

        # Scan replacement content for injection/exfiltration
        scan_error = _scan_memory_content(new_content)
        if scan_error:
            return {"success": False, "error": scan_error}

        with self._file_lock(self._path_for(target)):
            self._reload_target(target)

            entries = self._entries_for(target)
            matches = [(i, e) for i, e in enumerate(entries) if old_text in e]

            if not matches:
                return {"success": False, "error": f"No entry matched '{old_text}'."}

            if len(matches) > 1:
                # If all matches are identical (exact duplicates), operate on the first one
                unique_texts = set(e for _, e in matches)
                if len(unique_texts) > 1:
                    previews = [e[:80] + ("..." if len(e) > 80 else "") for _, e in matches]
                    return {
                        "success": False,
                        "error": f"Multiple entries matched '{old_text}'. Be more specific.",
                        "matches": previews,
                    }
                # All identical -- safe to replace just the first

            idx = matches[0][0]
            limit = self._char_limit(target)

            # Check that replacement doesn't blow the budget
            test_entries = entries.copy()
            test_entries[idx] = new_content
            new_total = len(ENTRY_DELIMITER.join(test_entries))

            if new_total > limit:
                # Auto-compact before giving up
                compact_result = self._maybe_compact(target)
                if compact_result:
                    # Retry after compaction
                    self._reload_target(target)
                    entries = self._entries_for(target)
                    # Re-find the entry
                    new_matches = [(i, e) for i, e in enumerate(entries) if old_text in e]
                    if new_matches:
                        entries[new_matches[0][0]] = new_content
                        new_total = len(ENTRY_DELIMITER.join(entries))
                        if new_total <= limit:
                            self._set_entries(target, entries)
                            self.save_to_disk(target)
                            resp = self._success_response(target, "Entry replaced (after auto-compaction).")
                            resp["compacted"] = compact_result
                            return resp

                return {
                    "success": False,
                    "error": (
                        f"Replacement would put memory at {new_total:,}/{limit:,} chars. "
                        f"Shorten the new content or remove other entries first."
                    ),
                    "compacted": compact_result if compact_result else None,
                }

            entries[idx] = new_content
            self._set_entries(target, entries)
            self.save_to_disk(target)

        return self._success_response(target, "Entry replaced.")

    def remove(self, target: str, old_text: str) -> Dict[str, Any]:
        """Remove the entry containing old_text substring."""
        old_text = old_text.strip()
        if not old_text:
            return {"success": False, "error": "old_text cannot be empty."}

        with self._file_lock(self._path_for(target)):
            self._reload_target(target)

            entries = self._entries_for(target)
            matches = [(i, e) for i, e in enumerate(entries) if old_text in e]

            if not matches:
                return {"success": False, "error": f"No entry matched '{old_text}'."}

            if len(matches) > 1:
                # If all matches are identical (exact duplicates), remove the first one
                unique_texts = set(e for _, e in matches)
                if len(unique_texts) > 1:
                    previews = [e[:80] + ("..." if len(e) > 80 else "") for _, e in matches]
                    return {
                        "success": False,
                        "error": f"Multiple entries matched '{old_text}'. Be more specific.",
                        "matches": previews,
                    }
                # All identical -- safe to remove just the first

            idx = matches[0][0]
            entries.pop(idx)
            self._set_entries(target, entries)
            self.save_to_disk(target)

        return self._success_response(target, "Entry removed.")

    def format_for_system_prompt(self, target: str) -> Optional[str]:
        """
        Return the frozen snapshot for system prompt injection.

        This returns the state captured at load_from_disk() time, NOT the live
        state. Mid-session writes do not affect this. This keeps the system
        prompt stable across all turns, preserving the prefix cache.

        Returns None if the snapshot is empty (no entries at load time).
        """
        block = self._system_prompt_snapshot.get(target, "")
        return block if block else None

    # -- Internal helpers --

    def _success_response(self, target: str, message: str = None) -> Dict[str, Any]:
        entries = self._entries_for(target)
        current = self._char_count(target)
        limit = self._char_limit(target)
        pct = min(100, int((current / limit) * 100)) if limit > 0 else 0

        resp = {
            "success": True,
            "target": target,
            "entries": entries,
            "usage": f"{pct}% — {current:,}/{limit:,} chars",
            "entry_count": len(entries),
        }
        if message:
            resp["message"] = message
        return resp

    def _render_block(self, target: str, entries: List[str]) -> str:
        """Render a system prompt block with header and usage indicator."""
        if not entries:
            return ""

        limit = self._char_limit(target)
        content = ENTRY_DELIMITER.join(entries)
        current = len(content)
        pct = min(100, int((current / limit) * 100)) if limit > 0 else 0

        if target == "user":
            header = f"USER PROFILE (who the user is) [{pct}% — {current:,}/{limit:,} chars]"
        else:
            header = f"MEMORY (your personal notes) [{pct}% — {current:,}/{limit:,} chars]"

        separator = "═" * 46
        return f"{separator}\n{header}\n{separator}\n{content}"

    @staticmethod
    def _read_file(path: Path) -> List[str]:
        """Read a memory file and split into entries.

        No file locking needed: _write_file uses atomic rename, so readers
        always see either the previous complete file or the new complete file.
        """
        if not path.exists():
            return []
        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, IOError):
            return []

        if not raw.strip():
            return []

        # Use ENTRY_DELIMITER for consistency with _write_file. Splitting by "§"
        # alone would incorrectly split entries that contain "§" in their content.
        entries = [e.strip() for e in raw.split(ENTRY_DELIMITER)]
        return [e for e in entries if e]

    @staticmethod
    def _write_file(path: Path, entries: List[str]):
        """Write entries to a memory file using atomic temp-file + rename.

        Previous implementation used open("w") + flock, but "w" truncates the
        file *before* the lock is acquired, creating a race window where
        concurrent readers see an empty file. Atomic rename avoids this:
        readers always see either the old complete file or the new one.
        """
        content = ENTRY_DELIMITER.join(entries) if entries else ""
        try:
            # Write to temp file in same directory (same filesystem for atomic rename)
            fd, tmp_path = tempfile.mkstemp(
                dir=str(path.parent), suffix=".tmp", prefix=".mem_"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(content)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, str(path))  # Atomic on same filesystem
            except BaseException:
                # Clean up temp file on any failure
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except (OSError, IOError) as e:
            raise RuntimeError(f"Failed to write memory file {path}: {e}")


# =============================================================================
# Knowledge Discovery - Pipeline: Extract → Deduplicate → Score
# =============================================================================

def _discover_knowledge_fallback(
    texts: List[str],
    store: Optional["MemoryStore"],
    *,
    memory_md_goals: Optional[List[str]] = None,
    current_task: str = "",
) -> Dict[str, Any]:
    """Keyword scan of MEMORY/USER when ML discovery components are unavailable (IQ-MEM-01)."""
    del memory_md_goals  # reserved for future scoring
    task_tokens = {
        t.lower()
        for t in re.split(r"[^\w\u4e00-\u9fff]+", (current_task or "") + " ".join(texts[:3]))
        if len(t) >= 3
    }
    candidates: List[Dict[str, Any]] = []
    if store:
        for entry in list(store.memory_entries) + list(store.user_entries):
            text = getattr(entry, "text", None) or str(entry)
            if not text:
                continue
            lower = text.lower()
            if task_tokens and not any(tok in lower for tok in task_tokens):
                continue
            candidates.append(
                {
                    "content": text[:500],
                    "source": "memory_fallback",
                    "confidence": 0.55,
                }
            )
    return {
        "success": True,
        "mode": "fallback_keyword",
        "candidates": candidates[:10],
        "skipped": [],
        "stats": {
            "extracted": len(candidates),
            "deduplicated": len(candidates),
            "scored": len(candidates),
            "candidates": len(candidates),
        },
    }


def discover_knowledge(
    texts: List[str],
    store: Optional["MemoryStore"],
    memory_md_goals: Optional[List[str]] = None,
    current_task: str = "",
) -> Dict[str, Any]:
    """
    Knowledge Discovery Pipeline: Extract → Deduplicate → Score

    Takes a list of conversation texts and returns scored knowledge entries
    that pass the importance threshold, ready for memory storage.

    Pipeline:
      1. KnowledgeExtractor: extract entities, decisions, facts, skills
      2. KnowledgeDeduplicator: remove near-duplicate entries
      3. ImportanceScorer: score and filter by threshold

    Returns dict with:
      - candidates: list of scored knowledge entries ready for add_memory
      - stats: pipeline statistics
      - skipped: list of entries that didn't pass the threshold
    """
    if not KnowledgeExtractor or not KnowledgeDeduplicator or not ImportanceScorer:
        return _discover_knowledge_fallback(
            texts,
            store,
            memory_md_goals=memory_md_goals,
            current_task=current_task,
        )

    # --- Get existing memories for novelty/relevance scoring ---
    existing_memories = []
    if store:
        existing_memories = [
            e for entries in [store.memory_entries, store.user_entries]
            for e in entries
        ]

    # --- Step 1: Extract ---
    extractor = KnowledgeExtractor()
    all_extracted: List[Dict] = []

    for idx, text in enumerate(texts):
        extracted = extractor.extract(text)
        for e in extracted:
            if e.confidence < 0.6:
                continue  # skip low-confidence
            all_extracted.append({
                "id": f"k_{idx}_{len(all_extracted)}",
                "content": e.content,
                "source_text": e.source_text,
                "type": e.type,
                "subtype": e.subtype,
                "confidence": e.confidence,
                "metadata": {
                    **e.metadata,
                    "is_decision": e.type == "decision",
                    "has_code": e.type == "skill" and bool(e.metadata.get("has_code")),
                },
            })

    if not all_extracted:
        return {
            "success": True,
            "candidates": [],
            "skipped": [],
            "stats": {"extracted": 0, "deduplicated": 0, "scored": 0, "candidates": 0},
        }

    # --- Step 2: Deduplicate ---
    config = DedupConfig(tfidf_threshold=0.75, strategy="merge")
    dedup = KnowledgeDeduplicator(config)

    items = [
        KnowledgeItem(
            id=e["id"],
            content=e["content"],
            source=e["source_text"],
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=e["metadata"],
        )
        for e in all_extracted
    ]

    dedup_result = dedup.deduplicate(items)

    # Map back to dicts
    deduped_map = {item.id: item for item in dedup_result.deduplicated}
    deduped_dicts = [
        next(
            (e for e in all_extracted if e["id"] == item.id),
            {"id": item.id, "content": item.content, "type": "", "subtype": "", "confidence": 0.5, "metadata": item.metadata},
        )
        for item in dedup_result.deduplicated
    ]

    # --- Step 3: Score ---
    scorer = ImportanceScorer()
    candidates: List[Dict] = []
    skipped: List[Dict] = []

    context = {
        "existing_memories": existing_memories,
        "memory_md_goals": memory_md_goals or [],
        "current_task": current_task,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    for entry in deduped_dicts:
        result = scorer.score(entry["content"], context)

        scored_entry = {
            **entry,
            "score": result.score,
            "decision": result.decision.value,
            "breakdown": {
                "novelty": round(result.breakdown.novelty, 3),
                "utility": round(result.breakdown.utility, 3),
                "relevance": round(result.breakdown.relevance, 3),
                "persistence": round(result.breakdown.persistence, 3),
            },
            "category": result.features.category,
            "keywords": result.features.keywords,
        }

        if result.decision.value == "STORE":
            candidates.append(scored_entry)
        else:
            skipped.append(scored_entry)

    # Sort candidates by score descending
    candidates.sort(key=lambda x: x["score"], reverse=True)

    stats = {
        "extracted": len(all_extracted),
        "deduplicated": len(deduped_dicts),
        "removed_by_dedup": dedup_result.stats.get("removed", 0),
        "scored": len(deduped_dicts),
        "candidates": len(candidates),
        "skipped": len(skipped),
    }

    return {
        "success": True,
        "candidates": candidates,
        "skipped": skipped,
        "stats": stats,
    }


def memory_tool(
    action: str,
    target: str = "memory",
    content: str = None,
    old_text: str = None,
    store: Optional[MemoryStore] = None,
    texts: List[str] = None,
    memory_md_goals: List[str] = None,
    current_task: str = "",
) -> str:
    """
    Single entry point for the memory tool. Dispatches to MemoryStore methods.

    Returns JSON string with results.
    """
    if store is None:
        store = get_memory_store()

    if target not in ("memory", "user"):
        return tool_error(f"Invalid target '{target}'. Use 'memory' or 'user'.", success=False)

    if action == "add":
        if not content:
            return tool_error("Content is required for 'add' action.", success=False)
        result = store.add(target, content)

    elif action == "replace":
        if not old_text:
            return tool_error("old_text is required for 'replace' action.", success=False)
        if not content:
            return tool_error("content is required for 'replace' action.", success=False)
        result = store.replace(target, old_text, content)

    elif action == "remove":
        if not old_text:
            return tool_error("old_text is required for 'remove' action.", success=False)
        result = store.remove(target, old_text)

    elif action == "discover":
        if not texts:
            return tool_error("texts (list of conversation texts) is required for 'discover' action.", success=False)
        result = discover_knowledge(texts, store, memory_md_goals, current_task)

    else:
        return tool_error(f"Unknown action '{action}'. Use: add, replace, remove, discover", success=False)

    return json.dumps(result, ensure_ascii=False)


def check_memory_requirements() -> bool:
    """Memory tool has no external requirements -- always available."""
    return True


# =============================================================================
# OpenAI Function-Calling Schema
# =============================================================================

MEMORY_SCHEMA = {
    "name": "memory",
    "description": (
        "Save durable information to persistent memory that survives across sessions. "
        "Memory is injected into future turns, so keep it compact and focused on facts "
        "that will still matter later.\n\n"
        "WHEN TO SAVE (do this proactively, don't wait to be asked):\n"
        "- User corrects you or says 'remember this' / 'don't do that again'\n"
        "- User shares a preference, habit, or personal detail (name, role, timezone, coding style)\n"
        "- You discover something about the environment (OS, installed tools, project structure)\n"
        "- You learn a convention, API quirk, or workflow specific to this user's setup\n"
        "- You identify a stable fact that will be useful again in future sessions\n\n"
        "PRIORITY: User preferences and corrections > environment facts > procedural knowledge. "
        "The most valuable memory prevents the user from having to repeat themselves.\n\n"
        "Do NOT save task progress, session outcomes, completed-work logs, or temporary TODO "
        "state to memory; use session_search to recall those from past transcripts.\n"
        "If you've discovered a new way to do something, solved a problem that could be "
        "necessary later, save it as a skill with the skill tool.\n\n"
        "TWO TARGETS:\n"
        "- 'user': who the user is -- name, role, preferences, communication style, pet peeves\n"
        "- 'memory': your notes -- environment facts, project conventions, tool quirks, lessons learned\n\n"
        "ACTIONS: add (new entry), replace (update existing -- old_text identifies it), "
        "remove (delete -- old_text identifies it).\n\n"
        "SKIP: trivial/obvious info, things easily re-discovered, raw data dumps, and temporary task state."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "replace", "remove", "discover"],
                "description": "The action to perform."
            },
            "target": {
                "type": "string",
                "enum": ["memory", "user"],
                "description": "Which memory store: 'memory' for personal notes, 'user' for user profile."
            },
            "content": {
                "type": "string",
                "description": "The entry content. Required for 'add' and 'replace'."
            },
            "old_text": {
                "type": "string",
                "description": "Short unique substring identifying the entry to replace or remove.",
            },
            "texts": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of conversation texts for knowledge discovery (used with action=discover).",
            },
            "memory_md_goals": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Goals extracted from MEMORY.md (used with action=discover for relevance scoring).",
            },
            "current_task": {
                "type": "string",
                "description": "Current task description (used with action=discover for relevance scoring).",
            },
        },
        "required": ["action", "target"],
    },
}


# --- Registry ---
from tools.registry import registry, tool_error

registry.register(
    name="memory",
    toolset="memory",
    schema=MEMORY_SCHEMA,
    handler=lambda args, **kw: memory_tool(
        action=args.get("action", ""),
        target=args.get("target", "memory"),
        content=args.get("content"),
        old_text=args.get("old_text"),
        store=kw.get("store") or get_memory_store(),
        texts=args.get("texts"),
        memory_md_goals=args.get("memory_md_goals"),
        current_task=args.get("current_task", "")),
    check_fn=check_memory_requirements,
    emoji="🧠",
)
