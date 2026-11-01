# Matrice de compatibilité — Atelier 0.2

Les extensions sont un premier filtre ; les moteurs lisent ensuite le contenu réel. Les formats
offerts dépendent des décodeurs/encodeurs Pillow présents. La fenêtre « Moteurs & formats » affiche
les extensions et encodeurs réellement détectés.

| Entrée | PNG | JPEG | WebP | TIFF | BMP | PDF |
| --- | --- | --- | --- | --- | --- | --- |
| PNG fixe, RGB/RGBA/L/LA/P/1 | Oui | Oui¹ | Oui² | Oui | Oui¹ | Oui³ |
| JPEG RGB/L | Oui | Oui¹⁴ | Oui² | Oui | Oui | Oui³, flux JPEG incorporé |
| WebP fixe RGB/RGBA | Oui | Oui¹ | Oui²⁴ | Oui | Oui¹ | Oui³ |
| BMP fixe RGB/L/P/1 | Oui | Oui¹ | Oui² | Oui | Oui⁴ | Oui³ |
| TIFF à une page, modes admis | Oui⁵ | Oui¹⁵ | Oui²⁵ | Oui⁴ | Oui¹⁵ | Oui³, selon mode |
| GIF fixe P/L | Oui | Oui¹ | Oui² | Oui | Oui¹ | Oui³ |
| AVIF (prise en charge différée) | Refus | Refus | Refus | Refus | Refus | Refus |
| PNG/TIFF 16 bits I;16 | Oui⁵ | Refus | Refus | Oui⁵ | Refus | Selon mode img2pdf³ |
| PDF non chiffré, sans signature | — | — | — | — | — | Fusion, ordre, extraction, retrait, rotation et découpage |
| SVG, CMYK, HDR, modes numériques non admis | Refus | Refus | Refus | Refus | Refus | Refus |
| Animation ou image multipage | Refus | Refus | Refus | Refus | Refus | Refus |

Les PNG couleur 16 bits et TIFF dont la profondeur réelle serait réduite par Pillow sont
refusés avant décodage. Le mode RGB exposé par le décodeur ne suffit pas à garantir la
profondeur d’origine. AVIF est différé : Pillow restitue ce format en RGB(A) 8 bits sans
exposer ici une garantie suffisante de conservation des sources haute profondeur/HDR.

1. JPEG : compression destructive, même à qualité 100 ; sous-échantillonnage désactivé pour
   réduire la perte chromatique. JPEG et BMP : transparence composée sur blanc. Une conversion
   de palette/couleur peut être nécessaire. BMP ne conserve pas toutes les métadonnées.
2. WebP : mode sans perte par défaut, y compris les composantes RGB des pixels transparents ;
   un mode avec perte réglable est disponible. Les modes gris/palette sont étendus en RGB/RGBA.
3. Une image fixe par page. Pas de réduction de dimensions ou de passage intermédiaire en JPEG.
   img2pdf incorpore les flux lorsqu’il le peut ; certains modes sont réencodés sans perte de pixels,
   d’autres sont refusés par le moteur. La transparence PNG est portée par un masque PDF. Le format
   de page suit la taille physique issue du DPI, à défaut les réglages img2pdf. Les métadonnées du
   fichier source ne sont pas toutes copiées dans celles du document PDF.
4. Si le format est identique, les métadonnées sont conservées et l’orientation EXIF vaut 1 :
   copie exacte par défaut, sans appliquer les réglages d’encodage. Décocher « Copier les formats
   identiques » force un encodage. L’application ne présente jamais le réencodage JPEG comme sans perte.
5. Conservation 16 bits vérifiée pour PNG et TIFF en mode I;16 natif. Le mode I;16B est accepté
   seulement si l’encodeur sait l’écrire ; sinon l’erreur est affichée, sans réduction automatique.

« Sans perte » signifie ici aucune perte supplémentaire de pixels dans un mode compatible. Cela
ne restaure pas les pertes de la source, ne garantit pas une conservation intégrale des métadonnées
et ne transforme pas une conversion de couleur en opération colorimétriquement neutre.
Les profils ICC sont conservés lorsque le mode couleur reste compatible ; le changement de mode
peut imposer leur omission, signalée dans le journal.

## PDF → PDF

Fusion sans rendu des pages en images : texte, vecteurs, dimensions et ordre préservés pour les
documents compatibles. pypdf importe les signets et les formulaires pris en charge ; les champs
de formulaire sont préfixés par document pour limiter les collisions de noms. Les articles et
actions supplémentaires de page sont exclus de la copie. La préservation exhaustive des éléments
interactifs, pièces jointes, balisages d’accessibilité ou métadonnées documentaires n’est pas garantie.
Les champs de signature et les PDF chiffrés sont refusés. Le mode strict rejette des PDF malformés.

## Outils PDF de l’itération 2

| Opération | Entrée / sortie | Comportement |
| --- | --- | --- |
| Aperçus | Un PDF → miniatures à l’écran | PDFium, pages visibles et voisines, basse résolution, cache limité. Aucun export depuis ces images. |
| Réorganisation | Un PDF → un PDF | Ordre choisi par glisser-déposer ou boutons, sélection multiple. |
| Extraction | Un PDF → un PDF | Sélection dans l’ordre de la grille ; sélection de positions/plages `1-3, 5`. |
| Retrait | Un PDF → un PDF | Seules les pages restantes sont exportées ; original inchangé. |
| Rotation | Pages sélectionnées | Ajout de 90°, 180° ou 270° à la rotation existante, visible dans l’aperçu et l’export. |
| Découpage | Un PDF → plusieurs PDF | Groupes `1-3 ; 4-6` ou un fichier par page, après les modifications de la grille. |

Les positions sont toujours celles de l’ordre **actuel** ; les numéros source restent indiqués
sur les cartes. Chaque fichier de découpage suit l’ordre écrit dans son groupe, et les groupes
peuvent reprendre une même page. Les répétitions au sein d’un groupe sont refusées.

### Préservation et limites réelles

- Contenu vectoriel et flux d’images copiés par pypdf, sans rendu ni réencodage des pages.
  Les tests comparent les flux de contenu et les dimensions après réorganisation/rotation.
- MediaBox, CropBox et rotation sont conservées ou modifiées seulement selon le plan demandé.
- Métadonnées Info et XMP lisibles copiées. Leur contenu peut contenir des valeurs devenues
  obsolètes après découpage (par exemple une description du document initial).
- pypdf importe les signets et destinations compatibles vers les pages conservées. Le remappage
  d’un lien interne et d’un signet est testé. Un lien vers une page retirée peut être supprimé
  ou perdre sa destination ; tous les types d’actions et destinations ne sont pas garantis.
- Annotations et formulaires standards copiés selon ce que pypdf sait importer. Les champs
  interactifs, leur affichage après rotation et les formulaires XFA complexes ne sont pas garantis.
  PDFium n’initialise pas les formulaires pour les miniatures : leurs champs peuvent ne pas apparaître.
- Pas de conservation garantie des pièces jointes, portfolios, calques, balisages PDF/UA,
  ressources documentaires ou conformité PDF/A. Le fichier exporté est un nouveau document PDF.
- PDF chiffrés, même ouvrables avec un mot de passe vide, et documents ayant un champ de signature
  refusés dès l’import et à nouveau à l’export. Aucune tentative de déchiffrement implicite.
- Un PDF que le mode strict pypdf refuse n’est pas annoncé comme modifiable, même si un lecteur
  plus tolérant parvient à l’afficher. Les erreurs de rendu d’une page restent visibles dans le journal.

Le retrait de pages n’est **pas un outil de caviardage** : des données liées ou métadonnées peuvent
rester dans le nouveau document. L’application ne promet pas d’assainir des PDF malveillants.

## Hors périmètre de cette version

DOCX/ODT/RTF/HTML/Markdown/TXT, audio et vidéo ne sont **pas** présentés comme convertibles.
La présence de LibreOffice ne signifie pas qu’un moteur bureautique est activé. Aucune conversion
PDF → DOCX fidèle n’est promise. Les futurs formats dépendront des filtres et codecs réellement
interrogés et testés, pas seulement d’une liste d’extensions.
