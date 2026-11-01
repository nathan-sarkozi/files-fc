# Validation exécutée — Atelier 0.2, 1er novembre 2026

## Résultat

Version 0.2 vérifiée sur la machine Linux x86_64 du projet, Python 3.12.3, glibc 2.39, GNOME/Wayland.
**95 tests automatisés réussis**, dont les **63 tests de la première version**, incluant les
parcours Qt avec de vrais processus de traitement et un vrai rendu PDFium.
Les fichiers de test sont créés localement ; aucun original de l’utilisateur n’a servi de cobaye.

## Vérifications réalisées

| Vérification | Résultat observé |
| --- | --- |
| `pytest -q`, Qt hors écran | 95 réussites, sans avertissement ; tests initiaux conservés |
| Ruff, code et scripts | Aucune erreur ; format vérifié |
| mypy strict sur `atelier` | Aucune erreur sur 21 modules |
| Compilation Python `compileall` | Réussie |
| `pip check` dans `.venv` | Aucune dépendance incohérente |
| Syntaxe Bash des scripts de préparation/lancement | Valide |
| Démarrage Qt hors écran et captures | Réussi |
| Démarrage natif dans la session graphique Linux via `scripts/dev.sh --smoke-test` | Réussi après correction des chemins GTK hérités de VS Code Snap |
| Construction du wheel et de l’archive Linux 0.2.0 | Réussie, dépendances réutilisées hors ligne et wheel PDFium ajoutée |
| Installation depuis l’archive, `--no-index`, dans un venv temporaire distinct | Réussie sans accès réseau, y compris chemins contenant des espaces |
| Lancement de l’installation depuis `/tmp`, hors du projet | Réussi |
| Entrée de menu avec `desktop-file-validate` | Valide |
| Nouvelle installation sur des chemins déjà occupés | Refus explicite, code de sortie 2 |
| Parcours depuis le Python du paquet 0.2 installé dans `/tmp`, hors du projet | Conversions existantes, vrais aperçus PDFium, ordre, rotation, extraction, retrait et deux modes de découpage réussis |
| Démarrage graphique natif du paquet installé avec `--pdf` | Réussi |

La version 0.1 et son archive sont conservées. Les sources présentes avant modification ont été
sauvegardées dans `artifacts/atelier-sources-avant-iteration2.tar.gz`. Le dossier `.git` fourni
n’est pas reconnu comme un dépôt Git valide : `git status` est indisponible et aucun commit n’a
été créé. L’absence de régression observée repose sur les tests, pas sur une comparaison Git.

## Couverture fonctionnelle

### Nouveaux outils PDF

- Extraction et réorganisation : nombre de pages, ordre, MediaBox, CropBox, texte et flux
  vectoriels comparés ; rotation supplémentaire de 90°, 180° et 270° appliquée correctement.
- Retrait réel de pages dans le plan puis export ; original comparé octet pour octet.
- Découpage par groupes et une page par fichier, noms cohérents et collisions sans écrasement.
- Métadonnées Info et XMP conservées sur le document de test.
- Remappage d’un signet et d’un lien interne vers une page conservée ; donnée d’un champ texte
  standard et annotation conservées. Cela ne garantit pas tous les formulaires ou actions PDF.
- JPEG déjà présent dans un PDF : flux DCT comparé octet pour octet après rotation/export.
- Plages invalides, hors limites, inversées, vides ou répétées refusées ; document vide non exportable.
- PDF chiffrés, signés et endommagés refusés ; source modifiée depuis ouverture détectée.
- Annulation avant publication : aucune sortie partielle ; les temporaires sont nettoyés par Job.
- Grille Qt : import d’un PDF par dépôt, vrai glissement interne, sélection de plages, rotation,
  extraction, retrait, exports multiples et historique d’annulation.
- Document de **200 pages** : miniatures demandées à proximité de la zone visible, navigation
  jusqu’à la page 195, cache borné à 48 images de 240 pixels de grand côté, ressources libérées
  lors d’un changement d’espace et modifications retrouvées au retour.
- Fermeture avec moteur de prévisualisation actif et annulation d’un export réel depuis Qt.
- Captures de la vraie interface, avec un document vectoriel de test :
  [pages et sélection](images/atelier-pdf-pages.png),
  [rotation, réorganisation et découpage](images/atelier-pdf-rotation-decoupage.png).

### Fonctionnalités précédentes, revérifiées

- Comparaison des pixels et dimensions de PNG, WebP sans perte, TIFF et BMP.
- Décodage des entrées JPEG, WebP, TIFF, BMP et GIF fixe avec l’installation courante.
- Refus d’AVIF et des PNG/TIFF couleur 16 bits que Pillow réduirait implicitement à 8 bits.
- Pixels RGBA préservés, y compris couleurs des pixels totalement transparents en WebP.
- Transparence de palette préservée vers PNG/TIFF/WebP, avec ou sans conservation des métadonnées.
- Composition sur blanc pour JPEG/BMP, avertissement explicite pour les encodages avec perte.
- Orientation EXIF, profil ICC, auteur, DPI et textes PNG ; suppression des métadonnées choisie.
- PNG/TIFF 16 bits, valeurs numériques comparées après relecture.
- Copie binaire d’un JPEG vers le même format ; encodage forcé quand l’option est décochée.
- Refus des animations/multipages, du CMYK, de réductions implicites de profondeur et
  des images dépassant le seuil de sécurité Pillow.
- Fusion PDF : ordre, dimensions, texte extractible et octets des sources préservés.
- JPEG incorporé dans le PDF : flux DCT comparé octet pour octet à la source.
- PDF d’image transparente : présence du masque alpha ; nombre réel de pages contrôlé.
- Refus des PDF chiffrés, des champs de signature et des fichiers corrompus.
- Lot poursuivi après une erreur ; aucun PDF partiel publié lors d’un échec d’assemblage.
- Nom de sortie existant ou lien symbolique : suffixe, aucun écrasement de la cible.
- Rejet des chemins de sortie dangereux, dossiers et FIFO.
- Annulation avant et pendant un lot ; conservation des résultats terminés.
- Annulation forcée d’un encodeur de test bloqué : processus arrêté et temporaire supprimé.
- Qt : import par glisser-déposer, réordre par boutons, files par espace,
  trois opérations réelles, annulation et fermeture de la fenêtre pendant le traitement.

## Limites de cette validation

La session graphique native et les captures ont été vérifiées ; tous les échanges avec les
gestionnaires de fichiers, portails et lecteurs PDF externes n’ont pas été automatisés.
Les cas colorimétriques professionnels, PDF complexes et charges de plusieurs gigaoctets n’ont
pas fait l’objet d’une campagne exhaustive. Les tests de pixels ne mesurent pas la fidélité
d’affichage d’un profil ICC dans chaque logiciel tiers.

Les 200 pages du test de navigation ne constituent pas une preuve de comportement sur tout PDF
volumineux. Les formulaires XFA, portfolios, calques, PDF/A, PDF/UA et annotations complexes n’ont
pas de garantie de conservation exhaustive. Le retrait de pages ne vaut pas caviardage. Les
miniatures ne rendent pas nécessairement les champs de formulaire.

L’archive est destinée au Linux/Python/CPU de construction et n’a pas été validée sur plusieurs
distributions ni sous Windows. Elle n’est ni un AppImage ni un Flatpak. Python/venv et les
bibliothèques graphiques de base doivent exister sur la machine cible.

Les chemins GTK de VS Code Snap ont causé un arrêt natif avant le correctif local. Aucun paquet
système n’a été installé pour y remédier. Les messages D-Bus en mode hors écran et le module
GTK optionnel `canberra-gtk-module` n’ont pas empêché les vérifications. Ces vérifications ne
constituent pas un audit de sécurité ni une preuve de résistance à tout document malveillant.
