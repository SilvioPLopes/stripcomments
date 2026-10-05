import ast
import tokenize
from dataclasses import dataclass
from typing import Iterable

from .core import strip_comments


@dataclass(frozen=True)
class CleanOutcome:
    text: str | None
    removed: int
    skipped_reason: str | None = None

    @property
    def accepted(self) -> bool:
        return self.skipped_reason is None


def _parse(source: str) -> ast.AST:
    return ast.parse(source.removeprefix("\ufeff"))


def _skip(reason: str) -> CleanOutcome:
    return CleanOutcome(text=None, removed=0, skipped_reason=reason)


def _describe_syntax_error(error: Exception) -> str:
    line = getattr(error, "lineno", None)
    message = getattr(error, "msg", None) or str(error)
    if line:
        return f"{message} (linha {line})"
    return message


def clean_source(source: str, extra_directives: Iterable[str] = ()) -> CleanOutcome:
    """Remove comentários e só aceita o resultado se a AST for idêntica à original."""
    try:
        original_tree = _parse(source)
    except (SyntaxError, ValueError, RecursionError) as error:
        return _skip(f"arquivo não compila: {_describe_syntax_error(error)}")

    try:
        result = strip_comments(source, extra_directives)
    except (tokenize.TokenError, SyntaxError, ValueError) as error:
        return _skip(f"falha ao remover comentários: {_describe_syntax_error(error)}")

    try:
        cleaned_tree = _parse(result.text)
    except (SyntaxError, ValueError, RecursionError) as error:
        return _skip(f"resultado não compila: {_describe_syntax_error(error)}")

    if ast.dump(original_tree) != ast.dump(cleaned_tree):
        return _skip("a AST do resultado difere da original")

    return CleanOutcome(text=result.text, removed=result.removed)
