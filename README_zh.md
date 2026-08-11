# 图片 → LaTeX → PDF 流水线

通用流水线：用任意本地 Qwen VL 模型对图片进行 OCR → 生成 LaTeX 文档 → 编译为 PDF。

[English](./README.md)   [中文版](./README_zh.md)

请注意！本skill不包含LATEX，Ollama和本地千问模型。

如果你没有以上所需内容，可以访问以下链接

[Ollama 官网](https://ollama.com)

[Qwen 模型仓库](https://huggingface.co/Qwen)

[TeX Live 下载](https://tug.org/texlive/)

## 快速参考：支持的用例

| 模式 | 功能 | LaTeX 文档类 | 触发示例 |
|------|------|-------------|---------|
| **solve** | 数学/考试题目 → 解答 PDF | `ctexart` / `article` | "解这道题"、"做题"、"解答" |
| **ocr** | 任意图片 → 逐字文本 → PDF | `ctexart` / `article` | "OCR 识别"、"识别文字"、"提取文字" |
| **table** | 表格图片 → LaTeX 表格 → PDF | `ctexart` / `article` | "提取表格"、"识别表格" |
| **formula** | 公式图片 → 独立公式 PDF | `standalone` | "渲染公式"、"识别公式" |
| **document** | 多页/扫描件 → 完整文档 PDF | `ctexart` / `report` | "数字化文档"、"扫描件转 PDF" |

如果用户意图不明确，请在继续之前询问用户想要哪种模式。

---

## 阶段 0：环境检查与配置

### 检查 OCR 脚本

OCR 辅助脚本位于本 SKILL.md 同级目录下的 `scripts/ocr_qwen.py`。验证其是否可运行：

```bash
python <skill_dir>/scripts/ocr_qwen.py --list-backends
```

如果脚本缺失或 Python 不可用，请回退到原始 Ollama CLI 方式（参见文末的[备选方案：原始 Ollama CLI](#备选方案原始-ollama-cli)）。

### 选择后端

脚本会自动检测最佳可用后端。你也可以显式查询：

```bash
python <skill_dir>/scripts/ocr_qwen.py --list-backends   # 显示所有后端及其状态
python <skill_dir>/scripts/ocr_qwen.py --list-models      # 显示可用的 Qwen VL 模型
```

**后端选项**（按自动检测优先级排列）：

| 后端 | 所需配置 | 适用场景 |
|---------|---------------|----------|
| **ollama** | `ollama pull qwen3-vl:2b` | 零配置、CPU 友好、快速上手 |
| **openai_compatible** | vLLM / SGLang / llama.cpp 服务器 | GPU 加速、高吞吐量 |
| **transformers** | `pip install transformers torch` | 直接控制模型、无需服务器 |

### 模型选择指南

| 模型 | 内存需求 | 速度 | 适用场景 |
|-------|-----------|-------|----------|
| `qwen3-vl:2b` | ~2 GB | 快（CPU 60–180 秒） | 简单文字 OCR、数学题 |
| `qwen3-vl:8b` | ~6 GB | 中等 | 复杂排版、表格、详细数学 |
| `qwen3-vl:32b` | ~20 GB | 慢（建议 GPU） | 密集文档、多语言 |
| `qwen3-vl:72b` | ~40 GB | 最慢（需 GPU） | 最高精度、学术出版 |

对于最常用的 2B 模型，每张图片预计 60–180 秒。建议设置 `--timeout 300` 以确保安全。

### 验证 xelatex

```bash
which xelatex
```

**xelatex** 是通过 `ctexart` 支持中日韩（CJK）文字所必需的。在本系统中，它位于 `c:/texlive/2025/bin/windows/xelatex`。如果缺失：
- **Windows：** 安装 TeX Live（https://tug.org/texlive/）或 MiKTeX（https://miktex.org/）
- **Linux：** `sudo apt install texlive-xetex texlive-lang-chinese`
- **macOS：** `brew install texlive`

如果 xelatex 不存在，请报告并终止。

---

## 阶段 1：对图片进行 OCR

### 步骤 1a：选择提示词

根据用户的**模式**和**语言**选择 OCR 提示词：

| 模式 | 语言 | 参数 |
|------|----------|------|
| 通用 OCR | 中文（默认） | `--lang zh --mode general` |
| 通用 OCR | 英文 | `--lang en --mode general` |
| 数学内容 | 任意 | `--mode math` |
| 表格提取 | 任意 | `--mode table` |

或者通过 `--prompt "你的自定义指令"` 传入自定义提示词。

### 步骤 1b：运行 OCR

```bash
python <skill_dir>/scripts/ocr_qwen.py "<image_path>" \
  --mode <mode> --lang <lang> --verbose
```

**耗时说明：** 在 Bash 调用中设置 `timeout: 300000`。如果超时，将命令转入后台，然后使用 `TaskOutput`（`block: true`，`timeout: 300000`）等待完成。

**输出解析：** 脚本返回干净的文本（无终端转义序列）。如果输出为空或以 `[ERROR]` 开头，按以下方式处理：

- `[ERROR] Ollama OCR timed out` → 使用 `--timeout 600` 重试
- `[ERROR] HTTP ...` → 检查服务器状态，重试一次
- `[ERROR] ... model not found` → 先拉取模型（`ollama pull <model>`）

### 步骤 1c：失败重试

如果 OCR 输出乱码或过短（< 20 个字符），使用重试提示词再试一次：

```
python <skill_dir>/scripts/ocr_qwen.py "<image_path>" \
  --prompt "<retry_prompt>" --verbose
```

其中 `<retry_prompt>` 为：
- 中文：`"请再次仔细识别图片中的所有文字，包括题目编号、公式、条件和问题。不要遗漏任何内容。"`
- 英文：`"Please re-examine the image and extract all text, including labels, equations, conditions, and questions. Do not omit any content."`

---

## 阶段 2：生成 LaTeX 文档

根据用户模式选择文档模板，然后编写 `.tex` 文件。

### 模板 A：数学题解答（`solve` 模式）

```latex
\documentclass[12pt,a4paper]{ctexart}

% === 页面设置 ===
\usepackage[top=2.5cm, bottom=2.5cm, left=2.5cm, right=2.5cm]{geometry}

% === 数学公式 ===
\usepackage{amsmath,amssymb,amsthm}

% === 定理环境 ===
\newtheorem{definition}{定义}
\newtheorem{theorem}{定理}

% === 其他 ===
\usepackage{enumitem}
\usepackage{hyperref}

\title{\textbf{[TITLE]}}
\author{}
\date{}

\begin{document}
\maketitle

\section*{题目}

\begin{quote}
% 将 OCR 识别结果逐字还原，转换为正确的 LaTeX 数学模式
\end{quote}

\section*{解答}

% 包含推理过程、公式和框内最终答案的完整解答

\end{document}
```

**数学解答的内容要求：**
- **题目还原：** 逐字复现 OCR 结果，转换为 LaTeX 数学格式（行内用 `$...$`，独立公式用 `\[ ... \]`，分段函数用 `\begin{cases}`）。
- **解答质量：**
  - 使用概念前先给出定义
  - 至少一个严谨证明；如有其他方法能增加洞见，可一并给出
  - 清晰的逻辑流程：`\textbf{步骤一：} ...`、`\textbf{步骤二：} ...`
  - 框出最终答案：`\[ \boxed{\text{...}} \]`
- **子问题 (1), (2), (3)：** 对应编号回答。

### 模板 B：通用 OCR（`ocr` 模式）

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

% 识别出的文字内容，保留原始结构
% 根据需要适当使用 section、paragraph 和 itemize/enumerate

\end{document}
```

**纯英文内容**请使用 `\documentclass[12pt,a4paper]{article}` 代替 `ctexart`。

### 模板 C：表格提取（`table` 模式）

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

% 使用 tabular/booktabs 重建表格
% 使用 \begin{tabular}{...} \toprule ... \midrule ... \bottomrule \end{tabular}

\end{document}
```

### 模板 D：纯公式（`formula` 模式）

```latex
\documentclass[12pt,preview,border=10pt]{standalone}

\usepackage{amsmath,amssymb,amsthm}

\begin{document}

\[
% 此处放置单个公式
\]

\end{document}
```

### 模板 E：文档数字化（`document` 模式）

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

% 按文档结构识别的各章节

\end{document}
```

### 多图片处理

如果用户提供多张图片：
1. **逐张依次处理**（不要并行——避免 GPU 显存溢出）
2. 合并 OCR 结果到单个文档中，每张图片用 `\section{}` 分隔
3. 使用统一标题，如"多页文档"

### 文件存放位置

保存到用户桌面：
```
C:\Users\<username>\Desktop\<descriptive-slug>.tex
```

使用简洁、描述性的文件名（如 `math-solution.tex`、`ocr-output.tex`、`table-data.tex`）。

---

## 阶段 3：编译为 PDF

运行 xelatex **两次**以解析交叉引用：

```bash
cd <output_dir> && xelatex -interaction=nonstopmode <filename>.tex && xelatex -interaction=nonstopmode <filename>.tex
```

**为什么用 xelatex：** 中文字体支持需要 `ctexart` 配合 xelatex。切勿使用 pdflatex——它无法通过 ctex 处理 CJK 字体。对于纯英文 `article` 类文档，pdflatex 也可接受，但为了一致性，推荐使用 xelatex。

### 编译失败修复

1. 查看 `.log` 文件以定位错误
2. 常见修复方法：
   - **未转义的特殊字符：** 文本模式中的 `&` `%` `#` `_` `$` `{` `}` ——需要转义
   - **未闭合的环境：** 检查每个 `\begin{...}` 是否有对应的 `\end{...}`
   - **数学模式中的 Unicode：** 将中文/Unicode 文本移到 `$...$` 或 `\[...\]` 之外
   - **缺失宏包：** 只使用模板中列出的标准宏包
   - **未定义的命令：** 检查 `\newtheorem` 或自定义命令是否有拼写错误
3. 修复 `.tex` 文件后重新编译

### 清理

PDF 生成成功后，删除辅助文件：

```bash
rm -f <filename>.aux <filename>.log <filename>.out <filename>.toc
```

---

## 阶段 4：报告结果

告知用户：

- **PDF：** 完整路径和文件大小（如 `C:\Users\21340\Desktop\solution.pdf`，71 KB）
- **LaTeX 源码：** 完整路径（供后续编辑）
- **OCR 信息：** 使用的后端和模型、耗时
- **内容摘要：** 一段话概括处理的内容

---

## 边界情况

| 场景 | 处理方式 |
|----------|--------|
| 图片在 QQ/微信数据目录（`...\nt_qq\nt_data\Pic\...`） | 直接使用——无需复制 |
| OCR 输出中混合了文字和 LaTeX 格式片段 | 提取 LaTeX 片段并直接使用 |
| 题目有子问题 (1), (2), (3)... | 在解答部分对应编号回答 |
| 用户提供多张图片 | 逐张处理，用 `\section{}` 合并到一个文档中 |
| 纯英文内容 | 使用 `article` 类代替 `ctexart`，英文 OCR 提示词 |
| 中英混合内容 | 使用 `ctexart` 配合双语 OCR 提示词 |
| 图片为手写笔记照片 | 使用 `--mode general`，提醒用户手写 OCR 精度可能较低 |
| 图片为代码截图 | 使用 `article` 类，配合 `\begin{verbatim}` 或 `listings` 宏包 |
| 图片过大（>10 MB） | OCR 脚本会按需用 PIL 自动缩放；无需手动处理 |
| OCR 结果完全错误 | 更换 `--mode` 或自定义 `--prompt` 重试，或尝试更大的模型 |
| 用户想要 beamer 幻灯片 | 使用 `\documentclass{beamer}` 模板，每页幻灯片一个 frame |
| 未安装 Ollama | 引导用户从 https://ollama.com 安装，然后 `ollama pull qwen3-vl:2b` |

---

## 配置参考

本 skill 使用分层配置系统（上层覆盖下层）：

1. **CLI 参数** — `--backend`、`--model`、`--prompt`、`--base-url` 等
2. **环境变量** — `QWEN_BACKEND`、`QWEN_MODEL`、`QWEN_TIMEOUT`、`OPENAI_BASE_URL`、`OPENAI_API_KEY`
3. **`config.json`** — SKILL.md 同级目录下的配置文件（从 `config.example.json` 复制）

### 安装新后端

**Ollama（推荐）：**
```bash
# 安装：https://ollama.com
ollama pull qwen3-vl:2b     # 最小、最快
ollama pull qwen3-vl:8b     # 更精确
```

**OpenAI 兼容接口（以 vLLM 为例）：**
```bash
pip install vllm
python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-VL-7B-Instruct --port 8000
# 然后使用：--backend openai --base-url http://localhost:8000/v1
```

**Transformers（直接加载）：**
```bash
pip install transformers torch pillow accelerate
# 然后使用：--backend transformers --model Qwen/Qwen2.5-VL-7B-Instruct
```

---

## 备选方案：原始 Ollama CLI

如果 `scripts/ocr_qwen.py` 不可用（缺少 Python、缺少 Pillow 等），回退到原始 Ollama CLI：

```bash
ollama run qwen3-vl:2b "请仔细识别这张图片中的所有文字内容，包括题目、公式、选项等。一字不漏地输出图片中的全部文字。" <image_path>
```

**备选方案的限制：**
- 仅适用于 Ollama 后端
- 输出包含终端转义序列（旋转动画），需要手动解析
- 无超时控制、无重试提示词选择、无模式切换
- 在输出中查找 `...done thinking.` 标记之后的内容

**仅当** Python 脚本无法运行时使用此备选方案。所有正常情况下优先使用脚本。
