"""Postprocessor: runs the v3 text pipeline (clean, dictionary, lists, AI polish, snippets)."""
from flowvoice.ai_polish import AiService, count_words
from flowvoice.cleanup import clean
from flowvoice.config import Config
from flowvoice.lists import format_lists
from flowvoice.snippets import expand_snippets, protect_snippets
from flowvoice.vocabulary import apply_dictionary, glossary_prompt

MAX_AI_WORDS = 1500


def _safe(step, text: str) -> str:
    """Run an optional text step; on any ordinary failure keep the previous text."""
    try:
        result = step(text)
    except Exception:
        return text
    return result if isinstance(result, str) else text


def _strip_leaks(text: str, mapping: dict[str, str]) -> str:
    for ph in mapping:
        text = text.replace(ph, "")
    return text


class Postprocessor:
    """Stateless between calls, so one instance can serve the dictation worker thread."""

    def __init__(self, ai: AiService | None = None):
        self.ai = ai

    def glossary(self, cfg: Config) -> str | None:
        return glossary_prompt(cfg.dictionary_terms)

    def process(self, text: str, cfg: Config) -> str:
        if not text:
            return ""
        mapping: dict[str, str] = {}

        def protect(t: str) -> str:
            protected, found = protect_snippets(t, cfg.snippets)
            mapping.update(found)
            return protected

        out = clean(text, fillers=cfg.filler_phrases, backtracks=cfg.backtrack_phrases,
                    commands=cfg.command_phrases if cfg.voice_commands else None,
                    before_commands=protect)
        out = _safe(lambda t: apply_dictionary(t, cfg.dictionary_terms, cfg.dictionary_fixes), out)
        if cfg.auto_lists:
            out = _safe(format_lists, out)
        if self.ai is not None and cfg.ai_enabled and count_words(out) <= MAX_AI_WORDS:
            try:
                polished = self.ai.polish(out, cfg)
            except Exception:
                polished = None
            if isinstance(polished, str) and polished.strip():
                out = polished
        try:
            out = expand_snippets(out, mapping)
        except Exception:
            out = _strip_leaks(out, mapping)
        return _strip_leaks(out, mapping)
