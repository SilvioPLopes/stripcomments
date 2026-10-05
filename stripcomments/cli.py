import argparse
import sys
from typing import Sequence

from .files import (
    CHANGED,
    DEFAULT_EXCLUDES,
    SKIPPED,
    UNCHANGED,
    FileReport,
    analyze_file,
    build_diff,
    collect_files,
    write_report,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stripcomments",
        description="Remove comentários # de arquivos .py. Por padrão apenas simula (dry-run).",
    )
    parser.add_argument("paths", nargs="+", metavar="caminho", help="arquivo ou pasta")
    parser.add_argument("--write", action="store_true", help="grava as alterações")
    parser.add_argument("--diff", action="store_true", help="mostra o diff unificado")
    parser.add_argument(
        "--exclude", action="append", default=[], metavar="padrão",
        help="padrão extra para ignorar (repetível)",
    )
    parser.add_argument(
        "--keep-directive", action="append", default=[], metavar="texto",
        help="diretiva extra a preservar (repetível)",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="sai com código 1 se houver algo a remover (para CI)",
    )
    return parser


def _parse(parser: argparse.ArgumentParser, argv: Sequence[str] | None):
    args = parser.parse_args(argv)
    if any(not directive.strip() for directive in args.keep_directive):
        parser.error("--keep-directive não aceita texto vazio")
    return args


def _make_output_tolerant() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass


def _plural(count: int) -> str:
    return "comentário" if count == 1 else "comentários"


def _print_summary(reports: list[FileReport], write: bool) -> int:
    changed = [r for r in reports if r.status == CHANGED]
    unchanged = [r for r in reports if r.status == UNCHANGED]
    skipped = [r for r in reports if r.status == SKIPPED]
    removed = sum(r.removed for r in changed)

    print()
    print("Relatório")
    print(f"  Arquivos analisados: {len(reports)}")
    print(f"  {'Alterados' if write else 'A alterar'}: {len(changed)}")
    print(f"  Sem mudança: {len(unchanged)}")
    print(f"  Pulados: {len(skipped)}")
    for report in skipped:
        print(f"    - {report.path}: {report.reason}")
    print(f"  Comentários {'removidos' if write else 'a remover'}: {removed}")
    if not write and changed:
        print()
        print("Dry-run: nada foi gravado. Use --write para aplicar.")
    return len(skipped)


def main(argv: Sequence[str] | None = None) -> int:
    _make_output_tolerant()
    parser = build_parser()
    try:
        args = _parse(parser, argv)
    except SystemExit as exit_request:
        return exit_request.code if isinstance(exit_request.code, int) else 2

    try:
        files = collect_files(args.paths, DEFAULT_EXCLUDES + tuple(args.exclude))
    except FileNotFoundError as error:
        print(f"erro: caminho não encontrado: {error}", file=sys.stderr)
        return 2

    print("Modo: gravação" if args.write else "Modo: dry-run (nada será gravado)")
    reports: list[FileReport] = []
    for file in files:
        report = analyze_file(file, args.keep_directive)
        if report.status == CHANGED and args.write:
            try:
                write_report(report)
            except OSError as error:
                report = FileReport(file, SKIPPED, reason=f"falha ao gravar: {error}")
        if report.status == CHANGED:
            label = "alterado" if args.write else "seria alterado"
            print(f"[{label}] {report.path}: {report.removed} {_plural(report.removed)}")
            if args.diff:
                print(build_diff(report), end="")
        reports.append(report)

    skipped_count = _print_summary(reports, args.write)
    if skipped_count:
        return 1
    if args.check and any(r.status == CHANGED for r in reports):
        return 1
    return 0
