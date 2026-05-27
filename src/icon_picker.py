"""장치별 아이콘 선택 위젯."""
from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox
from PyQt6.QtCore import pyqtSignal

ICON_OPTIONS = ["🔵", "🖱", "🎧", "⌨️", "🎮", "🔊", "📱", "⌚", "🖥"]


class IconPickerWidget(QWidget):
    icon_changed = pyqtSignal(str, str)  # (device_name, icon)

    def __init__(self, device_name: str, current_icon: str, parent=None):
        super().__init__(parent)
        self._device_name = device_name

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel(device_name)
        label.setMinimumWidth(160)
        layout.addWidget(label)

        self._combo = QComboBox()
        for icon in ICON_OPTIONS:
            self._combo.addItem(icon)

        idx = ICON_OPTIONS.index(current_icon) if current_icon in ICON_OPTIONS else 0
        self._combo.setCurrentIndex(idx)
        self._combo.currentTextChanged.connect(
            lambda icon: self.icon_changed.emit(self._device_name, icon)
        )
        layout.addWidget(self._combo)
        layout.addStretch()