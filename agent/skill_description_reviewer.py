"""Skill description quality reviewer (OS-REV-01).

Scores SKILL.md ``description`` frontmatter for curator / evolution visibility.
Uses heuristics aligned with ``agent.skills_qa.SkillsQA.score_skill_quality`` but
focused on the routing field agents read when selecting skills.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

_TRIGGER_PATTERNS = (
    r"\buse when\b",
    r"\bwhen the user\b",
    r"\bwhen user\b",
    r"\bhelps?\b",
    r"\bfor\b.+\b(task|request|query)\b",
    r"\btrigger",
)
_MIN_GOOD_LEN = 40
_IDEAL_MIN_LEN = 50
_IDEAL_MAX_LEN = 400
_MAX_LEN = 600


def skill_description_review_enabled() -> bool:
    """Default on (OS-REV-01), paired with OS-TQM-02 style gates."""
    return os.environ.get("MIMIR_SKILL_DESCRIPTION_REVIEW", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


@dataclass
class SkillDescriptionReview:
    skill_name: str
    description: str
    score: int = 0
    issues: List[str] = field(default_factory=list)

    def grade(self) -> str:
        if self.score >= 80:
            return "A"
        if self.score >= 60:
            return "B"
        if self.score >= 40:
            return "C"
        return "D"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "description": self.description[:200],
            "score": self.score,
            "grade": self.grade(),
            "issues": list(self.issues),
        }


def score_skill_description(
    skill_name: str,
    description: str,
    *,
    body: str = "",
) -> SkillDescriptionReview:
    """Score a single skill description (0–100)."""
    rev = SkillDescriptionReview(
        skill_name=skill_name,
        description=(description or "").strip(),
    )
    desc = rev.description
    if not desc:
        rev.issues.append("missing description")
        return rev

    score = 0
    length = len(desc)

    if length < 20:
        rev.issues.append("description too short (<20 chars)")
        score += max(length, 5)
    elif length < _MIN_GOOD_LEN:
        rev.issues.append("description short (<40 chars)")
        score += 25
    elif length <= _IDEAL_MAX_LEN:
        score += 35
        if length >= _IDEAL_MIN_LEN:
            score += 10
    elif length <= _MAX_LEN:
        rev.issues.append("description long (>400 chars)")
        score += 30
    else:
        rev.issues.append("description very long (>600 chars)")
        score += 15

    name_norm = skill_name.replace("-", " ").lower()
    if desc.lower().strip() == name_norm or desc.lower().strip() == skill_name.lower():
        rev.issues.append("description duplicates skill name only")
        score = min(score, 20)

    lower = desc.lower()
    if any(re.search(pat, lower) for pat in _TRIGGER_PATTERNS):
        score += 25
    else:
        rev.issues.append("no clear trigger phrase (e.g. 'Use when')")

    if re.search(r"[.!?]", desc):
        score += 5

    if body and len(body) > 100:
        body_lower = body.lower()
        words = [w for w in re.findall(r"[a-z]{4,}", lower) if w not in ("when", "user", "skill")]
        if words:
            hits = sum(1 for w in words[:8] if w in body_lower)
            if hits >= 2:
                score += 15
            elif hits == 0:
                rev.issues.append("description keywords weakly reflected in body")

    rev.score = max(0, min(100, score))
    return rev


def review_discovered_skills(
    discovered: Sequence[Tuple[str, Path, dict]],
) -> Dict[str, Any]:
    """Build report from skill_curator ``_discover_skills()`` tuples."""
    reviews: List[SkillDescriptionReview] = []
    for name, skill_dir, fm in discovered:
        desc = str((fm or {}).get("description") or "")
        body = ""
        skill_md = skill_dir / "SKILL.md"
        if skill_md.is_file():
            try:
                raw = skill_md.read_text(encoding="utf-8")
                if "---" in raw:
                    parts = raw.split("---", 2)
                    if len(parts) >= 3:
                        body = parts[2]
            except OSError:
                pass
        reviews.append(score_skill_description(name, desc, body=body))
    return build_description_review_report(reviews)


def build_description_review_report(
    reviews: List[SkillDescriptionReview],
) -> Dict[str, Any]:
    low = [r for r in reviews if r.score < 60]
    worst = sorted(reviews, key=lambda r: r.score)[:10]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(reviews),
        "low_quality_count": len(low),
        "average_score": round(
            sum(r.score for r in reviews) / len(reviews), 1
        )
        if reviews
        else 0.0,
        "reviews": [r.to_dict() for r in reviews],
        "worst": [r.to_dict() for r in worst],
    }


def _review_report_path() -> Path:
    from mimir_constants import get_mimir_data_dir

    return get_mimir_data_dir() / "skill_description_review.json"


def save_description_review_report(report: Dict[str, Any]) -> Path:
    path = _review_report_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_description_review_report() -> Dict[str, Any]:
    path = _review_report_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("skill_description_review: cannot read %s: %s", path, exc)
        return {}


def format_description_review_section(report: Dict[str, Any]) -> str:
    lines = [
        "## Description quality (OS-REV-01)",
        f"- reviewed: {report.get('total', 0)}",
        f"- low quality (<60): {report.get('low_quality_count', 0)}",
        f"- average score: {report.get('average_score', 0)}",
    ]
    for row in report.get("worst", [])[:8]:
        if row.get("score", 100) >= 60:
            continue
        issues = "; ".join(row.get("issues") or []) or "—"
        lines.append(
            f"- **{row.get('skill_name')}** score={row.get('score')} grade={row.get('grade')}: {issues}"
        )
    if report.get("low_quality_count", 0) == 0:
        lines.append("- (no low-quality descriptions)")
    return "\n".join(lines)


def run_description_review_pass() -> Dict[str, Any]:
    """Scan all skill roots, score descriptions, persist JSON report."""
    from agent.skill_curator import _discover_skills

    discovered = _discover_skills()
    report = review_discovered_skills(discovered)
    path = save_description_review_report(report)
    logger.info(
        "skill_description_review: %s skills, %s low quality -> %s",
        report.get("total"),
        report.get("low_quality_count"),
        path,
    )
    return report
