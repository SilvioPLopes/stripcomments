DEFAULT_DIRECTIVES: tuple[str, ...] = (
    "noqa",
    "type:",
    "pylint:",
    "flake8:",
    "mypy:",
    "pyright:",
    "ruff:",
    "isort:",
    "fmt:",
    "pragma:",
    "nosec",
    "pytype:",
)

START_ONLY_DIRECTIVES: frozenset[str] = frozenset({"type:"})
