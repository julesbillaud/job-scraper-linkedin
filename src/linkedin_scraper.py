"""
Recherche d'offres LinkedIn via l'API "invité" (jobs-guest), publique
et non-authentifiée — les mêmes endpoints que ceux utilisés par les
moteurs de recherche pour indexer les offres LinkedIn.

Aucun login, aucun cookie, aucun compte LinkedIn requis.

Limites connues :
- Pagination LinkedIn plafonnée à ~1000 résultats par recherche
  (largement suffisant pour une veille par mots-clés ciblés).
- LinkedIn peut bloquer une IP en cas de volume/fréquence excessifs :
  on reste volontairement à un rythme faible (délais entre requêtes,
  peu de requêtes par run).
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
JOB_DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

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

# Nombre de résultats par page (LinkedIn pagine par lots de 10 sur cet
# endpoint public).
PAGE_SIZE = 10

# Nombre maximum de pages parcourues par combinaison mot-clé x ville,
# pour éviter de scanner des centaines de pages à chaque run.
MAX_PAGES_PER_QUERY = 3


@dataclass
class JobPosting:
    job_id: str
    title: str
    company: str
    location: str
    url: str
    description: str = ""

    @property
    def dedup_key(self) -> str:
        return self.job_id


def _build_search_url(keyword: str, location: str, start: int) -> str:
    params = {
        "keywords": keyword,
        "location": location,
        "start": start,
        # f_TPR=r604800 = offres publiées dans les 7 derniers jours,
        # suffisant vu qu'on tourne 2x/jour et qu'on dédoublonne ensuite.
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
        # L'ID d'offre se trouve dans l'URL, sous la forme .../view/1234567890
        job_id = ""
        if "-" in href:
            tail = href.split("?")[0].rstrip("/").split("-")[-1]
            job_id = tail if tail.isdigit() else ""
        if not job_id:
            # Fallback : on garde l'URL complète comme clé de dédoublonnage.
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


def _fetch_job_description(job: JobPosting, session: requests.Session) -> str:
    """Récupère la description complète d'une offre (best-effort)."""
    try:
        resp = session.get(job.url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "html.parser")
        desc_tag = soup.select_one(
            "div.show-more-less-html__markup, div.description__text"
        )
        return desc_tag.get_text(" ", strip=True) if desc_tag else ""
    except requests.RequestException as exc:
        logger.warning("Échec récupération description pour %s : %s", job.url, exc)
        return ""


def search_jobs(
    keywords: Iterable[str],
    locations: Iterable[str],
    fetch_descriptions: bool = True,
) -> list[JobPosting]:
    """
    Lance une recherche pour chaque combinaison (mot-clé, ville) et
    retourne la liste dédoublonnée des offres trouvées (par job_id).
    """
    session = requests.Session()
    seen_ids: set[str] = set()
    results: list[JobPosting] = []

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
                        "Réponse %s pour '%s' à %s, arrêt de la pagination.",
                        resp.status_code, keyword, location,
                    )
                    break

                postings = _parse_search_results(resp.text)
                if not postings:
                    # Plus de résultats, pas la peine de continuer à paginer.
                    break

                for posting in postings:
                    if posting.job_id in seen_ids:
                        continue
                    seen_ids.add(posting.job_id)
                    results.append(posting)

                time.sleep(REQUEST_DELAY_SECONDS)

    if fetch_descriptions:
        for job in results:
            job.description = _fetch_job_description(job, session)
            time.sleep(REQUEST_DELAY_SECONDS)

    logger.info("Total offres uniques trouvées : %d", len(results))
    return results
