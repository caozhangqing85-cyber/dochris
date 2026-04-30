# Dochris

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Status](https://img.shields.io/badge/Status-Active-success.svg)

> A four-layer trust model with a four-stage pipeline for transforming raw files into a high-quality knowledge base

## Project Motivation

In the age of information explosion, we accumulate vast amounts of learning materials (PDFs, audio, videos, ebooks), but these are often scattered and difficult to use effectively. Traditional knowledge management tools face several challenges:

1. **Difficult retrieval**: Filename-based search cannot understand content semantics
2. **Knowledge silos**: Different file formats cannot be managed uniformly
3. **Variable quality**: LLM-generated content may contain hallucinations or template text
4. **Version chaos**: No way to distinguish between drafts, reviewed, and final versions

This project builds a trusted personal knowledge base system through a four-layer trust model and a four-stage pipeline, transforming raw materials into structured, searchable, verifiable knowledge assets.

## Key Features

### Trust Layers
- **Layer 0 (outputs/)**: LLM-generated, untrusted by default
- **Layer 1 (wiki/)**: Promoted after review, semi-trusted
- **Layer 2 (curated/)**: Manually curated, trusted
- **Layer 3 (locked/)**: Locked and protected, immutable

### Intelligent Compilation
- Multi-format support: PDF, audio, video, ebooks, articles
- LLM-driven structured extraction (summaries, key points, concepts)
- Multi-dimensional quality scoring system (85 minimum pass score)
- Pollution detection and automatic downgrade

### Obsidian Integration
- Vault Bridge bidirectional sync
- Pull notes from Obsidian as compilation seeds
- Push high-quality content back to Obsidian vault

### Batch Operations
- Batch quality checks and promotion
- Batch push to Obsidian
- Incremental compilation support (manifest-based)

## System Requirements

- Python 3.11+
- 4GB+ RAM (8GB recommended)
- 10GB+ free disk space
- Linux / macOS / WSL2

## Architecture Overview

### Four-Layer Trust Model

```
Layer 0: outputs/     — LLM generated, untrusted (default)
Layer 1: wiki/        — Promoted after review, semi-trusted
Layer 2: curated/     — Manually curated, trusted
Layer 3: locked/      — Locked protection, immutable
```

### Four-Stage Pipeline

```
Phase 1: Ingestion  — Scan raw files, create manifest
Phase 2: Compilation — LLM async compilation, output to outputs/
Phase 3: Review     — Quality gate + manual promotion
Phase 4: Distribution— Vault Bridge + batch operations
```

### Data Flow

```
/vol1/1000/baiduNetDownload/   Obsidian-Sync/
        |                           |
        v                           v
    raw/inbox/  <-- seed -- vault_bridge
        |
        v
  Phase 1: Create manifest (status: ingested)
        |
        v
  Phase 2: LLM compilation (status: compiled)
        |
        v
  outputs/summaries/  outputs/concepts/   (Layer 0)
        |
        v  promote (quality >= 85)
  wiki/summaries/  wiki/concepts/          (Layer 1)
        |
        v  promote
  curated/promoted/                        (Layer 2)
        |
        v  promote_to_obsidian
  Obsidian-Sync/06-Knowledge-Base/         (External)
```

## Directory Structure

```
knowledge-base/
├── scripts/                  # Core scripts
│   ├── phase1_ingestion.py   # Phase 1: File ingestion
│   ├── phase2_compilation.py # Phase 2: LLM compilation
│   ├── manifest_manager.py   # Manifest lifecycle management
│   ├── promote_artifact.py   # Single promote operation
│   ├── batch_promote.py      # Batch promotion
│   ├── vault_bridge.py       # Obsidian bidirectional sync
│   ├── quality_gate.py       # Quality gate & pollution detection
│   ├── log_entry.py          # Append-only logging
│   └── sanitize_sensitive_words.py  # Content sanitization
├── manifests/                # Manifest storage
│   ├── sources/              # SRC-NNNN.json files
│   └── source_index.csv      # CSV index
├── raw/                      # Raw files
│   ├── inbox/                # Notes imported from Obsidian
│   ├── pdfs/                 # PDF files
│   ├── articles/             # Articles (txt, html)
│   ├── audio/                # Audio files
│   ├── videos/               # Video files
│   ├── ebooks/               # Ebooks
│   └── other/                # Other formats
├── outputs/                  # Layer 0: LLM outputs (untrusted)
├── wiki/                     # Layer 1: Reviewed (semi-trusted)
├── curated/                  # Layer 2: Manually curated (trusted)
├── logs/                     # Compilation logs
└── log.md                    # Operation log
```

## Quick Start

### Installation

#### Method 1: Docker (Recommended)

```bash
# Build image
docker build -t knowledge-base:latest .

# Create configuration file
cp .env.example .env
# Edit .env and add your API key

# Start service
docker-compose up -d

# View logs
docker-compose logs -f

# Execute commands
docker-compose exec knowledge-base python scripts/phase2_compilation.py
```

**GPU Support** (for faster-whisper audio transcription):

```bash
# Install nvidia-docker
# https://github.com/NVIDIA/nvidia-docker

# Run with GPU
docker run --gpus all knowledge-base:latest compile
```

**Docker Common Commands**:

```bash
# Check system status
docker-compose exec knowledge-base kb status

# Ingest files
docker-compose exec knowledge-base kb ingest

# Compile first 10 files
docker-compose exec knowledge-base kb compile 10

# Query knowledge base
docker-compose exec knowledge-base kb query "Feynman Technique"

# Start interactive shell
docker-compose exec knowledge-base bash
```

#### Method 2: Local Installation

```bash
# Clone the project
git clone https://github.com/caozhangqing85-cyber/dochris.git
cd knowledge-base

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# Create configuration file
cp .env.example .env
# Edit .env and add your API key
```

### Configuration

Create a `.env` file with the following:

```bash
# LLM API configuration (required)
OPENAI_API_KEY=your_api_key_here
OPENAI_API_BASE=https://open.bigmodel.cn/api/paas/v4
MODEL=glm-5.1

# Optional configuration
WORKSPACE=~/.knowledge-base
MAX_CONCURRENCY=8
MIN_QUALITY_SCORE=85
```

**Docker-specific Configuration**:

```bash
# Docker environment overrides these settings
WORKSPACE=/app              # Workspace path inside container
LOG_LEVEL=INFO             # Log level
```

**Volume Mounts** (docker-compose.yml):

```yaml
volumes:
  - ./data:/app/data          # Data directory
  - ./raw:/app/raw            # Raw files
  - ./outputs:/app/outputs    # Compilation outputs
  - ./wiki:/app/wiki          # Wiki content
  - ./curated:/app/curated    # Curated content
  - ./logs:/app/logs          # Log files
```

### Usage

After installation, use the unified `kb` command:

```bash
# Check system status
kb status

# Show current configuration
kb config
```

#### 1. Ingest Files

```bash
# Scan default source directory and create manifest
kb ingest

# Ingest from specified directory
kb ingest /path/to/materials

# Output example:
# ✓ Created manifest: SRC-0001 (PDF)
# ✓ Created manifest: SRC-0002 (Audio)
# ...
# Total: 42 manifests created
```

#### 2. Compile

```bash
# Full compilation (based on manifest status)
kb compile

# Compile first 10
kb compile 10

# Use 4 concurrent workers
kb compile --concurrency 4

# Output example:
# [SRC-0001] Compiling...
# [SRC-0001] Quality score: 92/100 ✓
# [SRC-0002] Compiling...
# [SRC-0002] Quality score: 78/100 ✗ (below passing score)
# ...
# Compilation complete: 38 succeeded, 4 failed
```

#### 3. Quality Check & Promotion

```bash
# View quality report
kb quality --report

# Quality gate check
kb quality SRC-0001

# Pollution detection
kb quality --check-pollution

# Single promote
kb promote SRC-0001 --to wiki
kb promote SRC-0001 --to curated
kb promote SRC-0001 --to obsidian
```

#### 4. Batch Operations

```bash
# View promotable content (use Python script directly)
python scripts/batch_promote.py . wiki --dry-run --min-score 85

# Batch promote to wiki
python scripts/batch_promote.py . wiki --min-score 85 --limit 100

# Batch push to Obsidian
python scripts/batch_promote.py . obsidian --min-score 95
```

#### 5. Query Knowledge Base

```bash
# Query by keyword
kb query "Feynman Technique"

# Search concepts only
kb query "Deep Learning" --mode concept

# Combined query (default)
kb query "Investment Strategy" --mode combined

# Interactive mode
kb query
```

#### 6. Obsidian Integration

```bash
# Pull notes from Obsidian
kb vault seed "Financial Freedom"

# Push to Obsidian
kb vault promote SRC-0001

# List associated notes
kb vault list SRC-0001
```

## Configuration

### Key Parameters (phase2_compilation.py)

| Parameter | Value | Description |
|-----------|-------|-------------|
| MAX_CONCURRENCY | 8 | Concurrent compilation tasks |
| MAX_RETRIES | 3 | Maximum retry attempts |
| RETRY_BASE_DELAY | 1s | Retry base delay (exponential backoff) |
| MIN_QUALITY_SCORE | 85 | Minimum quality score for promotion |
| MIN_AUDIO_TEXT_LENGTH | 100 | Minimum audio text length in characters |
| MAX_CONTENT_CHARS | 20000 | Maximum characters per file |

### Environment Variables

| Variable | Description |
|----------|-------------|
| OPENAI_API_KEY | LLM API key |
| OPENAI_API_BASE | LLM API endpoint |
| MODEL | Model name (default: glm-5.1) |

## Manifest Format

```json
{
  "id": "SRC-0001",
  "title": "Source Title",
  "type": "pdf|audio|video|ebook|article|other",
  "source_path": "/vol1/1000/...",
  "file_path": "raw/pdfs/filename.pdf",
  "content_hash": "SHA-256",
  "date_ingested": "2026-04-07",
  "date_published": null,
  "size_bytes": 12345,
  "summary": null,
  "compiled_summary": null,
  "status": "ingested|compiled|failed|promoted_to_wiki|promoted",
  "quality_score": 0,
  "error_message": null,
  "promoted_to": null,
  "tags": []
}
```

## Quality Scoring

Total 100 points, passing line 85 points:

| Dimension | Score | Description |
|-----------|-------|-------------|
| detailed_summary length | 0-35 | 800-1500 characters |
| key_points completeness | 0-40 | 4-5 independent points |
| Learning value | 0-25 | Learning keyword density |
| Information density | 0-10 | Method/strategy/technique density |
| one_line quality | 0-10 | 10-50 characters |
| Concept completeness | 0-20 | 3-5 complete concepts |
| Template text detection | 0-10 | Bonus for no template text |

## CLI Command Reference

### Unified Entry Point (kb command)

| Command | Description |
|---------|-------------|
| `kb status` | Display system status overview |
| `kb config` | Show current configuration |
| `kb version` | Display version information |
| `kb ingest [path]` | Phase 1: Ingest files |
| `kb compile [limit]` | Phase 2: Compile documents |
| `kb query "keyword" [options]` | Phase 3: Query knowledge base |
| `kb promote <src_id> --to <target>` | Promote operation |
| `kb quality [--report]` | Quality check |
| `kb vault <subcommand>` | Obsidian integration |

### query Command Options

| Option | Description |
|--------|-------------|
| `--mode concept` | Search concepts only |
| `--mode summary` | Search summaries only |
| `--mode vector` | Vector search only |
| `--mode combined` | Combined query (default) |
| `--mode all` | Search all |
| `--top-k N` | Number of results (default 5) |

### promote Command Targets

| Target | Description |
|--------|-------------|
| `--to wiki` | Promote to wiki/ |
| `--to curated` | Promote to curated/ |
| `--to obsidian` | Push to Obsidian |

### vault Subcommands

| Subcommand | Description |
|------------|-------------|
| `kb vault seed "<topic>"` | Pull notes from Obsidian |
| `kb vault promote <src-id>` | Push to Obsidian |
| `kb vault list <src-id>` | List associated notes |

### quality Command Options

| Option | Description |
|--------|-------------|
| `--report` | Generate full quality report (JSON) |
| `--check-pollution` | Check wiki/ for pollution |
| `SRC-0001` | Check specific manifest quality gate |

### Using Python Scripts Directly

For advanced operations, you can call Python scripts directly:

### manifest_manager.py

| Function | Description |
|----------|-------------|
| `create_manifest(ws, id, title, type, src, fp, hash, ...)` | Create manifest |
| `get_manifest(ws, src_id)` | Read manifest |
| `update_manifest_status(ws, src_id, status, ...)` | Update manifest status |
| `get_all_manifests(ws, status=None)` | Get all manifests |
| `get_next_src_id(ws)` | Get next SRC-ID |
| `rebuild_index(ws)` | Rebuild source_index.csv |

### promote_artifact.py

| Function | Description |
|----------|-------------|
| `promote_to_wiki(ws, src_id)` | outputs/ → wiki/ |
| `promote_to_curated(ws, src_id)` | wiki/ → curated/ |
| `show_status(ws, src_id)` | Display manifest status |

### quality_gate.py

| Function | Description |
|----------|-------------|
| `check_pollution(ws)` | Pollution detection |
| `quality_gate(ws, src_id, min_score=85)` | Quality gate check |
| `auto_downgrade(ws, src_id, reason)` | Automatic downgrade |
| `scan_wiki(ws)` | Wiki scan |
| `generate_report(ws)` | Generate full report |

### vault_bridge.py

| Function | Description |
|----------|-------------|
| `seed_from_obsidian(ws, topic)` | Pull notes from Obsidian |
| `promote_to_obsidian(ws, src_id)` | Push to Obsidian |
| `list_associated_notes(ws, src_id)` | List associated notes |
| `clean_internal_references(content)` | Clean internal reference format |

### batch_promote.py

| Function | Description |
|----------|-------------|
| `batch_promote_to_wiki(ws, min_score, limit, dry_run)` | Batch promote to wiki |
| `batch_promote_to_curated(ws, min_score, limit, dry_run)` | Batch promote to curated |
| `batch_promote_to_obsidian(ws, min_score, limit, dry_run)` | Batch push to Obsidian |

## FAQ

### Q: API content filter error (400, error 1301) during compilation

A: This is the Zhipu AI content moderation mechanism. The system automatically calls `sanitize_sensitive_words.py` to sanitize sensitive words. If issues persist, you can manually extend the sensitive word list.

### Q: High PDF text extraction failure rate

A: For scanned PDFs, the system automatically attempts OCR. If OCR fails, the file is marked in `failed_queue.json`. You can use `ocr_failed_pdf.py` to manually retry.

### Q: Quality score is always 10

A: This is a scoring algorithm mismatch with model output. Retrying compilation usually yields the correct score.

### Q: How to speed up compilation

A: You can modify `MAX_CONCURRENCY` to increase concurrency (default 8), or use `nohup` to run in the background.

### Q: Can files in raw/ directory be deleted

A: No. Files in `raw/` are symbolic links pointing to original files. Deleting original files will invalidate manifests.

## Development

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-cov

# Run tests
pytest tests/

# View coverage
pytest --cov=scripts tests/
```

### Code Standards

- Follow PEP 8
- Use type annotations
- Docstring in Chinese
- Line length不超过 100 characters

## Contributing

Issues and Pull Requests are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

MIT License. See [LICENSE](LICENSE)

---

**Made with ❤️ for personal knowledge management**
