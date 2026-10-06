"""Settings tab: grouped rounded cards (Dictation, Hands-free, Interface, Phrases, Words,
Snippets, Lists and AI) and Save."""
import threading
from typing import Callable

from PySide6.QtCore import Property, QPointF, Qt, QTimer, Signal, Slot
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
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from flowvoice.cleanup import DEFAULT_BACKTRACK_PHRASES, DEFAULT_FILLER_PHRASES
from flowvoice.commands import DEFAULT_COMMANDS
from flowvoice.config import (
    AI_MIN_WORDS_MIN,
    MAX_FIXES,
    MAX_SNIPPETS,
    MAX_TERMS,
    UI_SCALE_MAX,
    UI_SCALE_MIN,
    Config,
)
from flowvoice.settings_logic import (
    escape_text,
    parse_phrases,
    rows_duplicates,
    rows_to_commands,
    rows_to_dict,
    snippet_warnings,
    terms_from_text,
)
from flowvoice.ui.hotkey_edit import HotkeyEdit
from flowvoice.ui.switch import Switch

MODELS = ["tiny.en", "base.en", "small.en", "medium.en"]
SILENCE_STEPS = 2  # slider units per second (0.5 s steps)
SILENCE_RANGE = (1, 10)
SCALE_STEPS = 20  # slider units per 1.0 of scale (0.05 steps)
AI_MIN_WORDS_MAX = 200
RESTART_NOTE = "Hotkey, model, microphone and start-with-Windows changes restart Flow Voice."
NO_AI_TIP = "AI is not available"
TEST_HELP = "Test AI sends a short sample and shows the result and how long it took."
SAVED_MS = 1400
ERROR_CHARS = 120

PAGE_MARGINS = (36, 30, 36, 20)
CARD_MARGINS = (18, 4, 18, 4)
ROW_MARGINS = (0, 12, 0, 12)
CONTROL_WIDTH = 230
SLIDER_WIDTH = 190
VALUE_WIDTH = 48
SPIN_WIDTH = 96
TABLE_HEIGHT = 250
SMALL_TABLE_HEIGHT = 190
EDITOR_HEIGHT = 120
ROW_HEIGHT = 32


def _label(text: str, name: str, wrap: bool = False) -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    label.setWordWrap(wrap)
    return label


def _short_error(err: BaseException) -> str:
    lines = str(err).strip().splitlines()
    return (lines[0] if lines else type(err).__name__)[:ERROR_CHARS]


def ai_status_text(status: str, detail: str) -> str:
    """The one-line status shown under the AI controls."""
    if status == "ready":
        return "AI: ready"
    if status == "warming":
        return "AI: warming up..."
    if status == "off":
        return "AI: off"
    if status == "missing model":
        return f"AI: model not installed - run: {detail}" if detail else "AI: model not installed"
    if status == "unavailable":
        return f"AI: unavailable - {detail}" if detail else "AI: unavailable"
    return f"AI: {status} - {detail}" if detail else f"AI: {status}"


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
    """Builds a Config from the form and hands it to `on_save`; never writes files itself.

    `capture_started` / `capture_finished` forward either hotkey field's capture lifecycle.
    `ai_probe` (optional) has `list_models(cfg) -> list[str]` and `test(cfg) -> str`; both
    may block, so they run on daemon threads and report back only through queued signals.
    """

    capture_started = Signal()
    capture_finished = Signal()
    _models_ready = Signal(object, str)
    _test_done = Signal(str)
    _status_changed = Signal(str, str)

    def __init__(self, config: Config, mics: list[tuple[str, int | None]],
                 on_save: Callable[[Config], None], ai_probe=None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._mics = list(mics)
        self._on_save = on_save
        self._base = config
        self._ai_probe = ai_probe
        self._refreshing = False
        self._testing = False
        self._layouts: list[tuple[QLayout, tuple[int, int, int, int], int]] = []
        self._widths: list[tuple[QWidget, int]] = []
        self._heights: list[tuple[QWidget, int]] = []
        self._switches: list[Switch] = []
        self._tables: list[QTableWidget] = []

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
        self._build_words(page)
        self._build_snippets(page)
        self._build_lists_ai(page)
        page.addStretch(1)
        self.scroll.setWidget(body)
        outer.addWidget(self.scroll, 1)
        outer.addWidget(self._build_footer())

        self._saved_timer = QTimer(self)
        self._saved_timer.setSingleShot(True)
        self._saved_timer.setInterval(SAVED_MS)
        self._saved_timer.timeout.connect(lambda: self.save_button.setText("Save"))

        for table in (self.snippets_table, self.command_table):
            model = table.model()
            for signal in (model.dataChanged, model.rowsInserted, model.rowsRemoved,
                           model.modelReset):
                signal.connect(self._refresh_snippet_warnings)
        self._models_ready.connect(self._on_models, Qt.QueuedConnection)
        self._test_done.connect(self._on_tested, Qt.QueuedConnection)
        self._status_changed.connect(self._apply_ai_status)

        self.load(config)
        self._apply_ai_status("off", "")
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

    def _button(self, text: str, slot: Callable[[], None]) -> QPushButton:
        button = QPushButton(text)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(slot)
        return button

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

    def _editor(self) -> QPlainTextEdit:
        edit = QPlainTextEdit()
        edit.setTabChangesFocus(True)
        self._heights.append((edit, EDITOR_HEIGHT))
        return edit

    def _table(self, headers: tuple[str, str], height: int) -> QTableWidget:
        table = QTableWidget(0, 2)
        table.setObjectName("CommandTable")
        table.setHorizontalHeaderLabels(list(headers))
        table.verticalHeader().hide()
        table.setShowGrid(False)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setHighlightSections(False)
        self._heights.append((table, height))
        self._tables.append(table)
        return table

    def _table_block(self, card: QVBoxLayout, title: str, helper: str, table: QTableWidget
                     ) -> tuple[QPushButton, QPushButton, QVBoxLayout]:
        """Title, helper and Add / Remove over `table`; returns the buttons and the block."""
        block = QVBoxLayout()
        self._track(block, ROW_MARGINS, 8)
        head = QHBoxLayout()
        self._track(head, (0, 0, 0, 0), 8)
        head_text = QVBoxLayout()
        self._track(head_text, (0, 0, 0, 0), 2)
        head_text.addWidget(_label(title, "RowTitle"))
        head_text.addWidget(_label(helper, "Secondary", wrap=True))
        head.addLayout(head_text, 1)
        add = self._button("Add", lambda: self._add_row(table))
        remove = self._button("Remove", lambda: self._remove_row(table))
        head.addWidget(add, 0, Qt.AlignVCenter)
        head.addWidget(remove, 0, Qt.AlignVCenter)
        block.addLayout(head)
        block.addWidget(table)
        card.addLayout(block)
        return add, remove, block

    def _text_block(self, layout: QHBoxLayout | QVBoxLayout, title: str, helper: str,
                    edit: QPlainTextEdit, margins: tuple[int, int, int, int] = (0, 0, 0, 0)
                    ) -> QVBoxLayout:
        col = QVBoxLayout()
        self._track(col, margins, 4)
        col.addWidget(_label(title, "RowTitle"))
        col.addWidget(_label(helper, "Secondary", wrap=True))
        col.addWidget(edit)
        layout.addLayout(col, 1)
        return col

    def _build_dictation(self, page: QVBoxLayout) -> None:
        card = self._section(page, "Dictation")
        self.ptt_edit = HotkeyEdit()
        self.tts_edit = HotkeyEdit()
        for edit in (self.ptt_edit, self.tts_edit):
            self._widths.append((edit, CONTROL_WIDTH))
            edit.capture_started.connect(self.capture_started)
            edit.capture_finished.connect(self.capture_finished)
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
        self.command_table = self._table(("Phrase", "Output"), TABLE_HEIGHT)
        self.add_row_button, self.remove_row_button, _ = self._table_block(
            card, "Command phrases", "Write \\n for a line break and \\t for a tab.",
            self.command_table)
        self.commands_switch.toggled.connect(self._sync_commands_enabled)

        card.addWidget(_separator())
        editors = QHBoxLayout()
        self._track(editors, ROW_MARGINS, 16)
        self.filler_edit = self._editor()
        self.backtrack_edit = self._editor()
        self._text_block(editors, "Filler words", "Removed when set off by commas. One per line.",
                         self.filler_edit)
        self._text_block(editors, "Backtrack phrases",
                         "Saying one deletes your last sentence. One per line.", self.backtrack_edit)
        card.addLayout(editors)

        card.addWidget(_separator())
        reset_row = QHBoxLayout()
        self._track(reset_row, ROW_MARGINS, 12)
        reset_row.addWidget(_label("Bring back the built-in phrase lists and commands.",
                                   "Secondary", wrap=True), 1)
        self.reset_phrases_button = self._button("Reset phrases to defaults", self.reset_phrases)
        reset_row.addWidget(self.reset_phrases_button, 0, Qt.AlignVCenter)
        card.addLayout(reset_row)

    def _build_words(self, page: QVBoxLayout) -> None:
        card = self._section(page, "Words")
        self.terms_edit = self._editor()
        self._text_block(card, "Dictionary",
                         "Names and terms the speech model should listen for and spell your way. "
                         "One per line.", self.terms_edit, ROW_MARGINS)
        card.addWidget(_separator())
        self.fixes_table = self._table(("Heard as", "Write as"), SMALL_TABLE_HEIGHT)
        self.add_fix_button, self.remove_fix_button, _ = self._table_block(
            card, "Corrections", "Fix words the speech model keeps getting wrong.",
            self.fixes_table)

    def _build_snippets(self, page: QVBoxLayout) -> None:
        card = self._section(page, "Snippets")
        self.snippets_table = self._table(("Trigger phrase", "Text"), SMALL_TABLE_HEIGHT)
        self.add_snippet_button, self.remove_snippet_button, block = self._table_block(
            card, "Trigger phrases", "Say the phrase to type the text exactly as written. "
            "Write \\n for a line break and \\t for a tab.", self.snippets_table)
        self.snippet_warnings_label = _label("", "WarningText", wrap=True)
        self.snippet_warnings_label.hide()
        block.addWidget(self.snippet_warnings_label)

    def _build_lists_ai(self, page: QVBoxLayout) -> None:
        card = self._section(page, "Lists and AI")
        self.auto_lists_switch = self._switch()
        self.ai_switch = self._switch()
        self.ai_model_combo = self._combo()
        self.ai_model_combo.setEditable(True)
        self.ai_model_combo.setInsertPolicy(QComboBox.NoInsert)
        self.refresh_models_button = self._button("Refresh", self._refresh_models)
        self.ai_min_words = QSpinBox()
        self.ai_min_words.setRange(AI_MIN_WORDS_MIN, AI_MIN_WORDS_MAX)
        self.ai_min_words.setAlignment(Qt.AlignCenter)
        self.ai_min_words.setButtonSymbols(QSpinBox.NoButtons)  # native arrows clash with the QSS
        self.ai_min_words.setToolTip("Type a number, or use the arrow keys or the mouse wheel.")
        self._widths.append((self.ai_min_words, SPIN_WIDTH))
        model_box = QHBoxLayout()
        self._track(model_box, (0, 0, 0, 0), 8)
        model_box.addWidget(self.ai_model_combo, 0, Qt.AlignVCenter)
        model_box.addWidget(self.refresh_models_button, 0, Qt.AlignVCenter)

        self._row(card, "Automatic lists",
                  'Say "one, ... two, ..." or "first, ... second, ..." to get a numbered list, '
                  'or "shopping list: apples, bread and milk" for bullets.',
                  self.auto_lists_switch, first=True)
        self._row(card, "AI polish",
                  "A local Ollama model splits long dictations into paragraphs and lists. "
                  "Your words are kept and nothing leaves this PC.", self.ai_switch)
        self._row(card, "AI model", "Any model installed in Ollama.",
                  model_box)
        self._row(card, "Minimum words", "Shorter dictations skip the AI.", self.ai_min_words)

        card.addWidget(_separator())
        row = QHBoxLayout()
        self._track(row, ROW_MARGINS, 16)
        text = QVBoxLayout()
        self._track(text, (0, 0, 0, 0), 2)
        self.ai_status_label = _label("", "RowTitle", wrap=True)
        self.ai_result_label = _label(TEST_HELP, "Secondary", wrap=True)
        self.ai_result_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        text.addWidget(self.ai_status_label)
        text.addWidget(self.ai_result_label)
        row.addLayout(text, 1)
        self.test_ai_button = self._button("Test AI", self._run_test)
        row.addWidget(self.test_ai_button, 0, Qt.AlignVCenter)
        card.addLayout(row)

        if self._ai_probe is None:
            for button in (self.refresh_models_button, self.test_ai_button):
                button.setEnabled(False)
                button.setToolTip(NO_AI_TIP)

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

        self.terms_edit.setPlainText("\n".join(config.dictionary_terms))
        self._fill(self.fixes_table, config.dictionary_fixes)
        self._fill(self.snippets_table, config.snippets)
        self.auto_lists_switch.setChecked(config.auto_lists)
        self.ai_switch.setChecked(config.ai_enabled)
        if self.ai_model_combo.findText(config.ai_model) < 0:
            self.ai_model_combo.addItem(config.ai_model)
        self.ai_model_combo.setEditText(config.ai_model)
        self.ai_min_words.setValue(int(config.ai_min_words))

    def to_config(self) -> Config:
        """The Config the form currently describes (AI timeout and URL are carried over)."""
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
            dictionary_terms=terms_from_text(self.terms_edit.toPlainText(), limit=MAX_TERMS),
            dictionary_fixes=rows_to_dict(self.fix_rows(), lower_keys=True, limit=MAX_FIXES),
            snippets=rows_to_dict(self.snippet_rows(), lower_keys=True, limit=MAX_SNIPPETS),
            auto_lists=self.auto_lists_switch.isChecked(),
            ai_enabled=self.ai_switch.isChecked(),
            ai_model=self.ai_model_combo.currentText().strip() or self._base.ai_model,
            ai_min_words=self.ai_min_words.value(),
            ai_timeout_seconds=self._base.ai_timeout_seconds,
            ai_url=self._base.ai_url,
        )

    def command_rows(self) -> list[tuple[str, str]]:
        """(phrase, escaped output) for every table row, as shown."""
        return self._rows(self.command_table)

    def fix_rows(self) -> list[tuple[str, str]]:
        """(heard as, escaped write as) for every corrections row, as shown."""
        return self._rows(self.fixes_table)

    def snippet_rows(self) -> list[tuple[str, str]]:
        """(trigger, escaped text) for every snippet row, as shown."""
        return self._rows(self.snippets_table)

    def add_command_row(self, phrase: str = "", output: str = "") -> int:
        """Append a row; `output` is shown as typed (already escaped)."""
        return self._append_row(self.command_table, phrase, output)

    def add_fix_row(self, heard: str = "", write: str = "") -> int:
        return self._append_row(self.fixes_table, heard, write)

    def add_snippet_row(self, trigger: str = "", text: str = "") -> int:
        """Append a snippet row; `text` is shown as typed (already escaped)."""
        return self._append_row(self.snippets_table, trigger, text)

    def reset_phrases(self) -> None:
        self._set_phrases(DEFAULT_FILLER_PHRASES, DEFAULT_BACKTRACK_PHRASES, DEFAULT_COMMANDS)

    def set_ai_status(self, status: str, detail: str) -> None:
        """Thread-safe: show the AI service status (queued to the GUI thread)."""
        try:
            self._status_changed.emit(status, detail)
        except RuntimeError:
            pass  # view already deleted

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
        for table in self._tables:
            table.verticalHeader().setDefaultSectionSize(px(ROW_HEIGHT))

    # ----- internals -----

    @staticmethod
    def _rows(table: QTableWidget) -> list[tuple[str, str]]:
        rows = []
        for r in range(table.rowCount()):
            cells = [table.item(r, c) for c in (0, 1)]
            rows.append(tuple(cell.text() if cell is not None else "" for cell in cells))
        return rows

    @staticmethod
    def _append_row(table: QTableWidget, first: str, second: str) -> int:
        row = table.rowCount()
        table.insertRow(row)
        table.setItem(row, 0, QTableWidgetItem(first))
        table.setItem(row, 1, QTableWidgetItem(second))
        return row

    def _fill(self, table: QTableWidget, mapping: dict[str, str]) -> None:
        table.setRowCount(0)
        for key, value in mapping.items():
            self._append_row(table, key, escape_text(value))

    def _set_phrases(self, filler: list[str], backtrack: list[str],
                     commands: dict[str, str]) -> None:
        self.filler_edit.setPlainText("\n".join(filler))
        self.backtrack_edit.setPlainText("\n".join(backtrack))
        self._fill(self.command_table, commands)

    def _sync_commands_enabled(self, on: bool) -> None:
        for widget in (self.command_table, self.add_row_button, self.remove_row_button):
            widget.setEnabled(on)

    def _add_row(self, table: QTableWidget) -> None:
        row = self._append_row(table, "", "")
        item = table.item(row, 0)
        table.setCurrentItem(item)
        table.scrollToItem(item)
        if table.isVisible():
            table.editItem(item)

    @staticmethod
    def _remove_row(table: QTableWidget) -> None:
        row = table.currentRow()
        if row >= 0:
            table.removeRow(row)

    def _refresh_snippet_warnings(self, *_) -> None:
        rows = self.snippet_rows()
        snippets = rows_to_dict(rows, lower_keys=True, limit=MAX_SNIPPETS)
        messages = snippet_warnings(snippets, rows_to_commands(self.command_rows()))
        messages += [f'"{key}" is used by more than one snippet; the last one wins.'
                     for key in rows_duplicates(rows, lower_keys=True)]
        self.snippet_warnings_label.setText("\n".join(messages))
        self.snippet_warnings_label.setVisible(bool(messages))

    # ----- AI probe (worker threads talk back only through queued signals) -----

    def _start_probe(self, target: Callable[..., None], *args) -> bool:
        try:
            threading.Thread(target=target, args=args, daemon=True, name="ai-probe").start()
            return True
        except Exception:
            return False

    def _refresh_models(self) -> None:
        if self._ai_probe is None or self._refreshing:
            return
        self._refreshing = True
        self.refresh_models_button.setEnabled(False)
        self.refresh_models_button.setText("Refreshing...")
        if not self._start_probe(self._list_worker, self._ai_probe, self.to_config()):
            self._on_models([], "could not start")

    def _list_worker(self, probe, cfg: Config) -> None:
        try:
            names, error = [str(n) for n in probe.list_models(cfg)], ""
        except Exception as e:
            names, error = [], _short_error(e)
        try:
            self._models_ready.emit(names, error)
        except RuntimeError:
            pass  # view already deleted

    def _on_models(self, names: list[str], error: str) -> None:
        self._refreshing = False
        self.refresh_models_button.setText("Refresh")
        self.refresh_models_button.setEnabled(True)
        if error:
            self.ai_result_label.setText(f"Could not list models: {error}")
            return
        if not names:
            self.ai_result_label.setText("No installed models found. Is Ollama running?")
            return
        text = self.ai_model_combo.currentText()
        self.ai_model_combo.clear()
        self.ai_model_combo.addItems(names)
        self.ai_model_combo.setEditText(text)

    def _run_test(self) -> None:
        if self._ai_probe is None or self._testing:
            return
        self._testing = True
        self.test_ai_button.setEnabled(False)
        self.test_ai_button.setText("Testing...")
        if not self._start_probe(self._test_worker, self._ai_probe, self.to_config()):
            self._on_tested("Test failed: could not start")

    def _test_worker(self, probe, cfg: Config) -> None:
        try:
            result = str(probe.test(cfg))
        except Exception as e:
            result = f"Test failed: {_short_error(e)}"
        try:
            self._test_done.emit(result)
        except RuntimeError:
            pass  # view already deleted

    def _on_tested(self, result: str) -> None:
        self._testing = False
        self.test_ai_button.setText("Test AI")
        self.test_ai_button.setEnabled(True)
        self.ai_result_label.setText(result)

    @Slot(str, str)
    def _apply_ai_status(self, status: str, detail: str) -> None:
        self.ai_status_label.setText(ai_status_text(status, detail))

    def _save(self) -> None:
        cfg = self.to_config()
        self._base = cfg
        self._on_save(cfg)
        self.save_button.setText("Saved")
        self._saved_timer.start()
