# Leaflet UI alignment notes

How this repo relates to [`ui-structure-prompt-standard.md`](ui-structure-prompt-standard.md).

## Current layout (GEDCOM / print focus)

| Standard location | Leaflet today |
|-------------------|---------------|
| `channels/ui/html/` | `assets/templates/family-cover.html` |
| `channels/ui/css/input/` | `assets/css/cover-entry.css` + `assets/css/fgs/` |
| `channels/ui/css/output/styles.css` | `assets/css/cover.bundle.css` |
| `channels/cli/` | `leaflet/__main__.py` (`python -m leaflet`) |
| `data/` | `data/*.ged` (inputs only; no ORM yet) |
| `{domain}/` | `leaflet/` (GEDCOM parse + HTML generators) |

A full move to `channels/ui/` is optional; the **contract** we follow here is the important part: **div + semantic classes**, **paired CSS**, **one built stylesheet**, **no landmark tags**, **no inline styles**.

## Family group sheet (`fgs-*`)

- **Template:** structure and placeholders only.
- **CSS:** `assets/css/fgs/base.css` (tokens), `layout.css` (grid/stacks/lines), `components.css` (pills, header).
- **Python:** `leaflet/cover_page.py` emits pill HTML; class names are fixed strings (not built at runtime).

Regenerate CSS after template or `fgs` CSS edits: `npm run build:css` or `npm run watch:css`.
