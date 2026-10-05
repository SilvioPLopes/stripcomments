# Roteiro de testes: validar o stripcomments em um projeto real

Faça na ordem. Se algum passo falhar, pare e me envie a saída completa.
Os comandos funcionam no PowerShell e no Git Bash. Onde muda, está indicado.

## 0. Preparação

1. Abra o terminal na pasta da biblioteca (onde está o `pyproject.toml`).
2. Instale (de preferência em um ambiente virtual):
   ```
   pip install -e ".[dev]"
   ```
3. Confirme que o comando existe:
   ```
   stripcomments --help
   ```
   Esperado: texto de ajuda com `--write`, `--diff`, `--exclude`, `--keep-directive`, `--check`.
4. Rode a suíte da biblioteca:
   ```
   python -m pytest -q
   ```
   Esperado: tudo verde. (A pasta de testes precisa se chamar `tests`.)

## 1. Prepare o projeto Django (seguro contra erros)

Entre na pasta do projeto Django (não na da biblioteca) e rode:

```
git status
git switch -c limpeza-comentarios
```

- `git status` deve estar limpo (sem alterações pendentes). Se não estiver, faça commit ou stash antes.
- A branch nova permite descartar tudo com facilidade se algo não agradar.
- Antes de limpar, confirme que o projeto funciona e guarde o resultado:
  ```
  python manage.py check
  python manage.py test
  ```
  Anote se algum teste já falhava antes. Isso não é culpa da limpeza.

## 2. Dry-run (não grava nada)

```
stripcomments .
```

Esperado:
- Primeira linha: `Modo: dry-run (nada será gravado)`.
- Uma linha `[seria alterado] caminho: N comentários` por arquivo.
- Bloco `Relatório` com analisados, a alterar, sem mudança, pulados e total.
- Nenhum arquivo foi modificado: `git status` continua limpo.

Verifique:
- [ ] `git status` está limpo.
- [ ] Nenhum arquivo de `migrations/`, `venv/`, `.venv/`, `env/`, `node_modules/` aparece na lista.
- [ ] O total de comentários parece plausível para o tamanho do projeto.

## 3. Veja o diff de um arquivo

Escolha um arquivo com bastante comentário:

```
stripcomments --diff caminho/do/arquivo.py
```

Verifique:
- [ ] Linhas com `-` são só comentários (ou código + comentário, onde o código reaparece com `+` sem o comentário).
- [ ] Nenhum código foi apagado.
- [ ] Comentários `# noqa`, `# type:`, `# pylint:` etc. continuam lá.
- [ ] `#` dentro de string (ex.: cores `"#fff"`) continua lá.
- [ ] Shebang (`#!...`) e linha de encoding (`# -*- coding... -*-`) continuam lá.

Para ver tudo de uma vez: `stripcomments --diff .` (pode ser longo).

## 4. Pulados

No relatório, veja a linha `Pulados`. Cada arquivo pulado traz o motivo (por exemplo, erro de sintaxe no arquivo original). Pulados **não são alterados** e fazem o comando sair com código 1. Anote os motivos.

Para ver o código de saída:
- PowerShell: `echo $LASTEXITCODE`
- Git Bash: `echo $?`

## 5. Gravar (`--write`)

```
stripcomments --write .
```

Esperado: linhas `[alterado] ...` e `Relatório` com `Alterados` igual ao `A alterar` do passo 2.

## 6. Conferir que nada quebrou

```
git diff --stat
git status
```

- [ ] Só arquivos `.py` foram alterados.
- [ ] Nenhum arquivo dentro de `migrations/` aparece:
  - PowerShell: `git status --short | Select-String migrations`
  - Git Bash: `git status --short | grep migrations`
  Esperado: nenhuma linha.
- [ ] O projeto ainda funciona:
  ```
  python manage.py check
  python manage.py test
  ```
  Resultado igual ao do passo 1.
- [ ] Todos os arquivos compilam: `python -m compileall -q .`
- [ ] Abra 2 ou 3 arquivos no editor e confira a olho: código intacto, docstrings intactas, sem linhas em branco estranhas onde havia comentários.

## 7. Idempotência e modo CI

```
stripcomments .
```
Esperado: `A alterar: 0` e código de saída 0 (a menos que haja pulados).

```
stripcomments --check .
```
Esperado: código de saída 0 (nada a remover).

Para ver o `--check` falhando: adicione `x = 1  # teste` a um arquivo qualquer e rode de novo. Esperado: código de saída 1. Desfaça a alteração depois.

## 8. Quebras de linha e codificação (opcional, se o projeto tiver)

Arquivos com `\r\n` (Windows) devem continuar com `\r\n`. Confira no diff do Git: o Git não deve mostrar o arquivo inteiro como alterado, só as linhas de comentário.

## 9. Diretiva própria (opcional)

```
stripcomments --keep-directive "TODO-GESTOR:" .
```
Comentários contendo `TODO-GESTOR:` devem ser preservados.

## 10. Se algo deu errado

Descarte tudo e volte ao estado original:
```
git restore .
git switch -
```

Ao me reportar um problema, envie: o comando usado, a saída do relatório, o arquivo afetado (antes/depois) e o resultado de `python manage.py check`.
