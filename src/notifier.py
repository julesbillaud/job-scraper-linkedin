"""Notification des nouvelles offres d'emploi via Telegram et/ou Email.

Configuration via variables d'environnement :
- TELEGRAM (recommandé) : TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
- EMAIL (optionnel) : SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, EMAIL_FROM, EMAIL_TO
"""

from __future__ import annotations

import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from .linkedin_scraper import JobPosting

logger = logging.getLogger(__name__)


def _send_telegram(jobs: list[JobPosting], token: str, chat_id: str) -> None:
    """Envoie un message formaté sur Telegram."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    # Telegram a une limite de 4096 caractères par message.
    # On découpe les offres par paquets de 10 si besoin.
    chunk_size = 10
    for i in range(0, len(jobs), chunk_size):
        chunk = jobs[i : i + chunk_size]
        lines = [f"💼 <b>[LinkedIn] {len(jobs)} nouvelle(s) offre(s)</b>\n"]
        
        for job in chunk:
            lines.append(f"• <b>{job.title}</b>")
            lines.append(f"  🏢 {job.company} | 📍 {job.location}")
            lines.append(f"  🔗 <a href='{job.url}'>Voir l'offre</a>\n")

        text = "\n".join(lines)
        
        resp = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            logger.error("Erreur envoi Telegram : %s", resp.text)
        else:
            logger.info("Message Telegram envoyé avec succès.")


def _send_email(jobs: list[JobPosting]) -> None:
    """Envoie un email récapitulatif."""
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    email_to = os.environ.get("EMAIL_TO")

    if not (smtp_host and smtp_user and smtp_password and email_to):
        return

    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    email_from = os.environ.get("EMAIL_FROM", smtp_user)

    lines = [f"{len(jobs)} nouvelle(s) offre(s) correspondant à ton profil :\n"]
    for job in jobs:
        lines.append(f"• {job.title} — {job.company} ({job.location})")
        lines.append(f"  {job.url}")
        lines.append("")

    msg = MIMEMultipart()
    msg["From"] = email_from
    msg["To"] = email_to
    msg["Subject"] = f"[Veille emploi] {len(jobs)} nouvelle(s) offre(s)"
    msg.attach(MIMEText("\n".join(lines), "plain", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(email_from, [email_to], msg.as_string())

    logger.info("Email envoyé avec %d offre(s).", len(jobs))


def send_notification(jobs: list[JobPosting]) -> None:
    if not jobs:
        logger.info("Aucune nouvelle offre, pas de notification envoyée.")
        return

    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    sent = False

    if telegram_token and telegram_chat_id:
        try:
            _send_telegram(jobs, telegram_token, telegram_chat_id)
            sent = True
        except Exception as exc:
            logger.error("Échec notification Telegram : %s", exc)

    # Fallback ou complément par email
    if os.environ.get("SMTP_USER"):
        try:
            _send_email(jobs)
            sent = True
        except Exception as exc:
            logger.error("Échec notification Email : %s", exc)

    if not sent:
        logger.warning(
            "Aucun canal de notification configuré (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID ou SMTP_USER)."
        )
