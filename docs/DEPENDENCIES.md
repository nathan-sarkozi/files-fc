# Dépendances et sources officielles

Les dépendances sont confinées à `.venv` pendant le développement, ou au venv de l’installation
personnelle. Les versions effectives sont figées dans `requirements.lock` et `requirements-dev.lock`.

| Composant | Usage | Licence annoncée par le projet |
| --- | --- | --- |
| Python | Exécution | PSF |
| PySide6-Essentials / Shiboken6 / Qt | Widgets, signaux, SVG, bureau Linux | LGPLv3/GPL selon composants, option commerciale disponible |
| Pillow | Décodage et encodage des images | MIT-CMU |
| pypdf | Fusion et contrôle structurel PDF | BSD-3-Clause |
| pypdfium2 5.14.0 / PDFium embarqué | Miniatures PDF dans un processus distinct | BSD-3-Clause / Apache-2.0 et licences des composants PDFium |
| img2pdf | Incorporation d’images sans perte ajoutée en PDF | LGPLv3 |
| pikepdf | Dépendance img2pdf, moteur PDF basé sur qpdf | MPL-2.0 |
| qpdf embarqué par pikepdf | Bibliothèque PDF native | Apache-2.0 |
| lxml, packaging | Dépendances transitives | BSD-3-Clause ; Apache-2.0/BSD-2-Clause respectivement |

Les wheels contiennent d’autres bibliothèques natives et leurs notices. Les conserver avec leurs
fichiers `.dist-info/licenses`, les notices Qt et les bibliothèques partagées est nécessaire pour
préparer une distribution. Le paquet personnel conserve les distributions d’origine et ne fusionne
pas statiquement les bibliothèques. Une diffusion publique et sa conformité devront être examinées
avec les artefacts précis ; ce document n’est pas une certification juridique. La licence du code
applicatif pourra être choisie par son propriétaire avant publication.

Sources consultées lors de la conception :

- [Qt for Python — déploiement](https://doc.qt.io/qtforpython-6/deployment/index.html)
- [Qt — obligations LGPL et modules soumis à d’autres licences](https://www.qt.io/development/open-source-lgpl-obligations)
- [PySide6-Essentials — distribution officielle](https://pypi.org/project/PySide6-Essentials/)
- [Pillow — formats, paramètres et contraintes](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html)
- [Pillow — licence](https://pillow.readthedocs.io/en/stable/about.html)
- [pypdf — fusion, formulaires et mémoire](https://pypdf.readthedocs.io/en/stable/user/merging-pdfs.html)
- [pypdf — distribution et licence](https://pypi.org/project/pypdf/)
- [img2pdf — formats incorporés, qualité et licence](https://pypi.org/project/img2pdf/)
- [pikepdf — licence et composants tiers](https://github.com/pikepdf/pikepdf)
- [pypdfium2 — distribution, licences et notices des wheels](https://pypi.org/project/pypdfium2/)
- [pypdfium2 — rendu, fermeture des ressources et incompatibilité avec les appels simultanés depuis plusieurs threads](https://pypdfium2.readthedocs.io/en/stable/python_api.html)

La wheel pypdfium2 utilisée inclut `libpdfium.so` et les notices dans son répertoire
`.dist-info/licenses`, y compris les licences BSD/Apache et celles des composants natifs tiers.
L’archive 0.2 conserve la wheel complète ; aucune compilation PDFium ni recherche d’une bibliothèque
système n’est effectuée. Les builds V8/XFA ne sont pas demandés. Ce moteur est réservé aux aperçus :
il ne remplace pas pypdf lors de l’export.

## Prérequis Linux

Un Python disposant de venv/pip, glibc compatible avec les wheels et une session graphique Linux
existante sont requis. Les wheels Qt évitent de compiler ou installer Qt via apt/dnf, mais les
bibliothèques graphiques de base restent fournies par la distribution. En cas de dépendance absente,
le projet n’exécute aucun gestionnaire de paquets système. Qt fournit des plugins Wayland et XCB ;
les prérequis varient selon la plateforme choisie.

Le message facultatif GTK sur `canberra-gtk-module` a été observé sans empêcher le démarrage.
Il n’a motivé aucune installation système.

## Extensions envisagées

LibreOffice est présent dans l’environnement, FFmpeg absent. Ils ne sont pas nécessaires au MVP.
Leur intégration future devra vérifier versions, filtres, encodeurs et erreurs, et annoncer toute
installation système nécessaire avant de la réaliser.

- [LibreOffice — mode headless et filtres de conversion](https://help.libreoffice.org/latest/en-GB/text/shared/guide/start_parameters.html)
- [FFmpeg — licences selon la compilation](https://www.ffmpeg.org/legal.html)

Les codecs FFmpeg disponibles et les options de construction déterminent les conversions réellement
possibles et la licence applicable. Une extension ne devra pas supposer qu’un conteneur équivaut
à un codec, ou que deux fichiers portant la même extension peuvent être concaténés sans réencodage.
