from pathlib import Path

import pytest

from stripcomments.files import (
    CHANGED,
    DEFAULT_EXCLUDES,
    SKIPPED,
    UNCHANGED,
    analyze_file,
    build_diff,
    collect_files,
    write_report,
)


def make(path: Path, content: bytes | str = b"x = 1\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode() if isinstance(content, str) else content)
    return path


def roundtrip(path: Path) -> bytes:
    report = analyze_file(path)
    assert report.status == CHANGED
    write_report(report)
    return path.read_bytes()


class TestReadAndWrite:
    def test_crlf_is_preserved(self, tmp_path):
        path = make(tmp_path / "a.py", b"x = 1  # a\r\n# b\r\ny = 2\r\n")
        assert roundtrip(path) == b"x = 1\r\ny = 2\r\n"

    def test_missing_final_newline_is_preserved(self, tmp_path):
        path = make(tmp_path / "a.py", b"x = 1  # a")
        assert roundtrip(path) == b"x = 1"

    def test_bom_is_preserved(self, tmp_path):
        path = make(tmp_path / "a.py", b"\xef\xbb\xbfx = 1  # a\n")
        assert roundtrip(path) == b"\xef\xbb\xbfx = 1\n"

    def test_declared_encoding_is_respected(self, tmp_path):
        original = b"# -*- coding: latin-1 -*-\nname = 'caf\xe9'  # nota\n"
        path = make(tmp_path / "a.py", original)
        assert roundtrip(path) == b"# -*- coding: latin-1 -*-\nname = 'caf\xe9'\n"

    def test_utf8_accents_are_preserved(self, tmp_path):
        path = make(tmp_path / "a.py", "nome = 'ação'  # nota\n")
        assert roundtrip(path) == "nome = 'ação'\n".encode()

    def test_report_for_changed_file(self, tmp_path):
        path = make(tmp_path / "a.py", "x = 1  # a\n# b\n")
        report = analyze_file(path)
        assert report.status == CHANGED
        assert report.removed == 2
        assert report.cleaned == "x = 1\n"

    def test_analyze_does_not_write(self, tmp_path):
        path = make(tmp_path / "a.py", "x = 1  # a\n")
        analyze_file(path)
        assert path.read_bytes() == b"x = 1  # a\n"

    def test_file_without_comments_is_unchanged(self, tmp_path):
        path = make(tmp_path / "a.py", "x = 1\n")
        assert analyze_file(path).status == UNCHANGED

    def test_preserved_comment_only_file_is_unchanged(self, tmp_path):
        path = make(tmp_path / "a.py", "import os  # noqa\n")
        assert analyze_file(path).status == UNCHANGED


class TestSkippedFiles:
    def test_syntax_error_is_skipped_and_untouched(self, tmp_path):
        path = make(tmp_path / "a.py", "def f(:\n  # x\n")
        report = analyze_file(path)
        assert report.status == SKIPPED
        assert "não compila" in report.reason
        assert path.read_bytes() == b"def f(:\n  # x\n"

    def test_undecodable_file_is_skipped(self, tmp_path):
        path = make(tmp_path / "a.py", b"x = '\xff'  # a\n")
        report = analyze_file(path)
        assert report.status == SKIPPED
        assert "não foi possível ler" in report.reason

    def test_invalid_encoding_declaration_is_skipped(self, tmp_path):
        path = make(tmp_path / "a.py", b"# coding: nao-existe\nx = 1  # a\n")
        assert analyze_file(path).status == SKIPPED

    def test_missing_file_is_skipped(self, tmp_path):
        assert analyze_file(tmp_path / "nada.py").status == SKIPPED


class TestCollectFiles:
    @pytest.fixture
    def project(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        for name in (
            "app/models.py",
            "app/migrations/0001_initial.py",
            "nested/deep/util.py",
            "venv/lib/mod.py",
            ".venv/lib/mod.py",
            "env/mod.py",
            ".git/hooks/hook.py",
            "node_modules/pkg/tool.py",
            "app/__pycache__/models.py",
            "libs/site-packages/dep.py",
            "app/legacy/old.py",
            "app/schema_pb2.py",
            "notes.txt",
        ):
            make(tmp_path / name)
        return tmp_path

    def names(self, files):
        return sorted(Path(f).as_posix() for f in files)

    def test_default_excludes_in_directory_walk(self, project):
        files = collect_files(["."], DEFAULT_EXCLUDES)
        assert self.names(files) == [
            "app/legacy/old.py",
            "app/models.py",
            "app/schema_pb2.py",
            "nested/deep/util.py",
        ]

    def test_default_excludes_apply_to_explicit_files(self, project):
        files = collect_files(
            ["app/migrations/0001_initial.py", "venv/lib/mod.py", "app/models.py"],
            DEFAULT_EXCLUDES,
        )
        assert self.names(files) == ["app/models.py"]

    def test_custom_name_exclude(self, project):
        files = collect_files(["."], DEFAULT_EXCLUDES + ("legacy",))
        assert "app/legacy/old.py" not in self.names(files)

    def test_custom_glob_exclude(self, project):
        files = collect_files(["."], DEFAULT_EXCLUDES + ("*_pb2.py",))
        assert "app/schema_pb2.py" not in self.names(files)

    def test_custom_path_exclude(self, project):
        files = collect_files(["."], DEFAULT_EXCLUDES + ("app/legacy",))
        assert "app/legacy/old.py" not in self.names(files)
        assert "app/models.py" in self.names(files)

    def test_non_py_explicit_file_is_ignored(self, project):
        assert collect_files(["notes.txt"], DEFAULT_EXCLUDES) == []

    def test_duplicates_are_collapsed(self, project):
        files = collect_files(["app/models.py", "app", "./app/models.py"], DEFAULT_EXCLUDES)
        assert self.names(files).count("app/models.py") == 1

    def test_missing_path_raises(self, project):
        with pytest.raises(FileNotFoundError):
            collect_files(["nao_existe"], DEFAULT_EXCLUDES)

    def test_project_inside_folder_named_env_is_not_excluded(self, tmp_path, monkeypatch):
        project = tmp_path / "env" / "proj"
        make(project / "a.py")
        elsewhere = tmp_path / "outro"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)
        assert len(collect_files([project], DEFAULT_EXCLUDES)) == 1
        assert len(collect_files([project / "a.py"], DEFAULT_EXCLUDES)) == 1


class TestDiff:
    def test_unified_diff(self, tmp_path):
        path = make(tmp_path / "a.py", "x = 1  # a\ny = 2\n")
        diff = build_diff(analyze_file(path))
        assert "--- a/" in diff and "+++ b/" in diff
        assert "-x = 1  # a" in diff
        assert "+x = 1\n" in diff

    def test_diff_marks_missing_final_newline(self, tmp_path):
        path = make(tmp_path / "a.py", "x = 1  # a")
        assert "\\ No newline at end of file" in build_diff(analyze_file(path))
