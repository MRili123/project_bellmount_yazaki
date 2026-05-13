"""
SECTION 2 – INBOX
Manages captured images and queues them for annotation.
"""

import cv2
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QGridLayout,
    QFrame, QMessageBox, QMenu, QDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QCursor

from utils import C, STYLE, label, btn, separator, CAPTURED_DIR, AppStatusBar, ndarray_to_qpixmap
import json
from app import STORE


class ImageCard(QFrame):
    toggled      = pyqtSignal(str, bool)
    delete_requested = pyqtSignal(str)
    preview_requested = pyqtSignal(str)

    def __init__(self, img_path: Path, in_dataset: bool):
        super().__init__()
        self.img_path = img_path
        self.selected = False
        self.in_dataset = in_dataset
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self._build()

    def _build(self):
        self.setFixedSize(160, 210)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._refresh_style(False)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(3)

        self._thumb = QLabel()
        self._thumb.setFixedSize(148, 108)
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb.setStyleSheet(f"background:{C['bg']}; border-radius:4px;")
        self._load_thumb()
        lay.addWidget(self._thumb)

        name = self.img_path.name
        short = name[:18] + "…" if len(name) > 20 else name
        n_lbl = QLabel(short)
        n_lbl.setStyleSheet(f"color:{C['text']}; font-size:9px;")
        n_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(n_lbl)

        try:
            img = cv2.imread(str(self.img_path))
            h, w = img.shape[:2]
            dim_text = f"{w}×{h}"
        except Exception:
            dim_text = "?×?"
        d_lbl = QLabel(dim_text)
        d_lbl.setStyleSheet(f"color:{C['muted']}; font-size:9px;")
        d_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(d_lbl)

        bottom = QHBoxLayout()
        bottom.setSpacing(4)
        bottom.setContentsMargins(0, 0, 0, 0)

        if self.in_dataset:
            badge_col, badge_txt = C['green'], "✓ Done"
        else:
            badge_col, badge_txt = C['yellow'], "● Pending"
        badge = QLabel(badge_txt)
        badge.setStyleSheet(f"""
            background:{badge_col}22; border:1px solid {badge_col}66;
            border-radius:3px; color:{badge_col}; font-size:9px;
            padding:2px 4px; font-weight:bold;
        """)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bottom.addWidget(badge, 1)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(22, 20)
        del_btn.setStyleSheet(f"""
            QPushButton {{
                background:{C['red']}22; border:1px solid {C['red']}66;
                border-radius:3px; color:{C['red']}; font-size:10px;
                font-weight:bold; padding:0px;
            }}
            QPushButton:hover {{ background:{C['red']}55; border-color:{C['red']}; }}
            QPushButton:pressed {{ background:{C['red']}88; }}
        """)
        del_btn.setToolTip("Delete this image file")
        del_btn.clicked.connect(lambda: self.delete_requested.emit(str(self.img_path)))
        bottom.addWidget(del_btn)

        lay.addLayout(bottom)

    def _load_thumb(self):
        try:
            img = cv2.imread(str(self.img_path))
            pm = ndarray_to_qpixmap(img)
            pm = pm.scaled(148, 108, Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
            self._thumb.setPixmap(pm)
        except Exception:
            self._thumb.setText("?")

    def _refresh_style(self, selected):
        if selected:
            border = C['accent']
            bg = C['hover']
        else:
            border = C['border']
            bg = C['card']
        self.setStyleSheet(f"""
            QFrame {{ background:{bg}; border:2px solid {border};
                      border-radius:8px; }}
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self.in_dataset:
            self.selected = not self.selected
            self._refresh_style(self.selected)
            self.toggled.emit(str(self.img_path), self.selected)

    def mouseDoubleClickEvent(self, event):
        self.preview_requested.emit(str(self.img_path))
        super().mouseDoubleClickEvent(event)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background:{C['panel']}; border:1px solid {C['border']};
                     color:{C['text']}; font-size:11px; padding:4px; }}
            QMenu::item {{ padding:5px 20px; border-radius:3px; }}
            QMenu::item:selected {{ background:{C['hover']}; }}
        """)
        if not self.in_dataset:
            sel_action = menu.addAction("☑  Select / Deselect")
            sel_action.triggered.connect(lambda: self._toggle_select())
        menu.addSeparator()
        del_action = menu.addAction("✕  Delete file")
        del_action.triggered.connect(lambda: self.delete_requested.emit(str(self.img_path)))
        menu.exec(self.mapToGlobal(pos))

    def _toggle_select(self):
        if not self.in_dataset:
            self.selected = not self.selected
            self._refresh_style(self.selected)
            self.toggled.emit(str(self.img_path), self.selected)


class InboxSection(QWidget):
    send_to_annotation = pyqtSignal(list)

    def __init__(self, status_bar: AppStatusBar):
        super().__init__()
        self.status_bar = status_bar
        self._selected = set()
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.setContentsMargins(16, 16, 16, 16)

        hdr = QHBoxLayout()
        hdr.addWidget(label("◈  INBOX", C['accent2'], 13, True))
        hdr.addStretch()
        self._count_lbl = label("0 images", C['muted'], 11)
        hdr.addWidget(self._count_lbl)
        refresh_btn = btn("↺ Refresh", C['muted'], True)
        refresh_btn.clicked.connect(self.refresh)
        hdr.addWidget(refresh_btn)
        lay.addLayout(hdr)
        lay.addWidget(separator())

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(f"background:{C['surface']}; border:none;")
        self._grid_widget = QWidget()
        self._grid_widget.setStyleSheet(f"background:{C['surface']};")
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setSpacing(10)
        self._grid.setContentsMargins(10, 10, 10, 10)
        self._scroll.setWidget(self._grid_widget)
        lay.addWidget(self._scroll, 1)

        ctrl = QHBoxLayout()
        self._sel_lbl = label("0 selected", C['muted'], 11)
        ctrl.addWidget(self._sel_lbl)
        ctrl.addStretch()
        self._del_btn = btn("✕  Delete Selected", C['red'])
        self._del_btn.setEnabled(False)
        self._del_btn.clicked.connect(self._delete_selected)
        ctrl.addWidget(self._del_btn)
        self._send_btn = btn("→  Send to Annotation", C['accent'])
        self._send_btn.setEnabled(False)
        self._send_btn.clicked.connect(self._send)
        ctrl.addWidget(self._send_btn)
        lay.addLayout(ctrl)

        self.refresh()

    def refresh(self):
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._selected.clear()

        dataset_files = {e["filename"] for e in STORE.load()}
        images = sorted(CAPTURED_DIR.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
        self._count_lbl.setText(f"{len(images)} images")

        cols = 4
        for i, img_path in enumerate(images):
            in_ds = img_path.name in dataset_files
            card = ImageCard(img_path, in_ds)
            card.toggled.connect(self._on_toggle)
            card.delete_requested.connect(self._delete_one)
            card.preview_requested.connect(self._show_preview)
            self._grid.addWidget(card, i // cols, i % cols)

        self._grid.setRowStretch(max(1, (len(images) // cols) + 1), 1)
        self._update_controls()

        pending = sum(1 for img in images if img.name not in dataset_files)
        self.status_bar.update_stats(total=len(dataset_files), pending=pending)

    def _on_toggle(self, path, selected):
        if selected:
            self._selected.add(path)
        else:
            self._selected.discard(path)
        self._update_controls()

    def _update_controls(self):
        n = len(self._selected)
        self._sel_lbl.setText(f"{n} selected")
        self._send_btn.setEnabled(n > 0)
        self._del_btn.setEnabled(n > 0)

    def _delete_one(self, path_str: str):
        path = Path(path_str)
        reply = QMessageBox.question(
            self, "Delete Image",
            f"Permanently delete:\n{path.name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                path.unlink()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not delete file:\n{e}")
            self._selected.discard(path_str)
            self.refresh()

    def _delete_selected(self):
        if not self._selected:
            return
        reply = QMessageBox.question(
            self, "Delete Multiple Images",
            f"Permanently delete {len(self._selected)} image(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            for path_str in self._selected:
                try:
                    Path(path_str).unlink()
                except Exception:
                    pass
            self._selected.clear()
            self.refresh()

    def _show_preview(self, path_str: str):
        dialog = QDialog(self)
        dialog.setWindowTitle(Path(path_str).name)
        dialog.setMinimumSize(800, 600)
        lay = QVBoxLayout(dialog)

        lbl = QLabel()
        img = cv2.imread(path_str)
        if img is not None:
            pm = ndarray_to_qpixmap(img)
            pm = pm.scaled(700, 500, Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
            lbl.setPixmap(pm)
        else:
            lbl.setText("Could not load image")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lbl)

        dialog.exec()

    def _send(self):
        if not self._selected:
            return
        paths = list(self._selected)
        self.send_to_annotation.emit(paths)

    def _on_send_to_annotation(self, paths: list):
        self._selected.clear()
        self.refresh()
