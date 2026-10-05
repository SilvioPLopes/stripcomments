import tokenize

import pytest

from stripcomments import validation
from stripcomments.core import StripResult
from stripcomments.validation import CleanOutcome, clean_source


class TestAccepted:
    def test_accepts_file_with_only_comments_removed(self):
        outcome = clean_source("x = 1  # nota\n# solta\ny = 2\n")
        assert outcome.accepted
        assert outcome.text == "x = 1\ny = 2\n"
        assert outcome.removed == 2
        assert outcome.skipped_reason is None

    def test_accepts_file_without_comments(self):
        source = "x = 1\n"
        outcome = clean_source(source)
        assert outcome.accepted
        assert outcome.text == source
        assert outcome.removed == 0

    def test_hash_inside_string_survives(self):
        outcome = clean_source('cor = "cor: #fff"  # fundo\n')
        assert outcome.accepted
        assert outcome.text == 'cor = "cor: #fff"\n'

    def test_docstrings_stay_intact(self):
        source = 'def f():\n    """Doc # não é comentário."""  # fim\n    return 1\n'
        outcome = clean_source(source)
        assert outcome.accepted
        assert '"""Doc # não é comentário."""' in outcome.text

    def test_accepts_source_with_bom(self):
        outcome = clean_source("\ufeffx = 1  # nota\n")
        assert outcome.accepted
        assert outcome.text == "\ufeffx = 1\n"

    def test_idempotent(self):
        first = clean_source("x = 1  # a\n# b\n")
        second = clean_source(first.text)
        assert second.text == first.text
        assert second.removed == 0

    def test_extra_directives_are_forwarded(self, monkeypatch):
        received = {}

        def fake(source, extra_directives=()):
            received["extra"] = tuple(extra_directives)
            return StripResult(source, 0)

        monkeypatch.setattr(validation, "strip_comments", fake)
        clean_source("x = 1\n", ["minha:"])
        assert received["extra"] == ("minha:",)


class TestSkipped:
    def test_syntax_error_is_skipped_with_reason(self):
        outcome = clean_source("def f(:\n    pass\n")
        assert not outcome.accepted
        assert outcome.text is None
        assert outcome.removed == 0
        assert "não compila" in outcome.skipped_reason
        assert "linha 1" in outcome.skipped_reason

    def test_null_byte_is_skipped(self):
        outcome = clean_source("x = 1\0\n")
        assert not outcome.accepted
        assert "não compila" in outcome.skipped_reason

    def test_tokenizer_failure_is_skipped(self, monkeypatch):
        def broken(source, extra_directives=()):
            raise tokenize.TokenError("EOF in multi-line statement", (1, 0))

        monkeypatch.setattr(validation, "strip_comments", broken)
        outcome = clean_source("x = 1\n")
        assert not outcome.accepted
        assert "falha ao remover comentários" in outcome.skipped_reason

    def test_changed_code_is_skipped(self, monkeypatch):
        monkeypatch.setattr(
            validation, "strip_comments", lambda s, e=(): StripResult("x = 2\n", 1)
        )
        outcome = clean_source("x = 1  # nota\n")
        assert not outcome.accepted
        assert outcome.text is None
        assert "AST" in outcome.skipped_reason

    def test_changed_docstring_is_skipped(self, monkeypatch):
        cleaned = 'def f():\n    """Outra."""\n'
        monkeypatch.setattr(
            validation, "strip_comments", lambda s, e=(): StripResult(cleaned, 1)
        )
        outcome = clean_source('def f():\n    """Doc."""  # x\n')
        assert not outcome.accepted
        assert "AST" in outcome.skipped_reason

    def test_result_that_does_not_compile_is_skipped(self, monkeypatch):
        monkeypatch.setattr(
            validation, "strip_comments", lambda s, e=(): StripResult("x = (\n", 1)
        )
        outcome = clean_source("x = 1  # nota\n")
        assert not outcome.accepted
        assert "resultado não compila" in outcome.skipped_reason


def test_outcome_is_frozen():
    outcome = CleanOutcome(text="x", removed=0)
    with pytest.raises(Exception):
        outcome.removed = 5
