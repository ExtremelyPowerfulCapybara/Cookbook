(function () {
  "use strict";

  // ---------- book metadata: display name, description, icon per source_book slug ----------
  // A book not in this map (newly added to the vault) still works — it falls
  // back to a prettified slug, a generic description, and a leaf icon.
  var BOOK_META = {
    "bakingfavorites": { name: "Baking Favorites", icon: "wheat",
      desc: "Cakes, cookies, and pastries as an all-purpose baking reference — reliable ratios more than adventurous technique." },
    "dishoftheday": { name: "Dish of the Day", icon: "fork",
      desc: "A big everyday-dinner rotation: soups, roasts, and sautés meant to be worked through one dish at a time." },
    "onepotoftheday": { name: "One Pot of the Day", icon: "pot",
      desc: "Braises, stews, and skillet dinners built around a single pot, favoring rich sauces over lean prep." },
    "dessertoftheday": { name: "Dessert of the Day", icon: "slice",
      desc: "Fruit desserts, custards, and baked sweets organized for year-round entertaining." },
    "betterfromscratchandmakeyourownpantryessentials": { name: "Better From Scratch", icon: "jar",
      desc: "Homemade stocks, condiments, and pantry staples — the building blocks other recipes lean on." },
    "healthydishoftheday": { name: "Healthy Dish of the Day", icon: "leaf",
      desc: "Lighter versions of weeknight staples, leaning on vegetables and lean proteins without losing flavor." },
    "williams-sonomacomfortfood": { name: "Comfort Food", series: "Williams-Sonoma", icon: "pot",
      desc: "Classic American comfort cooking — casseroles, braises, and baked goods meant to feed a crowd." },
    "williamssonomabreakfastbible": { name: "Breakfast Bible", series: "Williams-Sonoma", icon: "egg",
      desc: "Morning cooking from quick weekday plates to slower weekend spreads: eggs, batters, and breads." },
    "williamssonomatestkitchen-theonebowlmealscookbook": { name: "The One-Bowl Meals Cookbook", short: "One-Bowl Meals", series: "Williams-Sonoma Test Kitchen", icon: "bowl",
      desc: "Complete dinners built in a single bowl — grain bases topped with vegetables, proteins, and sauces." },
    "williamssonomafavoritecookies": { name: "Favorite Cookies", series: "Williams-Sonoma", icon: "cookie",
      desc: "A cookie-jar reference spanning drop cookies, bars, and holiday classics." },
    "goodforyou": { name: "Good for You", icon: "leaf",
      desc: "Nutrient-forward cooking with produce in the lead role, built around simple technique." },
    "goodhousekeepingmediterraneandietmadeeasy": { name: "Mediterranean Diet Made Easy", short: "Mediterranean Diet", series: "Good Housekeeping", icon: "leaf",
      desc: "Mediterranean staples — olive oil, legumes, seafood, vegetables — adapted for everyday cooking." },
    "williams-sonoma-quickslowcooking": { name: "Quick & Slow Cooking", series: "Williams-Sonoma", icon: "clock",
      desc: "Weeknight-fast recipes paired with slow-cooker counterparts for the same craving." },
    "pressurecookercookbook": { name: "Pressure Cooker Cookbook", icon: "pot",
      desc: "Braises and stews re-timed for the pressure cooker, built for weeknight turnaround." },
    "williamssonomatestkitchen-thedutchovencookbook": { name: "The Dutch Oven Cookbook", short: "Dutch Oven Cookbook", series: "Williams-Sonoma Test Kitchen", icon: "pot",
      desc: "One-pot braises, breads, and roasts built around a single Dutch oven." },
    "williams-sonomafrozendesserts": { name: "Frozen Desserts", series: "Williams-Sonoma", icon: "snowflake",
      desc: "Ice creams, sorbets, and frozen treats, from simple churned bases to layered desserts." },
    "rusticmexican": { name: "Rustic Mexican", icon: "chili",
      desc: "Regional Mexican home cooking — soups, salsas, and braises built on dried chiles and slow technique." },
    "williams-sonoma-weeknightfreshandfast": { name: "Weeknight Fresh and Fast", series: "Williams-Sonoma", icon: "lightning",
      desc: "Fast dinners under thirty minutes, leaning on fresh produce and simple pan sauces." },
    "bakingforeveryseason": { name: "Baking for Every Season", icon: "wheat",
      desc: "A baking book organized by season, following fruit and spice through the year." },
    "adrianskitchen": { name: "Adrian's Kitchen", icon: "heart",
      desc: "Personal recipes worth keeping — written from scratch, not scanned from someone else's cookbook." },
    "vikalinka": { name: "Vikalinka", icon: "globe",
      desc: "Recipes pulled in from vikalinka.com — quick, everyday dishes spanning a wide range of cuisines." }
  };

  function prettifySlug(slug) {
    return slug.replace(/[-_]+/g, " ").replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }

  // The cabinet is always this dark espresso wood regardless of the app's
  // own light/dark theme (it's furniture, not UI chrome), so spine colors
  // use one bright, saturated palette that reads clearly against it.
  var SPINE_PALETTE = [
    "#e06a4c", "#3fa393", "#e8b445", "#9670cf", "#df7ba3",
    "#5a9e6a", "#5c94c4", "#e0824f", "#a274cf", "#4bb3b3",
    "#c76a95", "#7ea35c"
  ];

  // One icon per book, chosen for what the book actually is (not cycled
  // arbitrarily) — rendered bold enough to read clearly against any spine
  // color or the cloth-weave texture behind it.
  function svgDataUri(inner, viewBox) {
    var svg = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='" + (viewBox || "0 0 24 24") + "'>" + inner + "</svg>";
    // encodeURIComponent leaves ' unescaped, and this URL is then embedded
    // inside an already double-quoted style="..." HTML attribute — so both
    // quote characters must be gone from the payload, or one of the quoted
    // contexts terminates early and the whole background-image is dropped.
    var encoded = encodeURIComponent(svg).replace(/'/g, "%27");
    return "url('data:image/svg+xml," + encoded + "')";
  }

  var ICON_DEFS = {
    wheat: "<path d='M12 3v18M12 6l-3-2M12 6l3-2M12 10l-3-2M12 10l3-2M12 14l-3-2M12 14l3-2' stroke='white' stroke-opacity='0.9' stroke-width='1.5' stroke-linecap='round' fill='none'/>",
    fork: "<g stroke='white' stroke-opacity='0.9' stroke-width='1.9' stroke-linecap='round'><line x1='7' y1='3' x2='7' y2='10'/><line x1='10' y1='3' x2='10' y2='10'/><line x1='13' y1='3' x2='13' y2='10'/><line x1='10' y1='10' x2='10' y2='21'/></g>",
    pot: "<ellipse cx='5' cy='10' rx='1.6' ry='2.5' fill='white' fill-opacity='0.9'/><ellipse cx='19' cy='10' rx='1.6' ry='2.5' fill='white' fill-opacity='0.9'/><path d='M6 10h12l-1 8a2 2 0 01-2 2H9a2 2 0 01-2-2z' fill='white' fill-opacity='0.9'/><rect x='9' y='6' width='6' height='2.4' rx='1.2' fill='white' fill-opacity='0.9'/>",
    jar: "<rect x='8' y='9' width='8' height='11' rx='1.6' fill='white' fill-opacity='0.9'/><rect x='9' y='5' width='6' height='4.4' rx='1' fill='white' fill-opacity='0.9'/>",
    leaf: "<path d='M4 20C4 10 12 3 20 3 20 12 13 20 4 20Z' fill='white' fill-opacity='0.85'/><line x1='5' y1='19' x2='18' y2='5' stroke='white' stroke-opacity='0.95' stroke-width='1.4'/>",
    egg: "<ellipse cx='12' cy='13' rx='9' ry='6' fill='white' fill-opacity='0.4'/><circle cx='12' cy='12' r='4.4' fill='white' fill-opacity='0.95'/>",
    bowl: "<path d='M3 11a9 5 0 0018 0z' fill='white' fill-opacity='0.9'/><path d='M3 11h18' stroke='white' stroke-opacity='0.95' stroke-width='1.4'/>",
    cookie: "<circle cx='12' cy='12' r='8' fill='none' stroke='white' stroke-opacity='0.85' stroke-width='1.7'/><circle cx='9' cy='9' r='1.4' fill='white' fill-opacity='0.9'/><circle cx='15' cy='10' r='1.4' fill='white' fill-opacity='0.9'/><circle cx='11' cy='15' r='1.4' fill='white' fill-opacity='0.9'/><circle cx='15.5' cy='15' r='1.2' fill='white' fill-opacity='0.9'/>",
    clock: "<circle cx='12' cy='12' r='8' fill='none' stroke='white' stroke-opacity='0.9' stroke-width='1.7'/><line x1='12' y1='12' x2='12' y2='7' stroke='white' stroke-opacity='0.95' stroke-width='1.7' stroke-linecap='round'/><line x1='12' y1='12' x2='15.5' y2='13' stroke='white' stroke-opacity='0.95' stroke-width='1.7' stroke-linecap='round'/>",
    snowflake: "<g stroke='white' stroke-opacity='0.9' stroke-width='1.6' stroke-linecap='round'><line x1='12' y1='3' x2='12' y2='21'/><line x1='4' y1='7' x2='20' y2='17'/><line x1='20' y1='7' x2='4' y2='17'/></g>",
    chili: "<path d='M9 3c2 1 0 3-1 5-3 5 0 12 6 11 5-1 6-8 3-12-2-3-4-1-5-3-1-1-2-1-3-1z' fill='white' fill-opacity='0.9'/>",
    lightning: "<path d='M13 2L4 14h6l-1 8 9-12h-6l1-8z' fill='white' fill-opacity='0.9'/>",
    slice: "<path d='M4 19L12 5l8 14z' fill='white' fill-opacity='0.9'/><line x1='7.5' y1='14' x2='16.5' y2='14' stroke='white' stroke-opacity='0.55' stroke-width='1'/>",
    heart: "<path d='M12 21s-7-4.3-9.5-8.5C1 9.5 2 6 5.5 6c2 0 3.3 1.1 4 2.2C10.2 7.1 11.5 6 13.5 6 17 6 18 9.5 16.5 12.5 14 16.7 12 21 12 21z' fill='white' fill-opacity='0.9'/>",
    globe: "<circle cx='12' cy='12' r='8' fill='none' stroke='white' stroke-opacity='0.9' stroke-width='1.5'/><ellipse cx='12' cy='12' rx='3.3' ry='8' fill='none' stroke='white' stroke-opacity='0.9' stroke-width='1.3'/><line x1='4.2' y1='12' x2='19.8' y2='12' stroke='white' stroke-opacity='0.9' stroke-width='1.3'/>"
  };

  function iconFor(slug) {
    var meta = BOOK_META[slug];
    var key = (meta && meta.icon) || "leaf";
    return svgDataUri(ICON_DEFS[key]);
  }

  var RECIPES = [];
  var BOOKS = {};

  function buildBooks() {
    var counts = {};
    var missing = 0;
    RECIPES.forEach(function (r) {
      if (!r.source_book) { missing++; return; }
      counts[r.source_book] = (counts[r.source_book] || 0) + 1;
    });
    if (missing > 0) {
      // Surfaces a vault export mistake (a book's recipes missing
      // source_book in frontmatter) as a visible warning instead of a
      // mysterious "Null" shelf with recipes that can't be found.
      console.warn(missing + " recipe(s) have no source_book set and are excluded from the By Book shelf.");
    }
    BOOKS = {};
    Object.keys(counts).forEach(function (slug) {
      var meta = BOOK_META[slug];
      BOOKS[slug] = {
        name: meta ? meta.name : prettifySlug(slug),
        short: meta && meta.short,
        series: meta && meta.series,
        desc: meta ? meta.desc : "",
        count: counts[slug]
      };
    });
  }

  function bookDisplay(slug) {
    var b = BOOKS[slug];
    if (!b) return slug;
    return b.series ? b.series + " — " + b.name : b.name;
  }

  var ACTIVE_TAGS = new Set();
  var ACTIVE_BOOK = null;
  var currentTab = "all";

  var grid = document.getElementById("grid");
  var shelfWrap = document.getElementById("shelf-wrap");
  var shelfIntroEl = document.getElementById("shelf-intro");
  var shelfEl = document.getElementById("shelf");
  var bookDetailEl = document.getElementById("book-detail");
  var controlsEl = document.getElementById("controls");
  var searchInput = document.getElementById("search");
  var tagFilters = document.getElementById("tag-filters");
  var overlay = document.getElementById("detail-overlay");
  var detailContent = document.getElementById("detail-content");
  var randomBtn = document.getElementById("random-btn");

  function escapeHtml(str) {
    var div = document.createElement("div");
    div.textContent = str == null ? "" : str;
    return div.innerHTML;
  }

  function allTags() {
    var set = new Set();
    RECIPES.forEach(function (r) { r.tags.forEach(function (t) { set.add(t); }); });
    return Array.from(set).sort();
  }

  function renderTagFilters() {
    tagFilters.innerHTML = "";
    allTags().forEach(function (tag) {
      var chip = document.createElement("span");
      chip.className = "tag-chip" + (ACTIVE_TAGS.has(tag) ? " active" : "");
      chip.textContent = tag;
      chip.onclick = function () {
        if (ACTIVE_TAGS.has(tag)) ACTIVE_TAGS.delete(tag); else ACTIVE_TAGS.add(tag);
        renderTagFilters();
        renderGrid();
      };
      tagFilters.appendChild(chip);
    });
  }

  function matchesSearch(recipe, query) {
    if (!query) return true;
    var haystack = (recipe.title + " " + recipe.ingredients.join(" ")).toLowerCase();
    return haystack.indexOf(query) !== -1;
  }

  function matchesTags(recipe) {
    if (ACTIVE_TAGS.size === 0) return true;
    return Array.from(ACTIVE_TAGS).every(function (t) { return recipe.tags.indexOf(t) !== -1; });
  }

  function getFiltered(pool) {
    var query = searchInput.value.trim().toLowerCase();
    return (pool || RECIPES).filter(function (r) { return matchesSearch(r, query) && matchesTags(r); });
  }

  function cardHtml(recipe) {
    return (
      '<div class="card" data-id="' + escapeHtml(recipe.id) + '">' +
      '<h3>' + escapeHtml(recipe.title.toLowerCase()) + "</h3>" +
      '<div class="meta">' + escapeHtml(bookDisplay(recipe.source_book)) + "</div>" +
      '<div class="tags">' + recipe.tags.map(function (t) { return '<span class="tag">' + escapeHtml(t) + "</span>"; }).join("") + "</div>" +
      "</div>"
    );
  }

  function renderGrid() {
    var filtered = getFiltered();
    if (filtered.length === 0) {
      grid.innerHTML = '<div id="empty-state">No recipes match.</div>';
      return;
    }
    grid.innerHTML = filtered.map(cardHtml).join("");
    Array.prototype.forEach.call(grid.querySelectorAll(".card"), function (el) {
      el.onclick = function () { openDetailById(el.getAttribute("data-id")); };
    });
  }

  function openDetailById(id) {
    var recipe = RECIPES.filter(function (r) { return r.id === id; })[0];
    if (recipe) openDetail(recipe);
  }

  // Notes often lead with a yield line ("SERVES 4", "Makes about 18
  // macaroons.") — pull that out to sit in the meta line next to the book
  // and page, the way a printed recipe card would, instead of burying it
  // in a paragraph of notes.
  function splitServing(notes) {
    if (!notes) return { serving: null, rest: notes };
    var m = notes.match(/^\s*((?:makes|serves|yields?)\b[^.\n]*)[.\n]?\s*/i);
    if (!m) return { serving: null, rest: notes };
    return { serving: m[1].trim(), rest: notes.slice(m[0].length).trim() };
  }

  // Remembers which view was on screen before a recipe was opened, so
  // "Back" returns to the right place (the grid, or the By Book shelf/page).
  var returnToBooks = false;

  function openDetail(recipe) {
    var pages = recipe.source_pages && recipe.source_pages.length === 2
      ? (recipe.source_pages[0] === recipe.source_pages[1] ? "p. " + recipe.source_pages[0] : "pp. " + recipe.source_pages[0] + "–" + recipe.source_pages[1])
      : "";
    var split = splitServing(recipe.notes);
    var metaParts = [];
    if (split.serving) metaParts.push(split.serving);
    metaParts.push(escapeHtml(bookDisplay(recipe.source_book)));
    if (pages) metaParts.push(pages);

    detailContent.innerHTML =
      '<div class="eyebrow">' + escapeHtml(bookDisplay(recipe.source_book)) + "</div>" +
      "<h2>" + escapeHtml(recipe.title.toLowerCase()) + "</h2>" +
      '<div id="detail-divider"></div>' +
      '<div class="meta">' + metaParts.join(" · ") + "</div>" +
      '<div id="detail-body">' +
      '<div class="ingredients-col"><h4>Ingredients</h4><ul>' + recipe.ingredients.map(function (i) { return "<li>" + escapeHtml(i) + "</li>"; }).join("") + "</ul></div>" +
      '<div class="instructions-col"><h4>Instructions</h4><ol>' + recipe.instructions.map(function (s) { return "<li>" + escapeHtml(s) + "</li>"; }).join("") + "</ol></div>" +
      "</div>" +
      (split.rest ? '<div class="notes-callout"><h4>Notes</h4><div class="notes">' + escapeHtml(split.rest) + "</div></div>" : "");

    // A recipe replaces whatever's on screen in normal document flow —
    // same pattern as the By Book page — rather than floating on top of it
    // as a position:fixed modal. Firefox for Android has a long-standing
    // bug where fixed-position elements repaint incorrectly during active
    // scrolling (tied to its dynamic URL-bar compositing), letting the
    // page underneath show through no matter how the fixed layer itself is
    // styled. Not using position:fixed at all sidesteps it entirely.
    returnToBooks = !shelfWrap.hidden;
    controlsEl.hidden = true;
    grid.hidden = true;
    shelfWrap.hidden = true;
    overlay.hidden = false;
    window.scrollTo(0, 0);
  }

  function closeDetail() {
    overlay.hidden = true;
    if (returnToBooks) {
      shelfWrap.hidden = false;
    } else {
      controlsEl.hidden = false;
      grid.hidden = false;
    }
  }

  document.getElementById("detail-close").onclick = closeDetail;
  document.getElementById("detail-download").onclick = function () { window.print(); };

  randomBtn.onclick = function () {
    var pool = getFiltered();
    if (pool.length === 0) return;
    openDetail(pool[Math.floor(Math.random() * pool.length)]);
  };

  searchInput.oninput = renderGrid;

  // ---------- by-book shelf ----------
  function colorForBook(slug, index) {
    return SPINE_PALETTE[index % SPINE_PALETTE.length];
  }

  var SHELF_ROWS = 3;

  // Longest word decides the minimum plate width, so a title never has to
  // break mid-word — only between words. Rough serif-at-11.5px metric with
  // a generous pad; overestimating is safer than clipping a word.
  var TITLE_CHAR_PX = 7.6;
  var TITLE_MIN_PAD = 30;

  function longestWordChars(title) {
    return title.split(/\s+/).reduce(function (max, w) { return Math.max(max, w.length); }, 0);
  }

  function spineHtml(slug, i, maxCount) {
    var b = BOOKS[slug];
    var title = b.short || b.name;
    var countWidth = 62 + Math.round((b.count / maxCount) * 58);
    var titleWidth = Math.ceil(longestWordChars(title) * TITLE_CHAR_PX) + TITLE_MIN_PAD;
    var width = Math.max(countWidth, titleWidth);
    var height = 155 + Math.round((b.count / maxCount) * 55);
    var active = slug === ACTIVE_BOOK;
    var color = colorForBook(slug, i);
    return (
      '<div class="spine' + (active ? " active" : "") + '" data-slug="' + escapeHtml(slug) + '" ' +
      'style="width:' + width + 'px; min-height:' + height + 'px; background-color:' + color + ';">' +
      '<div class="spine-deco"><div class="spine-icon" style="background-image:' + iconFor(slug) + ';"></div></div>' +
      '<div class="spine-plate">' +
      '<div class="spine-title">' + escapeHtml(title) + "</div>" +
      '<div class="spine-rule" style="background:' + color + ';"></div>' +
      '<div class="spine-count">' + b.count + "</div>" +
      "</div>" +
      '<div class="spine-deco"></div>' +
      "</div>"
    );
  }

  function renderShelf() {
    var slugs = Object.keys(BOOKS).sort(function (a, b) { return BOOKS[b].count - BOOKS[a].count; });
    var maxCount = Math.max.apply(null, slugs.map(function (s) { return BOOKS[s].count; })) || 1;

    var rows = [];
    for (var r = 0; r < SHELF_ROWS; r++) rows.push([]);
    slugs.forEach(function (slug, i) { rows[i % SHELF_ROWS].push(slug); });

    shelfEl.innerHTML =
      '<div class="shelf-post left"></div><div class="shelf-post right"></div>' +
      rows.map(function (row) {
        return '<div class="shelf-row"><div class="row">' + row.map(function (slug) {
          return spineHtml(slug, slugs.indexOf(slug), maxCount);
        }).join("") + '</div><div class="plank"></div></div>';
      }).join("");

    Array.prototype.forEach.call(shelfEl.querySelectorAll(".spine"), function (el) {
      el.onclick = function () {
        ACTIVE_BOOK = el.getAttribute("data-slug");
        showBookPage();
      };
    });
  }

  function showBookPage() {
    shelfIntroEl.hidden = true;
    shelfEl.hidden = true;
    shelfWrap.classList.add("book-open");
    renderBookDetail();
    bookDetailEl.hidden = false;
    shelfWrap.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function showShelfPage() {
    ACTIVE_BOOK = null;
    shelfWrap.classList.remove("book-open");
    bookDetailEl.hidden = true;
    shelfIntroEl.hidden = false;
    shelfEl.hidden = false;
  }

  function renderBookDetail() {
    var b = BOOKS[ACTIVE_BOOK];
    var recipes = RECIPES.filter(function (r) { return r.source_book === ACTIVE_BOOK; });
    var listHtml = recipes.length
      ? '<div class="card-grid">' + recipes.map(cardHtml).join("") + "</div>"
      : '<div id="empty-state" style="padding:1.5rem 0;">No recipes found for this book.</div>';
    bookDetailEl.innerHTML =
      '<button id="book-back" type="button">&larr; Back to shelf</button>' +
      "<h2>" + escapeHtml(bookDisplay(ACTIVE_BOOK)) + "</h2>" +
      '<div class="book-count-line">' + b.count + " recipes in this book</div>" +
      (b.desc ? '<div class="book-desc">' + escapeHtml(b.desc) + "</div>" : "") +
      listHtml;
    document.getElementById("book-back").onclick = showShelfPage;
    Array.prototype.forEach.call(bookDetailEl.querySelectorAll(".card"), function (el) {
      el.onclick = function () { openDetailById(el.getAttribute("data-id")); };
    });
  }

  // ---------- tabs ----------
  var tabButtons = document.querySelectorAll("#tabs button");
  Array.prototype.forEach.call(tabButtons, function (btn) {
    btn.onclick = function () {
      currentTab = btn.getAttribute("data-tab");
      Array.prototype.forEach.call(tabButtons, function (b) { b.classList.toggle("active", b === btn); });
      if (currentTab === "books") {
        controlsEl.hidden = true;
        grid.hidden = true;
        shelfWrap.hidden = false;
        showShelfPage();
        renderShelf();
      } else {
        controlsEl.hidden = false;
        grid.hidden = false;
        shelfWrap.hidden = true;
      }
    };
  });

  // ---------- theme toggle ----------
  var themeButtons = document.querySelectorAll("#theme-toggle button");
  function setTheme(choice) {
    if (choice === "light" || choice === "dark") {
      document.documentElement.setAttribute("data-theme", choice);
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
    Array.prototype.forEach.call(themeButtons, function (b) {
      b.classList.toggle("active", b.getAttribute("data-theme-choice") === choice);
    });
    try { localStorage.setItem("cookbook-shelf-theme", choice); } catch (e) {}
  }
  Array.prototype.forEach.call(themeButtons, function (b) {
    b.onclick = function () { setTheme(b.getAttribute("data-theme-choice")); };
  });

  var savedTheme = null;
  try { savedTheme = localStorage.getItem("cookbook-shelf-theme"); } catch (e) {}
  setTheme(savedTheme || "light");

  fetch("/api/recipes")
    .then(function (r) { return r.json(); })
    .then(function (data) {
      RECIPES = data;
      buildBooks();
      var bookCount = Object.keys(BOOKS).length;
      shelfIntroEl.textContent = bookCount + " cookbooks, " + RECIPES.length.toLocaleString() +
        " recipes — spine width and height scale with how many recipes each book contributed. Click a spine to open it.";
      renderTagFilters();
      renderGrid();
    })
    .catch(function () {
      grid.innerHTML = '<div id="empty-state">Failed to load recipes.</div>';
    });
})();
