"""
Recipe boundary detector.

NOTE: this file did not previously exist in the repo. It was written from
scratch as part of building the OCR pipeline (see ocr_pipeline.py) rather
than being an existing, pre-validated component - treat its segmentation
quality as unproven until checked against real transcripts.

Assembles the per-page transcripts produced by ocr_pipeline.py, asks a local
Ollama text model to segment them into individual recipes, and writes:
  - ./recipes/{book_slug}.json   structured recipes (source_type: photo_ocr)
  - ./review/{book_slug}.txt     pages flagged for human review, with reasons

Usage:
    python llm_boundary_eval.py <book_slug> [--model MODEL_NAME]
"""

import argparse
import json
import re
import sys
from pathlib import Path

import requests

OLLAMA_HOST = "http://localhost:11434"
DEFAULT_TEXT_MODEL = "llama3.1:8b"
NUM_CTX = 8192
REQUEST_TIMEOUT_SECONDS = 300
PAGE_MARKER_RE = re.compile(r"<<<PAGE (\d+)>>>")

ROOT = Path(__file__).resolve().parent
TRANSCRIPTS_DIR = ROOT / "transcripts"
RECIPES_DIR = ROOT / "recipes"
REVIEW_DIR = ROOT / "review"

SEGMENT_SYSTEM_PROMPT = """You segment a cookbook transcript into individual recipes.
The transcript is a concatenation of OCR'd pages, each preceded by a marker
like <<<PAGE 003>>>. A single recipe may span multiple pages, and a single
page may contain more than one recipe.

Respond with ONLY a JSON array (no markdown fences, no commentary). Each
element must have this shape:
{
  "title": "<recipe title as printed>",
  "ingredients": ["<ingredient line>", ...],
  "instructions": ["<instruction step>", ...],
  "notes": "<sidebar/yield/time text if present, else null>",
  "start_page": <int>,
  "end_page": <int>
}
If the transcript contains no identifiable recipes, respond with an empty
JSON array: []
"""


def load_transcript(book_slug: str) -> tuple[str, dict[int, str]]:
    transcript_dir = TRANSCRIPTS_DIR / book_slug
    if not transcript_dir.exists():
        raise SystemExit(f"No transcripts found at {transcript_dir}")

    page_files = sorted(
        transcript_dir.glob("page_*.txt"),
        key=lambda p: int(re.search(r"\d+", p.stem).group()),
    )
    if not page_files:
        raise SystemExit(f"No page_*.txt files found in {transcript_dir}")

    pages_by_num: dict[int, str] = {}
    combined_parts = []
    for page_file in page_files:
        page_num = int(re.search(r"\d+", page_file.stem).group())
        text = page_file.read_text(encoding="utf-8")
        pages_by_num[page_num] = text
        combined_parts.append(f"<<<PAGE {page_num:03d}>>>\n{text}")

    return "\n\n".join(combined_parts), pages_by_num


def call_ollama_json(prompt: str, model: str) -> str:
    payload = {
        "model": model,
        "system": SEGMENT_SYSTEM_PROMPT,
        "prompt": prompt,
        "stream": False,
        "options": {"num_ctx": NUM_CTX},
    }
    resp = requests.post(
        f"{OLLAMA_HOST}/api/generate", json=payload, timeout=REQUEST_TIMEOUT_SECONDS
    )
    resp.raise_for_status()
    return resp.json().get("response", "").strip()


def extract_json_array(raw: str) -> list | None:
    raw = raw.strip()
    fence_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", raw, re.DOTALL)
    if fence_match:
        raw = fence_match.group(1)
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        return json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None


def segment_transcript(combined_text: str, model: str) -> list[dict]:
    for attempt in range(2):
        raw = call_ollama_json(combined_text, model)
        parsed = extract_json_array(raw)
        if parsed is not None:
            return parsed
        print(f"    boundary detection attempt {attempt + 1}: could not parse JSON, retrying...")
    return None  # signals total failure after retry


def build_records(recipes_raw: list[dict], book_slug: str) -> list[dict]:
    records = []
    for i, r in enumerate(recipes_raw, start=1):
        records.append(
            {
                "id": f"{book_slug}-{i:03d}",
                "title": r.get("title", "").strip(),
                "ingredients": r.get("ingredients", []),
                "instructions": r.get("instructions", []),
                "notes": r.get("notes"),
                "source_type": "photo_ocr",
                "source_book": book_slug,
                "source_pages": [r.get("start_page"), r.get("end_page")],
            }
        )
    return records


def find_unflagged_gaps(
    pages_by_num: dict[int, str], records: list[dict]
) -> list[tuple[int, str]]:
    flagged: list[tuple[int, str]] = []
    covered_pages: set[int] = set()
    for r in records:
        start, end = r["source_pages"]
        if start is None or end is None:
            continue
        covered_pages.update(range(start, end + 1))

    for page_num, text in sorted(pages_by_num.items()):
        reasons = []
        if "[illegible]" in text.lower():
            reasons.append("contains [illegible] marker")
        if page_num not in covered_pages:
            reasons.append("zero recipes detected on this page")
        if reasons:
            flagged.append((page_num, "; ".join(reasons)))
    return flagged


def run(book_slug: str, model: str) -> tuple[list[dict], list[tuple[int, str]]]:
    combined_text, pages_by_num = load_transcript(book_slug)

    recipes_raw = segment_transcript(combined_text, model)

    RECIPES_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)

    if recipes_raw is None:
        print("    boundary detection failed after retry - flagging all pages")
        records: list[dict] = []
        flagged = [(p, "boundary detection failed to return parseable JSON") for p in pages_by_num]
    else:
        records = build_records(recipes_raw, book_slug)
        flagged = find_unflagged_gaps(pages_by_num, records)

    (RECIPES_DIR / f"{book_slug}.json").write_text(
        json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    review_path = REVIEW_DIR / f"{book_slug}.txt"
    if flagged:
        lines = [f"page {p:03d}: {reason}" for p, reason in flagged]
        review_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    elif review_path.exists():
        review_path.unlink()

    print(f"Wrote {len(records)} recipe(s) to {RECIPES_DIR / f'{book_slug}.json'}")
    print(f"Flagged {len(flagged)} page(s) for review.")
    return records, flagged


def main() -> None:
    parser = argparse.ArgumentParser(description="Segment OCR transcripts into recipes")
    parser.add_argument("book_slug")
    parser.add_argument("--model", default=DEFAULT_TEXT_MODEL)
    args = parser.parse_args()
    run(args.book_slug, args.model)


if __name__ == "__main__":
    main()
