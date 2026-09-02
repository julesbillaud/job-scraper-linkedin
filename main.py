"""Orchestration complète : recherche LinkedIn -> filtre -> dédoublonnage
-> notification email.

Usage :
    python main.py

Variables d'environnement requises (voir README.md) :
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, EMAIL_FROM, EMAIL_TO
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

KEYWORDS_PATH = "config/keywords.txt"
LOCATIONS_PATH = "config/locations.txt"
COMPANIES_PATH = "config/companies.txt"
SEEN_OFFERS_PATH = "seen_offers.json"


def main() -> None:
    keywords = load_lines(KEYWORDS_PATH)
    locations = load_lines(LOCATIONS_PATH)
    companies = load_lines(COMPANIES_PATH)

    logger.info(
        "Lancement : %d mots-clés x %d villes (filtre entreprise %s)",
        len(keywords), len(locations),
        f"actif sur {len(companies)} boîtes" if companies else "désactivé",
    )

    all_jobs = search_jobs(keywords, locations)
    matched_jobs = filter_jobs(all_jobs, keywords, companies)

    seen_ids = load_seen_ids(SEEN_OFFERS_PATH)
    new_jobs = filter_new_jobs(matched_jobs, seen_ids)

    logger.info(
        "%d offres trouvées, %d matchées, %d nouvelles",
        len(all_jobs), len(matched_jobs), len(new_jobs),
    )

    send_notification(new_jobs)

    seen_ids.update(job.dedup_key for job in matched_jobs)
    save_seen_ids(SEEN_OFFERS_PATH, seen_ids)


if __name__ == "__main__":
    main()
