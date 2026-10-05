import difflib
import io
import os
import tokenize
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable, Sequence

from .validation import clean_source

DEFAULT_EXCLUDES: tuple[str, ...] = (
    "migrations",
    ".git",
    "venv",
    ".venv",
    "env",
    "node_modules",
    "__pycache__",
    "site-packages",
)

CHANGED = "changed"
UNCHANGED = "unchanged"
SKIPPED = "skipped"


@dataclass(frozen=True)
class FileReport:
    path: Path
    status: str
    removed: int = 0
    reason: str | None = None
    original: str | None = None
    cleaned: str | None = None
    codec: str = "utf-8"


def _matches(pattern: str, parts: Sequence[str]) -> bool:
    pattern = pattern.replace("\\", "/").strip("/")
    if not pattern:
        return False
    if "/" in pattern:
        joined = "/".join(parts)
        return any(
            fnmatch(joined, candidate)
            for candidate in (pattern, f"*/{pattern}", f"{pattern}/*", f"*/{pattern}/*")
        )
    return any(fnmatch(part, pattern) for part in parts)


def is_excluded(parts: Sequence[str], patterns: Iterable[str]) -> bool:
    return any(_matches(pattern, parts) for pattern in patterns)


def _relative_parts(path: Path, fallback_root: Path) -> tuple[str, ...]:
    absolute = Path(os.path.abspath(path))
    try:
        return absolute.relative_to(Path.cwd()).parts
    except ValueError:
        return absolute.relative_to(Path(os.path.abspath(fallback_root))).parts


def _walk(root: Path, excludes: Sequence[str]) -> list[Path]:
    if is_excluded(_relative_parts(root, root), excludes):
        return []
    found: list[Path] = []
    for directory, subdirectories, filenames in os.walk(root):
        directory_path = Path(directory)
        subdirectories[:] = sorted(
            name
            for name in subdirectories
            if not is_excluded(_relative_parts(directory_path / name, root), excludes)
        )
        for name in sorted(filenames):
            candidate = directory_path / name
            if candidate.suffix == ".py" and not is_excluded(
                _relative_parts(candidate, root), excludes
            ):
                found.append(candidate)
    return found


def collect_files(paths: Iterable[str | Path], excludes: Sequence[str]) -> list[Path]:
    """Expande arquivos e pastas em uma lista de .py, aplicando as exclusões."""
    found: dict[str, Path] = {}
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            candidates = _walk(path, excludes)
        elif path.is_file():
            usable = path.suffix == ".py" and not is_excluded(
                _relative_parts(path, path.parent), excludes
            )
            candidates = [path] if usable else []
        else:
            raise FileNotFoundError(str(raw))
        for candidate in candidates:
            found.setdefault(os.path.abspath(candidate), candidate)
    return list(found.values())


def read_source(path: Path) -> tuple[str, str]:
    """Lê o arquivo sem traduzir quebras de linha. Devolve (texto, codec).

    Em arquivos com BOM o codec é utf-8 e o texto começa com U+FEFF, o que
    permite regravar os mesmos bytes.
    """
    data = path.read_bytes()
    encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
    codec = "utf-8" if encoding == "utf-8-sig" else encoding
    return data.decode(codec), codec


def analyze_file(path: Path, extra_directives: Iterable[str] = ()) -> FileReport:
    """Lê e limpa o arquivo na memória, sem gravar nada."""
    try:
        original, codec = read_source(path)
    except (OSError, SyntaxError, UnicodeDecodeError, LookupError) as error:
        return FileReport(path, SKIPPED, reason=f"não foi possível ler: {error}")

    outcome = clean_source(original, extra_directives)
    if not outcome.accepted:
        return FileReport(path, SKIPPED, reason=outcome.skipped_reason)
    if outcome.text == original:
        return FileReport(path, UNCHANGED)
    return FileReport(
        path,
        CHANGED,
        removed=outcome.removed,
        original=original,
        cleaned=outcome.text,
        codec=codec,
    )


def write_report(report: FileReport) -> None:
    report.path.write_bytes(report.cleaned.encode(report.codec))


def build_diff(report: FileReport) -> str:
    lines = difflib.unified_diff(
        report.original.splitlines(keepends=True),
        report.cleaned.splitlines(keepends=True),
        fromfile=f"a/{report.path.as_posix()}",
        tofile=f"b/{report.path.as_posix()}",
    )
    pieces = []
    for line in lines:
        if line.endswith("\n"):
            pieces.append(line)
        else:
            pieces.append(line + "\n\\ No newline at end of file\n")
    return "".join(pieces)
