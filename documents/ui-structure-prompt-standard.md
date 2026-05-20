# Project structure and UI prompt standard

Use this document as a **portable project standard** and as a **system prompt** when starting or extending a codebase. It defines:

1. **Top-level layout** — where `assets`, `channels`, `data`, `documents`, `scripts`, and `tests` live and what belongs in each.
2. **UI separation** — parallel `html/` and `css/` trees connected by semantic class hooks, with markup that favours `<div>` + classes over landmark tags.

The reference implementation in this repository is the Merlin repo root plus `channels/ui/html/` and `channels/ui/css/`. Rules are written generically so they apply to other domains and stacks (Django, other server-rendered frameworks, or static sites).

---

## Prompt block (copy into AI or team instructions)

```text
You are working on a project with a flat, literal top-level layout and strict separation of concerns.

PROJECT ROOT (where new work goes):
- assets/       — checked-in or vendored static inputs (CSV, images, seed files). Not application logic.
- channels/     — thin entrypoints only: api/, cli/, settings/, ui/. No domain algorithms here.
- data/         — persistence: ORM models, migrations, DB management commands, pure containers/.
- documents/    — human specs, architecture, ADRs, standards (this file). Not runtime code.
- scripts/      — short root-level shell wrappers that cd to repo root and delegate to Python/CLI.
- tests/        — pytest (or equivalent) at repo root; mirror module paths under test_*.py.
- {domain}/     — optional domain package (e.g. euromillions/): workflows, helpers, sql/, generators.

PLACEMENT RULES:
- Business logic, SQL, orchestration → {domain}/ (never channels/).
- HTTP/CLI/UI wiring → channels/ (call into {domain}/ or data/, do not reimplement logic).
- Schema and migrations → data/models/ + data/migrations/.
- One-off operator commands → data/management/commands/ or channels/cli/commands/.
- Long-form design → documents/; do not bury architecture only in code comments.
- Reproducible static inputs → assets/sources/; generated artefacts → gitignore or assets/data/ if adopted.

UI ({ui_root} = channels/ui in this pattern):

STRUCTURE (HTML only):
- All templates live under {ui_root}/html/ in mirrored folders: pages/, layouts/, components/.
- HTML defines hierarchy, template logic, and data binding only—not visual layout via element type.
- Use <div> + custom CSS class hooks for pages, containers, and components (e.g. home-page, content, navbar, panel, line).
- Do NOT use landmark or sectional elements for layout: no <header>, <nav>, <main>, <section>, <article>, <aside>, <footer>. Meaning lives in class names and paired CSS files, not HTML tag names.
- Document shell only: <html>, <head>, <body> are required for a valid page; put the page hook class on <body> (e.g. class="home-page") or on a single top-level <div class="home-page"> inside <body>. Do not add extra sectional tags between body and content.
- Inline text nodes may use <span> where appropriate (e.g. ball numbers, labels).
- No inline styles, no presentation attributes, no color/spacing/font rules in HTML.
- Compose with page shells (extends), region layouts (include), and small components (include).
- Dynamic fragments load via partial templates; keep each partial structurally minimal.

STYLE (CSS only):
- All styles live under {ui_root}/css/input/ in the same taxonomy: base/, layouts/, components/, pages/.
- One entry file (styles.css) imports every layer in fixed order: base → layouts → components → pages.
- Built CSS is emitted to {ui_root}/css/output/ and is the only file linked from HTML.
- Pair HTML and CSS by name: navbar.html ↔ components/navbar.css, home.html ↔ pages/home.css.
- layouts/ = positioning (flex, grid, gap, alignment, width constraints).
- components/ = visual identity (colors, borders, typography, shapes, states).
- pages/ = page-scoped layout and overrides (e.g. .home-page, .home-panels).
- base/ = theme tokens, global resets, shared variables.

CONTRACT:
- Class names are the API between HTML and CSS. Adding a class in HTML requires a rule in the matching CSS file (or an documented shared component file).
- Prefer base + modifier classes (.ball, .ball.main, .ball.main.match) over one-off utility strings in markup.
- State modifiers (.match, .is-open, .muted) belong at the bottom of the component CSS file and use solid opaque colors when they must cover underlying UI.
- Theme values live in CSS custom properties (:root, @theme), not in templates.

FORBIDDEN:
- Styling in HTML (style="", font tags, presentation tables).
- Layout or component markup via <header>, <nav>, <main>, <section>, <article>, <aside>, <footer> (use <div class="…"> instead).
- CSS that targets layout by element name (e.g. section { }, header nav { }) except html/body defaults in base/global.css.
- Duplicating the same visual rules across unrelated CSS files.
- Renaming canonical layout hooks (e.g. shared row/container classes) without updating every consumer.

When adding a feature:
1. Place domain code under {domain}/; persistence under data/; entrypoints under channels/.
2. For UI: create or extend the HTML partial, add or extend the paired CSS file, register the import in styles.css, rebuild output CSS, link only output/styles.css from the base page.
3. Add tests under tests/ mirroring the module you changed.
```

Replace `{ui_root}` with your UI path (e.g. `channels/ui`) and `{domain}` with your problem-domain package (e.g. `euromillions`).

---

## Generic project layout

Keep the repository **flat and literal**: top-level folders name what they hold. Avoid deep framework scaffolding unless it buys clarity.

```text
{project_root}/
├── assets/                 # Static inputs bundled with or loaded into the repo
│   └── sources/            # Authoritative files (CSV, JSON seeds, reference images)
├── channels/               # System entrypoints — adapters, not domain brains
│   ├── api/                # HTTP handlers → call workflows / query data
│   ├── cli/                # CLI commands and channel-local scripts
│   │   ├── commands/       # Named commands (load, test views, batch jobs)
│   │   └── scripts/        # Build/ops shell scripts (css build, reset, etc.)
│   ├── settings/           # App configuration (DB, static paths, installed apps)
│   └── ui/                 # Browser presentation (html/ + css/ trees — see below)
├── data/                   # Everything that talks to the database as “system of record”
│   ├── models/             # ORM models / schema definitions
│   ├── migrations/         # Versioned schema and view/procedure migrations
│   ├── management/
│   │   └── commands/       # Operator/maintenance commands tied to persistence
│   ├── containers/         # Pure data shapes (no behaviour, no I/O)
│   └── fixtures/           # Optional test/load fixtures
├── documents/              # Architecture, charters, flow docs, prompt standards
│   └── decisions/          # Optional ADRs / recorded decisions
├── scripts/                # Root-level bash/make wrappers for daily use
├── tests/                  # Automated tests (flat or mirroring package names)
├── {domain}/               # Optional: all problem-domain logic for one product area
│   ├── workflows/          # Orchestration (SQL calls, routing, materialisation)
│   ├── helpers/            # Small glue, constants, mappers
│   ├── sql/                # Views, functions, procedures (if SQL-first)
│   └── …                   # generators/, legacy_*/, etc. as needed
└── requirements.txt        # (or pyproject.toml) — dependency manifest at root
```

### `assets/`

| Put here | Do not put here |
|----------|-----------------|
| Source CSVs, reference tables, static images used by loaders | Python modules, SQL, HTML |
| `sources/{topic}/…` grouped by data source | Generated DB dumps (prefer gitignore + `assets/data/` if you need a convention) |

**Rule:** If it is a **file humans or loaders read** and it is not code, it belongs under `assets/`. Loaders live in `channels/cli/` or `data/management/commands/` and **read** from `assets/sources/`.

### `channels/`

| Put here | Do not put here |
|----------|-----------------|
| URL routes, view functions, template rendering | Domain algorithms, bulk analytics loops |
| API request/response mapping | ORM models (those live in `data/models/`) |
| CLI command registration, `build_css.sh`-style scripts | Business rules that survive without HTTP/CLI |

**Rule:** Channels **coordinate**; they do not **own** the problem domain. A view may call `euromillions.workflows…` or query via Django ORM; it should not embed scoring or prediction logic inline.

Subfolders:

- **`api/`** — HTTP handlers.
- **`cli/commands/`** — Named operational commands (often Django `manage.py` extensions).
- **`cli/scripts/`** — Shell scripts for build, reset, watch tasks.
- **`settings/`** — Framework config (`TEMPLATES`, `STATICFILES_DIRS`, database).
- **`ui/`** — `html/` + `css/` only for presentation (see UI sections below).

### `data/`

| Put here | Do not put here |
|----------|-----------------|
| ORM models, migrations, DB-backed management commands | HTML, CSS, HTTP handlers |
| `containers/` — dataclasses or structs for canonical shapes (Line, Ticket) | Workflow orchestration (→ `{domain}/workflows/`) |
| Fixtures for tests or seed loads | Ad hoc scripts (→ `scripts/` or `channels/cli/`) |

**Rule:** `data/` is the **persistence boundary**. Anything that defines tables, columns, constraints, or migration history lives here. Pure in-memory shapes used across layers go in `data/containers/`.

### `documents/`

| Put here | Do not put here |
|----------|-----------------|
| Architecture, charters, flow diagrams, prompt standards | Executable code |
| ADRs under `documents/decisions/` | User-facing copy that ships in templates (→ `channels/ui/html/`) |

**Rule:** If a human needs to understand **why** the system is shaped a certain way, it belongs in `documents/`. Keep this folder the single source for cross-cutting standards (including this file).

### `scripts/`

| Put here | Do not put here |
|----------|-----------------|
| Short, root-invokable shell entrypoints (`./scripts/foo.sh`) | Large Python programs (→ `channels/cli/commands/` or `{domain}/`) |
| Wrappers that `cd` to repo root and call `python manage.py …` | CSS/HTML |

**Rule:** `scripts/` is for **convenience at the repo root** — cron, muscle memory, CI steps. Implementation stays in Python modules; the shell file only sets paths, venv, and arguments.

### `tests/`

| Put here | Do not put here |
|----------|-----------------|
| `test_*.py` exercising workflows, generators, views | Production code |
| Fixtures used only by tests (or reference `data/fixtures/`) | Manual QA checklists (→ `documents/`) |

**Rule:** Tests sit at **`tests/`** repo root (not inside `channels/` or `{domain}/`). Name files after what they verify (`test_agate_generator.py`). Prefer testing domain workflows and orchestration without spinning up HTTP unless the adapter layer is the subject.

### `{domain}/` (optional but recommended)

When the product has a clear problem domain (e.g. `euromillions/`), **all domain logic** lives there:

- **`workflows/`** — orchestration, batch pipelines, prediction routing.
- **`helpers/`** — mapping, validation, registry constants (glue only).
- **`sql/`** — views, functions, procedures if the DB owns set-based work.
- **`lens_generators/`**, **`legacy_generators/`**, etc. — named by role, not by framework.

Do **not** create a second copy of domain logic under `channels/` or `data/` except ORM models in `data/models/`.

### Where does a new change go?

| You are adding… | Location |
|-----------------|----------|
| A new table or column | `data/models/` + `data/migrations/` |
| A pure Line/Ticket shape | `data/containers/` |
| A batch job that writes DB rows | `data/management/commands/` or `{domain}/workflows/` |
| A prediction/scoring pipeline | `{domain}/workflows/` + `{domain}/sql/` as appropriate |
| A REST or page endpoint | `channels/api/` or `channels/ui/views/` |
| A template or stylesheet | `channels/ui/html/…` + `channels/ui/css/input/…` |
| A source CSV | `assets/sources/…` |
| An architecture note | `documents/` |
| A developer shortcut command | `scripts/` (shell) or `channels/cli/commands/` (Python) |
| A regression test | `tests/test_….py` |

---

## Why two parallel UI trees

| Concern | Location | Responsibility |
|--------|----------|----------------|
| Structure | `{ui_root}/html/` | What exists on the page, hierarchy, ARIA, template logic |
| Presentation | `{ui_root}/css/input/` | How it looks: layout, color, type, motion, responsive behavior |

HTML and CSS are **siblings**, not nested. Templates never live inside `css/`; stylesheets never live inside `html/`. Static file configuration points at the CSS root; template configuration points at the HTML root. That split makes reviews obvious: a markup change is structure; a color change is style.

---

## Recommended directory layout

```text
{ui_root}/
├── html/
│   ├── pages/           # Full pages; extend a base shell
│   │   └── base.html    # <head>, global chrome, {% block content %}
│   ├── layouts/         # Page regions (columns, panels, modals host)
│   └── components/      # Small, reusable fragments (navbar, line, form field)
└── css/
    ├── input/           # Authoring source (edit these files)
    │   ├── styles.css   # Single import manifest
    │   ├── base/
    │   │   ├── theme.css      # Design tokens (@theme, :root variables)
    │   │   └── global.css     # Resets, html/body defaults
    │   ├── layouts/     # Positioning for named regions
    │   ├── components/  # Visual rules per component hook
    │   └── pages/       # Page-scoped rules (body/page class descendants)
    ├── output/          # Built bundle served to browsers
    │   └── styles.css
    └── README.md        # Build command and static path note
```

**Mirroring rule:** For every reusable fragment in `html/components/foo.html`, maintain `css/input/components/foo.css` (same basename). Layout regions follow `html/layouts/bar.html` ↔ `css/input/layouts/bar.css`. Pages follow `html/pages/home.html` ↔ `css/input/pages/home.css`.

---

## Markup: `<div>` + class hooks, not landmark tags

Structure and region identity are expressed with **class names**, not with HTML5 landmark or sectional tags.

| Use | Do not use for the same role |
|-----|------------------------------|
| `<div class="navbar">` | `<nav class="navbar">` |
| `<div class="content">` | `<main class="content">` |
| `<div class="lucky-dip-modal__header">` | `<header class="…">` |
| `<div class="home-layout">` | `<section class="home-layout">` |
| `<body class="home-page">` | styling via bare `section` / `header` selectors |

**Allowed element types**

- **Document shell:** `html`, `head`, `body` (and normal head children: `title`, `meta`, `link`, `script`).
- **Regions and components:** `div` almost everywhere; `span` for small inline content.
- **Form controls:** `form`, `input`, `select`, `button`, `label` where the control is real—not a styled `div` pretending to be a button unless there is a deliberate reason.

**Why:** Tag names like `section` and `header` invite element selectors and ambiguous “semantic” styling in CSS. Class hooks keep the contract explicit: every visual rule keys off a class declared in a named CSS file. Accessibility, when needed, is added with `role` and `aria-*` on the same `div`, not by switching tag names.

**Legacy in this repository:** Some templates still use `<nav>`, `<main>`, or `<header>` (e.g. `base.html`, `navbar.html`, modals). Treat those as debt; new markup should use `div` + classes. Do not introduce new landmark tags.

---

## Semantic class hooks (“custom CSS tags”)

This project does **not** use Web Components or custom HTML elements for styling. Instead, **semantic class names** act as stable tags that both layers agree on:

- **Base hook** — identifies the component: `panel`, `ball`, `navbar`, `formfield-box`
- **Type modifier** — variant of the component: `ball main`, `ball star`, `panel-minimal`
- **State modifier** — runtime outcome: `match`, `is-open`, `muted`, `busy`

Example structure (HTML):

```html
<div class="panel panel-minimal">
  <div class="line">
    <div class="balls main">
      <span class="ball main match">12</span>
    </div>
  </div>
</div>
```

Example presentation (CSS), with state rules last:

```css
.ball { /* dimensions, flex centering */ }
.ball.main { /* default main ball colors */ }
.ball.main.match { /* solid match state; overrides above */ }
```

Treat each class string as part of a **public contract**. Renaming a class is a breaking change across HTML, CSS, and any scripts that toggle classes.

### Import order in `styles.css`

```css
/* 1. Base */
@import './base/theme.css';
@import './base/global.css';

/* 2. Layouts (positioning regions) */
@import './layouts/container.css';
@import './layouts/prediction.css';

/* 3. Components (visual identity) */
@import './components/ball.css';
@import './components/panel.css';

/* 4. Pages (page root and descendants) */
@import './pages/home.css';
```

Lower layers should not depend on page-specific selectors. Pages may target components inside a page root (e.g. `.home-panels > .panel { ... }`).

---

## HTML rules (structure only)

1. **Base page** links exactly one compiled stylesheet: `output/styles.css`.
2. **Pages** set a page root class on `body` or a top-level `div` via template blocks (e.g. `{% block page_class %}home-page{% endblock %}` on `<body>`).
3. **Regions and components** use `<div class="…">` (or `span` for inline text), not `<header>`, `<nav>`, `<main>`, `<section>`, `<article>`, `<aside>`, or `<footer>`.
4. **Layouts** assemble regions; they use layout and component classes but do not invent ad hoc presentation classes.
5. **Components** are small, include-friendly partials with neutral parameters (`{% include "components/line.html" with selected_mains=mains %}`).
6. **No inline `style=""`** except rare, documented exceptions (e.g. hidden placeholders for JS-driven visibility). Prefer classes toggled from CSS or minimal JS.
7. **Scripts** handle behavior (open/close, HTMX targets); they toggle classes defined in CSS, they do not set colors or spacing inline.

### Composition patterns

- `pages/base.html` — document shell, global nav, modal hosts, script tags.
- `pages/*.html` — `{% extends "pages/base.html" %}`, fill `content` block, include layouts.
- `layouts/*.html` — multi-column or multi-panel regions.
- `components/*.html` — one concern per file (navbar, ticket line, form field).

Use server includes for static assembly; use partial fetches (HTMX, Turbo, etc.) only when the fragment is loaded or swapped dynamically.

---

## CSS rules (presentation only)

### `base/`

- **theme.css** — brand palette, semantic colors (`--color-text`, `--panel-border`), font stacks. Use `@theme` or `:root` so components reference tokens, not raw hex in every file.
- **global.css** — element defaults (`html`, `body`, `img`), utility classes used across the app (`busy`, `unselectable`).

### `layouts/`

- Flex/grid, gaps, max-width, scroll behavior, region sizing.
- May adjust child component **size** in context (e.g. smaller `.ball` inside `.prediction`) without redefining ball colors.

### `components/`

- Borders, backgrounds, typography, border-radius, shadows, hover/focus.
- **Base + modifier** cascade: general rules first, type modifiers next, state modifiers last.

### `pages/`

- Rules scoped under a page class: `.home-page`, `.home-layout`, `.home-panels`.
- Page-level background, padding, and arrangement of layout regions.

### Build pipeline

- **Author** in `css/input/`.
- **Compile** to `css/output/styles.css` (e.g. Tailwind CLI bundling `@import` and `@theme`).
- **Serve** only `output/` in production. Never hand-edit the built file.

---

## Separation of concerns checklist

When reviewing a change, ask:

| Question | Must be “yes” in… |
|----------|-------------------|
| Is domain logic out of `channels/` (only wiring in channels)? | `{domain}/` |
| Does persistence live in models/migrations, not in views? | `data/` |
| Does this change *what* is on screen (elements, order, conditionals)? | HTML |
| Does this change *how* it looks (color, size, spacing, font)? | CSS |
| Is there a paired CSS file for every new component partial? | CSS `components/` |
| Is the new stylesheet imported in `styles.css`? | `css/input/styles.css` |
| Are class names reused consistently (no `ticket-ball` vs `ball` for the same widget)? | Both |
| Are theme values centralized? | `base/theme.css` |
| Is there a test for non-trivial behaviour? | `tests/` |
| Is design rationale documented if non-obvious? | `documents/` |

---

## Anti-patterns

- Putting `style="display:flex; gap:1rem"` in templates instead of a layout class.
- Dumping all rules into one giant CSS file with no component/layout split.
- Naming classes after one page only (`home-red-button`) when the control is reusable — use `btn-run` in `components/buttons.css`.
- Using utility-only markup (`class="flex gap-4 p-2 rounded-lg"`) for domain UI that repeats across the app — extract a semantic component class.
- Using `<section>`, `<header>`, `<nav>`, or `<main>` for layout when a `<div class="…">` + paired CSS file is the intended pattern.
- Editing `output/styles.css` directly; it will be overwritten on the next build.

---

## Naming and legacy notes

- Prefer **short semantic names** (`panel`, `line`, `ball`) over framework-style long BEM chains for **new** work.
- Existing code may use legacy patterns (e.g. `btn-ellipse--help`); do not rewrite unrelated CSS. When touching a file, align new classes with the base + modifier style where practical.
- **Canonical layout hooks** (shared row/container class names used in many templates) should not be renamed casually; update HTML, CSS, and docs together.

---

## Minimal workflow for a new UI piece

1. Add `html/components/widget.html` — structure and semantic classes only.
2. Add `css/input/components/widget.css` — all visuals for those classes.
3. Add `@import "./components/widget.css";` to `css/input/styles.css`.
4. Include the partial from a layout or page: `{% include "components/widget.html" %}`.
5. Run the CSS build; verify `output/styles.css` in the browser.

---

## Framework mapping (optional)

| Concept | Django (this repo) | Generic |
|--------|-------------------|---------|
| HTML root | `TEMPLATES['DIRS']` → `channels/ui/html` | Template directory |
| CSS static root | `STATICFILES_DIRS` → `channels/ui/css` | Static assets directory |
| Link tag | `{% static 'output/styles.css' %}` | `/css/output/styles.css` |
| Build | `channels/cli/scripts/build_css.sh` | `npx @tailwindcss/cli -i input/styles.css -o output/styles.css` |

---

## Related reading in this repository

- `documents/architecture.md` — full stack layout, SQL vs Python boundary, `channels/` and `data/` roles, UI semantic layering.
- `channels/ui/css/README.md` — static path and input/output folders.

---

*This document is intentionally generic. Copy the prompt block at the top into new projects or agent instructions; adjust `{domain}`, `{ui_root}`, and build tooling to match the stack.*
