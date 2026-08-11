#!/usr/bin/env python3
"""
Unified OCR interface for Qwen VL models.

Supports multiple inference backends:
  - ollama           Local Ollama server (default, zero-config)
  - openai_compatible OpenAI-compatible API (vLLM, SGLang, llama.cpp server, etc.)
  - transformers      Direct HuggingFace transformers (GPU recommended)

Usage:
  python ocr_qwen.py <image_path> [options]

Examples:
  # Auto-detect backend (tries ollama → openai → transformers)
  python ocr_qwen.py photo.jpg

  # Explicit backend and model
  python ocr_qwen.py photo.jpg --backend ollama --model qwen3-vl:8b

  # Custom OCR prompt (use {lang} placeholder for auto-fill)
  python ocr_qwen.py scan.png --prompt "Extract all text from this document."

  # Specify language hint for prompt selection
  python ocr_qwen.py scan.png --lang en

  # OpenAI-compatible backend with custom endpoint
  python ocr_qwen.py photo.jpg --backend openai --base-url http://localhost:8000/v1

Environment variables:
  QWEN_BACKEND     Default backend (auto|ollama|openai|transformers)
  QWEN_MODEL       Default model name
  OPENAI_BASE_URL  OpenAI-compatible API base URL
  OPENAI_API_KEY   API key for OpenAI-compatible backend
"""

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# ─── Configuration defaults ───────────────────────────────────────────

DEFAULT_CONFIG = {
    "backend": "auto",
    "model": "qwen3-vl:2b",
    "timeout": 300,
    "backends": {
        "ollama": {
            "model": "qwen3-vl:2b",
            "host": "http://localhost:11434",
        },
        "openai_compatible": {
            "model": "qwen3-vl-8b",
            "base_url": "http://localhost:8000/v1",
            "api_key": "not-needed",
        },
        "transformers": {
            "model": "Qwen/Qwen2.5-VL-7B-Instruct",
            "device": "auto",
            "torch_dtype": "auto",
        },
    },
}

# ─── Prompts ───────────────────────────────────────────────────────────

PROMPTS = {
    "zh": (
        "请仔细识别这张图片中的所有文字内容，包括题目、公式、选项等。"
        "一字不漏地输出图片中的全部文字。"
    ),
    "zh-retry": (
        "请再次仔细识别图片中的所有文字，包括题目编号、公式、条件和问题。"
        "不要遗漏任何内容。"
    ),
    "en": (
        "Please carefully recognize all text content in this image, "
        "including titles, formulas, tables, and options. "
        "Output every word exactly as it appears. Do not miss anything."
    ),
    "en-retry": (
        "Please re-examine the image and extract all text, "
        "including labels, equations, conditions, and questions. "
        "Do not omit any content."
    ),
    "general": (
        "Extract and transcribe all visible text from this image. "
        "Preserve the original structure (paragraphs, lists, tables). "
        "Output the text verbatim."
    ),
    "math": (
        "Extract all mathematical content from this image. "
        "For formulas, use LaTeX notation ($...$ for inline, $$...$$ for display). "
        "Transcribe all text, numbers, and symbols exactly."
    ),
    "table": (
        "Extract the table from this image. "
        "Output it as a pipe-delimited markdown table. "
        "Preserve all cell content exactly, including numbers and units."
    ),
}


def load_config(config_path: Optional[str] = None) -> dict:
    """Load configuration from JSON file, with env var overrides."""
    config = DEFAULT_CONFIG.copy()

    # Try to find config.json
    search_paths = [
        config_path,
        Path(__file__).parent.parent / "config.json",
        Path.cwd() / "config.json",
    ]
    for p in search_paths:
        if p and Path(p).exists():
            try:
                with open(p, encoding="utf-8") as f:
                    user_config = json.load(f)
                _deep_merge(config, user_config)
                break
            except (json.JSONDecodeError, OSError):
                pass

    # Environment variable overrides
    if os.environ.get("QWEN_BACKEND"):
        config["backend"] = os.environ["QWEN_BACKEND"]
    if os.environ.get("QWEN_MODEL"):
        config["model"] = os.environ["QWEN_MODEL"]
    if os.environ.get("QWEN_TIMEOUT"):
        config["timeout"] = int(os.environ["QWEN_TIMEOUT"])
    if os.environ.get("OPENAI_BASE_URL"):
        config["backends"]["openai_compatible"]["base_url"] = os.environ["OPENAI_BASE_URL"]
    if os.environ.get("OPENAI_API_KEY"):
        config["backends"]["openai_compatible"]["api_key"] = os.environ["OPENAI_API_KEY"]

    return config


def _deep_merge(base: dict, override: dict) -> None:
    """Recursively merge override into base in-place."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


# ─── Backend: Ollama ───────────────────────────────────────────────────

def _check_ollama_available() -> bool:
    """Check if Ollama is installed and has Qwen VL models."""
    if not shutil.which("ollama"):
        return False
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
        # Look for any qwen vl model
        return "qwen" in result.stdout.lower() and "vl" in result.stdout.lower()
    except Exception:
        return False


def _ocr_ollama(image_path: str, model: str, prompt: str, timeout: int) -> str:
    """Run OCR via Ollama CLI."""
    abs_path = str(Path(image_path).resolve())

    cmd = ["ollama", "run", model, prompt, abs_path]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout
        # Clean up terminal escape sequences (spinner animation)
        output = _clean_ollama_output(output)
        return output.strip()
    except subprocess.TimeoutExpired:
        return f"[ERROR] Ollama OCR timed out after {timeout}s"
    except FileNotFoundError:
        return "[ERROR] ollama command not found. Install from https://ollama.com"
    except Exception as e:
        return f"[ERROR] Ollama OCR failed: {e}"


def _clean_ollama_output(raw: str) -> str:
    """Remove terminal escape sequences and spinner noise from ollama output."""
    import re
    # Remove ANSI escape sequences
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    cleaned = ansi_escape.sub('', raw)
    # Remove carriage returns
    cleaned = cleaned.replace('\r', '')
    # Try to find content after the thinking marker
    if 'done thinking.' in cleaned:
        parts = cleaned.split('done thinking.', 1)
        return parts[1].strip()
    # If no marker, return the longest non-empty line group
    lines = [l.strip() for l in cleaned.split('\n') if l.strip()]
    if lines:
        return '\n'.join(lines)
    return cleaned.strip()


# ─── Backend: OpenAI-compatible ────────────────────────────────────────

def _check_openai_available(base_url: str) -> bool:
    """Check if an OpenAI-compatible endpoint is reachable."""
    try:
        import urllib.request
        req = urllib.request.Request(f"{base_url.rstrip('/')}/models")
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req, timeout=5)
        return True
    except Exception:
        return False


def _ocr_openai(image_path: str, model: str, prompt: str,
                base_url: str, api_key: str, timeout: int) -> str:
    """Run OCR via OpenAI-compatible API (vLLM, SGLang, etc.)."""
    import urllib.request
    import urllib.error

    # Read and encode image
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    # Detect MIME type
    ext = Path(image_path).suffix.lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".png": "image/png", ".gif": "image/gif",
                ".webp": "image/webp", ".bmp": "image/bmp"}
    mime_type = mime_map.get(ext, "image/png")

    data_url = f"data:{mime_type};base64,{image_data}"

    payload = json.dumps({
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "max_tokens": 4096,
        "temperature": 0.1,
    }).encode("utf-8")

    url = f"{base_url.rstrip('/')}/chat/completions"
    req = urllib.request.Request(url, data=payload)
    req.add_header("Content-Type", "application/json")
    if api_key and api_key != "not-needed":
        req.add_header("Authorization", f"Bearer {api_key}")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            content = result["choices"][0]["message"]["content"]
            return content.strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return f"[ERROR] HTTP {e.code}: {body[:500]}"
    except Exception as e:
        return f"[ERROR] OpenAI-compatible OCR failed: {e}"


# ─── Backend: Transformers ─────────────────────────────────────────────

def _check_transformers_available() -> bool:
    """Check if transformers and torch are installed."""
    try:
        import importlib
        importlib.import_module("transformers")
        importlib.import_module("torch")
        return True
    except ImportError:
        return False


def _ocr_transformers(image_path: str, model_name: str, prompt: str,
                      device: str, torch_dtype: str, timeout: int) -> str:
    """Run OCR via HuggingFace transformers (direct model loading)."""
    try:
        import torch
        from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
        from PIL import Image
    except ImportError as e:
        return f"[ERROR] Missing dependency: {e}. Install with: pip install transformers torch pillow"

    try:
        # Determine device
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"

        # Determine dtype
        if torch_dtype == "auto":
            dtype = torch.bfloat16 if device == "cuda" else torch.float32
        else:
            dtype = getattr(torch, torch_dtype, torch.float32)

        # Load model and processor
        model = Qwen2VLForConditionalGeneration.from_pretrained(
            model_name,
            torch_dtype=dtype,
            device_map=device if device == "cuda" else None,
        )
        processor = AutoProcessor.from_pretrained(model_name)

        # Prepare inputs
        image = Image.open(image_path).convert("RGB")
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = processor(text=[text], images=[image], return_tensors="pt")

        if device == "cuda":
            inputs = inputs.to("cuda")

        # Generate
        with torch.no_grad():
            generated_ids = model.generate(**inputs, max_new_tokens=4096)
        generated_ids = generated_ids[:, inputs["input_ids"].shape[1]:]
        output = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

        # Cleanup
        del model, processor, inputs
        if device == "cuda":
            torch.cuda.empty_cache()

        return output.strip()
    except Exception as e:
        return f"[ERROR] Transformers OCR failed: {e}"


# ─── Auto-detection ────────────────────────────────────────────────────

def detect_backend(config: dict) -> str:
    """Auto-detect the best available backend.

    Priority: ollama > openai_compatible > transformers
    """
    # 1. Try Ollama (fastest, zero-config)
    if _check_ollama_available():
        return "ollama"

    # 2. Try OpenAI-compatible endpoint
    openai_config = config["backends"]["openai_compatible"]
    if _check_openai_available(openai_config["base_url"]):
        return "openai_compatible"

    # 3. Try transformers
    if _check_transformers_available():
        return "transformers"

    return "none"


def list_available_models(backend: str, config: dict) -> list:
    """List available Qwen VL models for the given backend."""
    if backend == "ollama":
        try:
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
            models = []
            for line in result.stdout.strip().split("\n")[1:]:  # skip header
                parts = line.split()
                if parts:
                    name = parts[0]
                    if "qwen" in name.lower() and "vl" in name.lower():
                        models.append(name)
            return models
        except Exception:
            return []
    elif backend == "openai_compatible":
        # Can't enumerate easily; return configured model
        return [config["backends"]["openai_compatible"]["model"]]
    elif backend == "transformers":
        return [config["backends"]["transformers"]["model"]]
    return []


# ─── Main ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Unified OCR interface for Qwen VL models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s photo.jpg
  %(prog)s photo.jpg --backend ollama --model qwen3-vl:8b
  %(prog)s scan.png --lang en --backend openai
  %(prog)s table.png --mode table

Available modes:
  general  - Extract all text verbatim (default)
  math     - Extract math content with LaTeX notation
  table    - Extract table as markdown
        """,
    )
    parser.add_argument("image", nargs="?", help="Path to the input image")
    parser.add_argument("--backend", "-b",
                        choices=["auto", "ollama", "openai", "transformers"],
                        default=None,
                        help="Inference backend (default: auto-detect)")
    parser.add_argument("--model", "-m", default=None,
                        help="Model name (overrides config)")
    parser.add_argument("--prompt", "-p", default=None,
                        help="Custom OCR prompt")
    parser.add_argument("--lang", "-l", choices=["zh", "en"], default="zh",
                        help="Language hint for default prompt (default: zh)")
    parser.add_argument("--mode", choices=["general", "math", "table"],
                        default="general",
                        help="OCR mode — selects a tuned prompt (default: general)")
    parser.add_argument("--timeout", "-t", type=int, default=None,
                        help="Timeout in seconds")
    parser.add_argument("--base-url", default=None,
                        help="OpenAI-compatible API base URL")
    parser.add_argument("--api-key", default=None,
                        help="API key for OpenAI-compatible backend")
    parser.add_argument("--config", "-c", default=None,
                        help="Path to config.json")
    parser.add_argument("--list-backends", action="store_true",
                        help="List available backends and exit")
    parser.add_argument("--list-models", action="store_true",
                        help="List available Qwen VL models and exit")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output (show backend/model being used)")

    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # Resolve backend
    backend = args.backend or config["backend"]
    if backend == "auto":
        backend = detect_backend(config)

    # Normalize backend names
    backend_aliases = {"openai": "openai_compatible"}
    backend = backend_aliases.get(backend, backend)

    # --list-backends and --list-models don't require an image
    if args.list_backends:
        print("Available Qwen VL backends:")
        print(f"  ollama:            {'[OK] detected' if _check_ollama_available() else '[X] not found'}")
        openai_ok = _check_openai_available(
            args.base_url or config["backends"]["openai_compatible"]["base_url"]
        )
        print(f"  openai_compatible: {'[OK] reachable' if openai_ok else '[X] not reachable'}")
        print(f"  transformers:      {'[OK] installed' if _check_transformers_available() else '[X] not installed'}")
        print(f"\n  -> Auto-selected: {backend}")
        return 0

    if args.list_models:
        models = list_available_models(backend, config)
        if models:
            print(f"Available Qwen VL models ({backend}):")
            for m in models:
                print(f"  - {m}")
        else:
            print(f"No Qwen VL models found for backend: {backend}")
        return 0

    # Validate image is provided for OCR operations
    if not args.image:
        parser.error("the following arguments are required: image")

    # Validate image
    image_path = args.image
    if not Path(image_path).exists():
        print(f"[ERROR] Image not found: {image_path}", file=sys.stderr)
        return 1
    if not Path(image_path).is_file():
        print(f"[ERROR] Not a file: {image_path}", file=sys.stderr)
        return 1

    # Resolve model
    model = args.model or config["model"]
    backend_config = config["backends"].get(backend, {})
    if "model" in backend_config and not args.model:
        model = backend_config["model"]

    # Resolve prompt
    if args.prompt:
        prompt = args.prompt
    elif args.mode != "general":
        prompt = PROMPTS.get(args.mode, PROMPTS["general"])
    else:
        prompt = PROMPTS.get(args.lang, PROMPTS["zh"])

    # Resolve timeout
    timeout = args.timeout or config.get("timeout", 300)

    # Verbose info
    if args.verbose:
        print(f"Backend: {backend}", file=sys.stderr)
        print(f"Model:   {model}", file=sys.stderr)
        print(f"Prompt:  {prompt[:80]}...", file=sys.stderr)
        print(f"Timeout: {timeout}s", file=sys.stderr)
        print("─" * 40, file=sys.stderr)

    # Run OCR
    start_time = time.time()

    if backend == "ollama":
        result = _ocr_ollama(image_path, model, prompt, timeout)
    elif backend == "openai_compatible":
        base_url = args.base_url or backend_config.get("base_url", "http://localhost:8000/v1")
        api_key = args.api_key or backend_config.get("api_key", "not-needed")
        result = _ocr_openai(image_path, model, prompt, base_url, api_key, timeout)
    elif backend == "transformers":
        device = backend_config.get("device", "auto")
        torch_dtype = backend_config.get("torch_dtype", "auto")
        result = _ocr_transformers(image_path, model, prompt, device, torch_dtype, timeout)
    elif backend == "none":
        print("[ERROR] No Qwen VL backend detected.", file=sys.stderr)
        print("Install one of:", file=sys.stderr)
        print("  1. Ollama:  https://ollama.com  (recommended)", file=sys.stderr)
        print("  2. vLLM:    pip install vllm", file=sys.stderr)
        print("  3. Transformers: pip install transformers torch", file=sys.stderr)
        return 1
    else:
        print(f"[ERROR] Unknown backend: {backend}", file=sys.stderr)
        return 1

    elapsed = time.time() - start_time

    if args.verbose:
        print(f"Done in {elapsed:.1f}s", file=sys.stderr)
        print("─" * 40, file=sys.stderr)

    # Check for errors
    if result.startswith("[ERROR]"):
        print(result, file=sys.stderr)
        return 1

    # Output the recognized text
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
