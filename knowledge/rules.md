# Mes règles d'entraînement

> Fichier unique lu par le coach. Ordre de priorité : d'abord les 10 règles de santé (source : Andrew Huberman, *Protocols*), puis mes règles personnelles.
> Les plafonds d'intensité calculés dans le code (`rules.py`, `settings.toml`) passent toujours avant tout : une règle ci-dessous ne permet jamais de dépasser le plafond du jour.

## Partie 1 : Les 10 règles prioritaires

### 1. Lumière du jour dans les yeux le matin
- **Règle :** dehors, dans les 30 à 60 premières minutes après le réveil, sans vitre, pare-brise ni lunettes de soleil. Un ciel couvert compte aussi. Sans soleil (réveil avant le lever du jour) : lampe de 10 000 lux. Journée ratée : rester dehors plus longtemps le lendemain.
- **Pourquoi :** elle déclenche le pic de cortisol du matin (humeur, attention, immunité), qui prépare un cortisol bas et de la mélatonine le soir. Un écran est trop faible pour cet effet.
- **Pour le coach :** premier conseil du rapport quand le sommeil ou l'HRV sont moyens ; le lier à la marche du matin. Signal : score de sommeil, HRV, heure de réveil.

### 2. Nuit sombre, sans écran, au frais
- **Règle :** soirée à lumière tamisée ; aucun écran les 30 dernières minutes avant de dormir (sinon écran en mode rouge / luminosité minimale) ; chambre la plus sombre possible (masque, bouchons si besoin) et fraîche. Un peu de lumière naturelle en fin d'après-midi aide à compenser les écrans du soir (moins efficace chez les adolescents). Réveil nocturne : 10 longues expirations ; ne pas ruminer.
- **Pourquoi :** la lumière le soir fait monter le cortisol et baisse la mélatonine. Les études associent nuits claires et risque de mortalité plus élevé ; les journées lumineuses et les nuits sombres s'additionnent.
- **Pour le coach :** conseil du soir ; adapter selon la dette de sommeil et le score de sommeil. Dormir sur le côté, tête légèrement surélevée, est évoqué pour l'élimination des déchets du cerveau (la source dit « semble »).

### 3. Musculation : composés, peu de séries, repos après les jambes
- **Règle :** échauffement (5 min de cardio léger), exercices composés (tractions, rowing, dips, squat, charnière de hanche / soulevé de terre), 2 à 3 séries de travail par exercice, séries proches de l'échec seulement si la récupération est bonne. Un jour de repos après une vraie séance de jambes. Alterner jours de force et jours de cardio.
- **Pourquoi :** 45 minutes de séries proches de l'échec font monter le cortisol de 3 à 4 fois, ce qui est un stress utile et ponctuel, pas un problème.
- **Pour le coach :** le nombre de séances de force par semaine est celui de `goals.md` ; la source propose une structure (composés, 2 à 3 séries), à garder quel que soit le volume. Signal : readiness, HRV, jours depuis la dernière séance intense.

### 4. Cardio : trois formats dans la semaine
- **Règle :** une séance longue et lente (~1 h), une séance modérée (~30 min), une séance courte d'intervalles (par exemple 1 min facile, puis 30 s à fond / 10 s facile, répétés).
- **Pourquoi :** endurance et capacité à sprinter ; l'entraînement à haute intensité et à la VO2 max est cité pour l'HRV.
- **Pour le coach :** viser la VO2 max de `goals.md` avec l'intervalle seulement quand la récupération est verte ; sinon basculer sur le format lent. Signal : VO2 max, ratio de charge aiguë/chronique, training readiness.

### 5. S'entraîner tôt et à heure régulière
- **Règle :** idéalement dans les 3 à 4 premières heures de la journée ; l'après-midi convient aussi. Garder à peu près la même heure. Après un effort tardif : longues expirations et douche chaude dans la dernière heure avant le lit.
- **Pourquoi :** l'horloge interne s'aligne sur l'heure de l'entraînement, ce qui augmente l'envie et l'énergie ; la douche chaude fait baisser la température centrale, favorable à l'endormissement.
- **Pour le coach :** proposer l'horaire habituel ; conseil de redescente le soir après une séance tardive.

### 6. Outil anti-stress immédiat : le soupir physiologique
- **Règle :** deux inspirations successives (la seconde, courte, remplit complètement les poumons), puis une longue expiration ; une seule fois suffit pour faire baisser l'activation. Pratique quotidienne de 5 minutes : respiration lente ou méditation. Quelques longues expirations dans la journée font monter l'HRV.
- **Pourquoi :** l'expiration longue ralentit le cœur (nerf vague). Dans l'étude citée, tous les groupes ont progressé et le soupir physiologique le plus.
- **Pour le coach :** conseil de stress du jour quand le stress moyen est au-dessus de ta moyenne 7 jours ou l'HRV sous ta baseline. Signal : stress, HRV.

### 7. Marcher : 7 000 à 8 000 pas, et 5 à 10 min après les repas
- **Règle :** viser 7 000 à 8 000 pas par jour (pas besoin de 10 000) ; marcher 5 à 10 minutes après un repas ; bouger souvent (escaliers, appels debout).
- **Pourquoi :** la marche atténue les pics de glycémie après un repas, et le mouvement spontané brûle beaucoup de calories. La baisse de métabolisme avec l'âge viendrait surtout de la perte de muscle et de mouvement.
- **Pour le coach :** objectif de pas du jour ; suffisant même un jour de repos ou de récupération. Signal : pas (`steps`).

### 8. Alimentation simple
- **Règle :** ni trop ni trop peu de calories ; protéines complètes à fort rapport protéines/calories (œufs, viande maigre, poisson) ; légumes et fruits ; aliments fermentés peu sucrés ; huile d'olive. Féculents (riz, pâtes, avoine) utiles pour les muscles et pour baisser le cortisol le soir, mais éviter de les combiner avec beaucoup de gras ; ne pas manger trop près du coucher ni dormir avec la faim.
- **Pourquoi :** les féculents font baisser le cortisol, ce qui aide à s'endormir ; l'excès de calories surcharge les mitochondries.
- **Pour le coach :** conseils généraux seulement ; Garmin ne mesure pas l'alimentation. Pas de régime ni de chiffres de calories personnalisés.

### 9. Un moment par jour sans objectif
- **Règle :** une fois par jour, sortir du mode « performance » : méditation, dessin, musique, promenade sans but. Au réveil, 10 respirations de méditation. Le soir, ne pas traiter un sujet stressant ni envoyer un message sensible quand on est fatigué.
- **Pourquoi :** le cortex préfrontal (prise de décision, contrôle des impulsions) est moins performant quand on est fatigué ou stressé, et les stress psychologiques se prolongent la nuit.
- **Pour le coach :** conseil de stress en complément de la règle 6, surtout après une mauvaise nuit ou une journée très stressante.

### 10. S'hydrater tôt
- **Règle :** 16 à 32 oz (~0,5 à 1 L) d'eau au réveil, puis environ 80 oz (~2,4 L) sur la journée, plus en début qu'en fin de journée. Électrolytes facultatifs.
- **Pourquoi :** la vigilance augmente quand on est hydraté, et l'eau le matin contribue au pic de cortisol.
- **Pour le coach :** rappel simple en début de rapport ; plus important les jours d'effort ou de chaleur.

---

## Partie 2 : Mes règles personnelles

### Charge et récupération
- Jamais deux séances intenses de suite.
- Une séance intense = au plus 1 jour sur 2 ; au moins 2 jours faciles ou de repos par semaine.
- Respecter la répartition hebdomadaire de `goals.md` : si un type de séance n'a pas été fait depuis plusieurs jours et que la récupération le permet, le proposer.
- Si une zone du corps est douloureuse (journal), ne pas la solliciter ; proposer une alternative.
- Ne jamais conseiller de dormir moins que nécessaire, même pour gagner du temps. La source suggère qu'une méditation régulière pourrait réduire le sommeil nécessaire : c'est une hypothèse, pas un conseil.

### Séances
- Musculation : échauffement 5 à 10 min, 4 à 6 exercices principaux, 2 à 3 séries de travail chacun (règle 3), repos 60 à 120 s, étirements en fin de séance.
- Cardio facile : allure où l'on peut parler en phrases complètes (zone 2).
- Natation : privilégier la technique et le volume facile ; l'intensité seulement si la forme est bonne.

### Format du rapport
- Toujours terminer par un conseil de récupération et un conseil de gestion du stress, adaptés à la journée.

---

## Partie 3 : Hors périmètre (ne pas conseiller)
- **Compléments** (magnésium, oméga-3, vitamine D, alpha-GPC, créatine), **peptides, GLP-1, psychédéliques** : dosages et décisions médicales individuelles ; l'application ne donne pas de conseil médical.
- **Foi, prière, religion** : choix personnel.
- **Lampes de lumière rouge** : le soleil suffit selon la source.
- **Exposition au froid** : à ne conseiller qu'avec prudence ; non retenue dans le top 10.
- **Blocs de travail intellectuel de 90 min, téléphone hors de la pièce, auto-évaluation** : utiles, mais hors des objectifs de l'application.

## Limites de la source
- Un seul entretien, avis d'un expert : certaines affirmations sont corrélationnelles (soleil et longévité, café et démence) ou spéculatives.
