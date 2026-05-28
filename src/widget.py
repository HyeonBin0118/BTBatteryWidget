"""항상 위에 떠있는 블루투스 배터리 위젯."""
from __future__ import annotations

import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QPoint, QTimer, QSize
from PyQt6.QtGui import QColor, QPainter, QFont, QPixmap, QFontMetrics, QCursor
from PyQt6.QtWidgets import QWidget, QApplication

from .battery import fetch_devices, Device
from .config import Config

_EDGE = 6  # 가장자리 감지 범위 (px)


class BatteryWidget(QWidget):
    def __init__(self, cfg: Config):
        super().__init__()
        self._cfg = cfg
        self._devices: list[Device] = []
        self._drag_pos: QPoint | None = None
        self._alerted: set[str] = set()

        # 리사이즈 상태
        self._resize_edge: str = ""
        self._resize_start_pos: QPoint | None = None
        self._resize_start_size: QSize | None = None
        self._resize_start_wpos: QPoint | None = None

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
        self.setMinimumSize(140, 60)
        self.resize(cfg_w := getattr(self._cfg, 'widget_w', 200),
                    cfg_h := getattr(self._cfg, 'widget_h', 80))
        self.move(self._cfg.pos_x, self._cfg.pos_y)
        self._apply_opacity()

    def _apply_opacity(self):
        self.setWindowOpacity(self._cfg.opacity)

    def _setup_timer(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(self._cfg.refresh_interval * 60 * 1000)

        self._detect_timer = QTimer(self)
        self._detect_timer.timeout.connect(self._detect_new)
        if self._cfg.detect_new_device:
            self._detect_timer.start(30 * 1000)

    def apply_config(self, cfg: Config):
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
        devices = fetch_devices()
        # device_order 기준으로 정렬, 순서에 없는 새 장치는 뒤에 추가
        order = self._cfg.device_order
        if order:
            ordered = [d for name in order for d in devices if d.name == name]
            ordered += [d for d in devices if d.name not in order]
            self._devices = ordered
        else:
            self._devices = devices
        self._check_alerts()
        self._auto_resize()
        self.update()

    def _detect_new(self):
        new = fetch_devices()
        if {d.name for d in new} != {d.name for d in self._devices}:
            self._devices = new
            self._auto_resize()
            self.update()

    def _check_alerts(self):
        if not self._cfg.alert_enabled:
            return
        for dev in self._devices:
            if dev.battery <= self._cfg.alert_threshold and dev.name not in self._alerted:
                self._alerted.add(dev.name)
                if hasattr(self, '_tray'):
                    self._tray.show_alert(dev.name, dev.battery)
            elif dev.battery > self._cfg.alert_threshold:
                self._alerted.discard(dev.name)

    def force_refresh(self):
        self._refresh()

    def _auto_resize(self):
        """장치 수가 바뀌었을 때만 높이 자동 조정. 너비는 유지."""
        row_h  = 32
        pad    = 12
        title_h = 24 if self._cfg.title else 0
        n = max(len(self._devices), 1)
        new_h = n * row_h + pad * 2 + title_h
        self.resize(self.width(), new_h)

    # ── 가장자리 판별 ─────────────────────────────────────────────────

    def _edge_at(self, pos: QPoint) -> str:
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        m = _EDGE
        r = x >= w - m
        b = y >= h - m
        l = x <= m
        t = y <= m
        if r and b: return "rb"
        if l and b: return "lb"
        if r and t: return "rt"
        if l and t: return "lt"
        if r: return "r"
        if b: return "b"
        if l: return "l"
        if t: return "t"
        return ""

    def _cursor_for_edge(self, edge: str) -> Qt.CursorShape:
        map_ = {
            "r":  Qt.CursorShape.SizeHorCursor,
            "l":  Qt.CursorShape.SizeHorCursor,
            "b":  Qt.CursorShape.SizeVerCursor,
            "t":  Qt.CursorShape.SizeVerCursor,
            "rb": Qt.CursorShape.SizeFDiagCursor,
            "lt": Qt.CursorShape.SizeFDiagCursor,
            "lb": Qt.CursorShape.SizeBDiagCursor,
            "rt": Qt.CursorShape.SizeBDiagCursor,
        }
        return map_.get(edge, Qt.CursorShape.ArrowCursor)

    # ── 마우스 이벤트 ─────────────────────────────────────────────────

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        if self._cfg.drag_lock:
            return
        edge = self._edge_at(e.position().toPoint())
        if edge:
            self._resize_edge      = edge
            self._resize_start_pos  = e.globalPosition().toPoint()
            self._resize_start_size = self.size()
            self._resize_start_wpos = self.pos()
        else:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        pos = e.position().toPoint()

        if self._resize_edge and self._resize_start_pos:
            # 리사이즈 처리
            delta = e.globalPosition().toPoint() - self._resize_start_pos
            sw = self._resize_start_size.width()
            sh = self._resize_start_size.height()
            sx = self._resize_start_wpos.x()
            sy = self._resize_start_wpos.y()
            min_w, min_h = self.minimumWidth(), self.minimumHeight()

            new_x, new_y, new_w, new_h = sx, sy, sw, sh

            if "r" in self._resize_edge:
                new_w = max(min_w, sw + delta.x())
            if "b" in self._resize_edge:
                new_h = max(min_h, sh + delta.y())
            if "l" in self._resize_edge:
                new_w = max(min_w, sw - delta.x())
                new_x = sx + (sw - new_w)
            if "t" in self._resize_edge:
                new_h = max(min_h, sh - delta.y())
                new_y = sy + (sh - new_h)

            self.setGeometry(new_x, new_y, new_w, new_h)
        elif self._drag_pos and not self._cfg.drag_lock:
            # 드래그 이동
            self.move(e.globalPosition().toPoint() - self._drag_pos)
        else:
            # 커서 모양 업데이트
            edge = self._edge_at(pos)
            if not self._cfg.drag_lock:
                self.setCursor(self._cursor_for_edge(edge))
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, _):
        if self._resize_edge:
            self._resize_edge = ""
            self._resize_start_pos = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
        elif self._drag_pos:
            if self._cfg.corner_snap:
                self._snap_to_corner()
        self._drag_pos = None
        self._cfg.pos_x = self.x()
        self._cfg.pos_y = self.y()

    def _snap_to_corner(self):
        screen = QApplication.primaryScreen().availableGeometry()
        m = self._cfg.snap_margin
        x, y = self.x(), self.y()
        w, h = self.width(), self.height()
        snap_x = 0 if x < m else (screen.width() - w if x + w > screen.width() - m else x)
        snap_y = 0 if y < m else (screen.height() - h if y + h > screen.height() - m else y)
        self.move(snap_x, snap_y)

    # ── 그리기 ────────────────────────────────────────────────────────

    def paintEvent(self, _):
        theme  = self._current_theme()
        is_dark = (theme == "dark")

        raw_bg   = QColor(self._cfg.bg_color_dark) if is_dark else QColor(self._cfg.bg_color_light)
        bg_color = QColor(raw_bg.red(), raw_bg.green(), raw_bg.blue(), 210)
        text_color = QColor(230, 230, 230) if is_dark else QColor(30, 30, 30)
        sub_color  = QColor(160, 160, 160) if is_dark else QColor(100, 100, 100)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setBrush(bg_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 12, 12)

        padding = 12
        y_offset = padding

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

        row_h = 32
        bar_w = 34
        bar_h = 8
        name_font = QFont("Segoe UI", 10)
        pct_font  = QFont("Segoe UI", 8, QFont.Weight.Bold)

        for dev in self._devices:
            color = QColor(self._battery_color(dev.battery))

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

            name_area_w = self.width() - x_start - bar_w - padding * 2
            painter.setFont(name_font)
            painter.setPen(text_color)
            metrics = painter.fontMetrics()
            display_name = metrics.elidedText(dev.name, Qt.TextElideMode.ElideRight, name_area_w)
            painter.drawText(x_start, y_offset, name_area_w, row_h,
                             Qt.AlignmentFlag.AlignVCenter, display_name)

            bx = self.width() - padding - bar_w
            by = y_offset + (row_h - bar_h) // 2

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(80, 80, 80) if is_dark else QColor(200, 200, 200))
            painter.drawRoundedRect(bx, by, bar_w, bar_h, 3, 3)

            fill_w = max(4, int(bar_w * dev.battery / 100))
            painter.setBrush(color)
            painter.drawRoundedRect(bx, by, fill_w, bar_h, 3, 3)

            if self._cfg.show_percentage:
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