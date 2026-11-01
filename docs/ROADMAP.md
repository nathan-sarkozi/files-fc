# Suite recommandée

1. **Suite des outils PDF** : aperçu agrandi, recherche textuelle, glissement avec indicateur
   d’insertion plus détaillé, gestion de plusieurs documents dans le même plan, sauvegarde/reprise
   et rétablissement après Ctrl+Z. Élargir les tests de formulaires, annotations et très gros PDF
   avant d’étendre les garanties. L’itération 2 fournit déjà sélection, extraction, retrait,
   réorganisation, rotation, découpage et miniatures à la demande.
2. **Documents bureautiques** : moteur LibreOffice headless, profil utilisateur isolé dans un
   temporaire, liste réelle de filtres, délais et arrêt du groupe de processus. Commencer par
   DOCX/ODT/RTF → PDF. La fidélité dépend aussi des polices ; les macros et ressources externes
   devront être désactivées. Détection des capacités sans installation automatique.
3. **Audio/vidéo** : détection FFmpeg/ffprobe, sonde codecs/conteneurs, distinction explicite
   remuxage/copie et réencodage. Concaténation directe seulement après vérification des flux,
   dimensions, fréquences, profils et bases temporelles. Proposer une normalisation intermédiaire
   clairement annoncée si les sources sont incompatibles.
4. **Lots avancés** : historique persistant choisi par l’utilisateur, reprise, modèles de noms,
   diagnostics d’espace disque et parallélisme borné après mesure de la mémoire.
5. **Distribution** : élargir les tests à plusieurs distributions et sessions X11/Wayland, puis
   envisager Flatpak ou AppImage pour embarquer davantage du runtime. La version actuelle est
   une archive avec installateur utilisateur, pas un binaire Linux universel.
6. **Qualité et sécurité** : tests colorimétriques/ICC plus complets, modes CMYK explicitement
   gérés, AVIF/HDR avec profondeur réellement préservée, images multipages sans perte de trames,
   tests de charge et confinement OS éventuel.

Chaque extension doit ajouter une matrice de compatibilité vérifiée, des tests sur fichiers réels,
des messages de qualité honnêtes et un diagnostic des dépendances. Aucun bouton d’opération future
n’est affiché comme utilisable dans le MVP.
