"""Orchestration complète : recherche LinkedIn -> filtre -> dédoublonnage
-> notification.

Usage :
    python main.py
"""

from __future__ import annotations

import logging

from src.linkedin_scraper import search_jobs
from src.filter import load_lines, filter_jobs
from src.dedup import load_seen_ids, save_seen_ids, filter_new_jobs
from src.notifier import send_notification

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

SEARCH_QUERIES_PATH = "config/search_queries.txt"
KEYWORDS_PATH = "config/keywords.txt"
LOCATIONS_PATH = "config/locations.txt"
COMPANIES_PATH = "config/companies.txt"
EXCLUDE_PATH = "config/exclude.txt"
SEEN_OFFERS_PATH = "seen_offers.json"


def main() -> None:
    # Deux listes distinctes, deux rôles :
    #  - queries   : ce qu'on DEMANDE à LinkedIn (court = rapide)
    #  - keywords  : ce qu'on GARDE dans les résultats (long = précis)
    queries = load_lines(SEARCH_QUERIES_PATH)
    keywords = load_lines(KEYWORDS_PATH)
    locations = load_lines(LOCATIONS_PATH)
    companies = load_lines(COMPANIES_PATH)
    exclusions = load_lines(EXCLUDE_PATH)

    logger.info(
        "Lancement : %d recherches x %d villes | %d règles de tri, "
        "%d exclusions | filtre entreprise %s",
        len(queries), len(locations), len(keywords), len(exclusions),
        f"actif sur {len(companies)} boîtes" if companies else "désactivé",
    )

    # Charger la mémoire anti-doublons AVANT la recherche
    # pour permettre l'arrêt anticipé dès qu'on retrouve des offres connues
    seen_ids = load_seen_ids(SEEN_OFFERS_PATH)

    all_jobs = search_jobs(queries, locations, already_seen=seen_ids)
    matched_jobs = filter_jobs(all_jobs, keywords, companies, exclusions)
    new_jobs = filter_new_jobs(matched_jobs, seen_ids)

    logger.info(
        "%d offres scannées, %d matchées, %d nouvelles à notifier",
        len(all_jobs), len(matched_jobs), len(new_jobs),
    )

    if new_jobs:
        send_notification(new_jobs)
    else:
        logger.info("⚠️  Aucune nouvelle offre à notifier — pas d'email envoyé.")

    # Sauvegarder TOUTES les offres matchées (pas seulement les nouvelles)
    seen_ids.update(job.dedup_key for job in matched_jobs)
    save_seen_ids(SEEN_OFFERS_PATH, seen_ids)


if __name__ == "__main__":
    main()
