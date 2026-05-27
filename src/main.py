"""BTBatteryWidget 진입점."""
import sys
from PyQt6.QtWidgets import QApplication
from .widget import BatteryWidget
from .tray import TrayIcon
from .config import load


def main():
    QApplication.setQuitOnLastWindowClosed(False)
    app = QApplication(sys.argv)

    cfg = load()
    app.setApplicationName(cfg.app_name)

    widget = BatteryWidget(cfg)
    widget.show()

    tray = TrayIcon(widget, cfg)
    tray.show()

    # 위젯 알림 시그널 연결 (widget → tray)
    # alert_requested는 widget에 따로 정의 안 했으니 tray에서 직접 연결
    # 대신 widget._check_alerts에서 tray.show_alert 직접 호출하도록 연결
    widget._tray = tray  # 참조 주입

    sys.exit(app.exec())


if __name__ == "__main__":
    main()