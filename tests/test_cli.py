from pathlib import Path

import pytest

from stripcomments.cli import main


def make(path: Path, content: bytes | str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode() if isinstance(content, str) else content)
    return path


@pytest.fixture(autouse=True)
def in_tmp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def run(capsys, *args):
    code = main(list(args))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


class TestDryRun:
    def test_default_does_not_touch_disk(self, capsys):
        path = make(Path("a.py"), "x = 1  # a\n")
        code, out, _ = run(capsys, ".")
        assert code == 0
        assert path.read_bytes() == b"x = 1  # a\n"
        assert "[seria alterado] a.py: 1 comentário" in out
        assert "Dry-run" in out

    def test_dry_run_with_diff_does_not_touch_disk(self, capsys):
        path = make(Path("a.py"), "x = 1  # a\n")
        code, out, _ = run(capsys, "--diff", "a.py")
        assert code == 0
        assert "-x = 1  # a" in out and "+x = 1" in out
        assert path.read_bytes() == b"x = 1  # a\n"


class TestWrite:
    def test_write_changes_files(self, capsys):
        path = make(Path("a.py"), "x = 1  # a\n# b\n")
        code, out, _ = run(capsys, "--write", ".")
        assert code == 0
        assert path.read_text() == "x = 1\n"
        assert "[alterado] a.py: 2 comentários" in out

    def test_second_run_is_idempotent(self, capsys):
        path = make(Path("a.py"), "x = 1  # a\n")
        run(capsys, "--write", ".")
        first = path.read_bytes()
        code, out, _ = run(capsys, "--write", ".")
        assert code == 0
        assert path.read_bytes() == first
        assert "Alterados: 0" in out

    def test_summary_counts(self, capsys):
        make(Path("changed.py"), "x = 1  # a\n# b\n")
        make(Path("clean.py"), "y = 2\n")
        make(Path("broken.py"), "def f(:\n")
        code, out, _ = run(capsys, "--write", ".")
        assert code == 1
        assert "Arquivos analisados: 3" in out
        assert "Alterados: 1" in out
        assert "Sem mudança: 1" in out
        assert "Pulados: 1" in out
        assert "broken.py: arquivo não compila" in out
        assert "Comentários removidos: 2" in out

    def test_dry_run_summary_labels(self, capsys):
        make(Path("a.py"), "x = 1  # a\n")
        _, out, _ = run(capsys, ".")
        assert "A alterar: 1" in out
        assert "Comentários a remover: 1" in out


class TestExclusions:
    def test_migrations_untouched_in_directory_walk(self, capsys):
        migration = make(Path("app/migrations/0001.py"), "x = 1  # a\n")
        make(Path("app/models.py"), "y = 1  # a\n")
        run(capsys, "--write", ".")
        assert migration.read_bytes() == b"x = 1  # a\n"
        assert Path("app/models.py").read_text() == "y = 1\n"

    def test_migrations_untouched_when_passed_explicitly(self, capsys):
        migration = make(Path("app/migrations/0001.py"), "x = 1  # a\n")
        code, out, _ = run(capsys, "--write", "app/migrations/0001.py")
        assert code == 0
        assert migration.read_bytes() == b"x = 1  # a\n"
        assert "Arquivos analisados: 0" in out

    def test_custom_exclude(self, capsys):
        legacy = make(Path("legacy/a.py"), "x = 1  # a\n")
        run(capsys, "--write", "--exclude", "legacy", ".")
        assert legacy.read_bytes() == b"x = 1  # a\n"

    def test_repeated_exclude(self, capsys):
        one = make(Path("one/a.py"), "x = 1  # a\n")
        two = make(Path("two/a.py"), "x = 1  # a\n")
        run(capsys, "--write", "--exclude", "one", "--exclude", "two", ".")
        assert one.read_bytes() == two.read_bytes() == b"x = 1  # a\n"


class TestKeepDirective:
    def test_extra_directive_is_preserved(self, capsys):
        path = make(Path("a.py"), "x = 1  # keepme: sim\ny = 2  # apagar\n")
        run(capsys, "--write", "--keep-directive", "keepme:", "a.py")
        assert path.read_text() == "x = 1  # keepme: sim\ny = 2\n"

    def test_without_flag_it_is_removed(self, capsys):
        path = make(Path("a.py"), "x = 1  # keepme: sim\n")
        run(capsys, "--write", "a.py")
        assert path.read_text() == "x = 1\n"

    def test_empty_directive_is_usage_error(self, capsys):
        make(Path("a.py"), "x = 1\n")
        code, _, err = run(capsys, "--keep-directive", "", "a.py")
        assert code == 2
        assert "vazio" in err


class TestExitCodes:
    def test_skipped_file_gives_exit_1_without_breaking_the_run(self, capsys):
        broken = make(Path("a_broken.py"), "def f(:\n  # x\n")
        good = make(Path("b_good.py"), "x = 1  # a\n")
        code, out, _ = run(capsys, "--write", ".")
        assert code == 1
        assert good.read_text() == "x = 1\n"
        assert broken.read_bytes() == b"def f(:\n  # x\n"
        assert "a_broken.py" in out

    def test_missing_path_is_usage_error(self, capsys):
        code, _, err = run(capsys, "nao_existe")
        assert code == 2
        assert "nao_existe" in err

    def test_no_arguments_is_usage_error(self, capsys):
        code, _, _ = run(capsys)
        assert code == 2

    def test_unknown_flag_is_usage_error(self, capsys):
        code, _, _ = run(capsys, "--inventada", ".")
        assert code == 2

    def test_empty_project_is_success(self, capsys):
        code, out, _ = run(capsys, ".")
        assert code == 0
        assert "Arquivos analisados: 0" in out


class TestCheck:
    def test_check_fails_when_something_to_remove(self, capsys):
        path = make(Path("a.py"), "x = 1  # a\n")
        code, _, _ = run(capsys, "--check", ".")
        assert code == 1
        assert path.read_bytes() == b"x = 1  # a\n"

    def test_check_passes_when_clean(self, capsys):
        make(Path("a.py"), "x = 1\n")
        code, _, _ = run(capsys, "--check", ".")
        assert code == 0

    def test_check_passes_when_only_preserved_comments(self, capsys):
        make(Path("a.py"), "import os  # noqa\n")
        code, _, _ = run(capsys, "--check", ".")
        assert code == 0


def test_multiple_paths(capsys):
    a = make(Path("one/a.py"), "x = 1  # a\n")
    b = make(Path("two/b.py"), "y = 1  # b\n")
    code, _, _ = run(capsys, "--write", "one", "two/b.py")
    assert code == 0
    assert a.read_text() == "x = 1\n" and b.read_text() == "y = 1\n"
