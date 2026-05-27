"""항상 위에 떠있는 블루투스 배터리 위젯."""
from __future__ import annotations

import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtGui import QColor, QPainter, QFont, QPixmap
from PyQt6.QtWidgets import QWidget, QApplication

from .battery import fetch_devices, Device
from .config import Config

class BatteryWidget(QWidget):
    def __init__(self, cfg: Config):
        super().__init__()
        self._cfg = cfg
        self._devices: list[Device] = []
        self._drag_pos: QPoint | None = None
        self._alerted: set[str] = set()  # 이미 알림 보낸 장치 이름

        self._setup_window()
        self._setup_timer()
        self._refresh()

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumWidth(180)
        self.move(self._cfg.pos_x, self._cfg.pos_y)
        self._apply_opacity()

    def _apply_opacity(self):
        self.setWindowOpacity(self._cfg.opacity)

    def _setup_timer(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(self._cfg.refresh_interval * 60 * 1000)

        # 새 장치 감지용 빠른 타이머 (30초)
        self._detect_timer = QTimer(self)
        self._detect_timer.timeout.connect(self._detect_new)
        if self._cfg.detect_new_device:
            self._detect_timer.start(30 * 1000)

    def apply_config(self, cfg: Config):
        """설정 창에서 OK 눌렀을 때 호출."""
        self._cfg = cfg
        self._apply_opacity()
        self._timer.setInterval(cfg.refresh_interval * 60 * 1000)
        if cfg.detect_new_device:
            self._detect_timer.start(30 * 1000)
        else:
            self._detect_timer.stop()
        self._refresh()

    def _current_theme(self) -> str:
        if self._cfg.theme == "auto":
            hour = datetime.datetime.now().hour
            if self._cfg.auto_theme_day_start <= hour < self._cfg.auto_theme_day_end:
                return "light"
            return "dark"
        return self._cfg.theme

    def _refresh(self):
        self._devices = fetch_devices()
        self._check_alerts()
        self._resize_to_content()
        self.update()

    def _detect_new(self):
        """현재 목록과 비교해서 새 장치 잡히면 즉시 갱신."""
        new = fetch_devices()
        current_names = {d.name for d in self._devices}
        new_names = {d.name for d in new}
        if new_names != current_names:
            self._devices = new
            self._resize_to_content()
            self.update()

    def _check_alerts(self):
        if not self._cfg.alert_enabled:
            return
        from PyQt6.QtWidgets import QSystemTrayIcon
        for dev in self._devices:
            if dev.battery <= self._cfg.alert_threshold and dev.name not in self._alerted:
                self._alerted.add(dev.name)
                # 부모(tray)한테 알림 요청 - tray에서 showMessage 호출
                if hasattr(self, '_tray'):
                    self._tray.show_alert(dev.name, dev.battery)
            elif dev.battery > self._cfg.alert_threshold:
                self._alerted.discard(dev.name)

    def force_refresh(self):
        self._refresh()

    def _resize_to_content(self):
        row_h   = 32
        padding = 12
        # 제목 있으면 한 줄 추가
        title_h = 28 if self._cfg.title else 0
        n = max(len(self._devices), 1)
        self.setFixedHeight(n * row_h + padding * 2 + title_h)

    def paintEvent(self, _):
        theme = self._current_theme()
        is_dark = (theme == "dark")

        bg_color   = QColor(30, 30, 30, int(210 * self._cfg.opacity + 0.5)) if is_dark else QColor(240, 240, 240, int(220 * self._cfg.opacity + 0.5))
        text_color = QColor(230, 230, 230) if is_dark else QColor(30, 30, 30)
        sub_color  = QColor(160, 160, 160) if is_dark else QColor(100, 100, 100)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 배경
        painter.setBrush(bg_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 12, 12)

        padding = 12
        y_offset = padding

        # 제목
        if self._cfg.title:
            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(sub_color)
            painter.drawText(padding, y_offset, self.width() - padding * 2, 20,
                             Qt.AlignmentFlag.AlignVCenter, self._cfg.title)
            y_offset += 24

        if not self._devices:
            painter.setPen(sub_color)
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "장치 없음")
            return

        row_h  = 32
        bar_w  = 34
        bar_h  = 8

        name_font = QFont("Segoe UI", 10)
        pct_font  = QFont("Segoe UI", 8, QFont.Weight.Bold)

        for dev in self._devices:
            color = QColor(self._battery_color(dev.battery))

            # 아이콘
            x_start = padding
            if self._cfg.show_icon:
                icon_str = self._cfg.device_icons.get(dev.name, "🔵")
                if icon_str and Path(icon_str).exists():
                    px = QPixmap(icon_str).scaled(
                        16, 16,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    painter.drawPixmap(x_start, y_offset + (row_h - 16) // 2, px)
                elif icon_str:
                    painter.setFont(QFont("Segoe UI Emoji", 11))
                    painter.setPen(text_color)
                    painter.drawText(x_start, y_offset, 20, row_h,
                                    Qt.AlignmentFlag.AlignVCenter, icon_str)
                x_start += 22

            # 장치 이름 (말줄임)
            name_area_w = self.width() - x_start - bar_w - padding * 2
            painter.setFont(name_font)
            painter.setPen(text_color)
            metrics = painter.fontMetrics()
            display_name = metrics.elidedText(dev.name, Qt.TextElideMode.ElideRight, name_area_w)
            painter.drawText(x_start, y_offset, name_area_w, row_h,
                             Qt.AlignmentFlag.AlignVCenter, display_name)

            # 배터리 바
            bx = self.width() - padding - bar_w
            by = y_offset + (row_h - bar_h) // 2

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(80, 80, 80) if is_dark else QColor(200, 200, 200))
            painter.drawRoundedRect(bx, by, bar_w, bar_h, 3, 3)

            fill_w = max(4, int(bar_w * dev.battery / 100))
            painter.setBrush(color)
            painter.drawRoundedRect(bx, by, fill_w, bar_h, 3, 3)

            # 퍼센트
            painter.setFont(pct_font)
            painter.setPen(text_color)
            painter.drawText(bx, by - 13, bar_w, 13,
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             f"{dev.battery}%")

            y_offset += row_h

    def _battery_color(self, pct: int) -> str:
        if pct > 50:
            return self._cfg.color_high
        if pct > 20:
            return self._cfg.color_mid
        return self._cfg.color_low

    # ── 드래그 / 스냅 ─────────────────────────────────────────────────

    def mousePressEvent(self, e):
        if self._cfg.drag_lock:
            return
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._cfg.drag_lock or not self._drag_pos:
            return
        if e.buttons() == Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, _):
        if self._drag_pos and self._cfg.corner_snap:
            self._snap_to_corner()
        self._drag_pos = None
        # 위치 저장
        self._cfg.pos_x = self.x()
        self._cfg.pos_y = self.y()

    def _snap_to_corner(self):
        screen = QApplication.primaryScreen().availableGeometry()
        m = self._cfg.snap_margin
        x, y = self.x(), self.y()
        w, h = self.width(), self.height()

        snap_x = x
        snap_y = y

        if x < m:
            snap_x = 0
        elif x + w > screen.width() - m:
            snap_x = screen.width() - w

        if y < m:
            snap_y = 0
        elif y + h > screen.height() - m:
            snap_y = screen.height() - h

        self.move(snap_x, snap_y)