# Coach santé IA : architecture technique

Oct 17, 2026 · @said

## Vue d'ensemble

Le système transforme chaque nuit tes données Garmin en un rapport du matin avec un programme adapté, pour progresser en sommeil, cardio, musculation et gestion du stress.

&#91;embedded content: architecture · 4 couches, 3 agents\]

Les données descendent couche par couche : collecte et stockage la nuit, analyse puis planification par les agents, et le rapport arrive avant ton réveil.

## Sources de données

Trois sources alimentent le système : la montre (objectif), tes objectifs (stable) et ton ressenti (subjectif).

| Source | Contenu | Fréquence |
| --- | --- | --- |
| Garmin Connect | VO2 max, HRV, score de sommeil, respiration, statut d'entraînement, fréquence cardiaque, stress, activités (gym, natation, course) | Chaque nuit |
| Base de connaissances | Tes objectifs, tes règles d'entraînement, principes sur le sommeil, le cardio, la musculation et la gestion du stress | Mise à jour manuelle |
| Journal personnel (optionnel) | Ressenti, fatigue, douleurs, humeur, contraintes du jour | Chaque matin ou soir |

## Ingestion et stockage

Un script Python récupère les données Garmin chaque nuit et les range dans une base locale.

- **Connecteur Garmin** : librairie open source `garminconnect` (Python), authentification avec ton compte, export JSON brut.
- **Normalisation** : un module transforme le JSON en tables propres (une ligne par jour et par activité).
- **Base de données** : SQLite pour démarrer, Postgres si tu ajoutes un tableau de bord ou un hébergement cloud.
- **Tables principales** : `daily_metrics` (HRV, sommeil, stress, FC repos, respiration, VO2 max), `activities` (type, durée, charge, zones), `journal`, `plans` (programmes générés), `reports`.
- **Indicateurs calculés** : moyennes sur 7 et 30 jours, écart à ta baseline HRV, dette de sommeil, ratio charge aiguë / chronique.

## Couche agents

Trois agents spécialisés travaillent à la suite, chacun avec un rôle clair et une sortie structurée en JSON.

| Agent | Entrées | Rôle | Sortie |
| --- | --- | --- | --- |
| Analyste | Métriques du jour + tendances 7/30 jours | Détecter récupération, fatigue, stress, progrès | Score de forme + alertes |
| Coach | Analyse + base de connaissances + historique des séances + journal | Choisir la séance du jour : gym, natation, course ou récupération, avec intensité | Programme détaillé du jour |
| Rédacteur | Analyse + programme | Mettre en forme le rapport lisible | Rapport du matin (Markdown / HTML) |

- **Modèles** : API Gemini pour les agents, ou Claude ; un seul fournisseur au début pour simplifier.
- **Base de connaissances** : fichiers Markdown dans le repo, injectés dans le prompt ; un index vectoriel (RAG) seulement si elle devient volumineuse.
- **Garde-fous** : règles fixes en code (par exemple pas de séance intense si HRV très basse plusieurs jours), le modèle ne fait que proposer dans ce cadre.

## Orchestration et planification

Deux options, à trancher ensemble avant de coder.

| Option | Comment | Avantages | Limites |
| --- | --- | --- | --- |
| n8n | Workflow visuel : cron, appel du script, nœuds IA, envoi | Rapide à monter, envoi mail/Telegram natif | Logique complexe moins lisible, moins versionnable |
| Python + LangChain (ou LangGraph) | Pipeline codé, lancé par GitHub Actions ou un cron | Tout dans le repo, testable, Claude Code t'aide à coder | Un peu plus de travail au départ |

Planification proposée : collecte vers 5 h, analyse et génération ensuite, rapport livré avant ton réveil.

## Sorties

- **Rapport du matin** (mail ou Telegram) : score de forme, sommeil, HRV, stress, tendances de la semaine, programme du jour, conseil récupération et gestion du stress.
- **Historique** : chaque rapport et programme stocké en base, pour mesurer la progression.
- **Bilan hebdomadaire** (phase 2) : évolution VO2 max, charge, régularité, ajustement des objectifs.
- **Tableau de bord** (phase 3) : Streamlit ou Grafana pour visualiser les courbes.

## Structure du repo GitHub et étapes

```
coach-sante-ia/
  ingestion/      # connecteur Garmin, normalisation
  storage/        # schéma SQLite, migrations
  metrics/        # tendances, baselines, charge
  agents/         # analyste, coach, rédacteur + prompts
  knowledge/      # objectifs et principes en Markdown
  delivery/       # mail, Telegram
  pipeline.py     # orchestration de bout en bout
  .github/workflows/daily.yml
```

- [ ] Étape 1 : connecter Garmin et stocker 30 jours d'historique
- [ ] Étape 2 : calculer tendances et baselines
- [ ] Étape 3 : écrire la base de connaissances (objectifs, règles)
- [ ] Étape 4 : agent analyste puis agent coach
- [ ] Étape 5 : rapport et envoi automatique chaque matin
- [ ] Étape 6 : journal, bilan hebdo, tableau de bord
