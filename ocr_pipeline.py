"""
Cookbook OCR pipeline: renders PDF pages to PNG and transcribes each page
via the OpenAI vision API.

Usage:
    python ocr_pipeline.py <pdf_path> [--pages 17,18 | --pages 17-20] [--max-pages N] [--model MODEL_NAME]
"""

import argparse
import base64
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

DEFAULT_MODEL = "gpt-6-luna"
IMAGE_DETAIL = "original"  # best for OCR: preserves fine detail/coordinates
NUM_RETRIES = 1
RETRY_BACKOFF_SECONDS = 2
RENDER_DPI = 300

ROOT = Path(__file__).resolve().parent
PROMPT_PATH = ROOT / "ocr_prompt.txt"
PAGES_DIR = ROOT / "pages"
TRANSCRIPTS_DIR = ROOT / "transcripts"


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "book"


def get_client() -> OpenAI:
    load_dotenv(ROOT / ".env")
    import os

    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit(
            "OPENAI_API_KEY is not set. Set it yourself outside this session, e.g.:\n"
            '  setx OPENAI_API_KEY "sk-..."   (then open a new terminal)\n'
            "or copy .env.example to .env and fill in the real key in a text editor.\n"
            "Never paste the key into a chat/agent conversation."
        )
    return OpenAI()


def parse_page_spec(spec: str, total_pages: int) -> list[int]:
    """Parses '17,18' or '17-20' or a mix into a sorted list of 1-indexed page numbers."""
    pages: set[int] = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            start_s, end_s = chunk.split("-", 1)
            start, end = int(start_s), int(end_s)
        else:
            start = end = int(chunk)
        for p in range(start, end + 1):
            if 1 <= p <= total_pages:
                pages.add(p)
    return sorted(pages)


def render_pages(pdf_path: Path, book_slug: str, page_numbers: list[int]) -> list[tuple[int, Path]]:
    import pymupdf

    out_dir = PAGES_DIR / book_slug
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open(pdf_path)
    rendered = []
    for page_num in page_numbers:
        page = doc[page_num - 1]
        pix = page.get_pixmap(dpi=RENDER_DPI)
        out_path = out_dir / f"page_{page_num:03d}.png"
        pix.save(out_path)
        rendered.append((page_num, out_path))
    doc.close()
    return rendered


def transcribe_page(client: OpenAI, image_path: Path, model: str, prompt: str) -> dict:
    image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {
                        "type": "input_image",
                        "image_url": f"data:image/png;base64,{image_b64}",
                        "detail": IMAGE_DETAIL,
                    },
                ],
            }
        ],
    )
    usage = getattr(response, "usage", None)
    return {
        "text": (response.output_text or "").strip(),
        "model": response.model,
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }


def transcribe_with_retry(client: OpenAI, image_path: Path, model: str, prompt: str) -> dict:
    """Returns a manifest-entry dict. status is 'ok', 'empty', or 'flagged'.

    A genuinely empty response (e.g. a photo-only page with no text) is not
    an error - retrying it would just burn another API call for the same
    result, so it's recorded as 'empty' on the first attempt with no retry.
    Only real API/network failures use the retry budget.
    """
    last_error = None
    elapsed = 0.0
    for attempt in range(NUM_RETRIES + 1):
        start = time.monotonic()
        try:
            result = transcribe_page(client, image_path, model, prompt)
        except Exception as exc:  # noqa: BLE001 - bounded retry wraps any API/network failure
            elapsed = time.monotonic() - start
            last_error = str(exc)
            print(f"    attempt {attempt + 1} error: {last_error}")
            if attempt < NUM_RETRIES:
                print(f"    request failed for {image_path.name}, retrying once...")
                time.sleep(RETRY_BACKOFF_SECONDS)
            continue

        elapsed = time.monotonic() - start
        result["elapsed_seconds"] = round(elapsed, 2)
        result["error"] = None
        result["status"] = "ok" if result["text"] else "empty"
        return result

    return {
        "text": "",
        "model": model,
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "elapsed_seconds": round(elapsed, 2),
        "status": "flagged",
        "error": last_error,
    }


def run(pdf_path: Path, page_numbers: list[int] | None, model: str, output_dir: Path) -> None:
    client = get_client()

    book_slug = slugify(pdf_path.stem)
    prompt = PROMPT_PATH.read_text(encoding="utf-8")

    import pymupdf

    with pymupdf.open(pdf_path) as doc:
        total_pages = len(doc)

    pages_to_run = page_numbers if page_numbers is not None else list(range(1, total_pages + 1))

    transcripts_out = output_dir / book_slug
    transcripts_out.mkdir(parents=True, exist_ok=True)

    print(f"Rendering {len(pages_to_run)} page(s) for '{book_slug}' at {RENDER_DPI} DPI...")
    rendered = render_pages(pdf_path, book_slug, pages_to_run)

    manifest = []
    for idx, (page_num, image_path) in enumerate(rendered, start=1):
        print(f"[{idx}/{len(rendered)}] OCR page {page_num} with model={model}")
        result = transcribe_with_retry(client, image_path, model, prompt)

        text = result["text"]
        if result["status"] == "flagged":
            text = f"[illegible] OCR request failed after retry: {result['error']}\n" + text
        elif result["status"] == "empty":
            text = "[no text on page]"

        out_path = transcripts_out / f"page_{page_num:03d}.txt"
        out_path.write_text(text, encoding="utf-8")

        manifest.append(
            {
                "pdf_page": page_num,
                "source_image": str(image_path),
                "model": result["model"],
                "elapsed_seconds": result["elapsed_seconds"],
                "input_tokens": result["input_tokens"],
                "output_tokens": result["output_tokens"],
                "total_tokens": result["total_tokens"],
                "status": result["status"],
                "error": result["error"],
            }
        )

    import json

    manifest_path = transcripts_out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    flagged = [m["pdf_page"] for m in manifest if m["status"] == "flagged"]
    empty = [m["pdf_page"] for m in manifest if m["status"] == "empty"]
    total_tokens = sum(m["total_tokens"] or 0 for m in manifest)
    print(f"Done. Transcripts written to {transcripts_out}")
    print(f"Manifest written to {manifest_path}")
    print(f"Total tokens used: {total_tokens}")
    if empty:
        print(f"Pages with no text (photo-only, not an error): {empty}")
    if flagged:
        print(f"Flagged pages (failed after retry): {flagged}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cookbook OCR pipeline (OpenAI vision)")
    parser.add_argument("pdf_path", type=Path)
    parser.add_argument("--pages", type=str, default=None, help="e.g. '17,18' or '17-20'")
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--output-dir", type=Path, default=TRANSCRIPTS_DIR)
    args = parser.parse_args()

    if not args.pdf_path.exists():
        raise SystemExit(f"PDF not found: {args.pdf_path}")

    import pymupdf

    with pymupdf.open(args.pdf_path) as doc:
        total_pages = len(doc)

    if args.pages:
        page_numbers = parse_page_spec(args.pages, total_pages)
    elif args.max_pages:
        page_numbers = list(range(1, min(args.max_pages, total_pages) + 1))
    else:
        page_numbers = None

    run(args.pdf_path, page_numbers, args.model, args.output_dir)


if __name__ == "__main__":
    main()
