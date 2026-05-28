from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass, asdict, field


def _config_path() -> Path:
    base = Path.home() / "AppData" / "Roaming" / "BTBatteryWidget"
    base.mkdir(parents=True, exist_ok=True)
    return base / "config.json"


@dataclass
class Config:
    # [일반]
    title: str = "BT Battery"
    app_name: str = "BTBatteryWidget"
    refresh_interval: int = 5
    startup: bool = False

    # [외관]
    theme: str = "dark"
    auto_theme_day_start: int = 8
    auto_theme_day_end: int = 20
    opacity: float = 0.85
    show_icon: bool = True
    show_percentage: bool = True
    color_high: str = "#50C878"
    color_mid: str  = "#FFB400"
    color_low: str  = "#DC3232"
    bg_color_dark: str  = "#1E1E1E"
    bg_color_light: str = "#F0F0F0"

    # [장치별 아이콘] - {"MX Master 4": "🖱", ...}
    device_icons: dict = field(default_factory=dict)

    # [장치 표시 순서] - ["MX Master 4", "Xbox Controller", ...]
    device_order: list = field(default_factory=list)

    # [동작]
    drag_lock: bool = False
    corner_snap: bool = True
    snap_margin: int = 20
    alert_enabled: bool = True
    alert_threshold: int = 20
    detect_new_device: bool = True

    # [위치]
    pos_x: int = 100
    pos_y: int = 100


def load() -> Config:
    path = _config_path()
    if not path.exists():
        return Config()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        default = asdict(Config())
        default.update({k: v for k, v in data.items() if k in default})
        if not isinstance(default.get("device_icons"), dict):
            default["device_icons"] = {}
        if not isinstance(default.get("device_order"), list):
            default["device_order"] = []
        return Config(**default)
    except Exception:
        return Config()


def save(cfg: Config):
    path = _config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(cfg), f, indent=2, ensure_ascii=False)