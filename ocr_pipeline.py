"""
Cookbook OCR pipeline: renders PDF pages to PNG, transcribes each page via a
local Ollama vision model, and saves the raw transcript per page.

Usage:
    python ocr_pipeline.py <pdf_path> [--max-pages N] [--model MODEL_NAME]
"""

import argparse
import base64
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

OLLAMA_HOST = "http://localhost:11434"
DEFAULT_MODEL = "qwen3-vl:8b"
FALLBACK_MODEL = "glm-ocr"
CPU_OFFLOAD_SWITCH_THRESHOLD = 50  # percent
CPU_CHECK_AFTER_PAGE = 3
NUM_CTX = 4096
RENDER_DPI = 300
REQUEST_TIMEOUT_SECONDS = 300

ROOT = Path(__file__).resolve().parent
PROMPT_PATH = ROOT / "ocr_prompt.txt"
PAGES_DIR = ROOT / "pages"
TRANSCRIPTS_DIR = ROOT / "transcripts"


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "book"


def ensure_ollama_running() -> None:
    try:
        resp = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        resp.raise_for_status()
        return
    except requests.exceptions.RequestException:
        pass

    print("Ollama not reachable at localhost:11434 - starting it...")
    subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    for _ in range(20):
        time.sleep(1)
        try:
            resp = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
            if resp.ok:
                return
        except requests.exceptions.RequestException:
            continue
    raise RuntimeError("Ollama did not become reachable after starting it")


def render_pages(pdf_path: Path, book_slug: str, max_pages: int | None) -> list[Path]:
    import pymupdf

    out_dir = PAGES_DIR / book_slug
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open(pdf_path)
    total = len(doc) if max_pages is None else min(max_pages, len(doc))
    page_paths = []
    for i in range(total):
        page = doc[i]
        pix = page.get_pixmap(dpi=RENDER_DPI)
        out_path = out_dir / f"page_{i + 1:03d}.png"
        pix.save(out_path)
        page_paths.append(out_path)
    doc.close()
    return page_paths


def transcribe_page(image_path: Path, model: str, prompt: str) -> str:
    image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    payload = {
        "model": model,
        "prompt": prompt,
        "images": [image_b64],
        "stream": False,
        "options": {"num_ctx": NUM_CTX},
    }
    resp = requests.post(
        f"{OLLAMA_HOST}/api/generate", json=payload, timeout=REQUEST_TIMEOUT_SECONDS
    )
    resp.raise_for_status()
    return resp.json().get("response", "").strip()


def transcribe_with_retry(image_path: Path, model: str, prompt: str) -> tuple[str, bool]:
    """Returns (text, flagged). flagged=True if the page failed even after one retry."""
    for attempt in range(2):
        try:
            text = transcribe_page(image_path, model, prompt)
        except requests.exceptions.RequestException as exc:
            text = ""
            print(f"    attempt {attempt + 1} request error: {exc}")
        if text:
            return text, False
        if attempt == 0:
            print(f"    empty/failed response for {image_path.name}, retrying once...")
    return "", True


def check_cpu_offload(model: str) -> float | None:
    """Parses `ollama ps` PROCESSOR column for the given model's CPU percentage."""
    try:
        result = subprocess.run(
            ["ollama", "ps"], capture_output=True, text=True, timeout=10, check=True
        )
    except (subprocess.SubprocessError, FileNotFoundError) as exc:
        print(f"    could not run 'ollama ps': {exc}")
        return None

    for line in result.stdout.splitlines()[1:]:
        if not line.strip() or not line.startswith(model.split(":")[0]):
            continue
        match = re.search(r"(\d+)%\s*CPU", line)
        if match:
            return float(match.group(1))
        if "100% GPU" in line:
            return 0.0
    return None


def run(pdf_path: Path, max_pages: int | None, model_override: str | None) -> None:
    ensure_ollama_running()

    book_slug = slugify(pdf_path.stem)
    prompt = PROMPT_PATH.read_text(encoding="utf-8")

    transcripts_out = TRANSCRIPTS_DIR / book_slug
    transcripts_out.mkdir(parents=True, exist_ok=True)

    print(f"Rendering pages for '{book_slug}' at {RENDER_DPI} DPI...")
    page_paths = render_pages(pdf_path, book_slug, max_pages)
    print(f"Rendered {len(page_paths)} page(s).")

    model = model_override or DEFAULT_MODEL
    switched = False
    flagged_pages: list[int] = []

    for idx, image_path in enumerate(page_paths, start=1):
        print(f"[{idx}/{len(page_paths)}] OCR page {idx} with model={model}")
        text, flagged = transcribe_with_retry(image_path, model, prompt)
        if flagged:
            flagged_pages.append(idx)
            text = "[illegible] OCR request failed after retry\n" + text

        out_path = transcripts_out / f"page_{idx:03d}.txt"
        out_path.write_text(text, encoding="utf-8")

        if not switched and not model_override and idx >= CPU_CHECK_AFTER_PAGE:
            cpu_pct = check_cpu_offload(model)
            if cpu_pct is not None and cpu_pct > CPU_OFFLOAD_SWITCH_THRESHOLD:
                print(
                    f"    ollama ps shows {cpu_pct:.0f}% CPU offload for {model} "
                    f"(>{CPU_OFFLOAD_SWITCH_THRESHOLD}%) - switching to {FALLBACK_MODEL}"
                )
                model = FALLBACK_MODEL
                switched = True

    print(f"Done. Transcripts written to {transcripts_out}")
    if flagged_pages:
        print(f"Flagged pages (failed after retry): {flagged_pages}")
    if switched:
        print(f"Model was switched from {DEFAULT_MODEL} to {FALLBACK_MODEL} mid-run.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cookbook OCR pipeline")
    parser.add_argument("pdf_path", type=Path)
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--model", type=str, default=None)
    args = parser.parse_args()

    if not args.pdf_path.exists():
        raise SystemExit(f"PDF not found: {args.pdf_path}")

    run(args.pdf_path, args.max_pages, args.model)


if __name__ == "__main__":
    main()
