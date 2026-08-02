# Système de design — GeoChallenge Tracker

**Date de création :** 2026-08-03
**Type :** Référence de design — conventions visuelles établies dans le code
**Portée :** Frontend (Vue 3 + Tailwind CSS 3), issu de l'audit design frontend (dark mode, cohérence des couleurs, hiérarchie visuelle, feedback de chargement)

> Ce document est la version publique et versionnée des choix de design du projet. Une version complémentaire, `DESIGN.md` à la racine du repo, est gitignorée et sert d'entrée machine-readable au skill de design utilisé pendant le développement ; son contenu narratif est repris ici.

---

## Vue d'ensemble

**« Le tableau de bord de la chasse au trésor »**

GeoChallenge Tracker remplace le suivi de challenges par tableur par une détection automatique et un calcul de progression. La majorité du temps, l'utilisateur est à son bureau ou dans son canapé en train de planifier et consulter, pas sur le terrain — l'exception étant la carte "Targets", utilisée en déplacement pour trouver la prochaine cache. Le système visuel suit donc les priorités du mode Operate : lisibilité, cohérence et faible charge cognitive priment sur la décoration. La couleur n'est jamais utilisée pour l'ambiance ; c'est un signal fonctionnel qui garde toujours le même sens partout où il apparaît. La seule couleur réellement "de marque" — une gamme or ancrée sur `#FFD700`, déjà présente dans `tailwind.config.ts` — est utilisée avec parcimonie, comme un marqueur symbolique de récompense (l'icône trophée d'un challenge complété), pas comme un accent visuel dominant.

**Caractéristiques clés :**
- Surfaces plates (une bordure, pas une ombre, définit une carte)
- Un rôle par couleur, réutilisé à l'identique sur toutes les pages
- Icône = de quoi parle le chiffre ; couleur = quel type de chiffre c'est
- Le mode sombre est une palette parallèle de premier ordre, pas un ajout après-coup
- Vocabulaire francophone et geocaching-natif (code GC, D/T, FTF, matrice, calendar challenge)

## Couleurs

Chaque couleur non neutre porte un **rôle** fixe, établi et vérifié pour le contraste WCAG AA pendant l'audit design frontend (août 2026). La même couleur garde toujours le même rôle, sur toutes les pages — une couleur n'est jamais choisie page par page pour varier visuellement.

### Primaire
- **Bleu primaire** (`blue-600` / `#2563eb`, survol `blue-700` / `#1d4ed8`) : la couleur d'action par défaut — boutons primaires ("Sauvegarder", "Se connecter"), tuile de taux de complétion principal, mises en avant d'état actif (accent des radios/checkbox, filtre sélectionné).

### Secondaire
- **Vert succès** (`green-600` / `#16a34a` pour l'icône ; le texte de libellé en mode clair est monté à `green-700` / `#15803d` pour respecter le contraste AA sur fond `green-50` ; `green-800` / `#166534` pour le grand chiffre) : marque un compteur de succès/complétion — "jours complétés", "combinaisons complétées", "Terminés". Jamais utilisé pour un état en cours ou neutre.
- **Violet secondaire** (`purple-600` / `#9333ea`, profond `purple-800` / `#6b21a8`) : une vue secondaire ou variante d'un taux qui a déjà un équivalent bleu primaire dans la même rangée de tuiles — ex. le taux de complétion sur 366 jours (année bissextile) à côté de celui sur 365 jours, ou "next round" à côté du taux courant.
- **Indigo méta** (`indigo-600` / `#4f46e5`, profond `indigo-800` / `#3730a3`) : un compteur méta récurrent qui n'est pas un simple total — "tours de matrice" complétés. Utilisé aussi pour le bouton d'action secondaire/synchronisation (sync des found caches) et l'état "activé" des interrupteurs (mode sombre).

### Tertiaire
- **Ambre d'avertissement** (`yellow-600`/`700`/`800`) : quelque chose que l'utilisateur doit remarquer sans que ce soit une erreur — "aucune localisation configurée", codes GC non reconnus après une synchronisation.
- **Rouge danger** (`red-600` pour boutons/erreurs, `red-700`/`800` pour le texte des bannières) : actions destructrices ("Supprimer") et états d'erreur.

### Neutre
- **Encre neutre** (`gray-900` texte en clair / `gray-100` en sombre) : titres et texte principal.
- **Libellé neutre** (`gray-500`/`600` en clair / `gray-400` en sombre) : texte secondaire, libellés de formulaire, texte d'aide, et toute tuile de stat dont le chiffre n'a pas de polarité bonne/mauvaise (un simple compteur d'activité, un total).
- **Surface neutre** (`white` / `gray-800` pour le fond de carte, `gray-100` / `gray-900` pour le fond de tuile teintée la plus claire, `gray-200` en clair / `gray-700` en sombre pour bordures et séparateurs) : la palette neutre structurelle dont toute carte, champ de formulaire ou séparateur est construit.

### Règles nommées
**La règle du rôle unique.** Une couleur n'apparaît jamais "parce que ça fait joli à côté des autres". Avant d'ajouter une couleur à une rangée de tuiles, nommer le rôle qu'elle joue (succès / taux principal / taux secondaire / compteur méta / neutre) ; si le rôle a déjà une couleur ailleurs dans l'appli, la réutiliser.

**La règle icône + couleur.** Une tuile de stat colorée associe toujours sa couleur de rôle à une icône qui nomme le sujet précis (`CheckCircleIcon` pour un compteur de complétion, `CalendarIcon` pour un taux basé sur les jours, `Squares2X2Icon` pour un taux de grille/combinaisons, `TrophyIcon` pour un compteur méta). La couleur seule ne porte jamais tout le sens.

**La règle de l'or rare.** `gold-600` (`#E6C200`) est réservé au motif trophée de challenge complété. Il n'apparaît jamais sur un bouton, un lien ou un fond — sa rareté est ce qui le garde symbolique.

**La règle du contraste vérifié.** Toute nouvelle association texte/fond ou icône/fond est vérifiée par rapport au WCAG AA (4.5:1 pour le texte, 3:1 pour les icônes/UI non textuelle) en utilisant les vraies valeurs hexadécimales Tailwind du projet, jamais à l'œil. Ça a permis de détecter un vrai échec pendant l'audit : le texte de libellé `green-600` sur fond `green-50` mesurait 3.15:1 et a dû passer à `green-700` (4.79:1).

## Typographie

**Police de texte :** la pile de polices système par défaut de Tailwind (`ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, ...`) — aucune police web personnalisée n'est engagée dans le projet.

**Caractère :** volontairement simple et natif ; le produit s'appuie sur la mise en page, les rôles de couleur et les icônes pour la hiérarchie plutôt que sur des effets typographiques.

### Hiérarchie
- **Titre** (`font-bold`, `text-2xl`) : titres `<h1>` de page ("Mon profil", "Calendar Challenge").
- **En-tête** (`font-medium`, `text-lg`) : titres `<h3>` de carte/section, généralement accompagnés d'une petite icône.
- **Corps** (`text-sm`, poids normal) : libellés de formulaire, texte courant, texte des boutons, cellules de tableau.
- **Libellé** (`text-xs`, `text-gray-500`/`400`) : texte d'aide, sous-texte de champ, métadonnées secondaires (ex. un code GC, un horodatage).

## Mise en page

Les pages de contenu sont centrées et limitées en largeur (`max-w-3xl` à `max-w-4xl`, `mx-auto`), avec un padding externe `p-4`-`p-6` et un rythme vertical via `space-y-4`/`space-y-6` entre sections — pas de système de grille au-delà du `grid-cols-*` responsive de Tailwind pour les rangées de tuiles et grilles de cartes. Les pages à carte rompent volontairement ce schéma : elles s'affichent en plein cadre (`absolute inset-0`) puisque la carte elle-même est le contenu, avec des panneaux flottants (barre d'outils, légende, résultats) positionnés dans les coins plutôt qu'empilés dans une colonne défilante.

## Élévation & profondeur

Le système est plat par défaut. Une carte est définie par une bordure de 1px (`border border-gray-200` / sombre `border-gray-700`) et un changement de fond, pas par une ombre. `shadow-sm` apparaît légèrement sur quelques cartes bordées ; `shadow-md`/`shadow-xl` sont réservées aux éléments qui doivent se détacher visuellement du contenu derrière eux — panneaux flottants sur les cartes (barre d'outils, légende, résultats), popovers, et le FAB de navigation. Aucune ombre marquée/"lifted" nulle part dans le système.

### Règle nommée
**La règle bordure-pas-ombre.** La séparation de surface par défaut est une bordure, pas une ombre. Réserver `shadow-md` et plus aux éléments qui flottent au-dessus d'un autre contenu (panneaux carte, popovers, FAB) et qui doivent réellement se lire "au-dessus", pas seulement "distincts".

## Formes

`rounded-lg` (8px) est le rayon dominant pour cartes, boutons et champs de formulaire. `rounded-full` est réservé aux éléments circulaires/pilules : le FAB, les boutons-icônes de filtre, les interrupteurs, les badges de statut. Les petits éléments en ligne (pastilles de légende, cellules de tableau) utilisent le `rounded` de base (4px, valeur par défaut Tailwind). Aucune surface à angle vif (`rounded-none`) n'est utilisée dans l'appli.

## Composants

### Boutons
- **Forme :** `rounded-md` (6px), `px-4 py-2`, `text-sm font-medium`.
- **Primaire :** `bg-blue-600` / survol `bg-blue-700`, texte blanc — l'action par défaut (sauvegarder, soumettre, se connecter).
- **Secondaire/neutre :** `bg-gray-600` / survol `bg-gray-700`, texte blanc — une action non primaire à côté d'une primaire (ex. "Ma position actuelle" à côté de "Sauvegarder").
- **Synchro/indigo :** `bg-indigo-600` / survol `bg-indigo-700` — spécifiquement l'action de synchronisation des found caches ; réutilise le rôle Indigo méta.
- **Destructeur :** `bg-red-600` / survol `bg-red-700`, texte blanc — actions irréversibles ("Supprimer").
- **Désactivé :** `disabled:opacity-50 disabled:cursor-not-allowed` sur toutes les variantes.

### Tuiles de statistiques
- **Forme :** `rounded-lg`, `p-3`, fond coloré au palier `-50` (sombre : `-950`).
- **Contenu :** une icône colorée selon le rôle (`h-6 w-6`) à côté d'un empilement à deux lignes — le chiffre (`text-2xl font-bold`) au-dessus de son libellé (`text-sm`).
- **Couleur :** toujours la couleur du rôle correspondant au type de métrique (voir Couleurs) ; jamais décorative.

### Cartes / conteneurs
- **Style d'angle :** `rounded-lg`.
- **Fond :** `bg-white` / sombre `bg-gray-800`.
- **Bordure :** `border border-gray-200` / sombre `border-gray-700`.
- **Stratégie d'ombre :** aucune par défaut (voir Élévation).
- **Padding interne :** `p-6` pour une carte pleine, `p-4` pour une carte plus dense.
- **Variantes de poids :** les sections principales et actionnables d'une page (ex. "Ma localisation", "Synchronisation") reçoivent le traitement de carte complet ci-dessus. Les sections secondaires, de simple consultation (ex. un bloc "Informations personnelles" en lecture seule), abandonnent entièrement fond/bordure/padding pour un simple titre "eyebrow" léger (`text-sm font-semibold uppercase tracking-wide`) — le poids d'une carte doit suivre la complexité réelle de sa section, pas être uniforme par défaut.

### Bannières d'alerte / information
- **Style :** `bg-{rôle}-50` / sombre `bg-{rôle}-950`, `border border-{rôle}-200` / sombre `border-{rôle}-900`, `rounded-lg`, `p-4`.
- **Contenu :** une icône de rôle en tête (`InformationCircleIcon` bleu, `ExclamationTriangleIcon` ambre/rouge, `CheckCircleIcon` vert) puis le texte du message dans la teinte `-700`/`800` (clair) ou `-300`/`400` (sombre) correspondante.

### Indicateur de chargement
- **Composant partagé** (`components/ui/LoadingIndicator.vue`) : une icône `ArrowPathIcon` qui tourne (`w-4 h-4 animate-spin`) à côté d'un libellé `text-sm text-gray-500`/sombre `gray-400`. Un seul style visuel réutilisé partout où une page ou un panneau attend des données ; chaque page garde son propre conteneur externe (bloc plein, ligne compacte en ligne, ou panneau flottant sur une carte) puisque ça varie légitimement selon la mise en page, mais le contenu icône+libellé lui-même ne varie jamais.

### Navigation (FAB + menu)
- **FAB :** un déclencheur de menu circulaire fixe (`rounded-full`, `h-14 w-14`) en bas à droite, `bg-white`/sombre `bg-gray-800`, `border`, `shadow-lg`. Toujours affiché au-dessus du contenu carte : chaque conteneur de carte Leaflet porte `isolation: isolate` en CSS pour que les z-index internes de la librairie (jusqu'à 1000, pour ses contrôles zoom/attribution) ne puissent jamais passer devant le chrome de l'appli.
- **Menu :** un panneau plein écran (`fixed inset-0`) partageant le `z-50` du FAB, fond opaque `bg-white`/sombre `bg-gray-900`, ouvert/fermé depuis le FAB.

### Champs de formulaire
- **Style :** `border border-gray-300` / sombre `border-gray-600`, `rounded-md`, `bg-white` / sombre `bg-gray-900`.
- **Focus :** `focus:ring-2 focus:ring-blue-500` (Bleu primaire), pas de changement de couleur de bordure.
- **Erreur :** la bordure passe à `border-red-300`, un message `text-sm text-red-600`/sombre `red-400` apparaît sous le champ.

## À faire et à éviter

### À faire :
- Donner à chaque couleur un rôle nommé (succès / taux principal / taux secondaire / compteur méta / neutre / avertissement / danger) avant de l'utiliser — ne jamais assigner une couleur à une tuile "pour varier".
- Associer une couleur de rôle à une icône spécifique au sujet sur les tuiles de stats ; la couleur seule ne porte jamais tout le sens.
- Faire une vraie vérification de contraste WCAG AA (4.5:1 texte, 3:1 icônes) sur toute nouvelle association de couleurs, avec les vraies valeurs hexadécimales Tailwind du projet, avant publication.
- Ajouter `isolate` à tout nouveau conteneur de carte Leaflet pour que son chrome interne ne puisse jamais s'afficher devant le FAB/menu de l'appli.
- Rendre une information accessible au clic/tap et au focus clavier, pas seulement au survol via un attribut `title` — vraie lacune d'accessibilité trouvée et corrigée sur le détail des jours du calendrier.
- Adapter le poids visuel d'une carte à la complexité réelle de sa section ; un bloc de consultation à 2 champs et un formulaire multi-étapes ne doivent pas se ressembler.

### À éviter :
- Inventer une nouvelle couleur d'accent pour une seule page — réutiliser un rôle existant, ou nommer explicitement un nouveau rôle si aucun ne convient.
- Utiliser `gold` en dehors du motif trophée de challenge complété.
- Mélanger les styles de points de suspension ("..." vs "…") dans les textes d'interface — le projet a standardisé sur "…" pendant l'audit du feedback de chargement.
- Ajouter une ombre portée à une carte au repos ; privilégier une bordure, une ombre seulement quand l'élément doit flotter au-dessus d'un autre contenu.
