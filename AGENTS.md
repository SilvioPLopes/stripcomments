# stripcomments: contexto para agentes de IA

> **Leia este arquivo inteiro antes de mexer em qualquer coisa.**
> **Atualize-o ao final de cada lote e a cada decisão nova** (seções 5, 6, 7 e 8).
> Se algo aqui contradiz o código, o código é a verdade: corrija este arquivo.

## 1. Objetivo

Biblioteca Python com interface de linha de comando que remove comentários `#`
de arquivos `.py` de projetos Django. Motivo: o código da empresa é escrito com
ajuda de IA, que enche os arquivos de comentários; o gestor quer tudo limpo
antes do commit e também no repositório já existente.

## 2. Regras de negócio (definidas pelo gestor)

- TODOS os comentários `#` são removidos. Não existe "comentário útil".
- Única exceção: o que, se removido, quebra ou altera o comportamento do código
  ou das ferramentas que o leem:
  - shebang (`#!...`) na linha 1;
  - linha de encoding (`# -*- coding: ... -*-`, `# coding=...`) nas linhas 1 ou 2;
  - comentários de diretiva de ferramenta (lista em `stripcomments/directives.py`).
- Regra das diretivas: se o comentário contém uma diretiva da lista em qualquer
  posição, ele é preservado inteiro. Exceção: `type:` só vale no início do
  comentário. Comparação sensível a maiúsculas e minúsculas.
- Docstrings e qualquer string ficam intactas. Docstrings são código (`__doc__`).
- Fora de escopo: templates HTML, JS, CSS, outras linguagens, remoção de docstrings.
- Não adicionar funcionalidades, flags ou configurações fora do que está
  descrito aqui ou pedido pelo usuário.

## 3. Requisitos técnicos

### 3.1 Como remover
- Usar `tokenize` da biblioteca padrão. NÃO usar regex para achar comentários
  (um `#` dentro de string, como `"cor: #fff"`, não é comentário).
- NÃO usar `tokenize.untokenize`. Coletar a posição (linha, coluna) dos tokens
  COMMENT e cortar o texto original nessas posições.
- Comentário no fim de linha: remover o comentário e os espaços antes dele.
- Linha só de comentário: remover a linha inteira.
- Preservar o tipo de quebra de linha (`\n` ou `\r\n`), a presença ou ausência
  de newline final e o BOM.
- Ler e gravar respeitando a codificação do arquivo (`tokenize.detect_encoding`).

### 3.2 Validação de segurança (Lote 2)
Por arquivo, antes de gravar: comparar `ast.dump(ast.parse(original))` com
`ast.dump(ast.parse(limpo))`. Iguais: aceito. Diferentes, ilegível ou não
compilável: pular o arquivo, não gravar nada e listá-lo no relatório com o motivo.

### 3.3 Interface de linha de comando (Lote 3)
`stripcomments <caminho> [<caminho> ...]`; o caminho é arquivo ou pasta
(recursivo, só `.py`).

- Padrão: DRY-RUN. Não grava; mostra os arquivos que seriam alterados e quantos
  comentários seriam removidos em cada um.
- `--write`: grava. `--diff`: mostra o diff unificado.
- `--exclude <padrão>` (repetível): padrões extras para ignorar.
- Ignorados por padrão: `migrations/`, `.git/`, `venv/`, `.venv/`, `env/`,
  `node_modules/`, `__pycache__/`, `site-packages/`.
- As exclusões valem também para arquivos passados explicitamente (necessário
  para o pre-commit).
- `--keep-directive <texto>` (repetível): adiciona diretivas à lista de preservação.
- `--check` (opcional): sai com 1 se houver algo a remover (CI).
- Relatório final: arquivos analisados, alterados, sem mudança, pulados (com
  motivo) e total de comentários removidos.
- Código de saída: 0 sucesso; 1 se algum arquivo foi pulado; 2 erro de uso.

### 3.4 Integração com o commit (Lote 4)
- `.pre-commit-hooks.yaml` e exemplo de configuração do `pre-commit` rodando nos
  `.py` staged com `--write`.
- README explicando o uso e como rodar uma vez no repositório inteiro, em um
  commit separado para facilitar a revisão.

## 4. Testes obrigatórios (resumo)

`#` em string simples, tripla e f-string; comentário de linha inteira e de fim
de linha; shebang e encoding; cada diretiva da lista; docstrings de módulo,
classe e função; `\r\n`, sem newline final e BOM; erro de sintaxe (pula e lista,
sem quebrar); comentário dentro de colchetes, parênteses e chaves multilinha;
idempotência; dry-run não altera disco; integração com mini projeto Django com
pasta `migrations/` intocada; suíte em pelo menos duas versões do Python
(`tokenize` mudou no 3.12, f-strings). Cada lote implementa só os testes dos
itens que cobre.

## 5. Arquitetura atual

```
stripcomments/                  raiz do projeto
├── AGENTS.md                   este arquivo (contexto vivo)
├── pyproject.toml              metadados, entry point, config do pytest
├── ROTEIRO_DE_TESTES.md        roteiro de validação em projeto real (Lote 3)
├── stripcomments/              o pacote
│   ├── __init__.py             exporta strip_comments, StripResult, DEFAULT_DIRECTIVES
│   ├── core.py                 strip_comments (Lote 1)
│   ├── directives.py           DEFAULT_DIRECTIVES e START_ONLY_DIRECTIVES
│   ├── validation.py           clean_source e CleanOutcome (Lote 2)
│   ├── files.py                varredura, leitura/escrita, FileReport, diff (Lote 3)
│   └── cli.py                  main(argv) -> int (Lote 3)
└── tests/
    ├── __init__.py
    ├── test_core.py            testes do núcleo (Lote 1)
    ├── test_validation.py      testes da validação por AST (Lote 2)
    ├── test_files.py           testes da camada de arquivos (Lote 3)
    └── test_cli.py             testes da CLI (Lote 3)
```

Arquivos previstos nos próximos lotes (nomes podem mudar; atualize esta árvore):
`.pre-commit-hooks.yaml` e `README.md` (Lote 4).

### API pública atual
```python
strip_comments(source: str, extra_directives: Iterable[str] = ()) -> StripResult
StripResult(text: str, removed: int)   # dataclass congelada
```
- `removed` conta só os comentários realmente removidos (preservados não contam).
- Exceções do `tokenize` NÃO são capturadas em `strip_comments`; quem chama
  trata. Quem trata é `clean_source` (Lote 2).

```python
clean_source(source: str, extra_directives: Iterable[str] = ()) -> CleanOutcome
CleanOutcome(text: str | None, removed: int, skipped_reason: str | None)  # congelada
CleanOutcome.accepted  # True quando skipped_reason is None
```
- `clean_source` é o ponto de entrada da camada de arquivos (Lote 3): ela só
  trabalha com `str` (decodificação/BOM/gravação ficam no Lote 3).
- Arquivo pulado: `text=None`, `removed=0`, `skipped_reason` em português.

### API da camada de arquivos (`stripcomments/files.py`)
```python
DEFAULT_EXCLUDES: tuple[str, ...]
collect_files(paths, excludes) -> list[Path]      # FileNotFoundError se o caminho não existe
analyze_file(path, extra_directives=()) -> FileReport   # não grava
write_report(report) -> None
build_diff(report) -> str
FileReport(path, status, removed, reason, original, cleaned, codec)  # status: CHANGED | UNCHANGED | SKIPPED
```
`stripcomments.cli.main(argv=None) -> int` devolve o código de saída (o entry
point do `pyproject.toml` já aponta para ela).

- `validation` não é reexportado em `__init__.py` (o Lote 1 não foi alterado);
  importar de `stripcomments.validation`.

## 6. Decisões de projeto

Origem: **[plano]** vem do documento original; **[usuário]** foi decidido pelo
usuário depois; **[agente]** foi decidido pelo agente onde o plano deixou margem.

1. **[usuário]** A biblioteca PODE ter comentários `#`. A regra original do plano
   ("o código da biblioteca não deve conter comentários") foi revogada. Mesmo
   assim, prefira nomes claros e use comentário só onde ajudar de verdade.
2. **[plano]** Apenas biblioteca padrão em runtime; `pytest` só em desenvolvimento.
   Type hints nas funções públicas. Docstrings curtas e só onde necessárias.
3. **[agente]** `requires-python = ">=3.10"` (o 3.9 saiu de suporte). Ajustar se o
   projeto do usuário usar outra versão.
4. **[agente]** `strip_comments` devolve `StripResult(text, removed)`; a CLI
   precisa da contagem para o relatório.
5. **[agente]** BOM: `strip_comments` aceita `\ufeff` no início e o devolve
   intacto. A camada de arquivos (Lote 3) decide como detectar e regravar o BOM
   (pista: `detect_encoding` devolve `utf-8-sig` quando há BOM).
6. **[agente]** Linha de encoding: linhas 1 ou 2 conforme o plano, com a regex do
   PEP 263. É a única regex da biblioteca e não serve para achar comentários.
7. **[agente]** Última linha só de comentário em arquivo sem newline final:
   `"x = 1\n# fim"` vira `"x = 1"` (a ausência de newline final é mantida).
8. **[agente]** `--keep-directive "type:"` herda a regra de "só no início do
   comentário", porque `type:` está em `START_ONLY_DIRECTIVES`.
9. **[agente]** A suíte nas duas versões do Python (requisito da seção 4) fica
   para o Lote 4, como workflow de CI com matriz (ex.: 3.10 e 3.13). Nos lotes
   anteriores a suíte é rodada manualmente em 3.11, 3.12 e 3.13.
10. **[agente]** `clean_source` valida em 3 etapas, cada uma com motivo próprio:
    (a) original não compila; (b) falha ao remover comentários (`TokenError`,
    `SyntaxError`, `ValueError`); (c) resultado não compila ou AST diferente.
    `ast.dump` padrão ignora posições e `type_comments` fica desligado, então
    só mudança real de código reprova.
11. **[agente]** BOM: `ast.parse` rejeita `\ufeff` no início de uma `str`
    ("invalid non-printable character"). `validation._parse` remove o BOM só
    para gerar a AST; o texto devolvido mantém o BOM.

12. **[agente]** Leitura em bytes (`read_bytes` + `decode`), sem tradução de
    quebras de linha: `\r\n` e a ausência de newline final voltam idênticos.
    BOM: codec `utf-8` e o texto mantém o `\ufeff` inicial, regravando os mesmos bytes.
13. **[agente]** Exclusões: padrão sem `/` casa com qualquer componente do caminho
    (`fnmatch`); padrão com `/` casa com o caminho inteiro ou um trecho dele.
    Os componentes são medidos a partir do diretório atual (ou, se o alvo estiver
    fora dele, a partir da pasta passada), para um projeto dentro de uma pasta
    chamada `env` não ser excluído por inteiro.
14. **[agente]** Arquivo explícito que não é `.py` é ignorado em silêncio;
    caminho inexistente é erro de uso (código 2).
15. **[agente]** `--check` sai com 1 se algum arquivo mudaria (ou mudou, se
    combinado com `--write`). Arquivo pulado sempre dá 1.
16. **[agente]** `--keep-directive ""` (vazio) é erro de uso (código 2), porque
    preservaria todos os comentários.
17. **[agente]** Saída tolerante: `stdout`/`stderr` usam `errors="replace"` para
    não quebrar em consoles Windows com caracteres não codificáveis.
18. **[agente]** Contagem do relatório: `removed` soma só arquivos alterados;
    pulados são listados com o motivo no próprio relatório final.

## 7. Fluxo de trabalho com o usuário

- Trabalho em lotes, na ordem. Faça SOMENTE o lote pedido e PARE.
- Só avance quando o usuário escrever "continuar".
- Ao terminar um lote: rode os testes dele e informe o que foi feito, o
  resultado dos testes, as decisões tomadas e qual é o próximo lote.
- Não adiante trabalho de lotes futuros. Não altere arquivos de lotes
  anteriores, exceto para corrigir erro (diga qual e por quê).
- Responder em português.
- O usuário vai validar a biblioteca em um projeto real. O roteiro de testes
  precisa ser claro e passo a passo (ver seção 9).
- Ao entregar, mostrar a árvore de arquivos do projeto.

## 8. Status dos lotes

| Lote | Conteúdo | Status |
|------|----------|--------|
| 1 | Estrutura, `strip_comments`, testes do núcleo | Concluído (70 testes passando em 3.12 e 3.13; 69 + 1 pulado em 3.11) |
| 2 | Validação por AST + testes | Concluído (14 testes em 3.12; ver nota abaixo) |
| 3 | Camada de arquivos + CLI + testes | Concluído (60 testes na suíte completa em 3.12, com núcleo temporário; confirmar com o `core.py` real) |
| 4 | Pre-commit, README, integração Django, CI | Pendente |

## 9. Pendências e combinados com o usuário

- [x] Fim do Lote 3 (entregue `ROTEIRO_DE_TESTES.md`; falta o usuário executar): entregar `ROTEIRO_DE_TESTES.md`, claro e passo a passo, para
      o usuário validar em um projeto real (dry-run, `--diff`, `--write`,
      conferência de que `migrations/` ficou intocada e de que o projeto continua
      funcionando). Antes do Lote 3 não há CLI, então não há o que testar além da
      suíte `pytest`.
- [ ] Lote 4: README com como usar (instalação, comandos, flags, códigos de saída,
      pre-commit, rodar uma vez no repositório inteiro em commit separado) e
      referência ao roteiro de testes.
- [ ] Manter este arquivo atualizado a cada lote.

## 10. Como rodar os testes

```bash
pip install -e ".[dev]"
python -m pytest -q
```

## 11. Histórico de alterações

- **Lote 3**: criados `stripcomments/{files,cli}.py`, `tests/test_{files,cli}.py`
  (46 testes novos) e `ROTEIRO_DE_TESTES.md`. Nenhum arquivo dos lotes 1 e 2
  foi alterado. Rodado em 3.12 com um substituto temporário de `core.py`.
- **Lote 2**: criados `stripcomments/validation.py` e `tests/test_validation.py`
  (14 testes). Nenhum arquivo do Lote 1 foi alterado. Observação: foi
  rodado em 3.12 com um substituto temporário de `core.py`; rodar `pytest`
  com o `core.py` real e confirmar.

- **Lote 1**: criados `pyproject.toml`, `stripcomments/{__init__,core,directives}.py`
  e `tests/test_core.py` (70 testes).
- **Pós-Lote 1**: criado este `AGENTS.md`; registrada a decisão de permitir
  comentários na biblioteca (decisão 1).
