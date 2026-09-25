"""
Lightweight recipe search app. Reads recipe notes straight out of an
Obsidian vault's Recipes/ folder (frontmatter written by
export_to_obsidian.py) and serves them as a searchable/filterable page.

No database, no build step - the vault markdown files are the source of
truth, re-read on every request so edits made in Obsidian show up on the
next page load.

Config (env vars):
    RECIPES_DIR   Path to the vault's Recipes folder. Default: ./sample-recipes
    PORT          Port to listen on. Default: 5000
"""

import os
from pathlib import Path

import frontmatter
from flask import Flask, jsonify, send_from_directory

RECIPES_DIR = Path(os.environ.get("RECIPES_DIR", Path(__file__).resolve().parent / "sample-recipes"))
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = Flask(__name__, static_folder=None)


def load_recipes() -> list[dict]:
    recipes = []
    if not RECIPES_DIR.exists():
        return recipes

    for md_path in sorted(RECIPES_DIR.glob("*.md")):
        try:
            post = frontmatter.load(md_path)
        except Exception:  # noqa: BLE001 - skip any note that fails to parse rather than 500 the whole page
            continue

        tags = post.get("tags") or []
        if "recipe" not in tags:
            continue  # skips utility notes like "Ingredient Search.md"

        recipes.append(
            {
                "id": md_path.stem,
                "title": post.get("title") or md_path.stem,
                "source_book": post.get("source_book"),
                "source_pages": post.get("source_pages") or [],
                "tags": [t for t in tags if t != "recipe"],
                "ingredients": post.get("ingredients") or [],
                "instructions": post.get("instructions") or [],
                "notes": post.get("notes"),
            }
        )

    recipes.sort(key=lambda r: r["title"])
    return recipes


@app.get("/api/recipes")
def api_recipes():
    return jsonify(load_recipes())


@app.get("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/<path:filename>")
def static_files(filename):
    return send_from_directory(STATIC_DIR, filename)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
