from __future__ import annotations

import importlib.metadata
import shutil
from pathlib import Path
from typing import cast

from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from atelier.core.files import output_directory, output_name, source_file
from atelier.core.images import available_targets, input_extensions
from atelier.core.models import Event, ImageOptions, Operation, Request
from atelier.jobs import Job
from atelier.ui.icons import icon
from atelier.ui.pdf_editor import PdfEditor
from atelier.ui.widgets import (
    DropZone,
    FileList,
    FileRow,
    button,
    card,
    format_size,
    label,
    make_item,
)

MODES = {
    Operation.PDF_TOOLS: (
        "Votre PDF, page par page",
        "Organisez, extrayez et tournez vos pages. Gardez la qualité de votre document.",
        "pages",
        "Outils PDF",
    ),
    Operation.CONVERT: (
        "Convertir des images",
        "Un nouveau format, la même attention aux détails.",
        "convert",
        "Conversion",
    ),
    Operation.MERGE: (
        "Fusionner des PDF",
        "Rassemblez vos documents, dans l’ordre qui vous convient.",
        "merge",
        "Fusion PDF",
    ),
    Operation.IMAGES_PDF: (
        "Créer un PDF d’images",
        "Vos images réunies, sans compression destructive ajoutée.",
        "images",
        "Images vers PDF",
    ),
}


class Window(QMainWindow):
    def __init__(self, settings: QSettings | None = None) -> None:
        super().__init__()
        self.settings = settings if settings is not None else QSettings()
        self.mode = Operation.CONVERT
        self.queues: dict[Operation, list[Path]] = {mode: [] for mode in Operation}
        self.job: Job | None = None
        self.log: list[str] = []
        self.results: dict[str, Path] = {}
        self.states: dict[str, str] = {}
        self._closing = False
        self.setWindowTitle("Atelier — Vos fichiers, à votre façon")
        self.setWindowIcon(QIcon(str(Path(__file__).parents[1] / "assets/atelier.svg")))
        self.resize(1250, 850)
        self.setMinimumSize(960, 720)
        root = QWidget()
        self.setCentralWidget(root)
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        shell.addWidget(self._sidebar())
        body = QVBoxLayout()
        body.setContentsMargins(30, 28, 30, 24)
        body.setSpacing(20)
        shell.addLayout(body, 1)
        top = QHBoxLayout()
        top.addWidget(label("VOTRE ATELIER NUMÉRIQUE", "eyebrow"))
        top.addStretch()
        top.addWidget(label("●  100 % local", "badge"))
        body.addLayout(top)
        heading = QVBoxLayout()
        heading.setSpacing(8)
        self.title = label("", "title")
        self.subtitle = label("", "muted", True)
        heading.addWidget(self.title)
        heading.addWidget(self.subtitle)
        body.addLayout(heading)
        work = QHBoxLayout()
        work.setSpacing(20)
        work.addWidget(self._files_card(), 1)
        options = self._options_card()
        scroll = QScrollArea()
        scroll.setObjectName("optionsScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(options)
        scroll.setFixedWidth(286)
        work.addWidget(scroll)
        legacy = QWidget()
        legacy_layout = QVBoxLayout(legacy)
        legacy_layout.setContentsMargins(0, 0, 0, 0)
        legacy_layout.setSpacing(20)
        legacy_layout.addLayout(work, 1)
        legacy_layout.addWidget(self._footer())
        self.workspaces = QStackedWidget()
        self.workspaces.addWidget(legacy)
        self.pdf_editor = PdfEditor(self.destination.text())
        self.pdf_editor.destination_changed.connect(self.destination.setText)
        self.destination.textChanged.connect(self.pdf_editor.destination.setText)
        self.pdf_editor.message.connect(self.log.append)
        self.pdf_editor.journal_requested.connect(self.show_log)
        self.pdf_editor.busy_changed.connect(self._pdf_busy)
        self.pdf_editor.idle.connect(self._pdf_idle)
        self.workspaces.addWidget(self.pdf_editor)
        body.addWidget(self.workspaces, 1)
        self._set_mode(Operation.CONVERT)
        QShortcut(QKeySequence.StandardKey.Open, self, self.pick_files)
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self, self.remove_selected)

    def _sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(204)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 30, 18, 24)
        layout.setSpacing(8)
        brand = QHBoxLayout()
        mark = label("")
        mark.setPixmap(QIcon(str(Path(__file__).parents[1] / "assets/atelier.svg")).pixmap(34, 34))
        brand.addWidget(mark)
        brand.addWidget(label("atelier", "brand"))
        brand.addStretch()
        layout.addLayout(brand)
        layout.addSpacing(7)
        layout.addWidget(label("Vos fichiers, à votre façon.", "muted"))
        layout.addSpacing(38)
        layout.addWidget(label("ESPACE DE TRAVAIL", "eyebrow"))
        layout.addSpacing(8)
        self.navigation = QButtonGroup(self)
        self.nav_buttons: dict[Operation, QPushButton] = {}
        for mode, (_title, _subtitle, glyph, caption) in MODES.items():
            nav = button(caption, glyph, "nav")
            nav.setCheckable(True)
            nav.clicked.connect(lambda checked=False, selected=mode: self._set_mode(selected))
            self.navigation.addButton(nav)
            self.nav_buttons[mode] = nav
            layout.addWidget(nav)
        layout.addStretch()
        engines = button("Moteurs && formats", "settings", "nav")
        engines.clicked.connect(self.show_engines)
        layout.addWidget(engines)
        layout.addSpacing(20)
        lock = label("Vos fichiers restent ici.", "cardTitle")
        lock.setStyleSheet("font-size:12px;color:#b5efd2;")
        layout.addWidget(lock)
        layout.addWidget(
            label("Aucun envoi. Aucun compte.\nSimplement votre ordinateur.", "note", True)
        )
        layout.addSpacing(12)
        layout.addWidget(label("ATELIER   /   0.2.0", "eyebrow"))
        return sidebar

    def _files_card(self) -> QFrame:
        frame, layout = card()
        header = QHBoxLayout()
        header.addWidget(label("01", "muted"))
        header.addWidget(label("Vos fichiers", "cardTitle"))
        header.addStretch()
        self.count = label("0 fichier", "muted")
        header.addWidget(self.count)
        layout.addLayout(header)
        self.drop = DropZone()
        self.drop.paths_dropped.connect(self.add_paths)
        drop_layout = QVBoxLayout(self.drop)
        drop_layout.setContentsMargins(15, 18, 15, 18)
        drop_layout.setSpacing(10)
        glyph = label("")
        glyph.setPixmap(icon("upload", "#b5efd2", 28).pixmap(28, 28))
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(glyph)
        text = label("Déposez vos fichiers ici", "cardTitle")
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(text)
        self.support = label("", "muted", True)
        self.support.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.support.setStyleSheet("font-size:11px;")
        drop_layout.addWidget(self.support)
        self.browse = button("Parcourir les fichiers", name="quiet")
        self.browse.clicked.connect(self.pick_files)
        drop_layout.addWidget(self.browse, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.drop)
        toolbar = QHBoxLayout()
        self.order_hint = label("L’ordre de la liste définit celui du PDF.", "note")
        toolbar.addWidget(self.order_hint, 1)
        self.up = button("", "up", "mini")
        self.down = button("", "down", "mini")
        self.remove = button("", "close", "mini")
        for widget, name in (
            (self.up, "Monter le fichier sélectionné"),
            (self.down, "Descendre le fichier sélectionné"),
            (self.remove, "Retirer les fichiers sélectionnés"),
        ):
            widget.setToolTip(name)
            widget.setAccessibleName(name)
            toolbar.addWidget(widget)
        self.up.clicked.connect(lambda: self.move_selected(-1))
        self.down.clicked.connect(lambda: self.move_selected(1))
        self.remove.clicked.connect(self.remove_selected)
        layout.addLayout(toolbar)
        self.files = FileList()
        self.files.paths_dropped.connect(self.add_paths)
        self.files.itemSelectionChanged.connect(self._update_controls)
        self.files.itemDoubleClicked.connect(self.show_item)
        layout.addWidget(self.files, 1)
        self.empty = label(
            "Tout commence par un fichier.\n"
            "Ajoutez vos premiers éléments pour préparer le traitement.",
            "muted",
            True,
        )
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty, 1)
        self.total = label("", "note")
        layout.addWidget(self.total)
        return frame

    def _options_card(self) -> QFrame:
        frame, layout = card()
        layout.addWidget(label("02    Réglages de sortie", "cardTitle"))
        self.image_controls = QWidget()
        image_layout = QVBoxLayout(self.image_controls)
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.setSpacing(12)
        image_layout.addWidget(label("Format cible", "muted"))
        self.target = QComboBox()
        self.target.setMinimumHeight(38)
        self.target.addItems(list(available_targets()))
        self.target.setAccessibleName("Format d’image cible")
        image_layout.addWidget(self.target)
        self.lossless = QCheckBox("WebP sans perte")
        self.lossless.setChecked(True)
        image_layout.addWidget(self.lossless)
        self.quality_label = label("Qualité d’encodage   ·   92", "muted")
        image_layout.addWidget(self.quality_label)
        self.quality = QSlider(Qt.Orientation.Horizontal)
        self.quality.setRange(1, 100)
        self.quality.setValue(92)
        self.quality.setAccessibleName("Qualité de compression, de 1 à 100")
        image_layout.addWidget(self.quality)
        self.metadata = QCheckBox("Conserver les métadonnées")
        self.metadata.setChecked(True)
        self.metadata.setToolTip(
            "EXIF, ICC, DPI et textes PNG selon le format.\n"
            "Ces données peuvent inclure la localisation GPS."
        )
        image_layout.addWidget(self.metadata)
        self.copy_same = QCheckBox("Copier les formats identiques")
        self.copy_same.setChecked(True)
        self.copy_same.setToolTip(
            "Si le format est identique, les métadonnées sont conservées et aucune "
            "rotation EXIF n’est nécessaire : copie exacte, sans appliquer la qualité.\n"
            "Décochez pour forcer un nouvel encodage."
        )
        image_layout.addWidget(self.copy_same)
        layout.addWidget(self.image_controls)
        self.pdf_controls = QWidget()
        pdf_layout = QVBoxLayout(self.pdf_controls)
        pdf_layout.setContentsMargins(0, 0, 0, 0)
        pdf_layout.addWidget(label("Nom du document", "muted"))
        self.pdf_name = QLineEdit("assemblage.pdf")
        self.pdf_name.setAccessibleName("Nom du PDF de sortie")
        pdf_layout.addWidget(self.pdf_name)
        layout.addWidget(self.pdf_controls)
        self.explanation = label("", "note", True)
        layout.addWidget(self.explanation)
        layout.addSpacing(4)
        layout.addWidget(label("Dossier de destination", "muted"))
        default = Path.home() / "Downloads"
        if not default.is_dir():
            default = Path.home()
        self.destination = QLineEdit(str(self.settings.value("destination", str(default))))
        self.destination.setReadOnly(True)
        self.destination.setAccessibleName("Dossier de destination")
        self.destination.setToolTip(self.destination.text())
        layout.addWidget(self.destination)
        self.choose_destination = button("Choisir un dossier", "folder", "quiet")
        self.choose_destination.clicked.connect(self.pick_destination)
        layout.addWidget(self.choose_destination)
        layout.addStretch()
        safe = QFrame()
        safe.setObjectName("safety")
        safe_layout = QVBoxLayout(safe)
        safe_layout.setContentsMargins(12, 12, 12, 12)
        safe_layout.addWidget(label("Les originaux sont préservés.", "note", True))
        safe_layout.addWidget(
            label(
                "Les noms déjà utilisés reçoivent un suffixe. Aucun fichier écrasé.", "note", True
            )
        )
        layout.addWidget(safe)
        self.target.currentTextChanged.connect(self._update_quality)
        self.lossless.toggled.connect(self._update_quality)
        self.quality.valueChanged.connect(self._update_quality)
        return frame

    def _footer(self) -> QFrame:
        frame, layout = card()
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)
        row = QHBoxLayout()
        text = QVBoxLayout()
        text.setSpacing(4)
        self.status = label("Prêt à préparer votre premier traitement.", wrap=True)
        self.status.setAccessibleName("État du traitement")
        self.status_detail = label("Ajoutez des fichiers pour commencer.", "note", True)
        text.addWidget(self.status)
        text.addWidget(self.status_detail)
        row.addLayout(text, 1)
        self.journal = button("Journal", name="quiet")
        self.journal.clicked.connect(self.show_log)
        row.addWidget(self.journal)
        self.open_output = button("", "folder", "quiet")
        self.open_output.setAccessibleName("Ouvrir le dossier de destination")
        self.open_output.setToolTip("Ouvrir le dossier de destination")
        self.open_output.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self.destination.text()))
        )
        row.addWidget(self.open_output)
        self.cancel = button("Annuler", name="quiet")
        self.cancel.clicked.connect(self.cancel_job)
        self.cancel.hide()
        row.addWidget(self.cancel)
        self.start = button("Convertir", "arrow", "primary")
        self.start.clicked.connect(self.start_job)
        row.addWidget(self.start)
        layout.addLayout(row)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(5)
        self.progress.setAccessibleName("Progression du traitement")
        layout.addWidget(self.progress)
        return frame

    def _paths(self) -> list[Path]:
        return [
            Path(self.files.item(index).data(Qt.ItemDataRole.UserRole))
            for index in range(self.files.count())
        ]

    def _set_mode(self, mode: Operation) -> None:
        if self.job is not None or self.pdf_editor.job is not None:
            return
        if self.mode != Operation.PDF_TOOLS:
            self.queues[self.mode] = self._paths()
        self.mode = mode
        self.nav_buttons[mode].setChecked(True)
        self.title.setText(MODES[mode][0])
        self.subtitle.setText(MODES[mode][1])
        self.pdf_editor.set_active(mode == Operation.PDF_TOOLS)
        self.workspaces.setCurrentIndex(1 if mode == Operation.PDF_TOOLS else 0)
        if mode == Operation.PDF_TOOLS:
            return
        self.files.clear()
        self.results.clear()
        self.states.clear()
        self.add_paths([str(path) for path in self.queues[mode]])
        self.image_controls.setVisible(mode == Operation.CONVERT)
        self.pdf_controls.setVisible(mode != Operation.CONVERT)
        self.order_hint.setText(
            "Sélectionnez un fichier pour le retirer."
            if mode == Operation.CONVERT
            else "Ordre du PDF · glissez pour réorganiser."
        )
        self.order_hint.setWordWrap(True)
        self.support.setText(
            "Documents PDF · non chiffrés"
            if mode == Operation.MERGE
            else "PNG, JPEG, WebP, BMP, TIFF, GIF\n"
            "Images fixes · codecs disponibles dans Moteurs et formats"
        )
        self.start.setText(
            {
                Operation.CONVERT: "Convertir",
                Operation.MERGE: "Fusionner",
                Operation.IMAGES_PDF: "Créer le PDF",
            }[mode]
        )
        self.status.setText("Préparez vos fichiers et choisissez la destination.")
        self.status_detail.setText("Traitement local · les fichiers sources restent intacts.")
        self.progress.setValue(0)
        self._update_quality()
        self._update_controls()

    def _update_quality(self) -> None:
        target = self.target.currentText()
        self.lossless.setVisible(target == "WEBP")
        lossy = target == "JPEG" or (target == "WEBP" and not self.lossless.isChecked())
        self.quality.setEnabled(lossy and self.job is None)
        self.quality.setVisible(lossy)
        self.quality_label.setVisible(lossy)
        self.quality_label.setEnabled(lossy)
        self.quality_label.setText(f"Qualité d’encodage   ·   {self.quality.value()}")
        if self.mode == Operation.MERGE:
            text = (
                "Les pages sont assemblées sans rasterisation. Les PDF chiffrés ou signés "
                "sont refusés. Certains éléments interactifs ne sont pas préservables."
            )
        elif self.mode == Operation.IMAGES_PDF:
            text = (
                "Une image fixe par page, dimensions et proportions conservées. "
                "JPEG incorporé sans réencodage lorsque possible. Les métadonnées "
                "des fichiers ne sont pas toutes transférées."
            )
        else:
            text = (
                "Compression avec perte, même à qualité 100. "
                if lossy
                else "Sans perte supplémentaire dans les modes compatibles. "
            )
            if target in {"JPEG", "BMP"}:
                text += "La transparence sera composée sur un fond blanc. "
            text += (
                "Dimensions conservées, orientation EXIF appliquée. "
                "Métadonnées selon le format cible."
            )
        self.explanation.setText(text)
        self.explanation.setStyleSheet("color:#e5c58d;font-size:12px;" if lossy else "")

    def _update_controls(self) -> None:
        running = self.job is not None
        count = self.files.count()
        selected = bool(self.files.selectedItems())
        self.start.setEnabled(count > 0 and not running)
        self.remove.setEnabled(selected and not running)
        self.up.setEnabled(selected and not running and self.files.currentRow() > 0)
        self.down.setEnabled(selected and not running and self.files.currentRow() < count - 1)
        self.empty.setVisible(count == 0)
        self.files.setVisible(count > 0)
        self.count.setText(f"{count} fichier{'s' if count != 1 else ''}")
        size = 0
        for path in self._paths():
            try:
                size += path.stat().st_size
            except OSError:
                pass
        self.total.setText(
            f"{format_size(size)} au total · aucun original modifié"
            if count
            else "Sans abonnement. Sans quota de fichiers."
        )

    def pick_files(self) -> None:
        if self.mode == Operation.PDF_TOOLS:
            self.pdf_editor.pick_file()
            return
        if self.job is not None:
            return
        filters = (
            "PDF (*.pdf *.PDF)"
            if self.mode == Operation.MERGE
            else (
                "Images (" + " ".join(f"*{ext} *{ext.upper()}" for ext in input_extensions()) + ")"
            )
        )
        paths, _ = QFileDialog.getOpenFileNames(self, "Ajouter des fichiers", "", filters)
        self.add_paths(paths)

    def add_paths(self, paths: list[str]) -> None:
        if self.job is not None:
            return
        existing = set(self._paths())
        errors = []
        for raw in paths:
            try:
                path = source_file(Path(raw))
                allowed = (".pdf",) if self.mode == Operation.MERGE else input_extensions()
                if path.suffix.lower() not in allowed:
                    raise ValueError("Format non compatible avec cet espace.")
                if path in existing:
                    continue
                item, row = make_item(path, path.stat().st_size)
                self.files.addItem(item)
                self.files.setItemWidget(item, row)
                existing.add(path)
            except Exception as exc:
                errors.append(f"{Path(raw).name} : {exc}")
        if errors:
            self.log.extend(errors)
            self.status.setText(f"{len(errors)} fichier(s) non ajouté(s). Consultez le journal.")
            self.status_detail.setText(errors[0])
        self._update_controls()

    def remove_selected(self) -> None:
        if self.mode == Operation.PDF_TOOLS:
            if self.pdf_editor.view.hasFocus():
                self.pdf_editor.remove_pages()
            return
        if self.job is not None:
            return
        for item in self.files.selectedItems():
            self.files.takeItem(self.files.row(item))
        self._update_controls()

    def move_selected(self, direction: int) -> None:
        if self.job is not None:
            return
        row = self.files.currentRow()
        new = row + direction
        if row < 0 or not 0 <= new < self.files.count():
            return
        paths = self._paths()
        paths[row], paths[new] = paths[new], paths[row]
        self.files.clear()
        for path in paths:
            self.add_paths([str(path)])
        self.files.setCurrentRow(new)
        self.results.clear()
        self.states.clear()

    def pick_destination(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Dossier de destination", self.destination.text()
        )
        if directory:
            self.destination.setText(directory)
            self.destination.setToolTip(directory)

    def start_job(self) -> None:
        if self.job is not None or not self.files.count():
            return
        try:
            destination = output_directory(Path(self.destination.text()))
            name = (
                output_name(self.pdf_name.text())
                if self.mode != Operation.CONVERT
                else "unused.pdf"
            )
        except Exception as exc:
            self.status.setText(str(exc))
            return
        request = Request(
            self.mode,
            tuple(self._paths()),
            destination,
            name,
            ImageOptions(
                self.target.currentText(),
                self.quality.value(),
                self.lossless.isChecked(),
                self.metadata.isChecked(),
                self.copy_same.isChecked(),
            ),
        )
        self.results.clear()
        self.states.clear()
        for index in range(self.files.count()):
            self._item_status(index, "pending", "En attente")
        self.progress.setValue(0)
        self.status.setText("Traitement en cours…")
        self.status_detail.setText(
            "Vous pouvez annuler ; les résultats déjà terminés seront conservés."
        )
        self.job = Job(request)
        self.job.update.connect(self.handle_event)
        self.job.finished.connect(self._job_stopped)
        self._set_running(True)
        self.job.start()

    def _set_running(self, running: bool) -> None:
        for widget in [
            self.drop,
            self.files,
            self.image_controls,
            self.pdf_controls,
            self.choose_destination,
            *self.nav_buttons.values(),
        ]:
            widget.setEnabled(not running)
        self.cancel.setVisible(running)
        self.cancel.setEnabled(running)
        self._update_controls()
        self._update_quality()

    def _item_status(self, index: int, state: str, message: str) -> None:
        item = self.files.item(index)
        if item is None:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        self.states[path] = state
        row = cast(FileRow, self.files.itemWidget(item))
        row.set_status(state, message)
        item.setToolTip(f"{path}\n{message}")

    def handle_event(self, event: Event) -> None:
        kind = event.get("kind")
        if kind == "item":
            index = event.get("index", 0)
            state = event.get("state", "pending")
            message = event.get("message", "")
            self._item_status(index, state, message)
            path = str(self._paths()[index])
            if state in {"success", "error"}:
                self.log.append(
                    f"{Path(path).name} · {message}"
                    + (f"\n  → {event['path']}" if event.get("path") else "")
                )
            if event.get("path"):
                self.results[path] = Path(event["path"])
        elif kind == "progress":
            self.progress.setValue(event.get("progress", 0))
        elif kind == "finished":
            successes = sum(state == "success" for state in self.states.values())
            errors = sum(state == "error" for state in self.states.values())
            self.status.setText(f"Traitement terminé · {successes} réussi(s), {errors} erreur(s).")
            self.status_detail.setText(
                "Double-cliquez sur un fichier pour ouvrir son résultat ou son erreur."
            )
        elif kind in {"fatal", "cancelled"}:
            message = event.get("message", "Erreur inconnue.")
            self.log.append(message)
            self.status.setText(message)
            self.status_detail.setText("Consultez le journal pour les détails.")
            for index, source in enumerate(self._paths()):
                if self.states.get(str(source)) not in {"success", "error"}:
                    self._item_status(
                        index, "cancelled" if kind == "cancelled" else "error", message
                    )

    def _job_stopped(self) -> None:
        job = self.job
        self.job = None
        if job is not None:
            job.deleteLater()
        self._set_running(False)
        if self._closing:
            self.close()

    def cancel_job(self) -> None:
        if self.job is not None:
            self.job.cancel()
            self.cancel.setEnabled(False)
            self.status.setText("Annulation en cours…")

    def show_item(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if path in self.results:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.results[path])))
        elif self.states.get(path) == "error":
            QMessageBox.information(self, "Détail du traitement", item.toolTip())

    def _text_dialog(self, title: str, text: str) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(700, 520)
        layout = QVBoxLayout(dialog)
        browser = QTextBrowser()
        browser.setPlainText(text)
        layout.addWidget(browser)
        close = button("Fermer")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        dialog.exec()

    def show_log(self) -> None:
        self._text_dialog(
            "Journal de la session", "\n\n".join(self.log) or "Aucun traitement pour le moment."
        )

    def show_engines(self) -> None:
        versions = "\n".join(
            f"{name} : {importlib.metadata.version(name)}"
            for name in ("PySide6-Essentials", "Pillow", "pypdf", "img2pdf", "pikepdf", "pypdfium2")
        )
        self._text_dialog(
            "Moteurs et compatibilité",
            f"MOTEURS ACTIFS\n{versions}\n\n"
            f"IMAGES EN ENTRÉE\n{', '.join(input_extensions())}\n\n"
            f"IMAGES EN SORTIE\n{', '.join(available_targets())}\n\n"
            "Images fixes uniquement. SVG, AVIF, CMYK et profondeurs non compatibles refusés. "
            "PNG/TIFF 16 bits : conservation selon le mode et l’encodeur.\n\n"
            "PDF → PDF : fusion de documents non chiffrés, non signés.\n"
            "Outils PDF : aperçus, ordre, extraction, retrait, rotation et découpage.\n"
            "Images fixes → PDF : une page par image, sans réencodage JPEG inutile.\n\n"
            "EXTENSIONS FUTURES, NON ACTIVÉES\n"
            f"LibreOffice : {shutil.which('libreoffice') or 'absent'}\n"
            f"FFmpeg : {shutil.which('ffmpeg') or 'absent'}\n\n"
            "Aucun de ces outils externes n’est installé ou lancé par cette version.\n"
            "Les protections de décompression Pillow sont conservées.\n"
            "Les temporaires sont supprimés après réussite, erreur ou annulation.\n"
            "La fusion conserve le contenu des pages ; elle ne garantit pas la "
            "préservation de tous les éléments interactifs.\n\n"
            "Licences : Qt/PySide LGPLv3 ; Pillow MIT-CMU ; pypdf BSD-3-Clause ; "
            "img2pdf LGPLv3 ; pikepdf MPL-2.0. Voir docs/DEPENDENCIES.md.",
        )

    def _pdf_busy(self, busy: bool) -> None:
        for nav in self.nav_buttons.values():
            nav.setEnabled(not busy)

    def _pdf_idle(self) -> None:
        if self._closing:
            self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        pdf_stopped = self.pdf_editor.shutdown()
        if self.job is not None or not pdf_stopped:
            self._closing = True
            self.cancel_job()
            event.ignore()
            return
        self.settings.setValue("destination", self.destination.text())
        super().closeEvent(event)
