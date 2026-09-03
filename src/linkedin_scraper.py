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

# Délai entre deux requêtes HTTP (secondes) — volontairement prudent.
REQUEST_DELAY_SECONDS = 2.5

# Nombre de résultats par page (LinkedIn pagine par lots de 10).
PAGE_SIZE = 10

# Nombre maximum de pages parcourues par combinaison mot-clé x ville.
MAX_PAGES_PER_QUERY = 3

# Seuil d'arrêt anticipé : si X offres ou plus sur une page sont déjà
# connues, on arrête de paginer (les suivantes seront encore plus anciennes).
EARLY_STOP_THRESHOLD = 5


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
        # Offres publiées dans les 7 derniers jours
        "f_TPR": "r604800",
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
    keywords: Iterable[str],
    locations: Iterable[str],
    already_seen: set[str] | None = None,
) -> list[JobPosting]:
    """
    Lance une recherche pour chaque combinaison (mot-clé, ville).

    Si `already_seen` est fourni, le script s'arrête de paginer dès
    qu'une page contient ≥ EARLY_STOP_THRESHOLD offres déjà connues
    (= les résultats suivants seront encore plus anciens, donc inutiles).
    """
    session = requests.Session()
    seen_ids: set[str] = set()
    results: list[JobPosting] = []
    known = already_seen or set()

    for keyword in keywords:
        for location in locations:
            for page in range(MAX_PAGES_PER_QUERY):
                start = page * PAGE_SIZE
                url = _build_search_url(keyword, location, start)

                try:
                    resp = session.get(url, headers=HEADERS, timeout=15)
                except requests.RequestException as exc:
                    logger.warning(
                        "Échec requête LinkedIn (%s / %s) : %s",
                        keyword, location, exc,
                    )
                    break

                if resp.status_code != 200:
                    logger.info(
                        "Réponse %s pour '%s' à %s, arrêt pagination.",
                        resp.status_code, keyword, location,
                    )
                    break

                postings = _parse_search_results(resp.text)
                if not postings:
                    break

                # Compteur d'offres déjà vues sur cette page
                already_known_count = 0

                for posting in postings:
                    if posting.job_id in seen_ids:
                        continue
                    seen_ids.add(posting.job_id)
                    results.append(posting)

                    if posting.job_id in known:
                        already_known_count += 1

                # Arrêt anticipé si la majorité de la page est déjà connue
                if already_known_count >= EARLY_STOP_THRESHOLD:
                    logger.info(
                        "Arrêt anticipé pour '%s' à %s : %d/%d offres déjà vues.",
                        keyword, location, already_known_count, len(postings),
                    )
                    break

                time.sleep(REQUEST_DELAY_SECONDS)

    logger.info("Total offres uniques scannées : %d", len(results))
    return results
