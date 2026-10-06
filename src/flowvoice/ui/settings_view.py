"""Settings tab: grouped rounded cards (Dictation, Hands-free, Interface, Phrases) and Save."""
from typing import Callable

from PySide6.QtCore import Property, QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from flowvoice.cleanup import DEFAULT_BACKTRACK_PHRASES, DEFAULT_FILLER_PHRASES
from flowvoice.commands import DEFAULT_COMMANDS
from flowvoice.config import UI_SCALE_MAX, UI_SCALE_MIN, Config
from flowvoice.settings_logic import escape_text, parse_phrases, rows_to_commands
from flowvoice.ui.hotkey_edit import HotkeyEdit
from flowvoice.ui.switch import Switch

MODELS = ["tiny.en", "base.en", "small.en", "medium.en"]
SILENCE_STEPS = 2  # slider units per second (0.5 s steps)
SILENCE_RANGE = (1, 10)
SCALE_STEPS = 20  # slider units per 1.0 of scale (0.05 steps)
RESTART_NOTE = "Hotkey, model, microphone and start-with-Windows changes restart Flow Voice."
SAVED_MS = 1400

PAGE_MARGINS = (36, 30, 36, 20)
CARD_MARGINS = (18, 4, 18, 4)
ROW_MARGINS = (0, 12, 0, 12)
CONTROL_WIDTH = 230
SLIDER_WIDTH = 190
VALUE_WIDTH = 48
TABLE_HEIGHT = 250
EDITOR_HEIGHT = 120


def _label(text: str, name: str, wrap: bool = False) -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    label.setWordWrap(wrap)
    return label


class ChevronCombo(QComboBox):
    """QComboBox that paints its own down chevron (the QSS hides the native arrow)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._arrow = QColor("#6e6e73")

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        unit = self.height() / 34
        x, y = self.width() - 18 * unit, self.height() / 2
        p.setPen(QPen(self._arrow, max(1.4, 1.6 * unit), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPolyline([QPointF(x - 4.5 * unit, y - 2.2 * unit), QPointF(x, y + 2.3 * unit),
                        QPointF(x + 4.5 * unit, y - 2.2 * unit)])
        p.end()

    def _get_arrow(self) -> QColor:
        return self._arrow

    def _put_arrow(self, c: QColor) -> None:
        self._arrow = QColor(c)
        self.update()

    arrowColor = Property(QColor, _get_arrow, _put_arrow)


def _separator() -> QFrame:
    line = QFrame()
    line.setObjectName("Separator")
    line.setFixedHeight(1)
    return line


class SettingsView(QWidget):
    """Builds a Config from the form and hands it to `on_save`; never writes files itself."""

    def __init__(self, config: Config, mics: list[tuple[str, int | None]],
                 on_save: Callable[[Config], None], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._mics = list(mics)
        self._on_save = on_save
        self._base = config
        self._layouts: list[tuple[QLayout, tuple[int, int, int, int], int]] = []
        self._widths: list[tuple[QWidget, int]] = []
        self._heights: list[tuple[QWidget, int]] = []
        self._switches: list[Switch] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.viewport().setObjectName("Page")
        body = QWidget()
        body.setObjectName("Page")
        page = QVBoxLayout(body)
        self._track(page, PAGE_MARGINS, 0)
        page.addWidget(_label("Settings", "PageTitle"))
        self._gaps: list[QWidget] = []

        self._build_dictation(page)
        self._build_hands_free(page)
        self._build_interface(page)
        self._build_phrases(page)
        page.addStretch(1)
        self.scroll.setWidget(body)
        outer.addWidget(self.scroll, 1)
        outer.addWidget(self._build_footer())

        self._saved_timer = QTimer(self)
        self._saved_timer.setSingleShot(True)
        self._saved_timer.setInterval(SAVED_MS)
        self._saved_timer.timeout.connect(lambda: self.save_button.setText("Save"))

        self.load(config)
        self.set_scale(1.0)

    # ----- building -----

    def _track(self, layout: QLayout, margins: tuple[int, int, int, int], spacing: int) -> None:
        self._layouts.append((layout, margins, spacing))

    def _section(self, page: QVBoxLayout, title: str) -> QVBoxLayout:
        gap = QWidget()
        self._gaps.append(gap)
        page.addWidget(gap)
        page.addWidget(_label(title.upper(), "SectionCaption"))
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        self._track(layout, CARD_MARGINS, 0)
        page.addWidget(card)
        return layout

    def _row(self, card: QVBoxLayout, title: str, helper: str, control: QWidget | QLayout,
             first: bool = False) -> None:
        if not first:
            card.addWidget(_separator())
        row = QHBoxLayout()
        self._track(row, ROW_MARGINS, 16)
        text = QVBoxLayout()
        self._track(text, (0, 0, 0, 0), 2)
        text.addWidget(_label(title, "RowTitle"))
        if helper:
            text.addWidget(_label(helper, "Secondary", wrap=True))
        row.addLayout(text, 1)
        if isinstance(control, QLayout):
            row.addLayout(control)
        else:
            row.addWidget(control, 0, Qt.AlignVCenter)
        card.addLayout(row)

    def _switch(self) -> Switch:
        switch = Switch()
        self._switches.append(switch)
        return switch

    def _combo(self) -> QComboBox:
        combo = ChevronCombo()
        combo.setCursor(Qt.PointingHandCursor)
        self._widths.append((combo, CONTROL_WIDTH))
        return combo

    def _slider(self, low: int, high: int, fmt: Callable[[int], str]) -> tuple[QSlider, QHBoxLayout]:
        slider = QSlider(Qt.Horizontal)
        slider.setRange(low, high)
        slider.setCursor(Qt.PointingHandCursor)
        self._widths.append((slider, SLIDER_WIDTH))
        value = _label("", "SliderValue")
        value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._widths.append((value, VALUE_WIDTH))
        slider.valueChanged.connect(lambda v: value.setText(fmt(v)))
        box = QHBoxLayout()
        self._track(box, (0, 0, 0, 0), 10)
        box.addWidget(slider, 0, Qt.AlignVCenter)
        box.addWidget(value, 0, Qt.AlignVCenter)
        return slider, box

    def _build_dictation(self, page: QVBoxLayout) -> None:
        card = self._section(page, "Dictation")
        self.ptt_edit = HotkeyEdit()
        self.tts_edit = HotkeyEdit()
        for edit in (self.ptt_edit, self.tts_edit):
            self._widths.append((edit, CONTROL_WIDTH))
        self.model_combo = self._combo()
        self.mic_combo = self._combo()
        self.history_switch = self._switch()
        self._row(card, "Push-to-talk key", "Hold it to dictate. Click the field, then press new keys.",
                  self.ptt_edit, first=True)
        self._row(card, "Read-aloud key", "Reads the selected text out loud.", self.tts_edit)
        self._row(card, "Speech model", "Larger models are more accurate but slower.",
                  self.model_combo)
        self._row(card, "Microphone", "The input Flow Voice listens to.", self.mic_combo)
        self._row(card, "Save history", "Keep a private list of your dictations on this PC.",
                  self.history_switch)

    def _build_hands_free(self, page: QVBoxLayout) -> None:
        card = self._section(page, "Hands-free")
        self.hands_free_switch = self._switch()
        self.silence_slider, silence_box = self._slider(
            SILENCE_RANGE[0] * SILENCE_STEPS, SILENCE_RANGE[1] * SILENCE_STEPS,
            lambda v: f"{v / SILENCE_STEPS:g} s")
        self._row(card, "Double-tap to go hands-free",
                  "Double-tap the push-to-talk key to dictate without holding it.",
                  self.hands_free_switch, first=True)
        self._row(card, "Stop after silence", "Ends a hands-free dictation after this much quiet.",
                  silence_box)

    def _build_interface(self, page: QVBoxLayout) -> None:
        card = self._section(page, "Interface")
        self.pill_switch = self._switch()
        self.autostart_switch = self._switch()
        self.scale_slider, scale_box = self._slider(
            round(UI_SCALE_MIN * SCALE_STEPS), round(UI_SCALE_MAX * SCALE_STEPS),
            lambda v: f"{round(v * 100 / SCALE_STEPS)}%")
        self._row(card, "Always show the pill", "Keep the small pill on screen while idle.",
                  self.pill_switch, first=True)
        self._row(card, "Interface size", "Scales the text and controls of this window and the pill.",
                  scale_box)
        self._row(card, "Start with Windows", "Launch Flow Voice when you sign in.",
                  self.autostart_switch)

    def _build_phrases(self, page: QVBoxLayout) -> None:
        card = self._section(page, "Phrases")
        self.commands_switch = self._switch()
        self._row(card, "Spoken commands",
                  'Say "comma" or "new line" to type punctuation and line breaks.',
                  self.commands_switch, first=True)

        card.addWidget(_separator())
        block = QVBoxLayout()
        self._track(block, ROW_MARGINS, 8)
        head = QHBoxLayout()
        self._track(head, (0, 0, 0, 0), 8)
        head_text = QVBoxLayout()
        self._track(head_text, (0, 0, 0, 0), 2)
        head_text.addWidget(_label("Command phrases", "RowTitle"))
        head_text.addWidget(_label("Write \\n for a line break and \\t for a tab.", "Secondary",
                                   wrap=True))
        head.addLayout(head_text, 1)
        self.add_row_button = QPushButton("Add")
        self.remove_row_button = QPushButton("Remove")
        for button, slot in ((self.add_row_button, self._add_clicked),
                             (self.remove_row_button, self._remove_clicked)):
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(slot)
            head.addWidget(button, 0, Qt.AlignVCenter)
        block.addLayout(head)
        self.command_table = QTableWidget(0, 2)
        self.command_table.setObjectName("CommandTable")
        self.command_table.setHorizontalHeaderLabels(["Phrase", "Output"])
        self.command_table.verticalHeader().hide()
        self.command_table.setShowGrid(False)
        self.command_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.command_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.command_table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        header = self.command_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setHighlightSections(False)
        self._heights.append((self.command_table, TABLE_HEIGHT))
        block.addWidget(self.command_table)
        card.addLayout(block)
        self.commands_switch.toggled.connect(self._sync_commands_enabled)

        card.addWidget(_separator())
        editors = QHBoxLayout()
        self._track(editors, ROW_MARGINS, 16)
        self.filler_edit = QPlainTextEdit()
        self.backtrack_edit = QPlainTextEdit()
        for title, helper, edit in (
            ("Filler words", "Removed when set off by commas. One per line.", self.filler_edit),
            ("Backtrack phrases", "Saying one deletes your last sentence. One per line.",
             self.backtrack_edit),
        ):
            col = QVBoxLayout()
            self._track(col, (0, 0, 0, 0), 4)
            col.addWidget(_label(title, "RowTitle"))
            col.addWidget(_label(helper, "Secondary", wrap=True))
            edit.setTabChangesFocus(True)
            self._heights.append((edit, EDITOR_HEIGHT))
            col.addWidget(edit)
            editors.addLayout(col, 1)
        card.addLayout(editors)

        card.addWidget(_separator())
        reset_row = QHBoxLayout()
        self._track(reset_row, ROW_MARGINS, 12)
        reset_row.addWidget(_label("Bring back the built-in phrase lists and commands.",
                                   "Secondary", wrap=True), 1)
        self.reset_phrases_button = QPushButton("Reset phrases to defaults")
        self.reset_phrases_button.setCursor(Qt.PointingHandCursor)
        self.reset_phrases_button.clicked.connect(self.reset_phrases)
        reset_row.addWidget(self.reset_phrases_button, 0, Qt.AlignVCenter)
        card.addLayout(reset_row)

    def _build_footer(self) -> QWidget:
        footer = QFrame()
        footer.setObjectName("Footer")
        row = QHBoxLayout(footer)
        self._track(row, (36, 12, 36, 14), 16)
        row.addWidget(_label(RESTART_NOTE, "Secondary", wrap=True), 1)
        self.save_button = QPushButton("Save")
        self.save_button.setProperty("variant", "primary")
        self.save_button.setCursor(Qt.PointingHandCursor)
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self._save)
        row.addWidget(self.save_button, 0, Qt.AlignVCenter)
        return footer

    # ----- public API -----

    def load(self, config: Config) -> None:
        """Show `config` in every control."""
        self._base = config
        self.ptt_edit.cancel_capture()
        self.tts_edit.cancel_capture()
        self.ptt_edit.set_hotkey(config.ptt_key)
        self.tts_edit.set_hotkey(config.tts_key)

        self.model_combo.clear()
        models = MODELS if config.model in MODELS else MODELS + [config.model]
        for name in models:
            self.model_combo.addItem(name, name)
        self.model_combo.setCurrentIndex(models.index(config.model))

        self.mic_combo.clear()
        mics = list(self._mics)
        if all(index != config.mic_device for _, index in mics):
            mics.append((f"{config.mic_device}: (not connected)", config.mic_device))
        for label, index in mics:
            self.mic_combo.addItem(label, index)
        self.mic_combo.setCurrentIndex(next(i for i, m in enumerate(mics) if m[1] == config.mic_device))

        self.autostart_switch.setChecked(config.start_with_windows)
        self.history_switch.setChecked(config.save_history)
        self.hands_free_switch.setChecked(config.hands_free)
        self.pill_switch.setChecked(config.pill_always_visible)
        self.commands_switch.setChecked(config.voice_commands)
        self.silence_slider.setValue(round(config.silence_stop_seconds * SILENCE_STEPS))
        self.scale_slider.setValue(round(config.ui_scale * SCALE_STEPS))
        self._set_phrases(config.filler_phrases, config.backtrack_phrases, config.command_phrases)
        self._sync_commands_enabled(config.voice_commands)

    def to_config(self) -> Config:
        """The Config the form currently describes."""
        return Config(
            ptt_key=self.ptt_edit.hotkey() or self._base.ptt_key,
            tts_key=self.tts_edit.hotkey() or self._base.tts_key,
            model=self.model_combo.currentData(),
            mic_device=self.mic_combo.currentData(),
            start_with_windows=self.autostart_switch.isChecked(),
            filler_phrases=parse_phrases(self.filler_edit.toPlainText()),
            backtrack_phrases=parse_phrases(self.backtrack_edit.toPlainText()),
            voice_commands=self.commands_switch.isChecked(),
            command_phrases=rows_to_commands(self.command_rows()),
            hands_free=self.hands_free_switch.isChecked(),
            silence_stop_seconds=self.silence_slider.value() / SILENCE_STEPS,
            save_history=self.history_switch.isChecked(),
            pill_always_visible=self.pill_switch.isChecked(),
            ui_scale=round(self.scale_slider.value() / SCALE_STEPS, 2),
        )

    def command_rows(self) -> list[tuple[str, str]]:
        """(phrase, escaped output) for every table row, as shown."""
        rows = []
        for r in range(self.command_table.rowCount()):
            cells = [self.command_table.item(r, c) for c in (0, 1)]
            rows.append(tuple(cell.text() if cell is not None else "" for cell in cells))
        return rows

    def add_command_row(self, phrase: str = "", output: str = "") -> int:
        """Append a row; `output` is shown as typed (already escaped)."""
        row = self.command_table.rowCount()
        self.command_table.insertRow(row)
        self.command_table.setItem(row, 0, QTableWidgetItem(phrase))
        self.command_table.setItem(row, 1, QTableWidgetItem(output))
        return row

    def reset_phrases(self) -> None:
        self._set_phrases(DEFAULT_FILLER_PHRASES, DEFAULT_BACKTRACK_PHRASES, DEFAULT_COMMANDS)

    def set_scale(self, scale: float) -> None:
        """Follow the UI size: margins, gaps and fixed control sizes (fonts come from the QSS)."""
        def px(v: float) -> int:
            return round(v * scale)

        for layout, (left, top, right, bottom), spacing in self._layouts:
            layout.setContentsMargins(px(left), px(top), px(right), px(bottom))
            layout.setSpacing(px(spacing))
        for gap in self._gaps:
            gap.setFixedHeight(px(22))
        for widget, width in self._widths:
            widget.setFixedWidth(px(width))
        for widget, height in self._heights:
            widget.setFixedHeight(px(height))
        for switch in self._switches:
            switch.set_scale(scale)
        self.command_table.verticalHeader().setDefaultSectionSize(px(32))

    # ----- internals -----

    def _set_phrases(self, filler: list[str], backtrack: list[str],
                     commands: dict[str, str]) -> None:
        self.filler_edit.setPlainText("\n".join(filler))
        self.backtrack_edit.setPlainText("\n".join(backtrack))
        self.command_table.setRowCount(0)
        for phrase, output in commands.items():
            self.add_command_row(phrase, escape_text(output))

    def _sync_commands_enabled(self, on: bool) -> None:
        for widget in (self.command_table, self.add_row_button, self.remove_row_button):
            widget.setEnabled(on)

    def _add_clicked(self) -> None:
        row = self.add_command_row()
        item = self.command_table.item(row, 0)
        self.command_table.setCurrentItem(item)
        self.command_table.scrollToItem(item)
        if self.command_table.isVisible():
            self.command_table.editItem(item)

    def _remove_clicked(self) -> None:
        row = self.command_table.currentRow()
        if row >= 0:
            self.command_table.removeRow(row)

    def _save(self) -> None:
        cfg = self.to_config()
        self._base = cfg
        self._on_save(cfg)
        self.save_button.setText("Saved")
        self._saved_timer.start()
