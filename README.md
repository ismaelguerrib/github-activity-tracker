# GitHub Activity Tracker

A Python tool to extract activity days for a specific GitHub user within an organization for a given month.

## Le site local (front Angular + API Python)

Le front est une **application Angular** (dernière version, SCSS) dans
[`frontend/`](frontend/). La landing page explique le concept et le fonctionnement,
puis un formulaire prépare les paramètres, affiche la commande équivalente, lance
l’analyse et, une fois la réponse obtenue, montre le **nombre de jours actifs** et
le **nombre de contributions**, avec téléchargement du rapport en **CSV** et **PDF**.
Le serveur Python ([`server.py`](server.py)) sert l’app Angular compilée et expose
l’API ; la logique d’analyse ([`extract_activity_gh.py`](extract_activity_gh.py))
est inchangée et reste utilisable en CLI.

## How to test (pas à pas)

Prérequis : **Python 3**, **Node.js 20+** (pour `npm`) et **GitHub CLI** (`gh`).

### 1. Préparer le backend Python

```bash
cd github-activity-tracker          # si vous êtes dans le dossier parent
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

### 2. Compiler le front Angular

```bash
npm --prefix frontend ci            # installe les dépendances (une seule fois)
npm --prefix frontend run build     # génère frontend/dist/frontend/browser/
```

### 3. Connecter GitHub CLI (pour lancer de vraies analyses)

```bash
gh auth status                      # vérifier
gh auth login                       # si nécessaire
```

### 4. Démarrer le site

```bash
python3 server.py                   # écoute sur http://127.0.0.1:8000
```

Ouvrez **[http://127.0.0.1:8000](http://127.0.0.1:8000)**. `server.py` sert l’app
Angular compilée **et** l’API : ouvrir les fichiers de `frontend/dist` directement,
ou via un simple serveur statique, ne permet pas de générer les rapports.
Si le port 8000 est pris : `python3 server.py --port 8080` puis
**[http://127.0.0.1:8080](http://127.0.0.1:8080)**.

### 5. Tester le parcours complet

1. Sur la landing page, cliquez **Générer mon rapport**.
2. Saisissez une **organisation** et un **utilisateur** GitHub, choisissez le **mois**.
3. Cliquez **Générer le rapport**. La page interroge l’API et affiche un indicateur
   d’analyse (plusieurs minutes possibles selon le nombre de dépôts).
4. À la réponse, le panneau affiche le **nombre de jours actifs**, le **nombre de
   contributions** et le détail au jour le jour.
5. Téléchargez le rapport via **Télécharger CSV** et **Télécharger PDF**.

> Rappel : la page se consulte sans connexion GitHub, mais une analyse exige `gh`
> connecté. Si `gh` est indisponible, l’erreur s’affiche directement dans le panneau.

### 6. Lancer les tests automatisés

```bash
# Tests Python (serveur + exports). pypdf est requis pour le test PDF.
source .venv/bin/activate
python3 -m pip install pypdf
python3 -m unittest discover -s tests -v

# Tests Angular (composant + service)
npm --prefix frontend test -- --watch=false
```

### Développer le front en direct (optionnel)

Pour le rechargement à chaud pendant le développement du front, gardez
`python3 server.py` lancé (API) et, dans un second terminal :

```bash
npm --prefix frontend start         # ng serve sur http://localhost:4200
```

Le serveur de dev Angular proxifie `/api` vers `http://127.0.0.1:8000`
(voir [`frontend/proxy.conf.json`](frontend/proxy.conf.json)). Ouvrez alors
**[http://localhost:4200](http://localhost:4200)**.

### Fonctionnement de l’interface

Le formulaire expose l’organisation, l’utilisateur, le mois, la méthode,
le nombre de dépôts récents, les dépôts à inclure et le mode détaillé.
L’analyse utilise la session GitHub CLI du serveur ; aucun token n’est demandé
par la page. Une seule analyse s’exécute à la fois. Les rapports restent en mémoire
et expirent après 24 heures (nettoyage au lancement d’une nouvelle analyse),
ou au redémarrage du serveur. Les rapports incomplets restent téléchargeables :
les échecs figurent dans la page et dans les deux exports. Le CSV contient une ligne
par activité, avec l’organisation, l’utilisateur, la période et le statut du rapport.
Le PDF contient la synthèse et le détail quotidien, sur plusieurs pages si nécessaire.

Cette interface est conçue pour un usage **local** et écoute uniquement sur
`127.0.0.1`. Un déploiement partagé nécessiterait une authentification des utilisateurs,
une gestion distincte de leurs accès GitHub et un stockage des tâches.
Les polices Google Fonts sont facultatives ; des polices système prennent le relais
sans connexion réseau.

## Features

- **Dual Strategy**: Combines repository-by-repository checking with the GitHub search API
- **Comprehensive Activity Detection**: Tracks commits, pull requests, issues, comments, PR reviews, and wiki edits
- **Repository Discovery**: Finds the repositories a user touched, rather than relying on a fixed cutoff
- **Flexible Date Ranges**: Specify any year and month
- **JSON Output**: Save results in structured format with detailed daily activity breakdown
- **Loud Failures**: A failed call is reported, not swallowed, so an incomplete report says so
- **Deduplication**: Automatically deduplicates activity found by both methods

## Installation

```bash
# CLI only: no additional dependencies beyond Python 3 and GitHub CLI
# Check if gh is installed and authenticated:
gh auth status

# If not authenticated, run:
gh auth login
```

## Usage

The script uses GitHub CLI for authentication and API access:

```bash
# Basic usage (checks last month by default)
python extract_activity_gh.py --org org-name --user username

# Use only repository-by-repository method
python extract_activity_gh.py --org org-name --user username --method repos

# Use only GitHub search (faster, may miss some activity)
python extract_activity_gh.py --org org-name --user username --method search

# Specific user/org/date
python extract_activity_gh.py --org org-name --user username --year 2024 --month 12

# Force a repo that only ever sees wiki edits or commit comments
python extract_activity_gh.py --org org-name --user username --include-repos docs-repo-name

# Save results to JSON
python extract_activity_gh.py --org org-name --user username --output activity_report.json
```

### Command Line Arguments
- `--org`: GitHub organization name (**required**)
- `--user`: GitHub username (**required**)
- `--year`: Year to analyze (default: last month's year)
- `--month`: Month to analyze (default: last month)
- `--method`: Method to use - 'repos', 'search', or 'both' (default: both)
- `--repo-limit`: Number of most recently pushed repos to check (default: 20). Repos found by search are checked on top of these, so this is a floor rather than a cap.
- `--include-repos`: Comma-separated list of repos to always include. See [When to use `--include-repos`](#when-to-use---include-repos) — most repos no longer need it.
- `--output`: Output file for JSON results
- `--verbose`: Enable verbose output. Failures are reported with or without it.

## Authentication

The tool uses GitHub CLI for authentication. Make sure you have:

1. GitHub CLI installed (`gh` command)
2. Authenticated with GitHub: `gh auth login`
3. Your token has appropriate permissions for the organization

## Output

The tool outputs:
- List of active days in YYYY-MM-DD format
- Total count of active days
- Detailed breakdown of activity by day
- Summary information

Example output:
```
=== Final Activity Summary ===
User: username
Organization: org-name
Period: 2025-08
Total active days: 12
GitHub API requests made: 252
gh commands run: 216

Detailed daily activity:
  2025-08-01:
    - Commit: abc1234: Fix bug in authentication in repo-name
    - PR Created: #123: Add new feature in repo-name
  2025-08-03:
    - PR Review: on PR #124: Add rate limiting in repo-name
    - Issue Comment: on issue #125: Login fails on Safari in repo-name
    - Wiki Edit: edited 'API Documentation' in docs-repo-name
  2025-08-07:
    - PR Comment: on PR #126: Refactor config loading in repo-name
    - Commit: def5678: Update dependencies in repo-name
  ...
```

`GitHub API requests made` counts HTTP requests, not subprocesses: a single
`gh` command sends one request per page when it paginates, so the two numbers
differ by roughly an order of magnitude on a full run.

Activity types tracked:
- **Commits**: Code commits to repositories
- **PR Created**: Pull requests opened
- **PR Review**: Formal pull request reviews
- **PR Comment**: Review comments on pull request code
- **Issue Created**: New issues opened
- **Issue Comment**: Comments on issues, including the conversation on a pull request
- **Commit Comment**: Comments on specific commits
- **Wiki Edit**: Edits to repository wikis

## Incomplete reports

Any failed call is printed to stderr as it happens and listed at the end of the
summary:

```
INCOMPLETE: 2 call(s) failed, so activity may be missing from this report:
  - repos/org-name/repo-name/commits: gh: Not Found (HTTP 404)
  - issue list (org-name/repo-name): GraphQL: Could not resolve to a Repository
Re-run to see whether the failures were transient.
```

The exit status is 1 when this happens, and the JSON output carries a
`complete` flag and a `failures` list. A run that prints no such block lost
nothing to a failed call.

## How It Works

The tool uses two complementary methods:

1. **Repository Method** (`--method repos`):
   - Checks each selected repository for commits, issues, comments and wiki edits
   - More thorough but makes more API calls

2. **Search Method** (`--method search`):
   - Uses GitHub's search API to find commits, PRs and issues
   - Faster with fewer API calls
   - Does not see wiki edits or commit comments

3. **Both Methods** (`--method both`, default):
   - Runs both and combines the results, deduplicated
   - Recommended for accurate, comprehensive tracking

### Which repositories get checked

Repository selection is the union of two sources:

- the `--repo-limit` most recently **pushed** repositories in the organization
- every repository the search API says the user touched that month

The second matters because push order measures code pushes, not one person's
activity. A repository dormant for months still collects reviews, comments and
issues, and no cutoff on the ranked list catches those: in one real month the
user's active repositories ranked as low as 40th while only 16 were active at
all, so raising `--repo-limit` would have scanned the wrong repositories more
expensively.

PR reviews are looked up by asking search which pull requests the user reviewed,
rather than by inspecting every pull request in every repository.

### When to use `--include-repos`

Search discovery covers commits, pull requests, issues and their comments, so
those repositories are found whatever their rank. Two activity types are
invisible to it:

- **wiki edits**, which come from the parent repository's events feed and are
  indexed by no search qualifier
- **commit comments**, which `involves:` does not cover

So `--include-repos` is worth setting only for a repository where the user
edits the wiki or comments on commits but does nothing else. If they also open
an issue or a pull request there, discovery finds it on its own.

Pass the **parent repository name**, never the `.wiki` suffix. A wiki is not a
repository in the REST API, so `docs-repo-name.wiki` can only produce 404s,
while `docs-repo-name` reads both the code and the wiki activity.

## Which day an activity counts towards

Commit days come from the search API, which preserves the author's UTC offset,
so work done at 00:50 +02:00 counts as that day rather than the previous one in
UTC. Commits whose author date carries no offset, which is common for commits
made on a server, fall back to UTC.

Everything else — issues, pull requests, reviews and comments — is only exposed
by GitHub in UTC, and is counted on the UTC day.

## Limitations

- **Wiki edits expire.** They are read from GitHub's repository events feed,
  which only returns recent activity. The documented window is 90 days, and in
  practice it can be considerably shorter: one docs repository reached back
  about three weeks. Wiki edits for an older month cannot be recovered by
  re-running, so keep the report generated at the time.
- **Search caps at 1000 results**, so a month with more matching commits than
  that will fall back to what the repository scan finds.
- **Merge commits** carry the offset of whoever's environment created them,
  which is usually but not always the person credited as author.

## Notes

- The tool automatically handles API pagination
- Commits and comments are filtered by date server-side, so a repository's full
  history is not downloaded to find one month
- Activity is automatically deduplicated when using both methods
- Use `--verbose` to see per-repository progress
