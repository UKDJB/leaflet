"""A4 portrait family group sheet — sketch layout (vertical stacks, pill rows).

Markup uses semantic ``fgs-*`` classes paired with ``assets/css/fgs/*.css``.
See ``documents/ui-structure-prompt-standard.md`` and ``documents/leaflet-ui-notes.md``.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

from leaflet.audit import DEFAULT_ROOT_INDI
from leaflet.gedcom import (
    Family,
    GedcomData,
    Individual,
    direct_lineage_people,
    family_couple_name,
    lineage_sibling_people,
)

_YEAR_RE = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\b")


def _repo_root(explicit: Path | None) -> Path:
    return explicit if explicit is not None else Path(__file__).resolve().parent.parent


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def _display_name(ind: Individual | None) -> str:
    if ind is None:
        return ""
    return ind.name.replace("/", "").strip()


def _proper_name(ind: Individual | None) -> str:
    """Title case for display (e.g. David Julian Brown)."""
    raw = _display_name(ind)
    if not raw:
        return "Unknown"
    return raw.title()


def _surname(ind: Individual | None) -> str:
    if ind is None or not ind.name:
        return ""
    parts = ind.name.split("/")
    if len(parts) >= 2 and parts[1].strip():
        return parts[1].strip()
    return _display_name(ind).split()[-1] if _display_name(ind) else ""


def _lifespan_short(ind: Individual | None) -> str:
    """Sketch style: birth year – death year (or open)."""
    if ind is None:
        return "—"
    b = (ind.birth.date or "").strip()
    d = (ind.death.date or "").strip()
    by = _YEAR_RE.search(b)
    dy = _YEAR_RE.search(d)
    b_y = by.group(1) if by else (b[:4] if len(b) >= 4 and b[:4].isdigit() else "")
    d_y = dy.group(1) if dy else (d[:4] if len(d) >= 4 and d[:4].isdigit() else "")
    if b_y and d_y:
        return f"{b_y} – {d_y}"
    if b_y:
        return f"{b_y} –"
    if d_y:
        return f"? – {d_y}"
    return "—"


def _avatar_src(sex: str, assets_base: str) -> str:
    """Relative URL to male.svg or female.svg (unknown → male silhouette)."""
    ab = assets_base.strip()
    leaf = "female.svg" if sex.upper() == "F" else "male.svg"
    if not ab or ab == ".":
        return f"assets/svg/{leaf}"
    prefix = ab.rstrip("/")
    return f"{prefix}/assets/svg/{leaf}"


def _sex_modifier(sex: str) -> str:
    s = sex.upper()[:1]
    if s == "M":
        return "m"
    if s == "F":
        return "f"
    return "u"


def _person_name_html(
    ind: Individual | None,
    *,
    direct_line: set[str],
    siblings: set[str],
) -> str:
    """Yellow ★ on direct line; green ▲ on siblings of that line and their descendants."""
    text = _esc(_proper_name(ind))
    if ind is None:
        return text
    if ind.xref in direct_line:
        text += '<span class="fgs-lineage-star" aria-hidden="true"> ★</span>'
    elif ind.xref in siblings:
        text += '<span class="fgs-lineage-sibling" aria-hidden="true"> ▲</span>'
    return text


def _pill(
    ind: Individual | None,
    *,
    assets_base: str = ".",
    variant: str = "std",
    direct_line: set[str] | None = None,
    siblings: set[str] | None = None,
) -> str:
    line = direct_line if direct_line is not None else set()
    sibs = siblings if siblings is not None else set()
    if ind is None:
        name = "Unknown"
        dates = "—"
        sex = ""
        mod = "u"
    else:
        name = _proper_name(ind)
        dates = _lifespan_short(ind)
        sex = ind.sex
        mod = _sex_modifier(sex)
    src = _avatar_src(sex, assets_base)
    alt = _display_name(ind) or "Unknown"
    if variant == "parent":
        av = 40
    elif variant == "child":
        av = 28
    else:
        av = 32
    return (
        f'<div class="fgs-pill fgs-pill--{variant}">'
        f'<div class="fgs-pill__sex fgs-pill__sex--{mod}">'
        f'<img class="fgs-pill__avatar" src="{_esc(src)}" width="{av}" height="{av}" alt="{_esc(alt)}" />'
        f"</div>"
        f'<div class="fgs-pill__body">'
        f'<div class="fgs-pill__name">{_person_name_html(ind, direct_line=line, siblings=sibs)}</div>'
        f'<div class="fgs-pill__dates">{_esc(dates)}</div>'
        f"</div></div>"
    )


def _format_family_id(xref: str) -> str:
    """Family id without GEDCOM @ delimiters (e.g. F1064)."""
    return xref.strip().strip("@")


def _marriage_year(fam: Family) -> str:
    m = (fam.marriage.date or "").strip()
    hit = _YEAR_RE.search(m)
    return hit.group(1) if hit else ""


def _first_child_birth_year(fam: Family, data: GedcomData) -> str:
    """Earliest birth year among children in this family."""
    years: list[int] = []
    for ch_xref in fam.children:
        ch = data.individuals.get(ch_xref)
        if ch is None:
            continue
        b = (ch.birth.date or "").strip()
        hit = _YEAR_RE.search(b)
        if hit:
            years.append(int(hit.group(1)))
    return str(min(years)) if years else ""


def _couple_year(fam: Family, data: GedcomData) -> str:
    """Marriage year if known, else earliest child birth year."""
    return _marriage_year(fam) or _first_child_birth_year(fam, data)


def _birth_family(data: GedcomData, person: Individual | None) -> Family | None:
    if person is None or not person.famc:
        return None
    return data.families.get(person.famc[0])


def _gp_header_html(
    fam: Family,
    husb: Individual | None,
    wife: Individual | None,
    data: GedcomData,
) -> str:
    """Top bar: ``1949 Brown - Bolton`` left, ``F1064`` right."""
    year = _couple_year(fam, data)
    names = family_couple_name(fam, data)
    left = f"{year} {names}" if year else names
    fid = _esc(_format_family_id(fam.xref))
    return (
        f'<div class="fgs-gp-couple__header">'
        f'<div class="fgs-gp-couple__header-left">{_esc(left)}</div>'
        f'<div class="fgs-gp-couple__id">{fid}</div>'
        f"</div>"
    )


def _gp_person_row(
    ind: Individual | None,
    *,
    assets_base: str,
    direct_line: set[str],
    siblings: set[str],
) -> str:
    if ind is None:
        dates = "—"
        sex = ""
        mod = "u"
    else:
        dates = _lifespan_short(ind)
        sex = ind.sex
        mod = _sex_modifier(sex)
    src = _avatar_src(sex, assets_base)
    alt = _display_name(ind) or "Unknown"
    return (
        f'<div class="fgs-gp-couple__person">'
        f'<div class="fgs-gp-couple__sex fgs-pill__sex--{mod}">'
        f'<img class="fgs-gp-couple__avatar" src="{_esc(src)}" width="28" height="28" alt="{_esc(alt)}" />'
        f"</div>"
        f'<div class="fgs-gp-couple__person-body">'
        f'<div class="fgs-gp-couple__name">{_person_name_html(ind, direct_line=direct_line, siblings=siblings)}</div>'
        f'<div class="fgs-gp-couple__dates">{_esc(dates)}</div>'
        f"</div></div>"
    )


def _gp_couple_block(
    data: GedcomData,
    parent: Individual | None,
    *,
    assets_base: str = ".",
    direct_line: set[str] | None = None,
    siblings: set[str] | None = None,
) -> str:
    """One rounded block: header, then both grandparents."""
    line = direct_line if direct_line is not None else set()
    sibs = siblings if siblings is not None else set()
    fam = _birth_family(data, parent)
    if fam is None:
        header = (
            '<div class="fgs-gp-couple__header">'
            '<div class="fgs-gp-couple__header-left">—</div>'
            '<div class="fgs-gp-couple__id">—</div>'
            "</div>"
        )
        husb, wife = None, None
    else:
        husb = data.individuals.get(fam.husb) if fam.husb else None
        wife = data.individuals.get(fam.wife) if fam.wife else None
        header = _gp_header_html(fam, husb, wife, data)
    return (
        f'<div class="fgs-gp-couple">'
        f"{header}"
        f'<div class="fgs-gp-couple__people">'
        f"{_gp_person_row(husb, assets_base=assets_base, direct_line=line, siblings=sibs)}"
        f"{_gp_person_row(wife, assets_base=assets_base, direct_line=line, siblings=sibs)}"
        f"</div></div>"
    )



def _header_title(
    fam: Family,
    _p1: Individual | None,
    _p2: Individual | None,
    data: GedcomData,
) -> str:
    year = _couple_year(fam, data)
    names = family_couple_name(fam, data)
    prefix = f"{year} {names}" if year else names
    fid = _esc(_format_family_id(fam.xref))
    return f'{_esc(prefix)} <span class="fgs-header__xref">({fid})</span>'


def _child_slot_html(pill: str, side: str) -> str:
    if side == "left":
        inner = f'{pill}<div class="fgs-child-slot__arm" aria-hidden="true"></div>'
    else:
        inner = f'<div class="fgs-child-slot__arm" aria-hidden="true"></div>{pill}'
    return f'<div class="fgs-child-slot fgs-child-slot--{side}">{inner}</div>'


def _pair_hub_html(*, last: bool) -> str:
    cls = "fgs-pair-hub fgs-pair-hub--last" if last else "fgs-pair-hub"
    return (
        f'<div class="{cls}" aria-hidden="true">'
        '<div class="fgs-pair-hub__v-up"></div>'
        '<div class="fgs-pair-hub__joint"></div>'
        '<div class="fgs-pair-hub__v-down"></div>'
        "</div>"
    )


def _child_slots(
    children: list[str],
    data: GedcomData,
    *,
    assets_base: str = ".",
    direct_line: set[str] | None = None,
    siblings: set[str] | None = None,
) -> str:
    line = direct_line if direct_line is not None else set()
    sibs = siblings if siblings is not None else set()
    if not children:
        return '<div class="fgs-empty">No children in GEDCOM.</div>'
    pair_rows = (len(children) + 1) // 2
    pairs: list[str] = []
    for p in range(pair_rows):
        left_xref = children[p * 2] if p * 2 < len(children) else None
        right_xref = children[p * 2 + 1] if p * 2 + 1 < len(children) else None
        is_last = p == pair_rows - 1
        if left_xref:
            left = _child_slot_html(
                _pill(
                    data.individuals.get(left_xref),
                    assets_base=assets_base,
                    variant="parent",
                    direct_line=line,
                    siblings=sibs,
                ),
                "left",
            )
        else:
            left = '<div class="fgs-child-slot fgs-child-slot--left fgs-child-slot--empty"></div>'
        if right_xref:
            right = _child_slot_html(
                _pill(
                    data.individuals.get(right_xref),
                    assets_base=assets_base,
                    variant="parent",
                    direct_line=line,
                    siblings=sibs,
                ),
                "right",
            )
        else:
            right = '<div class="fgs-child-slot fgs-child-slot--right fgs-child-slot--empty"></div>'
        pairs.append(
            f'<div class="fgs-children-pair">{left}{_pair_hub_html(last=is_last)}{right}</div>'
        )
    return (
        '<div class="fgs-children-row">'
        '<div class="fgs-children-spine__down" aria-hidden="true"></div>'
        + "\n".join(pairs)
        + "</div>"
    )


def build_family_cover_html(
    data: GedcomData,
    fam: Family,
    *,
    repo_root: Path | None = None,
    assets_base: str = ".",
    inline_css: bool = True,
    root_indi: str = DEFAULT_ROOT_INDI,
) -> str:
    """Fill ``assets/templates/family-cover.html`` and return a full HTML document."""
    root = _repo_root(repo_root)
    direct_line = direct_lineage_people(data, root_indi)
    siblings = lineage_sibling_people(data, root_indi)
    tpl_path = root / "assets/templates/family-cover.html"
    css_path = root / "assets/css/cover.bundle.css"
    template = tpl_path.read_text(encoding="utf-8")

    if inline_css and css_path.is_file():
        css_body = css_path.read_text(encoding="utf-8")
        extra_head = f"<style>\n{css_body}\n</style>"
    else:
        ab = assets_base.strip().rstrip("/")
        href = "assets/css/cover.bundle.css" if not ab or ab == "." else f"{ab}/assets/css/cover.bundle.css"
        extra_head = f'<link rel="stylesheet" href="{_esc(href)}" />'

    p1 = data.individuals.get(fam.husb) if fam.husb else None
    p2 = data.individuals.get(fam.wife) if fam.wife else None
    n1 = _display_name(p1) or "Parent 1"
    n2 = _display_name(p2) or "Parent 2"
    heading = f"{n1} & {n2}" if (n1 or n2) else f"Family {fam.xref}"

    reps: dict[str, str] = {
        "__EXTRA_HEAD__": extra_head,
        "__PAGE_TITLE__": _esc(f"{heading} — family group sheet"),
        "__HEADER_TITLE__": _header_title(fam, p1, p2, data),
        "__P1_GP_COUPLE__": _gp_couple_block(
            data, p1, assets_base=assets_base, direct_line=direct_line, siblings=siblings
        ),
        "__P2_GP_COUPLE__": _gp_couple_block(
            data, p2, assets_base=assets_base, direct_line=direct_line, siblings=siblings
        ),
        "__P1_PARENT__": _pill(
            p1,
            assets_base=assets_base,
            variant="parent",
            direct_line=direct_line,
            siblings=siblings,
        ),
        "__P2_PARENT__": _pill(
            p2,
            assets_base=assets_base,
            variant="parent",
            direct_line=direct_line,
            siblings=siblings,
        ),
        "__CHILD_SLOTS__": _child_slots(
            fam.children,
            data,
            assets_base=assets_base,
            direct_line=direct_line,
            siblings=siblings,
        ),
    }
    out = template
    for key, val in reps.items():
        out = out.replace(key, val)
    return out


def write_family_cover(
    path: Path | str,
    data: GedcomData,
    fam: Family,
    *,
    repo_root: Path | None = None,
    assets_base: str = ".",
    inline_css: bool = True,
    root_indi: str = DEFAULT_ROOT_INDI,
) -> None:
    Path(path).write_text(
        build_family_cover_html(
            data,
            fam,
            repo_root=repo_root,
            assets_base=assets_base,
            inline_css=inline_css,
            root_indi=root_indi,
        ),
        encoding="utf-8",
    )
