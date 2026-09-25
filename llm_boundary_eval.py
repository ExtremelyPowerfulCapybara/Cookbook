"""
Recipe boundary detector.

Assembles the per-page transcripts produced by ocr_pipeline.py, asks an
OpenAI text model to segment them into individual recipes, and writes:
  - ./recipes/{book_slug}.json   structured recipes (source_type: photo_ocr)
  - ./review/{book_slug}.txt     pages flagged for human review, with reasons

Usage:
    python llm_boundary_eval.py <book_slug> [--model MODEL_NAME]
"""

import argparse
import json
import re
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

DEFAULT_MODEL = "gpt-6-luna"
NUM_RETRIES = 2

# Whole-book transcripts fit in a single 1M+ context call, but pushing the
# model to produce 100+ recipes' worth of JSON in one response was observed
# to make it "economize" on output: ingredients got joined into one
# semicolon-separated string per recipe instead of one array element each.
# Chunking with overlap (so a recipe split across a chunk boundary is still
# fully visible in at least one chunk) keeps each call's output small enough
# that the model reliably follows the array-per-item format.
CHUNK_SIZE = 24
CHUNK_OVERLAP = 6

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
  "ingredients": ["<one ingredient per element>", ...],
  "instructions": ["<one step per element>", ...],
  "notes": "<sidebar/yield/time text if present, else null>",
  "start_page": <int>,
  "end_page": <int>
}

Formatting rules - follow these exactly, even when the transcript is long:
- Every ingredient printed on its own line in the source is its own array
  element. Never join multiple ingredients into one string with semicolons
  or commas.
- Every instruction step is its own array element. Never merge the whole
  method into a single paragraph string.
- Preserve quantities and units exactly as printed.

If the transcript contains no identifiable recipes, respond with an empty
JSON array: []
"""


def get_client() -> OpenAI:
    load_dotenv(ROOT / ".env")
    import os

    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit(
            "OPENAI_API_KEY is not set. Set it yourself outside this session "
            "(see .env.example / ocr_pipeline.py for instructions)."
        )
    return OpenAI()


def load_transcript(book_slug: str) -> dict[int, str]:
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
    for page_file in page_files:
        page_num = int(re.search(r"\d+", page_file.stem).group())
        pages_by_num[page_num] = page_file.read_text(encoding="utf-8")

    return pages_by_num


def build_combined_text(pages_by_num: dict[int, str], page_numbers: list[int]) -> str:
    parts = [f"<<<PAGE {p:03d}>>>\n{pages_by_num[p]}" for p in page_numbers]
    return "\n\n".join(parts)


def chunk_pages(all_pages: list[int], chunk_size: int, overlap: int) -> list[list[int]]:
    """Splits sorted page numbers into overlapping windows so a recipe that
    falls near a chunk boundary is still fully contained in at least one chunk."""
    if len(all_pages) <= chunk_size:
        return [all_pages]

    step = chunk_size - overlap
    chunks = []
    i = 0
    n = len(all_pages)
    while i < n:
        chunks.append(all_pages[i : i + chunk_size])
        if i + chunk_size >= n:
            break
        i += step
    return chunks


def call_openai_json(client: OpenAI, combined_text: str, model: str) -> str:
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": SEGMENT_SYSTEM_PROMPT},
            {"role": "user", "content": combined_text},
        ],
    )
    return (response.output_text or "").strip()


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


def segment_transcript(client: OpenAI, combined_text: str, model: str) -> list[dict] | None:
    for attempt in range(NUM_RETRIES + 1):
        try:
            raw = call_openai_json(client, combined_text, model)
        except Exception as exc:  # noqa: BLE001 - bounded retry wraps any API/network failure
            print(f"    boundary detection attempt {attempt + 1}: request error: {exc}")
            continue
        parsed = extract_json_array(raw)
        if parsed is not None:
            return parsed
        print(f"    boundary detection attempt {attempt + 1}: could not parse JSON, retrying...")
    return None  # signals total failure after retry


def segment_chunk_recursive(
    client: OpenAI,
    pages_by_num: dict[int, str],
    page_numbers: list[int],
    model: str,
    min_size: int = 4,
) -> tuple[list[dict], list[int]]:
    """Segments a page range, and if it fails after retries (e.g. a content
    filter false-positive triggered by that specific window of text), splits
    it into two smaller windows and retries each independently rather than
    giving up on the whole range."""
    combined_text = build_combined_text(pages_by_num, page_numbers)
    recipes_raw = segment_transcript(client, combined_text, model)
    if recipes_raw is not None:
        return recipes_raw, []

    if len(page_numbers) <= min_size:
        print(f"    giving up on pages {page_numbers[0]:03d}-{page_numbers[-1]:03d} after retries")
        return [], list(page_numbers)

    print(f"    splitting pages {page_numbers[0]:03d}-{page_numbers[-1]:03d} into two smaller chunks and retrying")
    mid = len(page_numbers) // 2
    left_recipes, left_failed = segment_chunk_recursive(
        client, pages_by_num, page_numbers[:mid], model, min_size
    )
    right_recipes, right_failed = segment_chunk_recursive(
        client, pages_by_num, page_numbers[mid:], model, min_size
    )
    return left_recipes + right_recipes, left_failed + right_failed


def repair_condensed_list(items: list) -> list:
    """Fallback for a model response that condensed a whole ingredient/step
    list into one semicolon-joined string instead of separate array elements."""
    if len(items) == 1 and isinstance(items[0], str) and items[0].count(";") >= 2:
        parts = [p.strip() for p in items[0].split(";") if p.strip()]
        if len(parts) > 1:
            return parts
    return items


def merge_chunk_results(chunk_recipe_lists: list[list[dict]]) -> list[dict]:
    """Merges recipes from overlapping chunks, deduplicating recipes that were
    detected in more than one chunk's overlap region."""
    seen = set()
    merged = []
    for recipes in chunk_recipe_lists:
        for r in recipes:
            key = (r.get("start_page"), (r.get("title") or "").strip().lower())
            if key in seen:
                continue
            seen.add(key)
            merged.append(r)
    merged.sort(key=lambda r: (r.get("start_page") or 0, r.get("end_page") or 0))
    return merged


def build_records(recipes_raw: list[dict], book_slug: str) -> list[dict]:
    records = []
    for i, r in enumerate(recipes_raw, start=1):
        records.append(
            {
                "id": f"{book_slug}-{i:03d}",
                "title": r.get("title", "").strip(),
                "ingredients": repair_condensed_list(r.get("ingredients", [])),
                "instructions": repair_condensed_list(r.get("instructions", [])),
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
    client = get_client()
    pages_by_num = load_transcript(book_slug)

    all_pages = sorted(pages_by_num)
    chunks = chunk_pages(all_pages, CHUNK_SIZE, CHUNK_OVERLAP)

    RECIPES_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)

    chunk_results: list[list[dict]] = []
    failed_chunks: list[list[int]] = []
    for idx, chunk_page_numbers in enumerate(chunks, start=1):
        print(
            f"[{idx}/{len(chunks)}] segmenting pages "
            f"{chunk_page_numbers[0]:03d}-{chunk_page_numbers[-1]:03d}"
        )
        recipes_raw, failed_pages = segment_chunk_recursive(client, pages_by_num, chunk_page_numbers, model)
        chunk_results.append(recipes_raw)
        if failed_pages:
            failed_chunks.append(failed_pages)

    merged_raw = merge_chunk_results(chunk_results)
    records = build_records(merged_raw, book_slug)
    flagged = find_unflagged_gaps(pages_by_num, records)
    for chunk_page_numbers in failed_chunks:
        for p in chunk_page_numbers:
            flagged.append((p, "boundary detection failed to return parseable JSON for this chunk"))
    flagged = sorted(set(flagged))

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
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()
    run(args.book_slug, args.model)


if __name__ == "__main__":
    main()
