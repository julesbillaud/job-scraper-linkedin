"""Mémoire des offres déjà notifiées, pour ne jamais notifier deux fois
la même offre. Le fichier JSON est committé dans le repo après chaque
run GitHub Actions (voir .github/workflows/scraper.yml)."""

from __future__ import annotations

import json
from pathlib import Path

from .linkedin_scraper import JobPosting

# Nombre max d'IDs conservés, pour éviter que le fichier ne grossisse
# indéfiniment au fil des mois.
MAX_SEEN_IDS = 5000


def load_seen_ids(path: str | Path) -> set[str]:
    p = Path(path)
    if not p.exists():
        return set()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return set(data.get("seen_ids", []))
    except (json.JSONDecodeError, OSError):
        return set()


def save_seen_ids(path: str | Path, seen_ids: set[str]) -> None:
    # On garde uniquement les N derniers si la liste dépasse la limite
    # (ordre non garanti, ce n'est qu'un garde-fou anti-croissance infinie).
    trimmed = list(seen_ids)[-MAX_SEEN_IDS:]
    Path(path).write_text(
        json.dumps({"seen_ids": trimmed}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def filter_new_jobs(
    jobs: list[JobPosting], seen_ids: set[str]
) -> list[JobPosting]:
    return [job for job in jobs if job.dedup_key not in seen_ids]
