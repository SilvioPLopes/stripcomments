import sys
import textwrap

import pytest

from stripcomments import DEFAULT_DIRECTIVES, strip_comments


def clean(source: str, *extra: str) -> str:
    return strip_comments(source, extra).text


def code(source: str) -> str:
    return textwrap.dedent(source).lstrip("\n")


class TestHashInsideStrings:
    def test_simple_strings(self):
        source = 'a = "cor: #fff"\nb = \'cor: #000\'\n'
        assert clean(source) == source

    def test_triple_quoted_string(self):
        source = 'texto = """linha 1\n# nao e comentario\nlinha 3"""\n'
        assert clean(source) == source

    def test_fstring(self):
        source = 'a = f"cor: #{valor}"\nb = f\'{valor} # fim\'\n'
        assert clean(source) == source

    def test_string_with_hash_followed_by_real_comment(self):
        assert clean('a = "#fff"  # nota\n') == 'a = "#fff"\n'

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="PEP 701")
    def test_comment_inside_multiline_fstring_field(self):
        source = 'a = f"{\n    valor  # nota\n}"\n'
        assert clean(source) == 'a = f"{\n    valor\n}"\n'


class TestRemoval:
    def test_full_line_comment_removes_the_whole_line(self):
        source = code(
            """
            # cabecalho
            x = 1
            # meio
            y = 2
            """
        )
        assert clean(source) == "x = 1\ny = 2\n"

    def test_indented_full_line_comment_is_removed(self):
        source = code(
            """
            def f():
                # explica
                return 1
            """
        )
        assert clean(source) == "def f():\n    return 1\n"

    def test_trailing_comment_removes_preceding_spaces(self):
        assert clean("x = 1  # nota\n") == "x = 1\n"

    def test_trailing_comment_removes_preceding_tabs(self):
        assert clean("x = 1\t\t# nota\n") == "x = 1\n"

    def test_comment_without_space_after_hash(self):
        assert clean("x = 1  #nota\n") == "x = 1\n"

    def test_other_formatting_is_untouched(self):
        source = "x   =   [1,2,\t3]  # nota\ny=(  4 )\n"
        assert clean(source) == "x   =   [1,2,\t3]\ny=(  4 )\n"

    def test_counts_removed_comments(self):
        source = "# a\nx = 1  # b\n# noqa\ny = 2\n"
        result = strip_comments(source)
        assert result.removed == 2
        assert result.text == "x = 1\n# noqa\ny = 2\n"

    def test_source_without_comments_is_returned_unchanged(self):
        source = "x = 1\n\n\ndef f():\n    return 2\n"
        result = strip_comments(source)
        assert result.text == source
        assert result.removed == 0

    def test_empty_source(self):
        assert strip_comments("").text == ""


class TestMultilineBrackets:
    def test_comments_inside_brackets_parentheses_and_braces(self):
        source = code(
            """
            lista = [
                1,  # um
                # separado
                2,
            ]
            tupla = (
                3,  # tres
                4,
            )
            mapa = {
                "a": 1,  # a
                # b
                "b": 2,
            }
            """
        )
        expected = code(
            """
            lista = [
                1,
                2,
            ]
            tupla = (
                3,
                4,
            )
            mapa = {
                "a": 1,
                "b": 2,
            }
            """
        )
        assert clean(source) == expected

    def test_comment_after_opening_bracket(self):
        assert clean("x = [  # abre\n    1,\n]\n") == "x = [\n    1,\n]\n"


class TestShebangAndEncoding:
    def test_shebang_on_first_line_is_preserved(self):
        source = "#!/usr/bin/env python\n# nota\nx = 1\n"
        assert clean(source) == "#!/usr/bin/env python\nx = 1\n"

    def test_shebang_after_first_line_is_a_regular_comment(self):
        assert clean("x = 1\n#!/usr/bin/env python\n") == "x = 1\n"

    @pytest.mark.parametrize(
        "line",
        ["# -*- coding: utf-8 -*-", "# coding=latin-1", "# vim: set fileencoding=utf-8 coding: utf-8"],
    )
    def test_encoding_line_on_first_line_is_preserved(self, line):
        assert clean(f"{line}\nx = 1  # nota\n") == f"{line}\nx = 1\n"

    def test_encoding_line_on_second_line_after_shebang(self):
        source = "#!/usr/bin/python\n# -*- coding: utf-8 -*-\n# nota\nx = 1\n"
        assert clean(source) == "#!/usr/bin/python\n# -*- coding: utf-8 -*-\nx = 1\n"

    def test_encoding_line_on_third_line_is_removed(self):
        source = "x = 1\ny = 2\n# coding: utf-8\n"
        assert clean(source) == "x = 1\ny = 2\n"

    def test_trailing_comment_that_looks_like_encoding_is_removed(self):
        assert clean("x = 1  # coding: utf-8\n") == "x = 1\n"


class TestDirectives:
    @pytest.mark.parametrize("directive", DEFAULT_DIRECTIVES)
    def test_every_default_directive_is_preserved(self, directive):
        comment = f"# {directive} valor" if directive == "type:" else f"# nota {directive}x"
        source = f"x = 1  {comment}\n"
        assert clean(source) == source

    @pytest.mark.parametrize(
        "line",
        [
            "import os  # noqa",
            "import os  # noqa: F401",
            "x = []  # type: list[int]",
            "y = f()  # type: ignore[attr-defined]",
            "z = 1  # pylint: disable=invalid-name",
            "# fmt: off",
            "# fmt: on",
            "def f():  # pragma: no cover",
            "x = 1  # flake8: noqa",
            "x = 1  # mypy: ignore-errors",
            "x = 1  # pyright: ignore",
            "x = 1  # ruff: noqa",
            "import b  # isort: skip",
            "x = 1  # nosec",
            "x = 1  # pytype: disable=attribute-error",
        ],
    )
    def test_directive_comments_are_kept_whole(self, line):
        source = f"{line}\n"
        assert clean(source) == source

    def test_directive_in_the_middle_of_comment_keeps_the_whole_comment(self):
        source = "x = 1  # codigo legado, noqa por enquanto\n"
        assert clean(source) == source

    def test_type_directive_only_counts_at_the_start(self):
        assert clean("x = 1  # isto nao e type: int\n") == "x = 1\n"

    def test_type_directive_without_space_after_hash(self):
        source = "x = 1  #type: int\n"
        assert clean(source) == source

    def test_directive_match_is_case_sensitive(self):
        assert clean("x = 1  # NOQA\n") == "x = 1\n"
        assert clean("x = 1  # Type: int\n") == "x = 1\n"

    def test_full_line_directive_is_kept(self):
        source = "# pylint: disable=all\nx = 1\n"
        assert clean(source) == source

    def test_extra_directive_is_preserved(self):
        source = "x = 1  # keepme\ny = 2  # outro\n"
        assert clean(source, "keepme") == "x = 1  # keepme\ny = 2\n"


class TestDocstringsAndStrings:
    def test_module_class_and_function_docstrings_are_intact(self):
        source = code(
            '''
            """Modulo # com hash."""
            # nota


            class Foo:
                """Classe.

                # nao e comentario
                """
                # nota

                def bar(self):
                    """Funcao # com hash."""  # nota
                    return 1
            '''
        )
        expected = code(
            '''
            """Modulo # com hash."""


            class Foo:
                """Classe.

                # nao e comentario
                """

                def bar(self):
                    """Funcao # com hash."""
                    return 1
            '''
        )
        assert clean(source) == expected

    def test_multiline_string_assignment_is_intact(self):
        source = 'sql = """\nSELECT 1 -- x\n# y\n"""  # nota\n'
        assert clean(source) == 'sql = """\nSELECT 1 -- x\n# y\n"""\n'


class TestLineEndingsAndBom:
    def test_crlf_is_preserved(self):
        source = "# a\r\nx = 1  # b\r\ny = 2\r\n"
        assert clean(source) == "x = 1\r\ny = 2\r\n"

    def test_crlf_with_multiline_string_and_brackets(self):
        source = 'x = [\r\n    1,  # a\r\n]\r\ns = """a\r\n#b\r\n"""\r\n'
        assert clean(source) == 'x = [\r\n    1,\r\n]\r\ns = """a\r\n#b\r\n"""\r\n'

    def test_no_final_newline_with_trailing_comment(self):
        assert clean("x = 1  # nota") == "x = 1"

    def test_no_final_newline_without_comment(self):
        assert clean("x = 1") == "x = 1"

    def test_no_final_newline_with_last_line_comment(self):
        assert clean("x = 1\n# fim") == "x = 1"

    def test_final_newline_is_kept(self):
        assert clean("x = 1  # nota\n") == "x = 1\n"

    def test_only_comments(self):
        assert clean("# a\n# b\n") == ""

    def test_bom_is_preserved(self):
        assert clean("\ufeff# nota\nx = 1  # b\n") == "\ufeffx = 1\n"

    def test_bom_with_shebang(self):
        source = "\ufeff#!/usr/bin/env python\nx = 1\n"
        assert clean(source) == source

    def test_bom_with_crlf_and_no_final_newline(self):
        assert clean("\ufeff# a\r\nx = 1  # b") == "\ufeffx = 1"


class TestIdempotence:
    def test_second_run_changes_nothing(self):
        source = code(
            '''
            #!/usr/bin/env python
            # -*- coding: utf-8 -*-
            """Doc # x."""
            import os  # noqa
            # comentario
            x = [
                1,  # um
                2,
            ]  # fim
            y = "#fff"  # cor
            z = 1  # type: int
            '''
        )
        first = strip_comments(source)
        second = strip_comments(first.text)
        assert second.text == first.text
        assert second.removed == 0
