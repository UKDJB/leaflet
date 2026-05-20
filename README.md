# leaflet
Generate clean, printable A4 outputs from GEDCOM files using Python.

## Family group sheet (tabular)

```bash
python3 -m leaflet --gedcom "data/Brown Family Tree.ged" --family F1062 -o sheet.html
```

## Relationships-style cover (Tailwind v4)

1. Install Node dependencies and compile CSS (when you change template or Tailwind classes):

   ```bash
   npm install
   npm run build:css
   ```

   While editing templates or `leaflet/cover_page.py`, you can rebuild CSS on save:

   ```bash
   npm run watch:css
   ```

2. Emit a single HTML file with inlined print CSS (save it in this repo root so `assets/svg/…` resolves when you open the file):

   ```bash
   python3 -m leaflet --gedcom "data/Brown Family Tree.ged" --family F1062 --cover -o cover.html
   ```

   Use `--no-inline-css` to link `assets/css/cover.bundle.css` instead (handy while tweaking CSS).

The cover uses the fixed template at `assets/templates/family-cover.html` and `leaflet/cover_page.py` (both are scanned by the Tailwind CLI).
