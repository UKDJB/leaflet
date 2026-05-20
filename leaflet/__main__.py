"""Command-line entry: list families, pick one, emit A4-ready HTML."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from leaflet.audit import DEFAULT_ROOT_INDI, audit_gedcom
from leaflet.cover_page import build_family_cover_html, write_family_cover
from leaflet.family_group_sheet import build_family_group_sheet_html, write_family_group_sheet
from leaflet.serve import run_server
from leaflet.gedcom import (
    GedcomData,
    family_summary_label,
    iter_families_sorted,
    normalise_family_xref,
    parse_gedcom,
)


def _filter_families(data: GedcomData, needle: str) -> list:
    needle_u = needle.upper()
    out = []
    for fam in iter_families_sorted(data):
        label = family_summary_label(fam, data.individuals)
        if needle_u in label.upper() or needle_u in fam.xref.upper():
            out.append(fam)
    return out


def _cmd_list(data: GedcomData, search: str | None) -> int:
    fams = _filter_families(data, search) if search else iter_families_sorted(data)
    for i, fam in enumerate(fams, start=1):
        print(f"{i:6d}  {fam.xref}  {family_summary_label(fam, data.individuals)}")
    print(f"\nTotal: {len(fams)} families", file=sys.stderr)
    return 0


def _pick_family_interactive(data: GedcomData, search: str | None):
    fams = _filter_families(data, search) if search else iter_families_sorted(data)
    if not fams:
        print("No families matched.", file=sys.stderr)
        return None
    _cmd_list(data, search)
    print("\nEnter line number (1–{}) or a family xref (e.g. @F1062@ or F1062):".format(len(fams)))
    choice = input("> ").strip()
    if not choice:
        return None
    if choice.isdigit():
        idx = int(choice)
        if 1 <= idx <= len(fams):
            return fams[idx - 1]
        print("Number out of range.", file=sys.stderr)
        return None
    xref = normalise_family_xref(choice)
    for fam in fams:
        if fam.xref == xref:
            return fam
    # Allow picking by xref even if filtered out
    if xref in data.families:
        return data.families[xref]
    print("Family not found.", file=sys.stderr)
    return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Leaflet — GEDCOM to HTML: tabular family group sheet or A4 Relationships-style cover."
    )
    p.add_argument(
        "--gedcom",
        required=True,
        type=Path,
        help="Path to a .ged file (e.g. data/Brown Family Tree.ged)",
    )
    p.add_argument(
        "--encoding",
        default="utf-8",
        help="Text encoding for the GEDCOM file (default: utf-8)",
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--list-families", action="store_true", help="Print all families (see --search).")
    g.add_argument("--interactive", action="store_true", help="List families and prompt for selection.")
    g.add_argument("--family", type=str, metavar="ID", help="Family xref, e.g. F1062 or @F1062@.")
    g.add_argument(
        "--serve",
        action="store_true",
        help="Run the family-picker web app (SPA) and print API on --port.",
    )
    g.add_argument(
        "--audit-csv",
        action="store_true",
        help="Write CSV of orphans, disconnected branches, and duplicates needing review.",
    )
    p.add_argument(
        "--search",
        type=str,
        metavar="TEXT",
        help="With --list-families or --interactive: filter by parent names or xref substring.",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Write HTML to this path (default: stdout for --family only when omitted).",
    )
    p.add_argument(
        "--cover",
        action="store_true",
        help="Emit the A4 Relationships-style cover (Tailwind-built CSS) instead of the tabular sheet.",
    )
    p.add_argument(
        "--no-inline-css",
        action="store_true",
        help="With --cover: link assets/css/cover.bundle.css instead of inlining (for local dev).",
    )
    p.add_argument(
        "--assets-base",
        default=".",
        metavar="PATH",
        help="With --cover: path prefix for img/src and stylesheet href (default: .).",
    )
    p.add_argument(
        "--port",
        type=int,
        default=8765,
        help="With --serve: TCP port (default: 8765).",
    )
    p.add_argument(
        "--host",
        default="127.0.0.1",
        help="With --serve: bind address (default: 127.0.0.1).",
    )
    p.add_argument(
        "--root",
        default=DEFAULT_ROOT_INDI,
        metavar="INDI",
        help=(
            f"Base person for lineage markers and audit connectivity "
            f"(default: {DEFAULT_ROOT_INDI})."
        ),
    )

    args = p.parse_args(argv)
    if not args.gedcom.is_file():
        print(f"GEDCOM file not found: {args.gedcom}", file=sys.stderr)
        return 2

    repo_root = Path(__file__).resolve().parent.parent

    if args.serve:
        bundle = repo_root / "assets/css/cover.bundle.css"
        if not bundle.is_file():
            print(
                "Warning: assets/css/cover.bundle.css missing; run `npm install` and `npm run build:css`.",
                file=sys.stderr,
            )
        run_server(
            args.gedcom,
            host=args.host,
            port=args.port,
            repo_root=repo_root,
            encoding=args.encoding,
            root_indi=args.root,
        )
        return 0

    if args.audit_csv:
        out = args.output
        if out is None:
            stem = args.gedcom.stem
            out = args.gedcom.parent / f"{stem}-maintenance.csv"
        n = audit_gedcom(args.gedcom, out, encoding=args.encoding, root_indi=args.root)
        print(f"Wrote {n} rows to {out}", file=sys.stderr)
        return 0

    data = parse_gedcom(args.gedcom, encoding=args.encoding)

    if args.list_families:
        return _cmd_list(data, args.search)

    if args.cover:
        bundle = repo_root / "assets/css/cover.bundle.css"
        if not bundle.is_file():
            print(
                "Warning: assets/css/cover.bundle.css missing; run `npm install` and `npm run build:css`.",
                file=sys.stderr,
            )

    if args.interactive:
        fam = _pick_family_interactive(data, args.search)
        if fam is None:
            return 1
        if args.cover:
            html_doc = build_family_cover_html(
                data,
                fam,
                repo_root=repo_root,
                assets_base=args.assets_base,
                inline_css=not args.no_inline_css,
                root_indi=args.root,
            )
        else:
            html_doc = build_family_group_sheet_html(data, fam)
        if args.output:
            args.output.write_text(html_doc, encoding="utf-8")
            print(f"Wrote {args.output}", file=sys.stderr)
        else:
            print(html_doc)
        return 0

    # --family
    xref = normalise_family_xref(args.family)
    fam = data.families.get(xref)
    if fam is None:
        print(f"Unknown family: {xref}", file=sys.stderr)
        return 1
    if args.cover:
        if args.output:
            write_family_cover(
                args.output,
                data,
                fam,
                repo_root=repo_root,
                assets_base=args.assets_base,
                inline_css=not args.no_inline_css,
                root_indi=args.root,
            )
            print(f"Wrote {args.output}", file=sys.stderr)
        else:
            print(
                build_family_cover_html(
                    data,
                    fam,
                    repo_root=repo_root,
                    assets_base=args.assets_base,
                    inline_css=not args.no_inline_css,
                    root_indi=args.root,
                )
            )
    elif args.output:
        write_family_group_sheet(args.output, data, fam)
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        print(build_family_group_sheet_html(data, fam))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
