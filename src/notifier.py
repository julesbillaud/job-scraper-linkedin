"""Envoi d'un email récapitulatif des nouvelles offres matchées.

Configuration via variables d'environnement (voir README.md) :
- SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
- EMAIL_FROM, EMAIL_TO
"""

from __future__ import annotations

import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .linkedin_scraper import JobPosting

logger = logging.getLogger(__name__)


def _build_email_body(jobs: list[JobPosting]) -> str:
    lines = [f"{len(jobs)} nouvelle(s) offre(s) correspondant à ton profil :\n"]
    for job in jobs:
        lines.append(f"• {job.title} — {job.company} ({job.location})")
        lines.append(f"  {job.url}")
        lines.append("")
    return "\n".join(lines)


def send_notification(jobs: list[JobPosting]) -> None:
    if not jobs:
        logger.info("Aucune nouvelle offre, pas d'email envoyé.")
        return

    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ["SMTP_USER"]
    smtp_password = os.environ["SMTP_PASSWORD"]
    email_from = os.environ.get("EMAIL_FROM", smtp_user)
    email_to = os.environ["EMAIL_TO"]

    msg = MIMEMultipart()
    msg["From"] = email_from
    msg["To"] = email_to
    msg["Subject"] = f"[Veille emploi] {len(jobs)} nouvelle(s) offre(s)"
    msg.attach(MIMEText(_build_email_body(jobs), "plain", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(email_from, [email_to], msg.as_string())

    logger.info("Email envoyé avec %d offre(s).", len(jobs))
