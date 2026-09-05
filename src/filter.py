"""Filtrage des offres par mots-clés (et optionnellement par entreprise)."""

from __future__ import annotations

import unicodedata
from pathlib import Path

from .linkedin_scraper import JobPosting


def _normalize(text: str) -> str:
    """
    Minuscule, sans accents, ponctuation remplacée par des espaces.

    La ponctuation compte : sans ça, « Front-Office » ne matcherait pas
    la règle « front office », et « Gérant(e) » raterait « gerant ».
    """
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = "".join(c if c.isalnum() else " " for c in text)
    return " ".join(text.split())


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
    """
    Une offre est retenue si son titre satisfait AU MOINS UNE règle.

    Une règle est soit une expression simple, soit plusieurs termes reliés
    par « + » qui doivent TOUS être présents, dans n'importe quel ordre :

        fixed income        -> le titre contient "fixed income"
        rates + trader      -> le titre contient "rates" ET "trader",
                               même séparés ("Global Rates ... Trader")

    Les titres réels sont rarement formulés exactement comme un intitulé
    de métier ; le « + » évite de rater une offre pour un mot intercalé.
    """
    haystack = _normalize(job.title)
    for rule in keywords:
        parts = [_normalize(p) for p in rule.split("+") if p.strip()]
        if parts and all(part in haystack for part in parts):
            return True
    return False


def matches_exclusions(job: JobPosting, exclusions: list[str]) -> bool:
    """Vrai si le titre déclenche une règle d'exclusion (même syntaxe « + »)."""
    if not exclusions:
        return False
    haystack = _normalize(job.title)
    for rule in exclusions:
        parts = [_normalize(p) for p in rule.split("+") if p.strip()]
        if parts and all(part in haystack for part in parts):
            return True
    return False


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
    exclusions: list[str] | None = None,
) -> list[JobPosting]:
    """Garde les offres qui matchent un mot-clé, la liste d'entreprises
    (si active), et qui ne déclenchent aucune exclusion."""
    exclusions = exclusions or []
    return [
        job
        for job in jobs
        if matches_keywords(job, keywords)
        and matches_company(job, companies)
        and not matches_exclusions(job, exclusions)
    ]
