# Veille emploi — LinkedIn guest API (finance de marché / gestion obligataire)

## Contexte

Voir en bas de ce fichier la section "Profil et contexte complet" si tu
(l'agent) reprends ce projet sans avoir l'historique de la conversation
d'origine.

Ce projet scanne LinkedIn (sans login, via l'API publique "invité" que
LinkedIn utilise pour son propre moteur de recherche) à la recherche
d'offres publiées dans les dernières 48h, et envoie un email
récapitulatif des nouvelles offres toutes les 2h, automatiquement,
via GitHub Actions.

## Structure

```
config/
  search_queries.txt  # ce qu'on DEMANDE à LinkedIn — garder COURT (= vitesse)
  keywords.txt        # ce qu'on GARDE dans les résultats — long = précis
  exclude.txt         # ce qu'on JETTE même si ça matchait un mot-clé
  locations.txt       # villes ciblées
  companies.txt       # filtre optionnel par entreprise (vide = désactivé)
src/
  linkedin_scraper.py   # requêtes à l'API guest LinkedIn
  filter.py              # matching mots-clés / exclusions / entreprise
  dedup.py                # mémoire anti-doublons (seen_offers.json)
  notifier.py              # envoi email (iCloud)
main.py                    # orchestration
.github/workflows/scraper.yml   # cron toutes les 2h
```

### Les trois fichiers de config, et pourquoi ils sont séparés

Le coût en temps est **entièrement** porté par `search_queries.txt` :
1 ligne = 6 villes × 2 pages ≈ 12 requêtes ≈ 30 s. Avec 12 lignes, un run
dure ~5 min. Mettre 59 termes ici faisait des runs de 60 min.

`keywords.txt` et `exclude.txt` sont **gratuits** : ils trient une liste
déjà en mémoire. C'est là qu'il faut affiner ce que tu reçois.

```
LinkedIn ──search_queries──> ~150 offres brutes
                             ──keywords──> ~35 pertinentes
                                           ──exclude──> ~30 envoyées
```

Syntaxe de `keywords.txt` / `exclude.txt` — le `+` signifie « ET » :

```
fixed income      # le titre contient l'expression telle quelle
rates + trader    # le titre contient "rates" ET "trader", ordre libre
```

Le `+` est essentiel : les vrais intitulés sont sales. *"Global Rates -
Euro STIRT and Cross Currency Trader"* est attrapé par `rates + trader`,
mais serait raté par `rates trader`.

## Setup local (pour tester avant de pousser sur GitHub)

```bash
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate sous Windows
pip install -r requirements.txt

export SMTP_USER=ton.identifiant@apple            # ton identifiant Apple
export SMTP_PASSWORD=xxxx-xxxx-xxxx-xxxx         # mot de passe POUR APPLICATION
export EMAIL_FROM=ton.adresse@icloud.com         # doit être une adresse du compte
export EMAIL_TO=ton.adresse@icloud.com

python main.py
```

`SMTP_HOST` / `SMTP_PORT` sont optionnels : par défaut
`smtp.mail.me.com:587` (iCloud).

Le mot de passe pour application se génère sur
[account.apple.com](https://account.apple.com) → Connexion et sécurité →
Mots de passe pour application. **Ce n'est pas ton mot de passe Apple
habituel** — celui-ci sera systématiquement refusé.

Piège fréquent : Apple n'accepte d'expédier que depuis une adresse
rattachée au compte (`@icloud.com`, `@me.com` ou un alias). Si ton
identifiant Apple est une adresse externe (Gmail par ex.), `SMTP_USER`
reste cet identifiant mais `EMAIL_FROM` doit être ton adresse iCloud.

## Setup GitHub Actions (exécution automatique)

1. Pousser ce repo sur GitHub (peut être privé).
2. Dans les Settings du repo → Secrets and variables → Actions, ajouter
   les secrets : `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM`, `EMAIL_TO`
   (et éventuellement `SMTP_HOST` / `SMTP_PORT` pour un autre
   fournisseur).
3. Le workflow tourne toutes les 2h entre 07h et 19h UTC (9h–21h Paris en
   été, 8h–20h en hiver). Un seul run à la fois (`concurrency`) : deux
   runs simultanés se marchaient dessus au moment de committer
   `seen_offers.json`, ce qui faisait échouer le second.
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
