# Veille emploi — LinkedIn guest API (finance de marché / gestion obligataire)

## Contexte

Voir en bas de ce fichier la section "Profil et contexte complet" si tu
(l'agent) reprends ce projet sans avoir l'historique de la conversation
d'origine.

Ce projet scanne LinkedIn (sans login, via l'API publique "invité" que
LinkedIn utilise pour son propre moteur de recherche) à la recherche
d'offres correspondant à une liste de mots-clés, et envoie un email
récapitulatif des nouvelles offres deux fois par jour, automatiquement,
via GitHub Actions.

## Structure

```
config/
  keywords.txt    # mots-clés de filtrage (déjà remplis)
  locations.txt   # villes ciblées (déjà remplies)
  companies.txt   # filtre optionnel par entreprise (vide = désactivé)
src/
  linkedin_scraper.py   # requêtes à l'API guest LinkedIn
  filter.py              # matching mots-clés / entreprise
  dedup.py                # mémoire anti-doublons (seen_offers.json)
  notifier.py              # envoi email
main.py                    # orchestration
.github/workflows/scraper.yml   # cron 11h/15h Paris
```

## Setup local (pour tester avant de pousser sur GitHub)

```bash
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate sous Windows
pip install -r requirements.txt

export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=ton.email@gmail.com
export SMTP_PASSWORD=xxxx-xxxx-xxxx-xxxx   # mot de passe d'application Gmail, pas ton mdp normal
export EMAIL_FROM=ton.email@gmail.com
export EMAIL_TO=ton.email@gmail.com

python main.py
```

Pour un mot de passe d'application Gmail : compte Google → Sécurité →
validation en 2 étapes (à activer si pas déjà fait) → "Mots de passe des
applications".

## Setup GitHub Actions (exécution automatique)

1. Pousser ce repo sur GitHub (peut être privé).
2. Dans les Settings du repo → Secrets and variables → Actions, ajouter
   les 6 secrets : `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`,
   `EMAIL_FROM`, `EMAIL_TO`.
3. Le workflow tourne automatiquement à 11h et 15h heure de Paris (voir
   note DST dans `scraper.yml` — il se déclenche 4x/jour pour couvrir
   heure d'été et d'hiver sans réglage manuel deux fois par an ; si tu
   préfères une précision exacte, on peut affiner avec un check
   `zoneinfo` dans le script plutôt que 4 cron entries).
4. Possible de le lancer manuellement via l'onglet "Actions" → "Run
   workflow" pour tester sans attendre l'horaire programmé.

## Points d'attention

- **Pas de compte LinkedIn utilisé** : l'API guest est publique et ne
  nécessite ni login ni cookie. Le script reste volontairement à un
  faible volume de requêtes (délais entre appels) pour limiter le risque
  de blocage IP.
- **`seen_offers.json`** est committé automatiquement par le workflow
  après chaque run — c'est la mémoire anti-doublons. Ne pas le supprimer
  manuellement sauf si tu veux forcer une renotification de tout.
- **`config/companies.txt`** est vide par défaut = pas de filtre
  entreprise, donc large sur toute offre finance de marché matchée par
  mots-clés. Décommenter la liste dans le fichier pour resserrer sur les
  ~51 boîtes ciblées (Amundi, PIMCO, Pictet, etc. — liste déjà présente
  en commentaire dans le fichier).
- Si LinkedIn change la structure HTML de ses pages (les sélecteurs CSS
  dans `linkedin_scraper.py` : `base-search-card__title`,
  `base-search-card__subtitle`, etc.), le parsing peut casser — c'est le
  seul point de fragilité de cette architecture (inhérent à toute
  utilisation d'un endpoint non documenté). Si `main.py` remonte 0
  résultat de façon suspecte, vérifier en premier ces sélecteurs.

## Profil et contexte complet (pour un agent sans historique)

L'utilisateur travaille chez Rothschild AM, sur un desk de gestion
obligataire (front office, buy side), et veut un poste équivalent
ailleurs (AM, banque, fonds) à Paris, Londres, Genève ou aux États-Unis.
Il travaille à temps plein donc n'a pas le temps de surveiller
manuellement les offres. Décisions déjà prises et à respecter :
- Pas de scoring par LLM/IA dans cette version (pas d'abonnement
  premium) — uniquement un filtre par mots-clés.
- Notification par email uniquement (pas de Telegram/Discord).
- Exécution automatique sans que le PC de l'utilisateur soit allumé
  → GitHub Actions.
- Source de données : LinkedIn via l'API guest (pas de scraping HTML
  fragile des pages carrière individuelles de chaque banque, approche
  abandonnée après un premier essai jugé trop complexe/peu fiable).
