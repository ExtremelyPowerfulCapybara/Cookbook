"""
Exports recipes/*.json into individual Obsidian-ready markdown notes, one
file per recipe, with YAML frontmatter for Dataview queries plus a readable
markdown body for full-text search.

Usage:
    python export_to_obsidian.py <output_dir> [--book BOOK_SLUG]

<output_dir> can be any folder, including one inside your Obsidian vault.
Existing notes for the same recipe id are overwritten on re-export.
"""

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RECIPES_DIR = ROOT / "recipes"

# Keyword -> tag, scanned across title + ingredients. Order doesn't matter;
# a recipe can pick up multiple tags (protein, dish type, cook method).
TAG_KEYWORDS: dict[str, list[str]] = {
    "chicken": ["chicken"],
    "beef": ["beef", "steak", "brisket"],
    "pork": ["pork", "bacon", "ham", "prosciutto", "sausage"],
    "lamb": ["lamb"],
    "turkey": ["turkey"],
    "salmon": ["salmon"],
    "shrimp": ["shrimp", "prawn"],
    "seafood": [
        "fish", "cod", "halibut", "tilapia", "tuna", "clam", "mussel",
        "crab", "lobster", "scallop", "anchov",
    ],
    "tofu": ["tofu"],
    "egg": ["egg"],
    "pasta": ["pasta", "penne", "spaghetti", "linguine", "fettuccine", "orzo", "noodle"],
    "rice": ["rice", "risotto"],
    "soup": ["soup", "stew", "chowder"],
    "salad": ["salad"],
    "pizza": ["pizza"],
    "beans": ["bean"],
    "grilled": ["grill"],
    "roasted": ["roast"],
    "braised": ["braise"],
    "sauteed": ["saut"],
    "baked": ["bake"],
    "broiled": ["broil"],
    "curry": ["curry", "curried"],
    "chili": ["chili"],
}


def extract_tags(recipe: dict) -> list[str]:
    haystack = " ".join([recipe.get("title") or ""] + (recipe.get("ingredients") or [])).lower()
    return [
        tag
        for tag, keywords in TAG_KEYWORDS.items()
        if any(re.search(rf"\b{re.escape(kw)}", haystack) for kw in keywords)
    ]


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "untitled"


def yaml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def yaml_list(items: list[str]) -> str:
    if not items:
        return " []"
    lines = [f'  - "{yaml_escape(str(item))}"' for item in items]
    return "\n" + "\n".join(lines)


def recipe_to_markdown(recipe: dict) -> str:
    title = recipe.get("title") or "Untitled"
    ingredients = recipe.get("ingredients") or []
    instructions = recipe.get("instructions") or []
    notes = recipe.get("notes")
    source_book = recipe.get("source_book")
    source_pages = recipe.get("source_pages") or [None, None]

    tags = ["recipe"] + extract_tags(recipe)

    frontmatter_lines = [
        "---",
        f'title: "{yaml_escape(title)}"',
        f"source_book: {source_book}",
        f"source_pages: [{source_pages[0]}, {source_pages[1]}]",
        f"tags: [{', '.join(tags)}]",
        f"ingredients:{yaml_list(ingredients)}",
        f"instructions:{yaml_list(instructions)}",
        f'notes: "{yaml_escape(notes)}"' if notes else "notes:",
        "---",
    ]
    frontmatter = "\n".join(frontmatter_lines)

    body_lines = [f"# {title}", "", "## Ingredients"]
    if ingredients:
        body_lines.extend(f"- {item}" for item in ingredients)
    else:
        body_lines.append("*(none extracted)*")

    body_lines += ["", "## Instructions"]
    if instructions:
        body_lines.extend(f"{i}. {step}" for i, step in enumerate(instructions, start=1))
    else:
        body_lines.append("*(none extracted)*")

    if notes:
        body_lines += ["", "## Notes", notes]

    body_lines += ["", f"*Source: {source_book}, pages {source_pages[0]}-{source_pages[1]}*"]

    return frontmatter + "\n\n" + "\n".join(body_lines) + "\n"


def export_book(recipes_path: Path, output_dir: Path) -> int:
    recipes = json.loads(recipes_path.read_text(encoding="utf-8"))
    book_dir = output_dir / recipes_path.stem
    book_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for recipe in recipes:
        recipe_id = recipe.get("id", "recipe")
        title_slug = slugify(recipe.get("title", ""))
        out_path = book_dir / f"{recipe_id}-{title_slug}.md"
        out_path.write_text(recipe_to_markdown(recipe), encoding="utf-8")
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Export recipes/*.json to Obsidian markdown notes")
    parser.add_argument(
        "output_dir",
        type=Path,
        help="Folder to write .md notes into (e.g. a folder inside your Obsidian vault)",
    )
    parser.add_argument("--book", type=str, default=None, help="Book slug to export (default: all books)")
    args = parser.parse_args()

    if args.book:
        recipes_paths = [RECIPES_DIR / f"{args.book}.json"]
        if not recipes_paths[0].exists():
            raise SystemExit(f"No recipes file found at {recipes_paths[0]}")
    else:
        recipes_paths = sorted(RECIPES_DIR.glob("*.json"))
        if not recipes_paths:
            raise SystemExit(f"No recipe JSON files found in {RECIPES_DIR}")

    total = 0
    for recipes_path in recipes_paths:
        n = export_book(recipes_path, args.output_dir)
        print(f"Exported {n} recipe(s) from {recipes_path.name}")
        total += n

    print(f"Done. {total} markdown note(s) written to {args.output_dir}")


if __name__ == "__main__":
    main()
