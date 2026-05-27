"""시스템 트레이 아이콘 및 메뉴."""
from __future__ import annotations

import sys
import winreg
from pathlib import Path

from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PyQt6.QtCore import Qt, pyqtSignal

from .widget import BatteryWidget
from .config import Config, save
from .settings import SettingsDialog


def _make_icon() -> QIcon:
    from PyQt6.QtGui import QPen, QLinearGradient
    from PyQt6.QtCore import QRectF

    size = 64
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # 배경 그라디언트
    grad = QLinearGradient(0, 0, 0, size)
    grad.setColorAt(0, QColor(50, 130, 255))
    grad.setColorAt(1, QColor(20, 80, 200))
    p.setBrush(grad)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(2, 2, size - 4, size - 4, 14, 14)

    # 배터리 몸통
    bx, by, bw, bh = 10, 22, 36, 20
    pen = QPen(QColor(255, 255, 255))
    pen.setWidth(3)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(bx, by, bw, bh, 4, 4)

    # 배터리 + 극
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 255, 255))
    p.drawRoundedRect(bx + bw + 2, by + 6, 4, bh - 12, 2, 2)

    # 배터리 충전 표시 (75% 정도)
    fill_w = int((bw - 6) * 0.75)
    p.setBrush(QColor(100, 220, 130))
    p.drawRoundedRect(bx + 3, by + 3, fill_w, bh - 6, 3, 3)

    # 블루투스 심볼 (우측 하단 작게)
    pen2 = QPen(QColor(255, 255, 255))
    pen2.setWidth(2)
    pen2.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen2)
    cx, t, b = 52, 36, 58
    mid = (t + b) // 2
    u   = t + (b - t) // 4
    lo  = b - (b - t) // 4
    r   = cx + 6
    p.drawLine(cx, t, cx, b)
    p.drawLine(cx, t, r, u)
    p.drawLine(r, u, cx, mid)
    p.drawLine(cx, mid, r, lo)
    p.drawLine(r, lo, cx, b)

    p.end()
    return QIcon(px)


def _exe_path() -> str:
    if getattr(sys, 'frozen', False):
        return str(Path(sys.executable).resolve())
    return str(Path(sys.argv[0]).resolve())


def _set_startup(app_name: str, enabled: bool):
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                         r"Software\Microsoft\Windows\CurrentVersion\Run",
                         0, winreg.KEY_SET_VALUE)
    if enabled:
        winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, _exe_path())
    else:
        try:
            winreg.DeleteValue(key, app_name)
        except FileNotFoundError:
            pass
    winreg.CloseKey(key)


class TrayIcon(QSystemTrayIcon):
    def __init__(self, widget: BatteryWidget, cfg: Config):
        super().__init__(_make_icon())
        self._widget = widget
        self._cfg = cfg
        self._build_menu()
        self.setToolTip(cfg.app_name)
        self.activated.connect(self._on_activated)

    def _build_menu(self):
        menu = QMenu()

        self._toggle_action = menu.addAction("위젯 숨기기")
        self._toggle_action.triggered.connect(self._toggle_widget)

        menu.addAction("지금 새로고침").triggered.connect(self._widget.force_refresh)

        menu.addSeparator()

        menu.addAction("설정").triggered.connect(self._open_settings)

        menu.addSeparator()

        menu.addAction("종료").triggered.connect(self._quit)

        self.setContextMenu(menu)

    def show_alert(self, name: str, battery: int):
        self.showMessage(
            "배터리 부족",
            f"{name} 배터리가 {battery}% 입니다.",
            QSystemTrayIcon.MessageIcon.Warning,
            5000,
        )

    def _toggle_widget(self):
        if self._widget.isVisible():
            self._widget.hide()
            self._toggle_action.setText("위젯 보이기")
        else:
            self._widget.show()
            self._toggle_action.setText("위젯 숨기기")

    def _open_settings(self):
        dlg = SettingsDialog(self._cfg, self._widget._devices)
        dlg.previewed.connect(self._widget.apply_config)
        dlg.applied.connect(self._on_settings_applied)
        dlg.exec()


    def _on_settings_applied(self, cfg: Config):
        self._cfg = cfg
        _set_startup(cfg.app_name, cfg.startup)
        self._widget.apply_config(cfg)
        save(cfg)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_widget()

    def _quit(self):
        # 종료 전 위치 저장
        self._cfg.pos_x = self._widget.x()
        self._cfg.pos_y = self._widget.y()
        save(self._cfg)
        QApplication.quit()