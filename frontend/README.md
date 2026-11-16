# Frontend — GitHub Activity Tracker

Application **Angular** (SCSS) qui sert de landing page et de formulaire pour
l'outil d'analyse d'activité GitHub. Elle appelle l'API locale exposée par
[`server.py`](../server.py) (racine du dépôt) ; elle n'a pas de backend propre.

- Landing page : explique le concept et le fonctionnement.
- Formulaire : organisation, utilisateur, mois, méthode, options avancées.
- Résultat : nombre de **jours actifs**, nombre de **contributions**, détail
  au jour le jour, et export **CSV** / **PDF**.

Généré avec Angular CLI. Composant racine : [`src/app/app.ts`](src/app/app.ts) ·
appels API : [`src/app/report.service.ts`](src/app/report.service.ts).

## Prérequis

- **Node.js 20+** (fournit `npm`)
- Le backend Python lancé à côté (voir le [README racine](../README.md)) —
  sans lui, le formulaire ne peut pas générer de rapport.

```bash
npm ci        # installe les dépendances (une seule fois)
```

## Développement (rechargement à chaud)

Lancez d'abord l'API Python (`python3 server.py` à la racine), puis :

```bash
npm start     # ng serve sur http://localhost:4200
```

Le serveur de dev proxifie `/api` vers `http://127.0.0.1:8000`
(voir [`proxy.conf.json`](proxy.conf.json)), donc les appels API fonctionnent
sans configuration supplémentaire.

## Build de production

```bash
npm run build # génère dist/frontend/browser/
```

C'est ce dossier que [`server.py`](../server.py) sert directement : après un
build, `python3 server.py` expose l'app **et** l'API sur le même port (8000).

## Tests

```bash
npm test -- --watch=false   # tests unitaires (Vitest)
```
