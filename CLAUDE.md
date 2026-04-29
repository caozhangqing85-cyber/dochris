# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Dochris (知识库编译系统) is a personal knowledge base compilation system that transforms raw materials (PDFs, audio, video, ebooks, markdown) into structured, searchable, and verifiable knowledge assets through a **four-stage pipeline** and **four-layer trust model**.

## Architecture

### Four-Stage Pipeline
1. **Phase 1 — Ingestion** (`phases/phase1_ingestion.py`): Scan source files, create symlinks, deduplicate by SHA-256 hash, create manifests
2. **Phase 2 — Compilation** (`phases/phase2_compilation.py`): Convert to text via markitdown, LLM extracts structured JSON (summary, key_points, concepts)
3. **Phase 3 — Review** (`quality/gate.py`): Quality scoring (0-100, threshold 85), pollution detection, auto-downgrade
4. **Phase 4 — Distribution** (`promote.py`, `vault/bridge.py`): Promote through trust layers, sync with Obsidian

### Four-Layer Trust Model
- **Layer 0** `outputs/`: LLM output, untrusted (default)
- **Layer 1** `wiki/`: Quality-gated (score ≥ 85), semi-trusted
- **Layer 2** `curated/`: Human-curated, trusted
- **Layer 3** `locked/`: Immutable, locked

### Data Flow
```
Source files (HDD) → raw/ (symlinks) → manifests/ → outputs/ (L0) → wiki/ (L1) → curated/ (L2) → Obsidian
```

## Project Structure

```
dochris/
├── src/dochris/       # Main package (standard src layout)
│   ├── __init__.py        # Package init, version
│   ├── __main__.py        # python -m dochris
│   ├── cli/               # CLI commands
│   │   ├── main.py        # Main CLI entry point
│   │   ├── cli_ingest.py  # Phase 1 command
│   │   ├── cli_compile.py # Phase 2 command
│   │   ├── cli_query.py   # Phase 3 command
│   │   └── ...
│   ├── core/              # Core modules
│   │   ├── llm_client.py  # LLM client
│   │   ├── quality_scorer.py
│   │   ├── retry_manager.py
│   │   ├── text_chunker.py
│   │   ├── cache.py
│   │   └── utils.py
│   ├── parsers/           # File parsers
│   │   ├── pdf_parser.py
│   │   ├── doc_parser.py
│   │   └── code_parser.py
│   ├── phases/            # Pipeline phases
│   │   ├── phase1_ingestion.py
│   │   ├── phase2_compilation.py
│   │   ├── phase3_query.py
│   │   └── query_utils.py
│   ├── compensate/        # Failure compensation
│   ├── quality/           # Quality gate & monitor
│   ├── vault/             # Obsidian integration
│   ├── workers/           # Background workers
│   ├── settings.py        # Configuration (dataclass-based)
│   ├── exceptions.py      # Exception hierarchy
│   └── log.py             # Logging utilities
├── tests/                 # Test suite
├── docs/                  # Documentation
└── pyproject.toml         # Project config
```

## Key Paths

| Path | Purpose |
|------|---------|
| `manifests/sources/` | Per-file JSON manifests (SRC-NNNN.json) |
| `raw/` | Symlinks to source files (pdfs/, audio/, videos/, etc.) |
| `outputs/` | Layer 0: LLM-generated summaries and concepts |
| `wiki/` | Layer 1: Quality-gated knowledge |
| `curated/` | Layer 2: Human-curated knowledge |
| `data/` | ChromaDB vector store |
| `logs/` | Per-run compilation logs |

## Commands

```bash
# Python virtual environment
VENV=~/.openclaw/vector_env/bin/python

# Unified CLI (recommended)
kb ingest              # Phase 1: Ingest files
kb compile [limit]     # Phase 2: Compile with LLM
kb query "关键词"       # Phase 3: Search knowledge base
kb status              # Show overview
kb promote SRC-0001 --to wiki  # Promote to trust layer
kb quality --report    # Quality check
kb vault seed "topic"  # Pull from Obsidian
kb config              # Show configuration
kb version             # Show version

# Direct module usage
$VENV -m dochris.cli.main ingest
$VENV -m dochris.phases.phase1_ingestion
```

## Tech Stack

- **Python 3.11** with standard src layout
- **ChromaDB** — persistent vector store
- **BAAI/bge-small-zh-v1.5** — Chinese semantic embedding
- **markitdown** — multi-format file-to-text conversion
- **LLM**: OpenAI-compatible API (GLM models via ZhipuAI)

## Configuration

Priority: `.env` file > environment variables > defaults

Key environment variables:
- `OPENAI_API_KEY` — LLM API key (required)
- `OPENAI_API_BASE` — LLM API base URL
- `MODEL` — Compilation model (default: glm-5.1)
- `WORKSPACE` — Workspace path (default: ~/.knowledge-base)
- `SOURCE_PATH` — Source materials directory

Configuration is loaded via `dochris.settings.get_settings()`.

## Code Conventions

- **Type annotations**: All public functions must have parameter and return types
- **Docstrings**: All public functions and modules must have docstrings
- **Error handling**: Use specific exception types from `dochris.exceptions`, never bare `except:`
- **Configuration**: Import from `dochris.settings`, never hardcode paths or values
- **Logging**: Use `logging.getLogger(__name__)`, never `print()` for output
- **Path handling**: Always use `pathlib.Path`, never string concatenation for paths
- **Imports**: Use `from dochris.xxx import yyy`, never `from scripts.xxx`

## Testing

```bash
# Run all tests
$VENV -m pytest tests/ -v

# Run with coverage
$VENV -m pytest tests/ --cov=dochris --cov-report=term-missing

# Run specific test file
$VENV -m pytest tests/test_quality_scorer.py -v
```

## Quality Scoring

Total 100 points, minimum 85 to promote:
- Summary length (0-35): 800-1500 characters optimal
- Key points completeness (0-40): 4-5 independent points
- Learning value (0-25): keyword density (methods, strategies, principles)
- Information density (0-10): specific techniques/tools density
- One-line quality (0-10): 10-50 character summary
- Concept completeness (0-20): 3-5 complete concepts
- Template detection: -20 penalty for template text

## Git Commit Rules

When committing changes, **create separate commits per file**. Each file gets its own commit with a descriptive message.

## Debugging Tips

- Check `logs/` for compilation logs
- Use `kb status` to see manifest states
- Failed compilations are logged in manifest `error_message` field
- Run compilation with `--resume` flag for incremental processing

## Best Practice Reference

See `docs/claude-code-best-practice/` for Claude Code best practices including:
- `best-practice/` — Settings, commands, skills, subagents, memory, MCP, power-ups
- `tips/` — Community tips and tricks
- `reports/` — Deep-dive analyses
- `implementation/` — Implementation guides

## ⚠️ 测试安全规则（CRITICAL）

- **禁止**测试写入 `~/.openclaw/` 下的任何真实文件（openclaw.json 等）
- **必须**使用 pytest 的 `tmp_path` fixture 创建临时文件
- **必须**使用 `monkeypatch` 或 `unittest.mock.patch` 修改环境变量，不修改真实环境
- **必须**在 teardown 中清理所有副作用（文件、环境变量、全局状态）
- 如果测试需要写配置文件，写到 `tmp_path` 然后通过 patch 指向它
