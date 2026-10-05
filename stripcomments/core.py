import io
import re
import tokenize
from collections.abc import Iterable
from dataclasses import dataclass

from stripcomments.directives import DEFAULT_DIRECTIVES, START_ONLY_DIRECTIVES

BOM = "\ufeff"
SHEBANG_PREFIX = "#!"
ENCODING_LINE = re.compile(r"^[ \t\f]*#.*?coding[:=][ \t]*[-\w.]+")
LAST_ENCODING_LINE = 2
INLINE_SPACING = " \t"


@dataclass(frozen=True)
class StripResult:
    text: str
    removed: int


def strip_comments(source: str, extra_directives: Iterable[str] = ()) -> StripResult:
    """Remove os comentários `#` de ``source`` sem reformatar o restante.

    Levanta as exceções do ``tokenize`` se o código não puder ser tokenizado.
    """
    bom, body = _split_bom(source)
    directives = (*DEFAULT_DIRECTIVES, *extra_directives)
    lines = io.StringIO(body).readlines()

    spans = {}
    for row, start, end in _comment_spans(lines):
        if not _is_preserved(lines[row - 1], row, start, end, directives):
            spans[row] = (start, end)

    text = "".join(_rebuild_lines(lines, spans))
    if spans and not body.endswith(("\n", "\r")):
        text = _drop_final_line_break(text)
    return StripResult(text=bom + text, removed=len(spans))


def _split_bom(source: str) -> tuple[str, str]:
    if source.startswith(BOM):
        return BOM, source[len(BOM):]
    return "", source


def _comment_spans(lines: list[str]) -> list[tuple[int, int, int]]:
    remaining = iter(lines)
    tokens = tokenize.generate_tokens(lambda: next(remaining, ""))
    spans = []
    for token in tokens:
        if token.type == tokenize.COMMENT:
            row, start = token.start
            spans.append((row, start, start + len(token.string.rstrip("\r\n"))))
    return spans


def _is_preserved(
    line: str, row: int, start: int, end: int, directives: Iterable[str]
) -> bool:
    comment = line[start:end]
    if row == 1 and start == 0 and comment.startswith(SHEBANG_PREFIX):
        return True
    if row <= LAST_ENCODING_LINE and ENCODING_LINE.match(line):
        return True
    return _has_directive(comment, directives)


def _has_directive(comment: str, directives: Iterable[str]) -> bool:
    text_after_hash = comment[1:].lstrip()
    for directive in directives:
        if directive in START_ONLY_DIRECTIVES:
            if text_after_hash.startswith(directive):
                return True
        elif directive in comment:
            return True
    return False


def _rebuild_lines(lines: list[str], spans: dict[int, tuple[int, int]]) -> list[str]:
    rebuilt = []
    for row, line in enumerate(lines, start=1):
        if row not in spans:
            rebuilt.append(line)
            continue
        start, end = spans[row]
        code_before = line[:start]
        if code_before.strip():
            rebuilt.append(code_before.rstrip(INLINE_SPACING) + line[end:])
    return rebuilt


def _drop_final_line_break(text: str) -> str:
    for line_break in ("\r\n", "\n", "\r"):
        if text.endswith(line_break):
            return text[: -len(line_break)]
    return text
