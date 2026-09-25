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


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "untitled"


def yaml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


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

    frontmatter = "\n".join(
        [
            "---",
            f'title: "{yaml_escape(title)}"',
            f"source_book: {source_book}",
            f"source_pages: [{source_pages[0]}, {source_pages[1]}]",
            "tags: [recipe]",
            f"ingredients:{yaml_list(ingredients)}",
            "---",
        ]
    )

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
    output_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for recipe in recipes:
        recipe_id = recipe.get("id", "recipe")
        title_slug = slugify(recipe.get("title", ""))
        out_path = output_dir / f"{recipe_id}-{title_slug}.md"
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
