# img-to-latex-pdf

Convert any image containing text, math, tables, or diagrams into a professionally formatted LaTeX document and compile to PDF — powered by local Qwen VL models.


## Documentation

- [SKILL.md](./SKILL.md) — Full skill reference (English)
- [SKILL_zh.md](./SKILL_zh.md) — 完整中文文档
- [config.example.json](./config.example.json) — Configuration template with comments



## Features

- **🖼️  5 OCR modes**: math solve, general OCR, table extraction, formula render, document digitization
- **🔌  3 backends**: Ollama (zero-config), OpenAI‑compatible (vLLM/SGLang), Transformers (direct)
- **🇨🇳  CJK support**: Full Chinese/Japanese/Korean via `ctexart` + `xelatex`
- **⚙️  Auto‑detection**: picks the best available backend and model automatically
- **📄  5 LaTeX templates**: `ctexart`, `article`, `report`, `standalone`, `beamer`
- **🪶  Lightweight**: OCR script has zero mandatory dependencies beyond Python stdlib

## Quick Start

### 1. Install prerequisites

```bash
# OCR engine (pick one)
ollama pull qwen3-vl:2b          # Ollama — easiest, ~2 GB

# PDF compiler
# Windows: https://tug.org/texlive/
# Linux:   sudo apt install texlive-xetex texlive-lang-chinese
# macOS:   brew install texlive
```

### 2. Install the skill

```bash
# Clone into Claude Code skills directory
git clone https://github.com/<your-username>/img-to-latex-pdf.git \
  ~/.claude/skills/img-to-latex-pdf
```

Or copy the folder manually into `~/.claude/skills/img-to-latex-pdf/` (or `.claude/skills/` inside your project).

### 3. Use it

In Claude Code, send an image and say:

> "Solve this math problem and output as PDF"

> "OCR this image into a LaTeX document"

> "Extract the table from this screenshot"

The skill triggers automatically when you provide an image and ask for LaTeX/PDF output.

## Manual CLI Usage

The OCR script can be used independently:

```bash
# Show available backends
python scripts/ocr_qwen.py --list-backends

# OCR an image (auto-detects backend)
python scripts/ocr_qwen.py photo.jpg --mode math --verbose

# Use a specific backend and model
python scripts/ocr_qwen.py scan.png --backend ollama --model qwen3-vl:8b

# English content
python scripts/ocr_qwen.py document.jpg --lang en --mode general
```

## Configuration

The skill uses a 3‑layer config system (higher overrides lower):

1. **CLI arguments** — `--backend`, `--model`, `--prompt`, etc.
2. **Environment variables** — `QWEN_BACKEND`, `QWEN_MODEL`, `QWEN_TIMEOUT`, `OPENAI_BASE_URL`, `OPENAI_API_KEY`
3. **`config.json`** — copy from `config.example.json` and customize

### Switching backends

**Ollama (default, zero-config):**
```bash
ollama pull qwen3-vl:2b
ollama pull qwen3-vl:8b    # larger, more accurate
```

**OpenAI-compatible (vLLM):**
```bash
pip install vllm
vllm serve Qwen/Qwen2.5-VL-7B-Instruct --port 8000
# Then: --backend openai --base-url http://localhost:8000/v1
```

**Transformers (direct load):**
```bash
pip install transformers torch pillow accelerate
# Then: --backend transformers --model Qwen/Qwen2.5-VL-7B-Instruct
```

## Supported Models

| Model | RAM | Speed | Best for |
|-------|-----|-------|----------|
| `qwen3-vl:2b` | ~2 GB | Fast | Simple OCR, math problems |
| `qwen3-vl:8b` | ~6 GB | Moderate | Complex layouts, tables |
| `qwen3-vl:32b` | ~20 GB | Slow | Dense documents, multilingual |
| `qwen3-vl:72b` | ~40 GB | Slowest | Academic publishing |
| `Qwen/Qwen2.5-VL-7B-Instruct` | ~16 GB | GPU needed | Transformers backend |

## File Structure

```
img-to-latex-pdf/
├── SKILL.md                # Main skill instructions (English)
├── SKILL_zh.md             # Chinese translation
├── config.example.json     # Configuration template
├── scripts/
│   └── ocr_qwen.py         # Multi-backend OCR interface
├── README.md               # This file
└── LICENSE
```


## License

MIT
