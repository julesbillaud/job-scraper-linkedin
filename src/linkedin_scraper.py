"""
Recherche d'offres LinkedIn via l'API "invité" (jobs-guest), publique
et non-authentifiée.

Aucun login, aucun cookie, aucun compte LinkedIn requis.

Optimisation : arrêt anticipé dès que la majorité d'une page de résultats
a déjà été vue lors d'un run précédent.
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

# User-Agent réaliste, comme un navigateur classique.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}

# Délai entre deux requêtes HTTP (secondes) — prudent mais pas timide.
REQUEST_DELAY_SECONDS = 1.5

# Nombre de résultats par page (LinkedIn pagine par lots de 10).
PAGE_SIZE = 10

# Nombre maximum de pages parcourues par combinaison requête x ville.
# 2 pages = 20 offres, largement assez sur une fenêtre de 48h.
MAX_PAGES_PER_QUERY = 2

# Fenêtre de publication LinkedIn, en secondes. 172800 = 48h.
# Le script tourne toutes les 2h : 48h laisse une grosse marge de
# sécurité si un run échoue, sans ramener trop de vieilles offres.
RECENCY_WINDOW_SECONDS = 172_800

# Seuil d'arrêt anticipé : dès que ce nombre d'offres DÉJÀ VUES apparaît
# sur une page, on arrête de paginer et on passe à la requête suivante.
# 1 seule serait trop fragile (une offre connue peut remonter par hasard) ;
# 3 signifie qu'on est clairement retombé sur du déjà-analysé.
EARLY_STOP_THRESHOLD = 3


@dataclass
class JobPosting:
    job_id: str
    title: str
    company: str
    location: str
    url: str

    @property
    def dedup_key(self) -> str:
        return self.job_id


def _build_search_url(keyword: str, location: str, start: int) -> str:
    params = {
        "keywords": keyword,
        "location": location,
        "start": start,
        "f_TPR": f"r{RECENCY_WINDOW_SECONDS}",
    }
    return f"{SEARCH_URL}?{urlencode(params)}"


def _parse_search_results(html: str) -> list[JobPosting]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("li")
    postings: list[JobPosting] = []

    for card in cards:
        link_tag = card.select_one("a.base-card__full-link")
        title_tag = card.select_one("h3.base-search-card__title")
        company_tag = card.select_one("h4.base-search-card__subtitle")
        location_tag = card.select_one("span.job-search-card__location")

        if not (link_tag and title_tag and company_tag):
            continue

        href = link_tag.get("href", "")
        job_id = ""
        if "-" in href:
            tail = href.split("?")[0].rstrip("/").split("-")[-1]
            job_id = tail if tail.isdigit() else ""
        if not job_id:
            job_id = href.split("?")[0]

        postings.append(
            JobPosting(
                job_id=job_id,
                title=title_tag.get_text(strip=True),
                company=company_tag.get_text(strip=True),
                location=location_tag.get_text(strip=True) if location_tag else "",
                url=href.split("?")[0],
            )
        )

    return postings


def search_jobs(
    queries: Iterable[str],
    locations: Iterable[str],
    already_seen: set[str] | None = None,
) -> list[JobPosting]:
    """
    Lance une recherche pour chaque combinaison (requête, ville).

    `queries` vient de config/search_queries.txt — volontairement court.
    Le tri fin est fait après coup par filter.filter_jobs().

    Si `already_seen` est fourni, on arrête de paginer une combinaison dès
    qu'une page contient ≥ EARLY_STOP_THRESHOLD offres déjà connues : on
    est retombé sur du déjà-analysé, la suite sera encore plus ancienne.
    """
    session = requests.Session()
    seen_ids: set[str] = set()
    results: list[JobPosting] = []
    known = already_seen or set()
    stopped_early = 0

    for query in queries:
        for location in locations:
            for page in range(MAX_PAGES_PER_QUERY):
                start = page * PAGE_SIZE
                url = _build_search_url(query, location, start)

                try:
                    resp = session.get(url, headers=HEADERS, timeout=15)
                except requests.RequestException as exc:
                    logger.warning(
                        "Échec requête LinkedIn (%s / %s) : %s",
                        query, location, exc,
                    )
                    break

                if resp.status_code != 200:
                    logger.info(
                        "Réponse %s pour '%s' à %s, arrêt pagination.",
                        resp.status_code, query, location,
                    )
                    break

                postings = _parse_search_results(resp.text)
                if not postings:
                    break

                # Compteur d'offres déjà vues sur cette page. On compte AVANT
                # le dédoublonnage intra-run : une offre déjà croisée par une
                # requête précédente reste un signal « terrain déjà couvert ».
                already_known_count = 0

                for posting in postings:
                    if posting.job_id in known:
                        already_known_count += 1
                    if posting.job_id in seen_ids:
                        continue
                    seen_ids.add(posting.job_id)
                    results.append(posting)

                # Arrêt anticipé : on passe à la requête/ville suivante
                if already_known_count >= EARLY_STOP_THRESHOLD:
                    logger.info(
                        "Arrêt anticipé '%s' / %s : %d/%d offres déjà vues.",
                        query, location, already_known_count, len(postings),
                    )
                    stopped_early += 1
                    break

                time.sleep(REQUEST_DELAY_SECONDS)

    logger.info(
        "Total offres uniques scannées : %d (%d recherches coupées court)",
        len(results), stopped_early,
    )
    return results
