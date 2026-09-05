"""Notification des nouvelles offres par email (iCloud).

Secrets GitHub Actions attendus :
- SMTP_USER      : ton identifiant Apple (l'adresse complète du compte)
- SMTP_PASSWORD  : un mot de passe pour application, généré sur
                   https://account.apple.com  →  Connexion et sécurité
                   (ce n'est PAS ton mot de passe Apple habituel)
- EMAIL_TO       : où recevoir les offres (défaut : EMAIL_FROM)
- EMAIL_FROM     : adresse d'expédition. Apple n'accepte QUE des adresses
                   rattachées au compte (@icloud.com / @me.com / alias).
                   Défaut : SMTP_USER — à définir explicitement si ton
                   identifiant Apple n'est pas une adresse iCloud.
- SMTP_HOST / SMTP_PORT : optionnels, pour un autre fournisseur.
"""

from __future__ import annotations

import os
import html
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .linkedin_scraper import JobPosting

logger = logging.getLogger(__name__)

ICLOUD_SMTP_HOST = "smtp.mail.me.com"
ICLOUD_SMTP_PORT = 587


def _build_plain_body(jobs: list[JobPosting]) -> str:
    lines = [f"{len(jobs)} nouvelle(s) offre(s) correspondant à ton profil :", ""]
    for job in jobs:
        lines.append(f"• {job.title} — {job.company} ({job.location})")
        lines.append(f"  {job.url}")
        lines.append("")
    return "\n".join(lines)


def _build_html_body(jobs: list[JobPosting]) -> str:
    rows = []
    for job in jobs:
        rows.append(
            '<tr>'
            f'<td style="padding:14px 0;border-bottom:1px solid #e5e5e5;">'
            f'<a href="{html.escape(job.url, quote=True)}" '
            'style="font-size:15px;font-weight:600;color:#0a66c2;'
            'text-decoration:none;">'
            f'{html.escape(job.title)}</a>'
            '<div style="font-size:13px;color:#555;margin-top:4px;">'
            f'{html.escape(job.company)}'
            f'{" &middot; " + html.escape(job.location) if job.location else ""}'
            '</div>'
            '</td></tr>'
        )
    return (
        '<div style="font-family:-apple-system,Helvetica,Arial,sans-serif;'
        'max-width:640px;margin:0 auto;padding:8px 16px;">'
        f'<p style="font-size:16px;font-weight:600;margin:0 0 4px;">'
        f'{len(jobs)} nouvelle(s) offre(s)</p>'
        '<p style="font-size:13px;color:#777;margin:0 0 8px;">'
        'Veille LinkedIn &middot; offres publiées ces 48 dernières heures</p>'
        f'<table style="width:100%;border-collapse:collapse;">{"".join(rows)}</table>'
        '</div>'
    )


def _send_email(jobs: list[JobPosting]) -> None:
    smtp_user = os.environ.get("SMTP_USER", "").strip()
    smtp_password = os.environ.get("SMTP_PASSWORD", "").strip()

    if not (smtp_user and smtp_password):
        raise RuntimeError(
            "Secrets manquants : "
            f"SMTP_USER={'défini' if smtp_user else 'MANQUANT'}, "
            f"SMTP_PASSWORD={'défini' if smtp_password else 'MANQUANT'}"
        )

    smtp_host = os.environ.get("SMTP_HOST", "").strip() or ICLOUD_SMTP_HOST
    smtp_port_raw = os.environ.get("SMTP_PORT", "").strip()
    smtp_port = int(smtp_port_raw) if smtp_port_raw else ICLOUD_SMTP_PORT
    email_from = os.environ.get("EMAIL_FROM", "").strip() or smtp_user
    email_to = os.environ.get("EMAIL_TO", "").strip() or email_from

    msg = MIMEMultipart("alternative")
    msg["From"] = email_from
    msg["To"] = email_to
    msg["Subject"] = f"[Veille LinkedIn] {len(jobs)} nouvelle(s) offre(s)"
    msg.attach(MIMEText(_build_plain_body(jobs), "plain", "utf-8"))
    msg.attach(MIMEText(_build_html_body(jobs), "html", "utf-8"))

    logger.info("Envoi via %s:%d — de %s vers %s",
                smtp_host, smtp_port, email_from, email_to)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(email_from, [email_to], msg.as_string())
    except smtplib.SMTPAuthenticationError as exc:
        raise RuntimeError(
            "Authentification refusée par Apple. Vérifie que SMTP_PASSWORD "
            "est bien un « mot de passe pour application » (account.apple.com "
            "→ Connexion et sécurité), et non ton mot de passe Apple habituel. "
            f"Détail : {exc}"
        ) from exc
    except smtplib.SMTPSenderRefused as exc:
        raise RuntimeError(
            f"Apple refuse d'expédier depuis « {email_from} ». Définis le "
            "secret EMAIL_FROM avec une adresse rattachée à ton compte "
            f"(@icloud.com, @me.com ou un alias). Détail : {exc}"
        ) from exc

    logger.info("Email envoyé à %s (%d offre(s)).", email_to, len(jobs))


def send_notification(jobs: list[JobPosting]) -> None:
    if not jobs:
        logger.info("Aucune nouvelle offre, pas de notification envoyée.")
        return

    # Volontairement non rattrapé : si l'email échoue, le run doit
    # apparaître en rouge dans GitHub Actions plutôt que d'échouer en silence.
    _send_email(jobs)
