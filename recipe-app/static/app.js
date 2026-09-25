let ALL_RECIPES = [];
let ACTIVE_TAGS = new Set();

const grid = document.getElementById("grid");
const searchInput = document.getElementById("search");
const tagFilters = document.getElementById("tag-filters");
const overlay = document.getElementById("detail-overlay");
const detailContent = document.getElementById("detail-content");
const randomBtn = document.getElementById("random-btn");
const printBtn = document.getElementById("detail-print");

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function allTags() {
  const set = new Set();
  for (const r of ALL_RECIPES) {
    for (const t of r.tags) set.add(t);
  }
  return [...set].sort();
}

function renderTagFilters() {
  tagFilters.innerHTML = "";
  for (const tag of allTags()) {
    const chip = document.createElement("span");
    chip.className = "tag-chip" + (ACTIVE_TAGS.has(tag) ? " active" : "");
    chip.textContent = tag;
    chip.onclick = () => {
      if (ACTIVE_TAGS.has(tag)) ACTIVE_TAGS.delete(tag);
      else ACTIVE_TAGS.add(tag);
      renderTagFilters();
      renderGrid();
    };
    tagFilters.appendChild(chip);
  }
}

function matchesSearch(recipe, query) {
  if (!query) return true;
  const haystack = (recipe.title + " " + recipe.ingredients.join(" ")).toLowerCase();
  return haystack.includes(query);
}

function matchesTags(recipe) {
  if (ACTIVE_TAGS.size === 0) return true;
  return [...ACTIVE_TAGS].every((t) => recipe.tags.includes(t));
}

function getFiltered() {
  const query = searchInput.value.trim().toLowerCase();
  return ALL_RECIPES.filter((r) => matchesSearch(r, query) && matchesTags(r));
}

function renderGrid() {
  const filtered = getFiltered();

  grid.innerHTML = "";
  if (filtered.length === 0) {
    grid.innerHTML = '<div id="empty-state">No recipes match.</div>';
    return;
  }

  for (const recipe of filtered) {
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <h3>${escapeHtml(recipe.title)}</h3>
      <div class="book">${escapeHtml(recipe.source_book || "")}</div>
      <div class="tags">${recipe.tags.map((t) => `<span class="tag">${escapeHtml(t)}</span>`).join("")}</div>
    `;
    card.onclick = () => openDetail(recipe);
    grid.appendChild(card);
  }
}

let CURRENT_RECIPE = null;

function openDetail(recipe) {
  CURRENT_RECIPE = recipe;
  const pages = recipe.source_pages && recipe.source_pages.length === 2
    ? `pages ${recipe.source_pages[0]}-${recipe.source_pages[1]}`
    : "";
  detailContent.innerHTML = `
    <h2>${escapeHtml(recipe.title)}</h2>
    <div class="book">${escapeHtml(recipe.source_book || "")}${pages ? ", " + pages : ""}</div>
    <h4>Ingredients</h4>
    <ul>${recipe.ingredients.map((i) => `<li>${escapeHtml(i)}</li>`).join("")}</ul>
    <h4>Instructions</h4>
    <ol>${recipe.instructions.map((s) => `<li>${escapeHtml(s)}</li>`).join("")}</ol>
    ${recipe.notes ? `<h4>Notes</h4><div class="notes">${escapeHtml(recipe.notes)}</div>` : ""}
  `;
  overlay.classList.remove("hidden");
}

document.getElementById("detail-close").onclick = () => overlay.classList.add("hidden");
overlay.onclick = (e) => {
  if (e.target === overlay) overlay.classList.add("hidden");
};

printBtn.onclick = () => window.print();

randomBtn.onclick = () => {
  const pool = getFiltered();
  if (pool.length === 0) return;
  const pick = pool[Math.floor(Math.random() * pool.length)];
  openDetail(pick);
};

searchInput.oninput = renderGrid;

fetch("/api/recipes")
  .then((r) => r.json())
  .then((data) => {
    ALL_RECIPES = data;
    renderTagFilters();
    renderGrid();
  })
  .catch(() => {
    grid.innerHTML = '<div id="empty-state">Failed to load recipes.</div>';
  });
