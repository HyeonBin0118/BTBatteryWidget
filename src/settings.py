"""설정 창 (탭 구조: 일반 / 외관 / 동작)."""
from __future__ import annotations

import copy
from PyQt6.QtWidgets import (
    QDialog, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QCheckBox, QComboBox, QSlider, QPushButton,
    QSpinBox, QColorDialog, QGroupBox, QFormLayout, QDialogButtonBox,
    QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from .config import Config
from .battery import Device
from .icon_picker import IconPickerWidget


def _color_button(hex_color: str) -> QPushButton:
    btn = QPushButton()
    btn.setFixedSize(60, 24)
    btn.setStyleSheet(f"background:{hex_color}; border:1px solid #555; border-radius:4px;")
    return btn


class SettingsDialog(QDialog):
    applied   = pyqtSignal(Config)
    previewed = pyqtSignal(Config)

    def __init__(self, cfg: Config, devices: list[Device], parent=None):
        super().__init__(parent)
        self._cfg      = cfg
        self._original = copy.deepcopy(cfg)
        self._devices  = devices
        self._color_high = cfg.color_high
        self._color_mid  = cfg.color_mid
        self._color_low  = cfg.color_low

        self.setWindowTitle("설정")
        self.setMinimumWidth(480)
        self.setModal(True)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._tab_general(),    "일반")
        tabs.addTab(self._tab_appearance(), "외관")
        tabs.addTab(self._tab_behavior(),   "동작")
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._apply)
        buttons.rejected.connect(self._cancel)
        layout.addWidget(buttons)

    def _preview(self):
        self._collect()
        self.previewed.emit(self._cfg)

    def _collect(self):
        theme_map = {0: "dark", 1: "light", 2: "auto"}
        self._cfg.title                = self._title_edit.text().strip() or "BT Battery"
        self._cfg.refresh_interval     = self._refresh_spin.value()
        self._cfg.startup              = self._startup_check.isChecked()
        self._cfg.theme                = theme_map[self._theme_combo.currentIndex()]
        self._cfg.auto_theme_day_start = self._day_start_spin.value()
        self._cfg.auto_theme_day_end   = self._day_end_spin.value()
        self._cfg.opacity              = self._opacity_slider.value() / 100
        self._cfg.show_icon            = self._icon_check.isChecked()
        self._cfg.color_high           = self._color_high
        self._cfg.color_mid            = self._color_mid
        self._cfg.color_low            = self._color_low
        self._cfg.drag_lock            = self._drag_lock_check.isChecked()
        self._cfg.corner_snap          = self._snap_check.isChecked()
        self._cfg.snap_margin          = self._snap_margin_spin.value()
        self._cfg.alert_enabled        = self._alert_check.isChecked()
        self._cfg.alert_threshold      = self._threshold_spin.value()
        self._cfg.detect_new_device    = self._detect_check.isChecked()

    # ── 탭: 일반 ──────────────────────────────────────────────────────

    def _tab_general(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)

        self._title_edit = QLineEdit(self._cfg.title)
        self._title_edit.textChanged.connect(self._preview)
        form.addRow("위젯 제목 문구", self._title_edit)

        self._refresh_spin = QSpinBox()
        self._refresh_spin.setRange(1, 60)
        self._refresh_spin.setSuffix(" 분")
        self._refresh_spin.setValue(self._cfg.refresh_interval)
        self._refresh_spin.valueChanged.connect(self._preview)
        form.addRow("새로고침 주기", self._refresh_spin)

        self._startup_check = QCheckBox("시작 시 자동 실행")
        self._startup_check.setChecked(self._cfg.startup)
        self._startup_check.stateChanged.connect(self._preview)
        form.addRow("", self._startup_check)

        return w

    # ── 탭: 외관 ──────────────────────────────────────────────────────

    def _tab_appearance(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        # 테마
        theme_group = QGroupBox("테마")
        theme_form  = QFormLayout(theme_group)

        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["다크", "라이트", "시간대 자동"])
        theme_map = {"dark": 0, "light": 1, "auto": 2}
        self._theme_combo.setCurrentIndex(theme_map.get(self._cfg.theme, 0))
        self._theme_combo.currentIndexChanged.connect(self._preview)
        theme_form.addRow("테마", self._theme_combo)

        self._day_start_spin = QSpinBox()
        self._day_start_spin.setRange(0, 23)
        self._day_start_spin.setSuffix(" 시")
        self._day_start_spin.setValue(self._cfg.auto_theme_day_start)
        self._day_start_spin.valueChanged.connect(self._preview)

        self._day_end_spin = QSpinBox()
        self._day_end_spin.setRange(0, 23)
        self._day_end_spin.setSuffix(" 시")
        self._day_end_spin.setValue(self._cfg.auto_theme_day_end)
        self._day_end_spin.valueChanged.connect(self._preview)

        time_row = QHBoxLayout()
        time_row.addWidget(QLabel("라이트 모드 시간"))
        time_row.addWidget(self._day_start_spin)
        time_row.addWidget(QLabel("~"))
        time_row.addWidget(self._day_end_spin)
        theme_form.addRow(time_row)
        layout.addWidget(theme_group)

        # 투명도
        opac_group = QGroupBox("투명도")
        opac_layout = QHBoxLayout(opac_group)
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(10, 100)
        self._opacity_slider.setValue(int(self._cfg.opacity * 100))
        self._opacity_label = QLabel(f"{int(self._cfg.opacity * 100)}%")
        self._opacity_slider.valueChanged.connect(
            lambda v: (self._opacity_label.setText(f"{v}%"), self._preview())
        )
        opac_layout.addWidget(self._opacity_slider)
        opac_layout.addWidget(self._opacity_label)
        layout.addWidget(opac_group)

        # 배터리 바 색상
        color_group = QGroupBox("배터리 바 색상")
        color_form  = QFormLayout(color_group)
        self._btn_high = _color_button(self._color_high)
        self._btn_mid  = _color_button(self._color_mid)
        self._btn_low  = _color_button(self._color_low)
        self._btn_high.clicked.connect(lambda: self._pick_color("high"))
        self._btn_mid.clicked.connect(lambda: self._pick_color("mid"))
        self._btn_low.clicked.connect(lambda: self._pick_color("low"))
        color_form.addRow("높음 (50% 초과)", self._btn_high)
        color_form.addRow("중간 (20~50%)",   self._btn_mid)
        color_form.addRow("낮음 (20% 이하)", self._btn_low)
        layout.addWidget(color_group)

        # 장치별 아이콘
        icon_group = QGroupBox("장치별 아이콘")
        icon_layout = QVBoxLayout(icon_group)

        self._icon_check = QCheckBox("아이콘 표시")
        self._icon_check.setChecked(self._cfg.show_icon)
        self._icon_check.stateChanged.connect(self._preview)
        icon_layout.addWidget(self._icon_check)

        if self._devices:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setMaximumHeight(160)
            scroll.setStyleSheet("QScrollArea { border: none; }")

            inner = QWidget()
            inner_layout = QVBoxLayout(inner)
            inner_layout.setSpacing(4)

            for dev in self._devices:
                current_icon = self._cfg.device_icons.get(dev.name, "🔵")
                picker = IconPickerWidget(dev.name, current_icon)
                picker.icon_changed.connect(self._on_icon_changed)
                inner_layout.addWidget(picker)

            inner_layout.addStretch()
            scroll.setWidget(inner)
            icon_layout.addWidget(scroll)
        else:
            icon_layout.addWidget(QLabel("  연결된 장치 없음"))

        layout.addWidget(icon_group)
        layout.addStretch()
        return w

    # ── 탭: 동작 ──────────────────────────────────────────────────────

    def _tab_behavior(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        move_group = QGroupBox("위젯 이동")
        move_layout = QVBoxLayout(move_group)

        self._drag_lock_check = QCheckBox("드래그 잠금 (실수 방지)")
        self._drag_lock_check.setChecked(self._cfg.drag_lock)
        self._drag_lock_check.stateChanged.connect(self._preview)
        move_layout.addWidget(self._drag_lock_check)

        self._snap_check = QCheckBox("화면 모서리 스냅")
        self._snap_check.setChecked(self._cfg.corner_snap)
        self._snap_check.stateChanged.connect(self._preview)
        move_layout.addWidget(self._snap_check)

        snap_row = QHBoxLayout()
        snap_row.addSpacing(24)
        snap_row.addWidget(QLabel("스냅 감지 거리"))
        self._snap_margin_spin = QSpinBox()
        self._snap_margin_spin.setRange(5, 100)
        self._snap_margin_spin.setSuffix(" px")
        self._snap_margin_spin.setValue(self._cfg.snap_margin)
        self._snap_margin_spin.valueChanged.connect(self._preview)
        snap_row.addWidget(self._snap_margin_spin)
        snap_row.addStretch()
        move_layout.addLayout(snap_row)
        layout.addWidget(move_group)

        alert_group = QGroupBox("배터리 낮음 알림")
        alert_layout = QVBoxLayout(alert_group)

        self._alert_check = QCheckBox("알림 활성화")
        self._alert_check.setChecked(self._cfg.alert_enabled)
        self._alert_check.stateChanged.connect(self._preview)
        alert_layout.addWidget(self._alert_check)

        threshold_row = QHBoxLayout()
        threshold_row.addSpacing(24)
        threshold_row.addWidget(QLabel("임계값"))
        self._threshold_spin = QSpinBox()
        self._threshold_spin.setRange(5, 50)
        self._threshold_spin.setSuffix(" %")
        self._threshold_spin.setValue(self._cfg.alert_threshold)
        self._threshold_spin.valueChanged.connect(self._preview)
        threshold_row.addWidget(self._threshold_spin)
        threshold_row.addStretch()
        alert_layout.addLayout(threshold_row)
        layout.addWidget(alert_group)

        self._detect_check = QCheckBox("새 블루투스 장치 연결 시 즉시 표시")
        self._detect_check.setChecked(self._cfg.detect_new_device)
        self._detect_check.stateChanged.connect(self._preview)
        layout.addWidget(self._detect_check)

        layout.addStretch()
        return w

    # ── 아이콘 변경 콜백 ──────────────────────────────────────────────

    def _on_icon_changed(self, device_name: str, icon: str):
        self._cfg.device_icons[device_name] = icon
        self._preview()

    # ── 색상 선택 ─────────────────────────────────────────────────────

    def _pick_color(self, which: str):
        current = {"high": self._color_high, "mid": self._color_mid, "low": self._color_low}[which]
        color = QColorDialog.getColor(QColor(current), self, "색상 선택")
        if not color.isValid():
            return
        hex_c = color.name()
        if which == "high":
            self._color_high = hex_c
            self._btn_high.setStyleSheet(f"background:{hex_c}; border:1px solid #555; border-radius:4px;")
        elif which == "mid":
            self._color_mid = hex_c
            self._btn_mid.setStyleSheet(f"background:{hex_c}; border:1px solid #555; border-radius:4px;")
        else:
            self._color_low = hex_c
            self._btn_low.setStyleSheet(f"background:{hex_c}; border:1px solid #555; border-radius:4px;")
        self._preview()

    def _apply(self):
        self._collect()
        self.applied.emit(self._cfg)
        self.accept()

    def _cancel(self):
        self.previewed.emit(self._original)
        self.reject()