"""Apple-style design tokens and the Qt stylesheet built from them."""
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

FONT_STACK = '"Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI"'

STATE_COLORS = {"idle": "#8e8e93", "recording": "#007aff", "processing": "#ff9f0a"}

LIGHT = {
    "bg": "#f5f5f7",
    "sidebar": "#ebebf0",
    "card": "#ffffff",
    "card_border": "#e3e3e8",
    "separator": "#dcdce1",
    "text": "#1d1d1f",
    "secondary": "#6e6e73",
    "tertiary": "#aeaeb2",
    "hover": "rgba(0, 0, 0, 0.05)",
    "control": "#ffffff",
    "control_border": "#d2d2d7",
    "control_hover": "#f2f2f5",
    "control_pressed": "#e5e5ea",
    "accent": "#007aff",
    "accent_hover": "#0a6fe0",
    "accent_pressed": "#0062cc",
    "destructive": "#ff3b30",
    "destructive_hover": "#e6352b",
    "scroll": "rgba(0, 0, 0, 0.22)",
    "select": "#eaf3ff",
    "warn_bg": "#fff4e0",
    "warn_border": "#ffd9a0",
    "switch_off": "#d1d1d6",
}

DARK = {
    "bg": "#1c1c1e",
    "sidebar": "#242426",
    "card": "#2c2c2e",
    "card_border": "#38383a",
    "separator": "#3a3a3c",
    "text": "#f5f5f7",
    "secondary": "#98989d",
    "tertiary": "#636366",
    "hover": "rgba(255, 255, 255, 0.06)",
    "control": "#3a3a3c",
    "control_border": "#48484a",
    "control_hover": "#444446",
    "control_pressed": "#4e4e50",
    "accent": "#0a84ff",
    "accent_hover": "#2491ff",
    "accent_pressed": "#0070e0",
    "destructive": "#ff453a",
    "destructive_hover": "#ff5f55",
    "scroll": "rgba(255, 255, 255, 0.25)",
    "select": "#1f3552",
    "warn_bg": "#3a2d16",
    "warn_border": "#6b4a16",
    "switch_off": "#48484a",
}

FONT_SIZES = {
    "body": 14,
    "small": 13,
    "caption": 11,
    "sidebar_title": 17,
    "sidebar_item": 14,
    "page_title": 28,
    "status": 24,
    "entry": 16,
    "button": 14,
}


HISTORY_GAP = 10  # bottom margin between history cards
HISTORY_SIDE_GAP = 4  # right margin of a history card


def scaled_px(value: float, scale: float) -> int:
    """Pixel value under the UI scale; the single rounding rule used by the stylesheet."""
    return max(1, round(value * scale))


def history_gaps(scale: float) -> tuple[int, int]:
    """(bottom, right) card margins in px at `scale`, shared by the QSS and HistoryView."""
    return scaled_px(HISTORY_GAP, scale), scaled_px(HISTORY_SIDE_GAP, scale)


def is_dark(app: QApplication) -> bool:
    """True when the application's window color is dark."""
    return app.palette().color(QPalette.Window).lightness() < 128


def tokens(dark: bool) -> dict[str, str]:
    return dict(DARK if dark else LIGHT)


def stylesheet(dark: bool, scale: float) -> str:
    """The full window stylesheet; `scale` multiplies font sizes and key paddings."""
    c = tokens(dark)
    f = {k: round(v * scale, 1) for k, v in FONT_SIZES.items()}

    def px(value: float) -> str:
        return f"{scaled_px(value, scale)}px"

    dot = px(12)
    return f"""
QWidget {{
    font-family: {FONT_STACK};
    font-size: {f["body"]}px;
    color: {c["text"]};
}}
QMainWindow, #Content {{ background: {c["bg"]}; }}
QStackedWidget, #Page {{ background: transparent; }}

#Sidebar {{
    background: {c["sidebar"]};
    border-right: 1px solid {c["separator"]};
}}
#SidebarTitle {{
    font-size: {f["sidebar_title"]}px;
    font-weight: 700;
    padding: {px(4)} {px(12)} {px(14)} {px(12)};
}}
#SidebarList {{
    background: transparent;
    border: none;
    outline: 0;
    font-size: {f["sidebar_item"]}px;
}}
#SidebarList::item {{
    padding: {px(8)} {px(10)};
    margin: {px(1)} 0;
    border-radius: 8px;
    color: {c["text"]};
}}
#SidebarList::item:hover:!selected {{ background: {c["hover"]}; }}
#SidebarList::item:selected {{ background: {c["accent"]}; color: #ffffff; }}

#Banner {{
    background: {c["warn_bg"]};
    border: 1px solid {c["warn_border"]};
    border-radius: 12px;
}}
#Card {{
    background: {c["card"]};
    border: 1px solid {c["card_border"]};
    border-radius: 14px;
}}
#PageTitle {{ font-size: {f["page_title"]}px; font-weight: 700; }}
#StatusLabel {{ font-size: {f["status"]}px; font-weight: 600; }}
#Caption {{
    font-size: {f["caption"]}px;
    font-weight: 600;
    color: {c["secondary"]};
    letter-spacing: 0.6px;
}}
#Secondary, #HintLabel {{ font-size: {f["small"]}px; color: {c["secondary"]}; }}
#EntryText {{ font-size: {f["entry"]}px; }}
#EntryText[empty="true"] {{ color: {c["tertiary"]}; }}
#Placeholder {{ font-size: {f["entry"]}px; color: {c["secondary"]}; }}

#StateDot {{
    min-width: {dot}; max-width: {dot};
    min-height: {dot}; max-height: {dot};
    border-radius: {max(1, round(6 * scale))}px;
    background: {STATE_COLORS["idle"]};
}}
#DotIndent {{ min-width: {dot}; max-width: {dot}; background: transparent; }}
#StateDot[state="recording"] {{ background: {STATE_COLORS["recording"]}; }}
#StateDot[state="processing"] {{ background: {STATE_COLORS["processing"]}; }}

QPushButton {{
    font-size: {f["button"]}px;
    font-weight: 500;
    background: {c["control"]};
    border: 1px solid {c["control_border"]};
    border-radius: 8px;
    padding: {px(6)} {px(14)};
}}
QPushButton:hover {{ background: {c["control_hover"]}; }}
QPushButton:pressed {{ background: {c["control_pressed"]}; }}
QPushButton:disabled {{ color: {c["tertiary"]}; }}
QPushButton[variant="primary"] {{
    background: {c["accent"]};
    color: #ffffff;
    border: none;
    border-radius: 10px;
    font-weight: 600;
    padding: {px(10)} {px(22)};
}}
QPushButton[variant="primary"]:hover {{ background: {c["accent_hover"]}; }}
QPushButton[variant="primary"]:pressed {{ background: {c["accent_pressed"]}; }}
QPushButton[variant="primary"][active="true"] {{ background: {c["destructive"]}; }}
QPushButton[variant="primary"][active="true"]:hover {{ background: {c["destructive_hover"]}; }}
QPushButton[variant="destructive"] {{ color: {c["destructive"]}; }}

QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {c["control"]};
    border: 1px solid {c["control_border"]};
    border-radius: 8px;
    padding: {px(6)} {px(10)};
    selection-background-color: {c["accent"]};
    selection-color: #ffffff;
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus {{ border: 1px solid {c["accent"]}; }}
QComboBox::drop-down {{ border: none; width: {px(24)}; }}
QComboBox QAbstractItemView {{
    background: {c["card"]};
    border: 1px solid {c["separator"]};
    border-radius: 8px;
    padding: {px(4)};
    outline: 0;
    selection-background-color: {c["accent"]};
    selection-color: #ffffff;
}}

QCheckBox {{ spacing: {px(8)}; }}
QCheckBox::indicator {{
    width: {px(18)}; height: {px(18)};
    border-radius: 5px;
    border: 1px solid {c["control_border"]};
    background: {c["control"]};
}}
QCheckBox::indicator:checked {{
    background: {c["accent"]};
    border: 1px solid {c["accent"]};
}}

Switch {{
    qproperty-onColor: {c["accent"]};
    qproperty-offColor: {c["switch_off"]};
    qproperty-knobColor: #ffffff;
    qproperty-ringColor: {c["accent"]};
}}
#SectionCaption {{
    font-size: {f["caption"]}px;
    font-weight: 600;
    color: {c["secondary"]};
    letter-spacing: 0.6px;
    padding: 0 0 {px(6)} {px(4)};
}}
#RowTitle {{ font-size: {f["body"]}px; font-weight: 500; }}
#SliderValue {{ font-size: {f["small"]}px; color: {c["secondary"]}; }}
#Separator {{ background: {c["separator"]}; border: none; }}
#Footer {{ background: {c["bg"]}; border-top: 1px solid {c["separator"]}; }}
QLineEdit[capturing="true"] {{ border: 1px solid {c["accent"]}; color: {c["accent"]}; }}
#CommandTable {{ background: {c["card"]}; border: 1px solid {c["control_border"]}; border-radius: 8px; }}
#CommandTable::item {{ padding: 0 {px(8)}; border-bottom: 1px solid {c["separator"]}; }}
#CommandTable::item:selected {{ background: {c["select"]}; color: {c["text"]}; }}
#CommandTable QHeaderView {{
    background: transparent;
    border: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}}
#CommandTable QHeaderView::section {{ background: transparent; padding: {px(6)} {px(8)}; }}
#CommandTable QTableCornerButton::section {{ background: transparent; border: none; }}
ChevronCombo {{ qproperty-arrowColor: {c["secondary"]}; }}
#CommandTable QLineEdit {{ border-radius: 4px; padding: 0 {px(6)}; }}
QWidget:disabled {{ color: {c["tertiary"]}; }}

QSlider::groove:horizontal {{
    height: 4px;
    border-radius: 2px;
    background: {c["separator"]};
}}
QSlider::sub-page:horizontal {{ background: {c["accent"]}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    background: #ffffff;
    border: 1px solid {c["control_border"]};
    width: {px(18)};
    margin: -{px(8)} 0;
    border-radius: {max(1, round(9 * scale))}px;
}}

QListWidget, QTableWidget, QTreeWidget {{
    background: {c["card"]};
    border: 1px solid {c["card_border"]};
    border-radius: 12px;
    outline: 0;
}}
#HistoryList {{ background: transparent; border: none; }}
#HistoryList::item {{
    background: {c["card"]};
    border: 1px solid {c["card_border"]};
    border-radius: 12px;
    margin: 0 {px(HISTORY_SIDE_GAP)} {px(HISTORY_GAP)} 0;
}}
#HistoryList::item:selected {{ background: {c["select"]}; border: 1px solid {c["accent"]}; }}
#HistoryRowBody {{ background: transparent; }}
QHeaderView::section {{
    background: transparent;
    border: none;
    border-bottom: 1px solid {c["separator"]};
    color: {c["secondary"]};
    padding: {px(6)} {px(8)};
}}

QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{
    background: {c["scroll"]};
    border-radius: 3px;
    min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

QToolTip {{
    background: {c["card"]};
    color: {c["text"]};
    border: 1px solid {c["separator"]};
    border-radius: 6px;
    padding: 4px 8px;
}}
"""


