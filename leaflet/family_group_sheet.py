"""Build a print-oriented HTML family group sheet from parsed GEDCOM data."""

from __future__ import annotations

import html
from pathlib import Path

from leaflet.gedcom import EventInfo, Family, GedcomData, Individual


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def _event_cells(ev: EventInfo) -> tuple[str, str]:
    return _esc(ev.date), _esc(ev.place)


def _person_block(title: str, section_id: str, person: Individual | None, marriage: EventInfo) -> str:
    """HTML fragment for one parent (or child) row block."""
    if person is None:
        name = ""
        sex = ""
        birth_d, birth_p = "", ""
        death_d, death_p = "", ""
    else:
        name = _esc(person.name.replace("/", "").strip())
        sex = _esc(person.sex)
        birth_d, birth_p = _event_cells(person.birth)
        death_d, death_p = _event_cells(person.death)
    m_date, m_place = _event_cells(marriage)

    return f"""
    <section class="person" aria-labelledby="{section_id}">
      <h2 class="person-title" id="{section_id}">{_esc(title)}</h2>
      <table class="grid">
        <tbody>
          <tr><th scope="row">Name</th><td colspan="3" class="name">{name or "—"}</td></tr>
          <tr><th scope="row">Sex</th><td colspan="3">{sex or "—"}</td></tr>
          <tr><th scope="row">Birth</th><td class="d">{birth_d or "—"}</td>
              <th scope="row" class="sub">Place</th><td class="p">{birth_p or "—"}</td></tr>
          <tr><th scope="row">Marriage (this family)</th><td class="d">{m_date or "—"}</td>
              <th scope="row" class="sub">Place</th><td class="p">{m_place or "—"}</td></tr>
          <tr><th scope="row">Death</th><td class="d">{death_d or "—"}</td>
              <th scope="row" class="sub">Place</th><td class="p">{death_p or "—"}</td></tr>
        </tbody>
      </table>
    </section>
    """


def _children_table(
    data: GedcomData,
    children: list[str],
) -> str:
    rows: list[str] = []
    for i, ch_xref in enumerate(children, start=1):
        ch = data.individuals.get(ch_xref)
        if ch is None:
            rows.append(
                f"<tr><td>{i}</td><td>{_esc(ch_xref)}</td>"
                f"<td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td></tr>"
            )
            continue
        name = _esc(ch.name.replace("/", "").strip())
        sex = _esc(ch.sex)
        bd, bp = _event_cells(ch.birth)
        dd, dp = _event_cells(ch.death)
        # Marriage on child: first listed family-as-spouse only (minimal heuristic).
        m_date, m_place = "—", "—"
        if ch.fams:
            fam0 = data.families.get(ch.fams[0])
            if fam0 is not None:
                md, mp = _event_cells(fam0.marriage)
                m_date, m_place = md or "—", mp or "—"
        rows.append(
            f"<tr><td>{i}</td><td>{name}</td><td>{sex}</td>"
            f"<td>{bd}</td><td>{bp}</td><td>{m_date}</td><td>{m_place}</td>"
            f"<td>{dd}</td><td>{dp}</td></tr>"
        )

    body = "\n".join(rows)
    return f"""
    <section class="children" aria-labelledby="h-children">
      <h2 class="person-title" id="h-children">Children</h2>
      <table class="children-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Name</th>
            <th>Sex</th>
            <th>Birth date</th>
            <th>Birth place</th>
            <th>Marriage date</th>
            <th>Marriage place</th>
            <th>Death date</th>
            <th>Death place</th>
          </tr>
        </thead>
        <tbody>
          {body}
        </tbody>
      </table>
    </section>
    """


def build_family_group_sheet_html(data: GedcomData, fam: Family) -> str:
    """Full HTML document suitable for browser print to A4."""
    husb = data.individuals.get(fam.husb or "", None)
    wife = data.individuals.get(fam.wife or "", None)
    h_label = "Parent 1 (Husband)" if (husb and husb.sex == "M") else "Parent 1"
    w_label = "Parent 2 (Wife)" if (wife and wife.sex == "F") else "Parent 2"

    title_bits: list[str] = []
    if husb:
        title_bits.append(husb.name.replace("/", "").strip())
    if wife:
        title_bits.append(wife.name.replace("/", "").strip())
    heading = " & ".join(t for t in title_bits if t) or f"Family {fam.xref}"

    parents_html = _person_block(h_label, "sec-parent-1", husb, fam.marriage) + _person_block(
        w_label, "sec-parent-2", wife, fam.marriage
    )
    children_html = _children_table(data, fam.children)

    css = """
    @page { size: A4; margin: 12mm; }
    html { font-family: Georgia, "Times New Roman", serif; font-size: 11pt; color: #111; }
    body { margin: 0; }
    header.doc-head { margin-bottom: 1rem; border-bottom: 1px solid #333; padding-bottom: 0.5rem; }
    header.doc-head h1 { font-size: 16pt; margin: 0 0 0.25rem 0; }
    header.doc-head .meta { font-size: 9pt; color: #444; }
    section.person { margin-bottom: 1rem; break-inside: avoid; page-break-inside: avoid; }
    section.children { break-inside: auto; }
    h2.person-title { font-size: 12pt; margin: 0 0 0.35rem 0; }
    table.grid { width: 100%; border-collapse: collapse; font-size: 10pt; }
    table.grid th, table.grid td { border: 1px solid #999; padding: 0.25rem 0.4rem; vertical-align: top; }
    table.grid th { text-align: left; background: #f3f3f3; width: 8.5em; font-weight: 600; }
    table.grid th.sub { width: 5em; }
    table.grid td.name { font-weight: 600; }
    table.children-table { width: 100%; border-collapse: collapse; font-size: 9pt; margin-top: 0.35rem; }
    table.children-table th, table.children-table td {
      border: 1px solid #999; padding: 0.2rem 0.3rem; vertical-align: top;
    }
    table.children-table thead th { background: #e8e8e8; font-weight: 600; }
    tr { break-inside: avoid; page-break-inside: avoid; }
    @media print {
      html { font-size: 10.5pt; }
      a { color: inherit; text-decoration: none; }
    }
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{_esc(heading)} — Family Group Sheet</title>
  <style>{css}</style>
</head>
<body>
  <header class="doc-head">
    <h1>Family Group Sheet</h1>
    <div class="meta">Family record {_esc(fam.xref)} · {_esc(heading)}</div>
  </header>
  <main>
    {parents_html}
    {children_html}
  </main>
</body>
</html>
"""


def write_family_group_sheet(path: Path | str, data: GedcomData, fam: Family) -> None:
    """Write HTML document to ``path``."""
    out = Path(path)
    out.write_text(build_family_group_sheet_html(data, fam), encoding="utf-8")
