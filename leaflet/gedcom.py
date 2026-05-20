"""Minimal GEDCOM 5.x line parser: individuals, families, and cross-references.

Assumptions (explicit):
- Input is UTF-8 (CHAR UTF-8 in HEAD is typical for modern exports).
- We only model INDI/FAM fields needed for a family group sheet; other records are skipped.
- Multiple MARR or DIV blocks on a family: we keep the first MARR date/place for display.
- CONC/CONT continuation lines are not merged; long values may be truncated in source data.
"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


@dataclass
class EventInfo:
    """Birth, death, or marriage-like event (date and place only)."""

    date: str = ""
    place: str = ""


@dataclass
class Individual:
    xref: str
    name: str = ""
    sex: str = ""
    birth: EventInfo = field(default_factory=EventInfo)
    death: EventInfo = field(default_factory=EventInfo)
    famc: list[str] = field(default_factory=list)
    fams: list[str] = field(default_factory=list)


@dataclass
class Family:
    xref: str
    husb: str | None = None
    wife: str | None = None
    children: list[str] = field(default_factory=list)
    marriage: EventInfo = field(default_factory=EventInfo)


@dataclass
class GedcomData:
    individuals: dict[str, Individual]
    families: dict[str, Family]


_LINE_RE = re.compile(
    r"^(?P<level>\d+)\s+"
    r"(?:(?P<xref>@[^@]+@)\s+)?"
    r"(?P<tag>\S+)"
    r"(?:\s+(?P<value>.*))?$"
)


def _parse_line(raw: str) -> tuple[int, str | None, str, str]:
    """Return (level, xref or None, tag, value)."""
    m = _LINE_RE.match(raw.rstrip("\r\n"))
    if not m:
        return 0, None, "UNPARSED", raw
    level = int(m.group("level"))
    xref = m.group("xref")
    tag = m.group("tag")
    value = m.group("value") or ""
    return level, xref, tag, value


def iter_gedcom_lines(path: Path | str, encoding: str = "utf-8") -> Iterator[str]:
    """Yield physical lines from a GEDCOM file."""
    p = Path(path)
    with p.open(encoding=encoding, errors="replace", newline="") as fh:
        yield from fh


def parse_gedcom(path: Path | str, encoding: str = "utf-8") -> GedcomData:
    """Parse a GEDCOM file into individuals and families."""
    individuals: dict[str, Individual] = {}
    families: dict[str, Family] = {}

    current_indi: Individual | None = None
    current_fam: Family | None = None
    # When inside INDI: which level-1 event block we are filling ('BIRT', 'DEAT', or '').
    indi_event: str = ""
    # When inside FAM: whether we are inside the first MARR block.
    fam_in_marr: bool = False

    for raw in iter_gedcom_lines(path, encoding=encoding):
        if not raw.strip():
            continue
        level, xref, tag, value = _parse_line(raw)

        if level == 0:
            indi_event = ""
            fam_in_marr = False
            if tag == "INDI" and xref:
                current_indi = Individual(xref=xref)
                individuals[xref] = current_indi
                current_fam = None
            elif tag == "FAM" and xref:
                current_fam = Family(xref=xref)
                families[xref] = current_fam
                current_indi = None
            else:
                current_indi = None
                current_fam = None
            continue

        if current_indi is not None:
            if level == 1:
                indi_event = ""
                if tag == "NAME":
                    current_indi.name = value or current_indi.name
                elif tag == "SEX":
                    current_indi.sex = value.strip()[:1] or current_indi.sex
                elif tag == "BIRT":
                    indi_event = "BIRT"
                elif tag == "DEAT":
                    indi_event = "DEAT"
                elif tag == "FAMC":
                    if value:
                        current_indi.famc.append(value.strip())
                elif tag == "FAMS":
                    if value:
                        current_indi.fams.append(value.strip())
            elif level == 2 and indi_event in {"BIRT", "DEAT"}:
                tgt = current_indi.birth if indi_event == "BIRT" else current_indi.death
                if tag == "DATE" and not tgt.date:
                    tgt.date = value.strip()
                elif tag == "PLAC" and not tgt.place:
                    tgt.place = value.strip()
            continue

        if current_fam is not None:
            if level == 1:
                fam_in_marr = False
                if tag == "HUSB" and value:
                    current_fam.husb = value.strip()
                elif tag == "WIFE" and value:
                    current_fam.wife = value.strip()
                elif tag == "CHIL" and value:
                    current_fam.children.append(value.strip())
                elif tag == "MARR":
                    fam_in_marr = True
            elif level == 2 and fam_in_marr:
                if tag == "DATE" and not current_fam.marriage.date:
                    current_fam.marriage.date = value.strip()
                elif tag == "PLAC" and not current_fam.marriage.place:
                    current_fam.marriage.place = value.strip()
            continue

    return GedcomData(individuals=individuals, families=families)


def normalise_family_xref(token: str) -> str:
    """Accept 'F1062', '@F1062@', or '@f1062@' and return canonical '@F1062@'."""
    t = token.strip()
    if not t:
        return t
    if t.startswith("@") and t.endswith("@") and len(t) >= 3:
        inner = t[1:-1]
        return f"@{inner}@"
    return f"@{t}@"


def family_sort_key(fam: Family, individuals: dict[str, Individual]) -> tuple[str, str, str]:
    """Stable sort: husband surname, given, then family xref."""
    h = individuals.get(fam.husb or "", None)
    w = individuals.get(fam.wife or "", None)
    h_name = (h.name if h else "").upper()
    w_name = (w.name if w else "").upper()
    return (h_name, w_name, fam.xref)


def iter_families_sorted(data: GedcomData) -> list[Family]:
    """All families sorted for display lists."""
    fams = list(data.families.values())
    fams.sort(key=lambda f: family_sort_key(f, data.individuals))
    return fams


_YEAR_RE = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\b")


def year_from_gedcom_date(date: str) -> str:
    """Extract a four-digit year from a GEDCOM DATE value, if present."""
    hit = _YEAR_RE.search((date or "").strip())
    return hit.group(1) if hit else ""


def individual_surname(ind: Individual | None) -> str:
    if ind is None or not ind.name:
        return ""
    parts = ind.name.split("/")
    if len(parts) >= 2 and parts[1].strip():
        return parts[1].strip()
    plain = ind.name.replace("/", "").strip()
    return plain.split()[-1] if plain else ""


def family_marriage_year(fam: Family) -> str:
    return year_from_gedcom_date(fam.marriage.date)


def family_first_child_birth_year(fam: Family, data: GedcomData) -> str:
    years: list[int] = []
    for ch_xref in fam.children:
        ch = data.individuals.get(ch_xref)
        if ch is None:
            continue
        y = year_from_gedcom_date(ch.birth.date)
        if y:
            years.append(int(y))
    return str(min(years)) if years else ""


def family_display_year(fam: Family, data: GedcomData) -> str:
    """Marriage year if known, else earliest child birth year."""
    return family_marriage_year(fam) or family_first_child_birth_year(fam, data)


def individual_ancestors(data: GedcomData, xref: str) -> set[str]:
    """All ancestors of *xref* (parents, grandparents, …)."""
    if xref not in data.individuals:
        return set()
    seen: set[str] = set()
    q: deque[str] = deque()
    for fam_xref in data.individuals[xref].famc:
        fam = data.families.get(fam_xref)
        if fam is None:
            continue
        for parent in (fam.husb, fam.wife):
            if parent and parent not in seen:
                seen.add(parent)
                q.append(parent)
    while q:
        n = q.popleft()
        ind = data.individuals.get(n)
        if ind is None:
            continue
        for fam_xref in ind.famc:
            fam = data.families.get(fam_xref)
            if fam is None:
                continue
            for parent in (fam.husb, fam.wife):
                if parent and parent not in seen:
                    seen.add(parent)
                    q.append(parent)
    return seen


def individual_descendants(data: GedcomData, xref: str) -> set[str]:
    """All descendants of *xref* (children, grandchildren, …)."""
    if xref not in data.individuals:
        return set()
    seen: set[str] = set()
    q: deque[str] = deque()
    for fam_xref in data.individuals[xref].fams:
        fam = data.families.get(fam_xref)
        if fam is None:
            continue
        for child in fam.children:
            if child and child not in seen:
                seen.add(child)
                q.append(child)
    while q:
        n = q.popleft()
        ind = data.individuals.get(n)
        if ind is None:
            continue
        for fam_xref in ind.fams:
            fam = data.families.get(fam_xref)
            if fam is None:
                continue
            for child in fam.children:
                if child and child not in seen:
                    seen.add(child)
                    q.append(child)
    return seen


def individual_siblings(data: GedcomData, xref: str) -> set[str]:
    """Other children in the same birth family(ies) as *xref*."""
    if xref not in data.individuals:
        return set()
    sibs: set[str] = set()
    for fam_xref in data.individuals[xref].famc:
        fam = data.families.get(fam_xref)
        if fam is None:
            continue
        for child in fam.children:
            if child and child != xref:
                sibs.add(child)
    return sibs


def direct_lineage_people(data: GedcomData, root: str) -> set[str]:
    """Root plus direct ancestors and descendants (excludes collateral siblings)."""
    if root not in data.individuals:
        return set()
    return individual_ancestors(data, root) | individual_descendants(data, root) | {root}


def lineage_relatives(data: GedcomData, root: str) -> set[str]:
    """Root, ancestors, descendants, and siblings of each person on that line."""
    if root not in data.individuals:
        return set()
    core = individual_ancestors(data, root) | individual_descendants(data, root) | {root}
    expanded = set(core)
    for person in core:
        expanded |= individual_siblings(data, person)
    return expanded


def lineage_sibling_people(data: GedcomData, root: str) -> set[str]:
    """Siblings of anyone on the direct line, and all their descendants."""
    if root not in data.individuals:
        return set()
    direct = direct_lineage_people(data, root)
    core = individual_ancestors(data, root) | individual_descendants(data, root) | {root}
    collateral: set[str] = set()
    for person in core:
        for sib in individual_siblings(data, person):
            collateral.add(sib)
            collateral |= individual_descendants(data, sib)
    return collateral - direct


def family_on_lineage(fam: Family, data: GedcomData, lineage: set[str]) -> bool:
    """True when husband, wife, or any child is on the root lineage (incl. siblings)."""
    for xref in (fam.husb, fam.wife, *fam.children):
        if xref and xref in lineage:
            return True
    return False


def format_family_id(xref: str) -> str:
    """Family id without GEDCOM @ delimiters (e.g. F1064)."""
    return xref.strip().strip("@")


_UNKNOWN_PARENT = "Unknown"


def family_parent_surname_labels(fam: Family, data: GedcomData) -> tuple[str, str]:
    """Father and mother surnames for lists/headers; missing role → ``Unknown``."""

    def side(xref: str | None) -> str:
        if not xref:
            return _UNKNOWN_PARENT
        ind = data.individuals.get(xref)
        if ind is None:
            return _UNKNOWN_PARENT
        surn = individual_surname(ind).title()
        return surn if surn else _UNKNOWN_PARENT

    return side(fam.husb), side(fam.wife)


def family_couple_name(fam: Family, data: GedcomData) -> str:
    """``Brown - Wright`` or ``Unknown - Kenealy`` when a parent is not in the FAM."""
    father, mother = family_parent_surname_labels(fam, data)
    return f"{father} - {mother}"


def family_picker_label(fam: Family, data: GedcomData) -> str:
    """SPA list label: ``1981 Brown - Wright``."""
    year = family_display_year(fam, data)
    names = family_couple_name(fam, data)
    return f"{year} {names}" if year else names


def family_picker_sort_key(fam: Family, data: GedcomData) -> tuple:
    """Newest year first, then father surname, mother surname, xref."""
    year = family_display_year(fam, data)
    father, mother = family_parent_surname_labels(fam, data)
    year_key = -int(year) if year else 0
    return (year_key, father.upper(), mother.upper(), fam.xref)


def iter_families_for_picker(data: GedcomData) -> list[Family]:
    fams = list(data.families.values())
    fams.sort(key=lambda f: family_picker_sort_key(f, data))
    return fams


def family_summary_label(fam: Family, individuals: dict[str, Individual]) -> str:
    """One-line description for CLI / HTML option lists."""
    parts: list[str] = []
    if fam.husb and fam.husb in individuals:
        parts.append(individuals[fam.husb].name.replace("/", "").strip() or fam.husb)
    else:
        parts.append("(unknown husband)")
    parts.append(" & ")
    if fam.wife and fam.wife in individuals:
        parts.append(individuals[fam.wife].name.replace("/", "").strip() or fam.wife)
    else:
        parts.append("(unknown wife)")
    parts.append(f" — {fam.xref}")
    n_ch = len(fam.children)
    parts.append(f" ({n_ch} child{'ren' if n_ch != 1 else ''})")
    return "".join(parts)
