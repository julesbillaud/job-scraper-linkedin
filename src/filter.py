"""Filtrage des offres par mots-clés (et optionnellement par entreprise)."""

from __future__ import annotations

import unicodedata
from pathlib import Path

from .linkedin_scraper import JobPosting


def _normalize(text: str) -> str:
    """Minuscule + suppression des accents, pour un matching robuste."""
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def load_lines(path: str | Path) -> list[str]:
    """Charge un fichier config en ignorant lignes vides et commentaires."""
    lines = []
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def matches_keywords(job: JobPosting, keywords: list[str]) -> bool:
    haystack = _normalize(job.title)
    return any(_normalize(kw) in haystack for kw in keywords)


def matches_company(job: JobPosting, companies: list[str]) -> bool:
    """Si `companies` est vide, aucun filtre entreprise n'est appliqué."""
    if not companies:
        return True
    company_norm = _normalize(job.company)
    return any(_normalize(c) in company_norm for c in companies)


def filter_jobs(
    jobs: list[JobPosting],
    keywords: list[str],
    companies: list[str],
) -> list[JobPosting]:
    return [
        job
        for job in jobs
        if matches_keywords(job, keywords) and matches_company(job, companies)
    ]
