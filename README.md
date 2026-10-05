# stripcomments

Remove os comentários `#` de arquivos Python (`.py`), pensada para limpar código gerado por IA antes do commit em projetos Python/Django.

Por padrão ela **só simula** (dry-run): nada é gravado até você pedir com `--write`.

## Instalação

```
pip install git+https://github.com/SilvioPLopes/stripcommentslib.git
```

Para desenvolvimento (a partir da pasta do projeto):

```
pip install -e ".[dev]"
```

## Uso

```
stripcomments [--write] [--diff] [--exclude padrão] [--keep-directive texto] [--check] caminho
```

`caminho` pode ser um arquivo ou uma pasta (use `.` para o projeto inteiro).

| Opção | O que faz |
|---|---|
| *(nenhuma)* | Dry-run: lista o que seria alterado, sem gravar |
| `--diff` | Mostra o diff unificado do que seria removido |
| `--write` | Grava as alterações |
| `--check` | Sai com código 1 se houver algo a remover (para CI) |
| `--exclude padrão` | Ignora mais caminhos além dos padrão (repetível) |
| `--keep-directive texto` | Preserva também comentários com esse texto (repetível) |

### Fluxo recomendado

```
git switch -c limpeza-comentarios
stripcomments .
stripcomments --diff caminho/do/arquivo.py
stripcomments --write .
```

Trabalhe em uma branch limpa: se algo não agradar, `git restore .` desfaz tudo.

## Exemplo

Antes:

```python
from django.shortcuts import render

# Create your views here.
# comentário comum
x = 1  # comentário no fim da linha
cor = "#fff"  # o # dentro da string deve ficar
y = 2  # noqa
```

Depois:

```python
from django.shortcuts import render

x = 1
cor = "#fff"
y = 2  # noqa
```

## O que é preservado

- Diretivas: `# noqa`, `# type:`, `# pylint:` e similares
- Shebang (`#!...`) e linha de encoding (`# -*- coding: ... -*-`)
- `#` dentro de strings (ex.: `"#fff"`) e docstrings
- Comentários que contenham um texto passado em `--keep-directive`
- Quebras de linha originais (`\r\n` continua `\r\n`)

## O que é ignorado

As pastas `migrations/`, `venv/`, `.venv/`, `env/` e `node_modules/` nunca são analisadas. Use `--exclude` para ignorar outras.

Arquivos que não puderem ser analisados (por exemplo, com erro de sintaxe) são **pulados sem alteração** e aparecem no relatório com o motivo.

## Códigos de saída

| Código | Quando |
|---|---|
| `0` | Tudo certo (com `--check`: nada a remover) |
| `1` | Há arquivos pulados, ou `--check` encontrou comentários a remover |

## Observações

- Rodar `--write` de novo não altera nada (idempotente).
- A linha de um comentário removido some, mas as linhas em branco ao redor permanecem.

## Testes

```
python -m pytest -q
```
