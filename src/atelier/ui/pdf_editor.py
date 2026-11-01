from __future__ import annotations

import math
from pathlib import Path
from typing import cast

from PySide6.QtCore import QItemSelection, QItemSelectionModel, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import (
    QDesktopServices,
    QDragEnterEvent,
    QDropEvent,
    QImage,
    QKeySequence,
    QResizeEvent,
    QShortcut,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from atelier.core.files import output_directory, output_name, source_file
from atelier.core.models import Event, Operation, PdfOutput, PdfPlan, Request, UserError
from atelier.core.pdf_tools import PdfInfo, parse_pages, parse_split
from atelier.jobs import Job
from atelier.previews import PreviewSession
from atelier.ui.pdf_pages import PageModel, PageView
from atelier.ui.widgets import button, card, label


class PdfEditor(QWidget):
    busy_changed = Signal(bool)
    idle = Signal()
    message = Signal(str)
    journal_requested = Signal()
    destination_changed = Signal(str)

    def __init__(self, destination: str) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.info: PdfInfo | None = None
        self.path: Path | None = None
        self.session: PreviewSession | None = None
        self.sessions: list[PreviewSession] = []
        self.job: Job | None = None
        self.active = False
        self.loading = False
        self.output_paths: list[Path] = []
        self.model = PageModel()
        self.refresh = QTimer(self)
        self.refresh.setSingleShot(True)
        self.refresh.setInterval(45)
        self.refresh.timeout.connect(self.request_visible)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        work = QHBoxLayout()
        work.setSpacing(18)
        frame, pages = card()
        pages.setSpacing(12)
        top = QHBoxLayout()
        self.document_label = label("Aucun document ouvert", "cardTitle")
        self.document_label.setMinimumWidth(0)
        self.document_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        top.addWidget(self.document_label, 1)
        self.open_button = button("Ouvrir un PDF", "upload", "quiet")
        self.open_button.clicked.connect(self.pick_file)
        top.addWidget(self.open_button)
        pages.addLayout(top)
        self.description = label(
            "Un document à la fois · glissez un PDF dans cet espace.", "note", True
        )
        pages.addWidget(self.description)
        toolbar = QHBoxLayout()
        self.undo_button = button("", "undo", "mini")
        self.up = button("", "up", "mini")
        self.down = button("", "down", "mini")
        self.remove_button = button("", "trash", "mini")
        for widget, text in (
            (self.undo_button, "Annuler la dernière modification (Ctrl+Z)"),
            (self.up, "Avancer la sélection (Alt+Haut)"),
            (self.down, "Reculer la sélection (Alt+Bas)"),
            (self.remove_button, "Retirer les pages sélectionnées (Suppr)"),
        ):
            widget.setToolTip(text)
            widget.setAccessibleName(text)
            toolbar.addWidget(widget)
        toolbar.addStretch()
        self.rotation = QComboBox()
        self.rotation.addItems(["90°", "180°", "270°"])
        self.rotation.setAccessibleName("Rotation à ajouter aux pages sélectionnées")
        toolbar.addWidget(self.rotation)
        self.rotate_button = button("Tourner", "rotate", "quiet")
        toolbar.addWidget(self.rotate_button)
        pages.addLayout(toolbar)
        selection = QHBoxLayout()
        self.range_selection = QLineEdit()
        self.range_selection.setPlaceholderText("Positions : 1-3, 5")
        self.range_selection.setAccessibleName("Positions à sélectionner dans l’ordre actuel")
        self.range_selection.setToolTip("Positions dans l’ordre actuel, et non numéros source.")
        selection.addWidget(self.range_selection, 1)
        self.select_button = button("Sélectionner", name="quiet")
        self.select_button.clicked.connect(self.select_range)
        selection.addWidget(self.select_button)
        self.goto = QSpinBox()
        self.goto.setMinimum(1)
        self.goto.setPrefix("Aller à ")
        self.goto.setAccessibleName("Aller à la position")
        self.goto.valueChanged.connect(self.go_to)
        selection.addWidget(self.goto)
        pages.addLayout(selection)
        self.view = PageView(self.model)
        self.view.files_dropped.connect(self.open_paths)
        self.view.reordered.connect(self.select_rows)
        self.view.verticalScrollBar().valueChanged.connect(lambda: self.refresh.start())
        self.view.selectionModel().selectionChanged.connect(self.update_controls)
        pages.addWidget(self.view, 1)
        self.empty = label(
            "Votre PDF, page par page.\nOuvrez un document pour organiser son contenu.",
            "muted",
            True,
        )
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setMinimumHeight(90)
        pages.addWidget(self.empty)
        self.selection_label = label("Ctrl / Maj pour sélectionner plusieurs pages.", "note", True)
        pages.addWidget(self.selection_label)
        work.addWidget(frame, 1)
        panel, options = card()
        options.addWidget(label("Préparer l’export", "cardTitle"))
        options.addWidget(label("Contenu de la sortie", "muted"))
        self.export_mode = QComboBox()
        self.export_mode.addItems(
            ["Tout le document", "La sélection", "Découper par plages", "Une page par fichier"]
        )
        self.export_mode.setAccessibleName("Type d’export PDF")
        self.export_mode.setMinimumHeight(38)
        self.export_mode.currentIndexChanged.connect(self.update_controls)
        options.addWidget(self.export_mode)
        self.split_label = label("Un fichier par groupe (séparateur ;)", "note", True)
        self.split_ranges = QLineEdit()
        self.split_ranges.setPlaceholderText("1-3 ; 4-6 ; 7, 9")
        self.split_ranges.setAccessibleName("Groupes de positions à découper")
        options.addWidget(self.split_label)
        options.addWidget(self.split_ranges)
        options.addWidget(label("Nom du document / préfixe", "muted"))
        self.output_name = QLineEdit("document - modifie.pdf")
        self.output_name.setAccessibleName("Nom du PDF ou préfixe des fichiers découpés")
        options.addWidget(self.output_name)
        options.addWidget(label("Dossier de destination", "muted"))
        self.destination = QLineEdit(destination)
        self.destination.setReadOnly(True)
        self.destination.setAccessibleName("Destination des outils PDF")
        options.addWidget(self.destination)
        self.choose_destination = button("Choisir un dossier", "folder", "quiet")
        self.choose_destination.clicked.connect(self.pick_destination)
        options.addWidget(self.choose_destination)
        options.addWidget(
            label(
                "Les plages utilisent les positions actuelles de la grille. "
                "L’extraction suit l’ordre affiché, rotations comprises.",
                "note",
                True,
            )
        )
        options.addStretch()
        options.addWidget(
            label(
                "Le PDF original reste intact.\nLes pages exportées restent vectorielles.",
                "note",
                True,
            )
        )
        options.addWidget(
            label(
                "Annotations, formulaires, liens internes et signets : "
                "préservation selon compatibilité. Vérifiez les documents "
                "interactifs après export. PDF chiffrés ou signés refusés.",
                "note",
                True,
            )
        )
        scroll = QScrollArea()
        scroll.setObjectName("optionsScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(panel)
        scroll.setFixedWidth(270)
        work.addWidget(scroll)
        layout.addLayout(work, 1)
        footer, bottom = card()
        bottom.setContentsMargins(16, 12, 16, 12)
        bottom.setSpacing(10)
        actions = QHBoxLayout()
        self.status = label("Prêt à ouvrir un PDF.", wrap=True)
        actions.addWidget(self.status, 1)
        journal = button("Journal", name="quiet")
        journal.clicked.connect(self.journal_requested.emit)
        actions.addWidget(journal)
        open_folder = button("", "folder", "quiet")
        open_folder.setAccessibleName("Ouvrir le dossier de sortie PDF")
        open_folder.setToolTip("Ouvrir le dossier de sortie PDF")
        open_folder.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self.destination.text()))
        )
        actions.addWidget(open_folder)
        self.cancel_button = button("Annuler", name="quiet")
        self.cancel_button.clicked.connect(self.cancel)
        actions.addWidget(self.cancel_button)
        self.export_button = button("Exporter le PDF", "arrow", "primary")
        self.export_button.clicked.connect(self.export)
        actions.addWidget(self.export_button)
        bottom.addLayout(actions)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(5)
        bottom.addWidget(self.progress)
        layout.addWidget(footer)
        self.undo_button.clicked.connect(self.model.undo)
        self.up.clicked.connect(lambda: self.move_selection(-1))
        self.down.clicked.connect(lambda: self.move_selection(1))
        self.remove_button.clicked.connect(self.remove_pages)
        self.rotate_button.clicked.connect(self.rotate_pages)
        self.model.changed.connect(self.model_changed)
        for sequence, callback in [
            ("Ctrl+Z", self.model.undo),
            ("Ctrl+R", self.rotate_pages),
            ("Alt+Up", lambda: self.move_selection(-1)),
            ("Alt+Down", lambda: self.move_selection(1)),
        ]:
            shortcut = QShortcut(QKeySequence(sequence), self.view, callback)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.update_controls()

    def selected_rows(self) -> list[int]:
        return sorted(index.row() for index in self.view.selectionModel().selectedIndexes())

    def select_rows(self, rows: list[int]) -> None:
        selection = QItemSelection()
        for row in rows:
            index = self.model.index(row)
            selection.select(index, index)
        self.view.selectionModel().select(
            selection, QItemSelectionModel.SelectionFlag.ClearAndSelect
        )
        if rows:
            self.view.selectionModel().setCurrentIndex(
                self.model.index(rows[0]), QItemSelectionModel.SelectionFlag.NoUpdate
            )

    def select_range(self) -> None:
        try:
            self.select_rows(list(parse_pages(self.range_selection.text(), len(self.model.pages))))
            self.status.setText("Sélection appliquée aux positions actuelles.")
        except UserError as exc:
            self.status.setText(str(exc))

    def go_to(self, position: int) -> None:
        index = self.model.index(position - 1)
        self.view.scrollTo(index)
        self.view.setCurrentIndex(index)

    def move_selection(self, direction: int) -> None:
        if self.job is None:
            self.select_rows(self.model.step(self.selected_rows(), direction))

    def rotate_pages(self) -> None:
        if self.job is None:
            rows = self.selected_rows()
            self.model.rotate(rows, (self.rotation.currentIndex() + 1) * 90)
            self.select_rows(rows)

    def remove_pages(self) -> None:
        if self.job is None:
            self.model.remove(self.selected_rows())

    def model_changed(self) -> None:
        self.update_controls()
        self.refresh.start()

    def update_controls(self) -> None:
        count = len(self.model.pages)
        selected = len(self.selected_rows())
        busy = self.job is not None
        ready = self.info is not None and not self.loading and not busy
        self.view.setEnabled(ready)
        self.empty.setVisible(count == 0)
        self.empty.setText(
            "Chargement du document…"
            if self.loading
            else "Votre PDF, page par page.\nOuvrez un document pour organiser son contenu."
        )
        self.selection_label.setText(
            f"{count} page(s) · {selected} sélectionnée(s) · "
            "glissez pour réorganiser · Ctrl / Maj pour sélectionner"
        )
        self.goto.blockSignals(True)
        self.goto.setMaximum(max(1, count))
        self.goto.blockSignals(False)
        for widget in [self.up, self.down, self.remove_button, self.rotate_button, self.rotation]:
            widget.setEnabled(ready and selected > 0)
        self.undo_button.setEnabled(ready and bool(self.model.history))
        self.open_button.setEnabled(not busy)
        for widget in [
            self.export_mode,
            self.output_name,
            self.split_ranges,
            self.choose_destination,
        ]:
            widget.setEnabled(not busy)
        for widget in [self.range_selection, self.select_button, self.goto]:
            widget.setEnabled(ready and count > 0)
        splitting = self.export_mode.currentIndex() == 2
        self.split_label.setVisible(splitting)
        self.split_ranges.setVisible(splitting)
        self.export_button.setEnabled(
            ready and count > 0 and (self.export_mode.currentIndex() != 1 or selected > 0)
        )
        self.export_button.setText(
            "Exporter les PDF" if self.export_mode.currentIndex() >= 2 else "Exporter le PDF"
        )
        self.cancel_button.setVisible(busy or self.loading)
        self.cancel_button.setEnabled(busy or self.loading)

    def pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Ouvrir un PDF à manipuler", "", "PDF (*.pdf *.PDF)"
        )
        if path:
            self.open_paths([path])

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() and self.job is None:
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        if self.job is None and event.mimeData().hasUrls():
            self.open_paths(
                [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
            )
            event.acceptProposedAction()

    def open_paths(self, paths: list[str]) -> None:
        if self.job is not None:
            return
        try:
            if len(paths) != 1:
                raise UserError("Ouvrez un seul PDF à la fois dans cet espace.")
            path = source_file(Path(paths[0]))
            if path.suffix.lower() != ".pdf":
                raise UserError("Choisissez un fichier PDF.")
        except Exception as exc:
            self.status.setText(str(exc))
            return
        self.stop_preview()
        self.path = path
        self.info = None
        self.model.reset_document(0)
        self.output_paths.clear()
        self.output_name.setText(path.stem + " - modifie.pdf")
        self.document_label.setText(path.name)
        self.document_label.setToolTip(str(path))
        self.start_preview()

    def start_preview(self) -> None:
        if self.path is None or self.session is not None:
            return
        self.loading = True
        self.status.setText("Lecture du document et préparation des aperçus…")
        session = PreviewSession(self.path)
        self.session = session
        self.sessions.append(session)
        session.loaded.connect(self.on_loaded)
        session.thumbnail.connect(self.on_thumbnail)
        session.page_failed.connect(self.on_page_failed)
        session.failed.connect(self.on_failed)
        session.finished.connect(self.on_stopped)
        self.update_controls()
        session.start()

    @Slot(object)
    def on_loaded(self, info: PdfInfo) -> None:
        self.loaded(cast(PreviewSession, self.sender()), info)

    @Slot(int, QImage)
    def on_thumbnail(self, index: int, image: QImage) -> None:
        self.thumbnail(cast(PreviewSession, self.sender()), index, image)

    @Slot(int, str)
    def on_page_failed(self, index: int, message: str) -> None:
        self.page_failed(cast(PreviewSession, self.sender()), index, message)

    @Slot(str)
    def on_failed(self, message: str) -> None:
        self.preview_failed(cast(PreviewSession, self.sender()), message)

    @Slot()
    def on_stopped(self) -> None:
        self.preview_stopped(cast(PreviewSession, self.sender()))

    def loaded(self, session: PreviewSession, info: PdfInfo) -> None:
        if session is not self.session:
            return
        if self.info is not None and self.info.stamp != info.stamp:
            self.preview_failed(session, "Le document a changé. Réimportez-le pour continuer.")
            return
        restoring = self.info is not None
        self.info = info
        self.loading = False
        if not restoring:
            self.model.reset_document(info.page_count)
        self.description.setText(
            f"{info.page_count} page(s) source · "
            + (" ".join(info.notices) or "Le PDF original reste intact.")
        )
        self.status.setText("Document prêt. Sélectionnez, déplacez ou tournez les pages.")
        for notice in info.notices:
            self.message.emit(notice)
        self.update_controls()
        self.refresh.start()

    def thumbnail(self, session: PreviewSession, index: int, image: QImage) -> None:
        if session is self.session and self.active:
            self.model.store_image(index, image)

    def page_failed(self, session: PreviewSession, index: int, message: str) -> None:
        if session is self.session:
            self.model.errors[index] = message
            self.view.viewport().update()
            self.message.emit(f"Aperçu de la page {index + 1} : {message}")

    def preview_failed(self, session: PreviewSession, message: str) -> None:
        if session is self.session:
            self.loading = False
            self.info = None
            self.model.cache.clear()
            self.status.setText(message)
            self.message.emit(message)
            self.stop_preview()
            self.update_controls()

    def preview_stopped(self, session: PreviewSession) -> None:
        if session in self.sessions:
            self.sessions.remove(session)
        if session is self.session:
            self.session = None
        session.deleteLater()
        self.idle.emit()

    def stop_preview(self) -> None:
        self.refresh.stop()
        if self.session is not None:
            self.session.cancel()
            self.session = None

    def set_active(self, active: bool) -> None:
        self.active = active
        if not active:
            self.stop_preview()
            self.model.cache.clear()
        elif self.path is not None:
            self.start_preview()

    def request_visible(self) -> None:
        if self.session is None or not self.active or self.loading:
            return
        columns = max(1, self.view.viewport().width() // 158)
        first = max(0, self.view.verticalScrollBar().value() // 218 * columns - columns)
        last = first + (math.ceil(self.view.viewport().height() / 218) + 3) * columns
        missing = tuple(
            page.index
            for page in self.model.pages[first:last]
            if page.index not in self.model.cache and page.index not in self.model.errors
        )
        self.session.request(missing)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.refresh.start()

    def pick_destination(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Destination des PDF", self.destination.text()
        )
        if path:
            self.destination.setText(path)
            self.destination_changed.emit(path)

    def make_request(self) -> Request:
        if self.info is None or not self.model.pages:
            raise UserError("Le document de sortie doit contenir au moins une page.")
        name = output_name(self.output_name.text())
        mode = self.export_mode.currentIndex()
        groups: tuple[tuple[int, ...], ...]
        if mode == 0:
            groups = (tuple(range(len(self.model.pages))),)
        elif mode == 1:
            if not self.selected_rows():
                raise UserError("Sélectionnez au moins une page à extraire.")
            groups = (tuple(self.selected_rows()),)
        elif mode == 2:
            groups = parse_split(self.split_ranges.text(), len(self.model.pages))
        else:
            groups = tuple((row,) for row in range(len(self.model.pages)))
        width = max(3, len(str(len(groups))))
        outputs = tuple(
            PdfOutput(
                name if mode < 2 else f"{Path(name).stem} - {index + 1:0{width}}.pdf",
                tuple(self.model.pages[row] for row in group),
            )
            for index, group in enumerate(groups)
        )
        return Request(
            Operation.PDF_TOOLS,
            (self.info.path,),
            output_directory(Path(self.destination.text())),
            pdf_plan=PdfPlan(self.info.stamp, outputs),
        )

    def export(self) -> None:
        if self.job is not None:
            return
        try:
            request = self.make_request()
        except Exception as exc:
            self.status.setText(str(exc))
            return
        self.output_paths.clear()
        self.progress.setValue(0)
        self.status.setText("Export en cours… Les pages restent vectorielles.")
        self.job = Job(request)
        self.job.update.connect(self.handle_event)
        self.job.finished.connect(self.job_stopped)
        self.busy_changed.emit(True)
        self.update_controls()
        self.job.start()

    def handle_event(self, event: Event) -> None:
        kind = event.get("kind")
        if kind == "progress":
            self.progress.setValue(event.get("progress", 0))
        elif kind == "output":
            path = Path(event["path"])
            self.output_paths.append(path)
            self.message.emit(f"{path}\n{event.get('message', '')}")
        elif kind == "finished":
            self.status.setText(f"Export terminé · {len(self.output_paths)} fichier(s) créé(s).")
        elif kind in {"fatal", "cancelled"}:
            text = event.get("message", "Erreur d’export.")
            self.status.setText(text)
            self.message.emit(text)

    def job_stopped(self) -> None:
        job = self.job
        self.job = None
        if job is not None:
            job.deleteLater()
        self.busy_changed.emit(False)
        self.update_controls()
        self.idle.emit()

    def cancel(self) -> None:
        if self.job is not None:
            self.job.cancel()
            self.cancel_button.setEnabled(False)
            self.status.setText("Annulation de l’export…")
        elif self.loading:
            self.stop_preview()
            self.loading = False
            self.status.setText("Chargement annulé.")
            self.update_controls()

    def shutdown(self) -> bool:
        self.stop_preview()
        for session in self.sessions:
            session.cancel()
        if self.job is not None:
            self.job.cancel()
        return self.job is None and not any(session.isRunning() for session in self.sessions)
