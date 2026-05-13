"""
SECTION 1 – CAPTURE
Handles camera capture, SDK integration, and frame recording.
"""

import cv2
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGroupBox, QComboBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap

try:
    from dino_camera import DinoCamera
    _DINO_CAMERA_AVAILABLE = True
except ImportError:
    _DINO_CAMERA_AVAILABLE = False
    DinoCamera = None

# Import shared UI utilities from utils
from utils import C, STYLE, label, btn, separator, CAPTURED_DIR, ndarray_to_qpixmap, AppStatusBar


class CaptureSection(QWidget):
    def __init__(self, status_bar: AppStatusBar):
        super().__init__()
        self.status_bar = status_bar
        self._cap = None
        self._dino = None
        self._sdk = None
        self._session_count = 0
        self._capturing = False
        self._device_index = 0
        self._amr_value = 0.0
        self._last_frame = None

        self._preview_timer = QTimer()
        self._capture_timer = QTimer()
        self._amr_timer = QTimer()
        self._preview_timer.timeout.connect(self._update_preview)
        self._capture_timer.timeout.connect(self._capture_frame)
        self._amr_timer.timeout.connect(self._poll_amr)

        self._build_ui()
        self._init_sdk()
        self._start_preview()

    def _init_sdk(self):
        if not _DINO_CAMERA_AVAILABLE:
            self._sdk_status_lbl.setText("SDK: dino_camera.py not found — plain webcam mode")
            self._sdk_status_lbl.setStyleSheet(f"color:{C['muted']}; font-size:10px;")
            self._sdk_panel.hide()
            return

        self._dino = DinoCamera()
        self._cap  = self._dino.cap
        self._sdk  = self._dino.sdk

        if self._sdk is None:
            self._sdk_status_lbl.setText("SDK: DNX64 unavailable — plain webcam mode")
            self._sdk_status_lbl.setStyleSheet(f"color:{C['muted']}; font-size:10px;")
            self._sdk_panel.hide()
            return

        devices = self._dino.list_devices()
        self._device_combo.clear()
        if not devices:
            self._sdk_status_lbl.setText("SDK: loaded  |  No Dino-Lite devices found")
            self._sdk_status_lbl.setStyleSheet(f"color:{C['yellow']}; font-size:10px;")
        else:
            for i, name in enumerate(devices):
                self._device_combo.addItem(f"[{i}] {name}", userData=i)
            self._sdk_status_lbl.setText(f"SDK: loaded  |  {len(devices)} device(s) found")
            self._sdk_status_lbl.setStyleSheet(f"color:{C['green']}; font-size:10px;")
            self._sdk_panel.show()
            self._amr_timer.start(500)

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.setContentsMargins(16, 16, 16, 16)

        hdr = QHBoxLayout()
        hdr.addWidget(label("◉  CAPTURE", C['accent'], 13, True))
        hdr.addStretch()
        self._session_lbl = label("Session: 0 frames", C['muted'], 11)
        hdr.addWidget(self._session_lbl)
        lay.addLayout(hdr)

        self._sdk_status_lbl = label("SDK: initialising…", C['muted'], 10)
        lay.addWidget(self._sdk_status_lbl)
        lay.addWidget(separator())

        self._sdk_panel = QGroupBox("DINO-LITE CONTROLS")
        self._sdk_panel.hide()
        sdk_lay = QVBoxLayout(self._sdk_panel)
        sdk_lay.setSpacing(8)

        dev_row = QHBoxLayout()
        dev_row.addWidget(label("Device:", C['muted'], 10))
        self._device_combo = QComboBox()
        self._device_combo.setStyleSheet(STYLE)
        self._device_combo.currentIndexChanged.connect(self._on_device_changed)
        dev_row.addWidget(self._device_combo, 1)
        sdk_lay.addLayout(dev_row)

        amr_row = QHBoxLayout()
        self._amr_lbl  = label("Magnification: —×", C['accent'],  11)
        self._fov_lbl  = label("FOV: — µm",         C['accent2'], 11)
        amr_row.addWidget(self._amr_lbl)
        amr_row.addStretch()
        amr_row.addWidget(self._fov_lbl)
        sdk_lay.addLayout(amr_row)

        led_row = QHBoxLayout()
        led_row.addWidget(label("LED:", C['muted'], 10))
        self._led_on_btn  = btn("ON",  C['green'],  True)
        self._led_off_btn = btn("OFF", C['red'],    True)
        self._led_on_btn.clicked.connect(lambda: self._set_led(1))
        self._led_off_btn.clicked.connect(lambda: self._set_led(0))
        led_row.addWidget(self._led_on_btn)
        led_row.addWidget(self._led_off_btn)
        led_row.addStretch()
        sdk_lay.addLayout(led_row)

        ae_row = QHBoxLayout()
        ae_row.addWidget(label("Auto-Exposure:", C['muted'], 10))
        self._ae_on_btn  = btn("ON",  C['green'], True)
        self._ae_off_btn = btn("OFF", C['red'],   True)
        self._ae_on_btn.clicked.connect(lambda: self._set_ae(1))
        self._ae_off_btn.clicked.connect(lambda: self._set_ae(0))
        ae_row.addWidget(self._ae_on_btn)
        ae_row.addWidget(self._ae_off_btn)
        ae_row.addStretch()
        sdk_lay.addLayout(ae_row)

        lay.addWidget(self._sdk_panel)

        self._cam_label = QLabel()
        self._cam_label.setMinimumSize(480, 360)
        self._cam_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cam_label.setStyleSheet(f"""
            background: {C['surface']}; border: 1px solid {C['border']};
            border-radius: 8px; color: {C['muted']}; font-size: 13px;
        """)
        self._cam_label.setText("⬡  No camera feed")
        lay.addWidget(self._cam_label, 1)

        ctrl = QHBoxLayout()
        self._btn_start = btn("▶  Start Capture", C['green'])
        self._btn_stop  = btn("■  Stop Capture",  C['red'])
        self._btn_stop.setEnabled(False)
        self._btn_start.clicked.connect(self._start_capture)
        self._btn_stop.clicked.connect(self._stop_capture)
        ctrl.addWidget(self._btn_start)
        ctrl.addWidget(self._btn_stop)
        ctrl.addStretch()
        lay.addLayout(ctrl)

        info = QHBoxLayout()
        info.addWidget(label("Interval: 3 sec  |  Format: PNG  |  Color: BGR  |  "
                             "Video frames via cv2.VideoCapture", C['muted'], 10))
        lay.addLayout(info)

    def _on_device_changed(self, combo_idx: int):
        if self._device_combo.count() == 0:
            return
        sdk_idx = self._device_combo.itemData(combo_idx)
        if sdk_idx is None:
            sdk_idx = combo_idx
        self._device_index = sdk_idx
        if self._dino:
            self._preview_timer.stop()
            self._dino.switch_device(sdk_idx)
            self._cap = self._dino.cap
            if self._cap and self._cap.isOpened():
                self._preview_timer.start(50)
        else:
            self._reopen_cap(sdk_idx)

    def _poll_amr(self):
        if self._dino is None:
            return
        amr = self._dino.get_amr(self._device_index)
        if amr > 0:
            self._amr_value = amr
            self._amr_lbl.setText(f"Magnification: {amr:.1f}×")
            fov = self._dino.get_fov(amr, self._device_index)
            if fov > 0:
                self._fov_lbl.setText(f"FOV: {fov:.1f} µm")

    def _set_led(self, state: int):
        if self._sdk:
            try:
                self._sdk.SetLEDState(self._device_index, state)
            except Exception:
                pass

    def _set_ae(self, state: int):
        if self._sdk:
            try:
                self._sdk.SetAutoExposure(self._device_index, state)
            except Exception:
                pass

    def _reopen_cap(self, index: int):
        if self._cap:
            self._preview_timer.stop()
            self._cap.release()
        self._cap = cv2.VideoCapture(index)
        if self._cap.isOpened():
            self._preview_timer.start(50)

    def _start_preview(self):
        if self._cap is None:
            self._cap = cv2.VideoCapture(self._device_index)
        if self._cap and self._cap.isOpened():
            self._preview_timer.start(50)

    def _update_preview(self):
        if self._cap and self._cap.isOpened():
            ret, frame = self._cap.read()
            if ret:
                self._last_frame = frame
                if self._amr_value > 0:
                    cv2.putText(
                        frame, f"{self._amr_value:.1f}x",
                        (10, 28), cv2.FONT_HERSHEY_SIMPLEX,
                        0.8, (80, 220, 255), 2, cv2.LINE_AA
                    )
                pm = ndarray_to_qpixmap(frame)
                pm = pm.scaled(
                    self._cam_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self._cam_label.setPixmap(pm)

    def _start_capture(self):
        self._capturing = True
        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._capture_timer.start(3000)

    def _stop_capture(self):
        self._capturing = False
        self._capture_timer.stop()
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)

    def _capture_frame(self):
        if not (self._cap and self._cap.isOpened()):
            return
        ret, frame = self._cap.read()
        if ret:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            fname = f"capture_{ts}.png"
            fpath = CAPTURED_DIR / fname
            cv2.imwrite(str(fpath), frame)
            self._session_count += 1
            self._session_lbl.setText(f"Session: {self._session_count} frames")
            self.status_bar.showMessage(f"Captured: {fname}  |  {self._amr_value:.1f}×", 2000)

    def closeEvent(self, event):
        self._preview_timer.stop()
        self._capture_timer.stop()
        self._amr_timer.stop()
        if self._dino:
            self._dino.release()
        elif self._cap:
            self._cap.release()
        super().closeEvent(event)
