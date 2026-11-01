# Décisions d’architecture — Atelier 0.2

## Environnement examiné

Le 1er novembre 2026 : dossier initial vide, Linux x86_64, glibc 2.39, Python 3.12.3,
session GNOME/Wayland, VS Code Snap. LibreOffice présent ; FFmpeg absent. Pas de bibliothèque
Qt Python, pypdf ou img2pdf disponible au départ. Aucun paquet système n’a été modifié.

## Stack retenue

| Solution évaluée | Décision pour cet usage personnel Linux |
| --- | --- |
| Python + Qt/PySide6 Widgets | Retenue : bureau natif, dialogues et glisser-déposer, moteurs Python éprouvés, wheels incluant Qt, UI indépendante du traitement. |
| Tauri | Possible plus tard, mais une chaîne Rust et les prérequis WebKitGTK ajoutent des contraintes système pour ce MVP. |
| Electron | Capable, mais distribuer Chromium et Node apporte un coût de mémoire/distribution inutile pour ces trois opérations. |
| GTK/PyGObject | Bonne intégration GNOME, mais sa préparation dépend davantage des bindings et paquets fournis par la distribution. |

Qt Widgets avec une feuille de style et des icônes SVG locales donne une interface cohérente
sans navigateur ni serveur local. Seule la distribution `PySide6-Essentials` est nécessaire.
La portabilité Windows reste possible dans le cœur, mais le lancement et l’installateur sont
explicitement développés et vérifiés pour Linux.

L’itération 2 conserve cette stack. pypdf reste le moteur de manipulation sans rasterisation ;
pypdfium2/PDFium est ajouté uniquement pour le rendu des aperçus. Sa wheel inclut la bibliothèque
native : aucun nouveau paquet système. QtPdf n’est pas dans la distribution Essentials utilisée ;
ajouter les modules Qt Addons aurait imposé une dépendance plus large pour ce seul besoin.

## Organisation

```text
src/atelier/
  app.py                démarrage, palette, police et options de vérification
  desktop.py            correction locale de l’environnement GTK de VS Code Snap
  core/models.py        requêtes immuables, opérations et événements typés
  core/files.py         validation des chemins et publication sans écrasement
  core/images.py        Pillow, modes/qualité/métadonnées, copie sans réencodage
  core/pdf.py           fusion pypdf et incorporation img2pdf
  core/pdf_tools.py     inspection, plages, plans d’export et contrôle des sorties PDF
  core/runner.py        lot, progression, résultats et erreurs
  jobs.py               supervision Qt d’un processus multiprocessing « spawn »
  previews.py           processus PDFium persistant, requêtes de rendu bornées et annulation
  ui/pdf_pages.py       modèle de pages, historique, grille, délégué et cache de miniatures
  ui/pdf_editor.py      préparation des opérations PDF et suivi de l’export
  ui/                   fenêtre, composants, thème et icônes
scripts/                développement, construction et installation Linux
tests/                  tests des moteurs et parcours Qt réels
```

Le cœur ne dépend pas de Qt. Une nouvelle opération ajoute une requête et un moteur au
dispatcher existant ; aucune infrastructure de plugins complexe n’est introduite pour ces
opérations. Les capacités image sont interrogées depuis les registres Pillow de l’installation.

Les requêtes d’export PDF contiennent un `PdfPlan` immuable : un instantané du fichier source et
une liste de sorties nommées, chacune composée d’indices source et de rotations supplémentaires.
Le modèle Qt ne manipule aucun objet pypdf. Il garde uniquement cet ordre et ses 20 derniers états.

## Miniatures et ressources de l’espace PDF

L’inspection pypdf et le rendu PDFium s’exécutent hors du fil graphique, dans un processus dédié.
PDFium n’étant pas thread-safe, tous ses appels sont sérialisés dans ce processus. Le superviseur
Qt échange des messages par Pipe ; les signaux vers l’interface sont connectés à des slots QObject,
qui sont déconnectés automatiquement à la destruction des widgets.

La grille utilise QListView/QAbstractListModel et un délégué, sans widget par page. Elle demande
les pages visibles et quelques voisines. Une nouvelle demande remplace la file obsolète ; une
seule page est rendue à la fois. Les images ont un grand côté de 240 pixels au plus et le cache
LRU est limité à 48 images (environ 8 Mio de pixels RGB, hors surcoûts Qt). Les rotations de l’aperçu
sont appliquées au dessin, sans multiplier les entrées du cache. Le cache se vide et le processus
se ferme lorsque l’utilisateur quitte l’espace PDF. Le plan des pages reste disponible en mémoire.

Les pages et bitmaps PDFium sont fermés explicitement après chaque rendu. Annulation et fermeture
interrompent le superviseur, puis terminent le processus si nécessaire sans bloquer l’interface.
Le document source est contrôlé par périphérique, inode, taille et mtime nanoseconde à l’ouverture,
avant/après rendu et avant publication. Un changement détecté impose une réimportation. Ce contrôle
n’est pas une empreinte cryptographique et ne remplace pas un confinement de fichiers hostiles.

## Traitement et annulation

L’interface crée une requête, puis un QThread supervise un processus séparé. Un Pipe transporte
les événements ; les widgets sont modifiés uniquement dans le thread graphique. Les vérifications
d’annulation ont lieu entre les phases et fichiers. Si un encodeur reste bloqué dans une fonction
native, le superviseur termine le processus après un court délai. Le processus est rejoint avant
le nettoyage de son dossier temporaire.

Les lots image sont séquentiels pour limiter la mémoire et continuent après une erreur individuelle.
Une fusion est indivisible : aucun PDF partiel n’est publié. La progression PDF reflète les entrées
préparées jusqu’à 85 %, puis l’écriture/validation ; ce n’est pas une mesure des octets traités.
Un encodage individuel peut donc conserver le même pourcentage pendant un certain temps.

Les outils PDF réutilisent `Job` pour l’export. Toutes les plages et tous les noms sont validés
avant traitement. Les PDF de découpage sont tous écrits et relus avant la première publication.
Chaque fichier final est publié atomiquement. Un lot de plusieurs fichiers n’est pas une transaction
globale : en cas d’annulation ou d’erreur pendant la publication, les fichiers déjà terminés restent
disponibles et sont indiqués dans le journal. La progression est limitée aux changements de pourcentage
pour éviter de saturer la file de signaux avec un très grand document.

La validation des sorties contrôle leur nombre de pages, MediaBox, CropBox et rotation, en plus
de la relecture stricte pypdf. Le moteur ne remplace jamais le contenu des pages par les miniatures.

## Intégrité et fichiers

Un `TemporaryDirectory` privé est créé dans le dossier de destination. Chaque résultat y est encodé
et relu avant publication. La publication utilise `os.link` : la création du nom final est atomique
et échoue si le nom existe déjà, y compris pour un lien symbolique. Un suffixe est essayé jusqu’à
trouver un nom libre. Les données sont synchronisées avant publication ; ce mécanisme ne prétend
pas garantir une transaction durable face à toutes les pannes matérielles.

Cette garantie exige un système de fichiers avec liens physiques. Les dossiers ext4/Btrfs usuels
conviennent ; FAT/exFAT et certains montages réseau peuvent être refusés avec une erreur explicite.
Un arrêt brutal de toute l’application ou une coupure peut laisser un dossier `.atelier-*` caché :
aucun balayage automatique des dossiers utilisateur n’est réalisé pour éviter une suppression risquée.

## Confidentialité et limites

Pas de code réseau, télémétrie, mise à jour automatique, service distant ou invocation de shell par
les moteurs. Les imports acceptent des fichiers ordinaires ; les périphériques, FIFO et dossiers sont
refusés. Les noms de sortie n’acceptent pas de chemin. Les formats déclarés sont vérifiés par les
parseurs, et les protections Pillow contre la décompression excessive restent actives.

L’isolation en processus garantit surtout la réactivité et l’arrêt d’un traitement, **pas une isolation
des permissions Linux**. Les codecs natifs s’exécutent avec les droits du compte. Aucun assainissement
global du contenu actif des PDF n’est garanti. Les PDF malformés sont refusés en mode strict ; cela
peut exclure des documents qu’un lecteur plus tolérant accepte.

Les PDF volumineux peuvent consommer beaucoup de mémoire : pypdf garde un graphe d’objets et img2pdf
ne garantit pas une mémoire constante pour tout format. Pillow décode une image à la fois. Les limites
des bibliothèques sont explicites, sans promesse de capacité illimitée. L’interface garde des files et
un journal en mémoire pour la session ; seule la destination est mémorisée avec QSettings.
