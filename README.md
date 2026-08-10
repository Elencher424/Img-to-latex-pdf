# Image → LaTeX → PDF Pipeline

General-purpose pipeline: OCR the image with any local Qwen VL model → generate LaTeX → compile PDF.

./README_zh.md

## Quick Reference: Supported Use Cases

| Mode | What it does | LaTeX class | Trigger examples |
|------|-------------|-------------|-----------------|
| **solve** | Math/exam problem → solution PDF | `ctexart` / `article` | "solve this", "做题", "解答" |
| **ocr** | Any image → verbatim text → PDF | `ctexart` / `article` | "OCR this", "识别文字", "extract text" |
| **table** | Table image → LaTeX tabular → PDF | `ctexart` / `article` | "extract table", "识别表格" |
| **formula** | Formula image → standalone equation PDF | `standalone` | "render formula", "识别公式" |
| **document** | Multi-page / scanned → full document PDF | `ctexart` / `report` | "digitize document", "扫描件转PDF" |

If the user's intent is unclear, ask which mode they want before proceeding.

---

## Phase 0: Prerequisites & Configuration

### Check the OCR script

The OCR helper script lives at `scripts/ocr_qwen.py` relative to this SKILL.md. Verify it runs:

```bash
python <skill_dir>/scripts/ocr_qwen.py --list-backends
```

If the script is missing or Python is unavailable, fall back to the raw Ollama CLI path (see [Fallback: Raw Ollama CLI](#fallback-raw-ollama-cli) at the end).

### Select a backend

The script auto-detects the best available backend. You can also query explicitly:

```bash
python <skill_dir>/scripts/ocr_qwen.py --list-backends   # Show all backends and their status
python <skill_dir>/scripts/ocr_qwen.py --list-models      # Show available Qwen VL models
```

**Backend options** (in order of auto-detection priority):

| Backend | Setup required | Best for |
|---------|---------------|----------|
| **ollama** | `ollama pull qwen3-vl:2b` | Zero-config, CPU-friendly, quick setup |
| **openai_compatible** | vLLM / SGLang / llama.cpp server | GPU-accelerated, high throughput |
| **transformers** | `pip install transformers torch` | Direct model control, no server needed |

### Model selection guide

| Model | RAM needed | Speed | Best for |
|-------|-----------|-------|----------|
| `qwen3-vl:2b` | ~2 GB | Fast (60–180s CPU) | Simple text OCR, math problems |
| `qwen3-vl:8b` | ~6 GB | Moderate | Complex layouts, tables, detailed math |
| `qwen3-vl:32b` | ~20 GB | Slow (GPU recommended) | Dense documents, multilingual |
| `qwen3-vl:72b` | ~40 GB | Slowest (GPU required) | Maximum accuracy, academic publishing |

For the 2B model (most common), expect 60–180 seconds per image. Set `--timeout 300` to be safe.

### Verify xelatex

```bash
which xelatex
```

**xelatex** is required for CJK (Chinese/Japanese/Korean) support via `ctexart`. On this system it's at `c:/texlive/2025/bin/windows/xelatex`. If missing:
- **Windows:** Install TeX Live (https://tug.org/texlive/) or MiKTeX (https://miktex.org/)
- **Linux:** `sudo apt install texlive-xetex texlive-lang-chinese`
- **macOS:** `brew install texlive`

If xelatex is absent, report it and stop.

---

## Phase 1: OCR the Image

### Step 1a: Choose the prompt

Select the OCR prompt based on the user's **mode** and **language**:

| Mode | Language | Flag |
|------|----------|------|
| General OCR | Chinese (default) | `--lang zh --mode general` |
| General OCR | English | `--lang en --mode general` |
| Math content | Any | `--mode math` |
| Table extraction | Any | `--mode table` |

Or pass a custom prompt with `--prompt "your custom instruction"`.

### Step 1b: Run the OCR

```bash
python <skill_dir>/scripts/ocr_qwen.py "<image_path>" \
  --mode <mode> --lang <lang> --verbose
```

**Timing:** Set `timeout: 300000` on the Bash call. If it times out, use `TaskOutput` with `block: true` and `timeout: 300000` to wait for the background task.

**Parsing output:** The script returns clean text (no terminal escape sequences). If the output is empty or starts with `[ERROR]`, handle accordingly:

- `[ERROR] Ollama OCR timed out` → Retry with `--timeout 600`
- `[ERROR] HTTP ...` → Check server status, retry once
- `[ERROR] ... model not found` → Pull the model first (`ollama pull <model>`)

### Step 1c: Retry on failure

If OCR output is garbled or too short (< 20 characters), retry once with the retry prompt:

```
python <skill_dir>/scripts/ocr_qwen.py "<image_path>" \
  --prompt "<retry_prompt>" --verbose
```

Where `<retry_prompt>` is:
- Chinese: `"请再次仔细识别图片中的所有文字，包括题目编号、公式、条件和问题。不要遗漏任何内容。"`
- English: `"Please re-examine the image and extract all text, including labels, equations, conditions, and questions. Do not omit any content."`

---

## Phase 2: Generate LaTeX Document

Choose the document template based on the user's mode, then write the `.tex` file.

### Template A: Math Problem Solution (`solve` mode)

```latex
\documentclass[12pt,a4paper]{ctexart}

% === Page setup ===
\usepackage[top=2.5cm, bottom=2.5cm, left=2.5cm, right=2.5cm]{geometry}

% === Math ===
\usepackage{amsmath,amssymb,amsthm}

% === Theorem environments ===
\newtheorem{definition}{定义}
\newtheorem{theorem}{定理}

% === Other ===
\usepackage{enumitem}
\usepackage{hyperref}

\title{\textbf{[TITLE]}}
\author{}
\date{}

\begin{document}
\maketitle

\section*{题目}

\begin{quote}
% Problem restated verbatim from OCR, in proper LaTeX math mode
\end{quote}

\section*{解答}

% Full solution with reasoning, formulas, and boxed final answer

\end{document}
```

**Content requirements for math solutions:**
- **Problem restatement:** Reproduce verbatim from OCR, converting to LaTeX math (`$...$` inline, `\[ ... \]` display, `\begin{cases}` for piecewise).
- **Solution quality:**
  - Define relevant concepts before using them
  - At least one rigorous proof; additional approaches if they add insight
  - Clear logical flow: `\textbf{Step 1:} ...`, `\textbf{Step 2:} ...`
  - Boxed final answer: `\[ \boxed{\text{...}} \]`
- **Sub-questions (1), (2), (3):** Number answers correspondingly.

### Template B: General OCR (`ocr` mode)

```latex
\documentclass[12pt,a4paper]{ctexart}

\usepackage[top=2.5cm, bottom=2.5cm, left=2.5cm, right=2.5cm]{geometry}
\usepackage{amsmath,amssymb}
\usepackage{enumitem}
\usepackage{hyperref}

\title{\textbf{[TITLE]}}
\author{}
\date{}

\begin{document}
\maketitle

% Recognized text, preserving original structure
% Use sections, paragraphs, and itemize/enumerate as appropriate

\end{document}
```

**For English-only content**, use `\documentclass[12pt,a4paper]{article}` instead of `ctexart`.

### Template C: Table Extraction (`table` mode)

```latex
\documentclass[12pt,a4paper]{ctexart}

\usepackage[top=2cm, bottom=2cm, left=2cm, right=2cm]{geometry}
\usepackage{amsmath,amssymb}
\usepackage{array,booktabs}
\usepackage{hyperref}

\title{\textbf{[TABLE_TITLE]}}
\author{}
\date{}

\begin{document}
\maketitle

% Reconstructed table using tabular/booktabs
% Use \begin{tabular}{...} \toprule ... \midrule ... \bottomrule \end{tabular}

\end{document}
```

### Template D: Formula Only (`formula` mode)

```latex
\documentclass[12pt,preview,border=10pt]{standalone}

\usepackage{amsmath,amssymb,amsthm}

\begin{document}

\[
% Single formula here
\]

\end{document}
```

### Template E: Document Digitization (`document` mode)

```latex
\documentclass[12pt,a4paper]{ctexart}

\usepackage[top=2.5cm, bottom=2.5cm, left=2.5cm, right=2.5cm]{geometry}
\usepackage{amsmath,amssymb,amsthm}
\usepackage{graphicx}
\usepackage{enumitem}
\usepackage{hyperref}

\title{\textbf{[DOCUMENT_TITLE]}}
\author{}
\date{}

\begin{document}
\maketitle

\tableofcontents
\newpage

% Sections as recognized from the document structure

\end{document}
```

### Multi-image handling

If the user provides multiple images:
1. Process them **one at a time in sequence** (not parallel — to avoid GPU OOM)
2. Combine OCR results into a single document with `\section{}` per image
3. Use a unified title like "Multi-page Document"

### File location

Save to the user's Desktop:
```
C:\Users\<username>\Desktop\<descriptive-slug>.tex
```

Use a concise, descriptive filename (e.g., `math-solution.tex`, `ocr-output.tex`, `table-data.tex`).

---

## Phase 3: Compile to PDF

Run xelatex **twice** to resolve cross-references:

```bash
cd <output_dir> && xelatex -interaction=nonstopmode <filename>.tex && xelatex -interaction=nonstopmode <filename>.tex
```

**Why xelatex:** Required for `ctexart` Chinese support. Do NOT use pdflatex — it cannot handle CJK fonts via ctex. For English-only `article` class documents, pdflatex is acceptable but xelatex is preferred for consistency.

### Compilation failure recovery

1. Read the `.log` file to find the error
2. Common fixes:
   - **Unescaped special chars:** `&` `%` `#` `_` `$` `{` `}` in text mode — escape them
   - **Unclosed environments:** Verify every `\begin{...}` has a matching `\end{...}`
   - **Unicode in math mode:** Move Chinese/Unicode text outside `$...$` or `\[...\]`
   - **Missing packages:** Use only standard packages listed in the templates
   - **Undefined commands:** Check for typos in `\newtheorem` or custom commands
3. Fix the `.tex` file and recompile

### Cleanup

After successful PDF generation, remove auxiliary files:

```bash
rm -f <filename>.aux <filename>.log <filename>.out <filename>.toc
```

---

## Phase 4: Report Results

Tell the user:

- **PDF:** Full path and file size (e.g., `C:\Users\21340\Desktop\solution.pdf`, 71 KB)
- **LaTeX source:** Full path (for future editing)
- **OCR info:** Which backend and model were used, time taken
- **Content summary:** A one-paragraph recap of what was processed

---

## Edge Cases

| Scenario | Action |
|----------|--------|
| Image in QQ/WeChat data folder (`...\nt_qq\nt_data\Pic\...`) | Use directly — no need to copy |
| OCR output mixes problem text with LaTeX-like formatting | Parse out the LaTeX fragments and use them directly |
| Problem has sub-questions (1), (2), (3)... | Number answers correspondingly in the solution section |
| User provides multiple images | Process one at a time, combine into one document with `\section{}` per image |
| English-only content | Use `article` class instead of `ctexart`, English OCR prompt |
| Mixed CN/EN content | Use `ctexart` with bilingual OCR prompt |
| Image is a photo of handwritten notes | Use `--mode general`, note to user that handwriting OCR may be less accurate |
| Image is a screenshot of code | Use `article` class with `\begin{verbatim}` or `listings` package |
| Very large image (>10 MB) | The OCR script auto-resizes with PIL if needed; no manual action needed |
| OCR produces completely wrong text | Retry with different `--mode` or a custom `--prompt`, or try a larger model |
| User wants beamer slides | Use `\documentclass{beamer}` template, one frame per slide |
| Ollama not installed | Guide user to install from https://ollama.com, then `ollama pull qwen3-vl:2b` |

---

## Configuration Reference

The skill uses a layered config system (higher overrides lower):

1. **CLI arguments** — `--backend`, `--model`, `--prompt`, `--base-url`, etc.
2. **Environment variables** — `QWEN_BACKEND`, `QWEN_MODEL`, `QWEN_TIMEOUT`, `OPENAI_BASE_URL`, `OPENAI_API_KEY`
3. **`config.json`** — file next to SKILL.md (copy from `config.example.json`)

### Installing a new backend

**Ollama (recommended):**
```bash
# Install: https://ollama.com
ollama pull qwen3-vl:2b     # Smallest, fastest
ollama pull qwen3-vl:8b     # More accurate
```

**OpenAI-compatible (vLLM example):**
```bash
pip install vllm
python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-VL-7B-Instruct --port 8000
# Then use: --backend openai --base-url http://localhost:8000/v1
```

**Transformers (direct):**
```bash
pip install transformers torch pillow accelerate
# Then use: --backend transformers --model Qwen/Qwen2.5-VL-7B-Instruct
```

---

## Fallback: Raw Ollama CLI

If `scripts/ocr_qwen.py` is unavailable (missing Python, missing Pillow, etc.), fall back to the raw Ollama CLI:

```bash
ollama run qwen3-vl:2b "请仔细识别这张图片中的所有文字内容，包括题目、公式、选项等。一字不漏地输出图片中的全部文字。" <image_path>
```

**Limitations of the fallback:**
- Only works with Ollama backend
- Output contains terminal escape sequences (spinner) that need manual parsing
- No timeout control, no retry prompt selection, no mode switching
- Look for content after `...done thinking.` marker in the output

Use this fallback **only** when the Python script cannot run. Prefer the script in all normal cases.

