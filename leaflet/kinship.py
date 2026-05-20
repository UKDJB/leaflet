"""Kinship phrases from one individual (ego) to another within parsed GEDCOM data.

Blood ties use pedigree links (FAMC / FAMS). Marriage adds spouse edges between HUSB/WIFE.
Returns \"\" when there is no path in this graph (unrelated / disconnected component).
"""

from __future__ import annotations

from collections import deque
from typing import Literal

from leaflet.gedcom import Family, GedcomData, Individual

Edge = Literal["U", "D", "S"]  # up to parent, down to child, spouse hop


def _sex_word(ind: Individual | None, male: str, female: str, neutral: str = "") -> str:
    if ind is None:
        return neutral or male
    s = (ind.sex or "").upper()[:1]
    if s == "M":
        return male
    if s == "F":
        return female
    return neutral or male


def _ordinal(n: int) -> str:
    if 10 <= (n % 100) <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def _cousin_phrase(degree: int, removal: int) -> str:
    """degree 1 = first cousin; removal 0 = same generation."""
    if degree < 1:
        return ""
    ord_word = _ordinal(degree)
    base = f"{ord_word} cousin"
    if removal == 0:
        return base
    if removal == 1:
        return f"{base} once removed"
    if removal == 2:
        return f"{base} twice removed"
    return f"{base} {removal}x removed"


def _fam_married(fam: Family | None) -> bool:
    return bool(fam and (fam.marriage.date or "").strip())


def _couple_family(data: GedcomData, a: str, b: str) -> Family | None:
    """FAM where *a* and *b* are HUSB/WIFE (either order)."""
    ia = data.individuals.get(a)
    if ia is None:
        return None
    for fam_xref in ia.fams:
        fam = data.families.get(fam_xref)
        if fam is None:
            continue
        pair = {fam.husb, fam.wife} - {None}
        if a in pair and b in pair:
            return fam
    return None


def _spouse_label(data: GedcomData, ego: str, subject: str) -> str | None:
    fam = _couple_family(data, ego, subject)
    if fam is None:
        return None
    ind = data.individuals.get(subject)
    if _fam_married(fam):
        return _sex_word(ind, "Husband", "Wife", "Spouse")
    return "Partner"


def _child_spouse_label(data: GedcomData, ego: str, subject: str) -> str | None:
    """Spouse of ego's child (in-law when married, else partner)."""
    for ch in _children_of(data, ego):
        fam = _couple_family(data, ch, subject)
        if fam is None:
            continue
        ind = data.individuals.get(subject)
        if _fam_married(fam):
            return _sex_word(ind, "Son-in-law", "Daughter-in-law", "Child-in-law")
        return "Partner"
    return None


def _parent_in_law_label(data: GedcomData, ego: str, subject: str) -> str | None:
    """Parent of ego's spouse."""
    for fam_xref in data.individuals[ego].fams:
        fam = data.families.get(fam_xref)
        if fam is None:
            continue
        sp = fam.husb if fam.wife == ego else fam.wife if fam.husb == ego else None
        if not sp or subject not in _parents(data, sp):
            continue
        ind = data.individuals.get(subject)
        if _fam_married(fam):
            return _sex_word(ind, "Father-in-law", "Mother-in-law", "Parent-in-law")
        return None
    return None


def _sibling_in_law_label(data: GedcomData, ego: str, subject: str) -> str | None:
    """Spouse of ego's sibling, or sibling of ego's spouse."""
    ind = data.individuals.get(subject)
    for sib in _birth_siblings(data, ego):
        fam = _couple_family(data, sib, subject)
        if fam is None:
            continue
        if _fam_married(fam):
            return _sex_word(ind, "Brother-in-law", "Sister-in-law", "Sibling-in-law")
        return None
    for fam_xref in data.individuals[ego].fams:
        fam = data.families.get(fam_xref)
        if fam is None or not _fam_married(fam):
            continue
        sp = fam.husb if fam.wife == ego else fam.wife if fam.husb == ego else None
        if not sp or subject not in _birth_siblings(data, sp):
            continue
        return _sex_word(ind, "Brother-in-law", "Sister-in-law", "Sibling-in-law")
    return None


def _ancestors_depth_map(data: GedcomData, start: str) -> dict[str, int]:
    """Map each strict ancestor xref → generations above start (1 = parent)."""
    seen: dict[str, int] = {}
    q: deque[tuple[str, int]] = deque()
    ind = data.individuals.get(start)
    if ind is None:
        return seen
    for fam_xref in ind.famc:
        fam = data.families.get(fam_xref)
        if fam is None:
            continue
        for p in (fam.husb, fam.wife):
            if p and p not in seen:
                seen[p] = 1
                q.append((p, 1))
    while q:
        cur, depth = q.popleft()
        ic = data.individuals.get(cur)
        if ic is None:
            continue
        nd = depth + 1
        for fam_xref in ic.famc:
            fam = data.families.get(fam_xref)
            if fam is None:
                continue
            for p in (fam.husb, fam.wife):
                if p and p not in seen:
                    seen[p] = nd
                    q.append((p, nd))
    return seen


def _ancestor_label(data: GedcomData, ego: str, subject: str) -> str | None:
    depth_map = _ancestors_depth_map(data, ego)
    d = depth_map.get(subject)
    if d is None:
        return None
    ind = data.individuals.get(subject)
    if d == 1:
        return _sex_word(ind, "Father", "Mother", "Parent")
    if d == 2:
        return _sex_word(ind, "Grandfather", "Grandmother", "Grandparent")
    if d == 3:
        return _sex_word(ind, "Great-grandfather", "Great-grandmother", "Great-grandparent")
    ord_word = _ordinal(d - 2)
    base = _sex_word(ind, "great-grandfather", "great-grandmother", "great-grandparent")
    return f"{ord_word} {base}"


def _descendant_depth_map(data: GedcomData, start: str) -> dict[str, int]:
    """Map xref → generations below start (1 = child)."""
    seen: dict[str, int] = {}
    q: deque[tuple[str, int]] = deque([(start, 0)])
    while q:
        cur, gen = q.popleft()
        ic = data.individuals.get(cur)
        if ic is None:
            continue
        for fam_xref in ic.fams:
            fam = data.families.get(fam_xref)
            if fam is None:
                continue
            for ch in fam.children:
                if not ch:
                    continue
                nd = gen + 1
                if ch not in seen or nd < seen[ch]:
                    seen[ch] = nd
                    q.append((ch, nd))
    seen.pop(start, None)
    return seen


def _descendant_label(data: GedcomData, ego: str, subject: str) -> str | None:
    depths = _descendant_depth_map(data, ego)
    d = depths.get(subject)
    if d is None:
        return None
    ind = data.individuals.get(subject)
    if d == 1:
        return _sex_word(ind, "Son", "Daughter", "Child")
    if d == 2:
        return _sex_word(ind, "Grandson", "Granddaughter", "Grandchild")
    if d == 3:
        return _sex_word(ind, "Great-grandson", "Great-granddaughter", "Great-grandchild")
    ord_word = _ordinal(d - 2)
    base = _sex_word(ind, "great-grandson", "great-granddaughter", "great-grandchild")
    return f"{ord_word} {base}"


def _birth_siblings(data: GedcomData, xref: str) -> set[str]:
    sibs: set[str] = set()
    ind = data.individuals.get(xref)
    if ind is None:
        return sibs
    for fam_xref in ind.famc:
        fam = data.families.get(fam_xref)
        if fam is None:
            continue
        for ch in fam.children:
            if ch and ch != xref:
                sibs.add(ch)
    return sibs


def _parents(data: GedcomData, xref: str) -> set[str]:
    ps: set[str] = set()
    ind = data.individuals.get(xref)
    if ind is None:
        return ps
    for fam_xref in ind.famc:
        fam = data.families.get(fam_xref)
        if fam is None:
            continue
        for p in (fam.husb, fam.wife):
            if p:
                ps.add(p)
    return ps


def _sibling_label(data: GedcomData, ego: str, subject: str) -> str | None:
    if subject in _birth_siblings(data, ego):
        ind = data.individuals.get(subject)
        return _sex_word(ind, "Brother", "Sister", "Sibling")
    return None


def _aunt_uncle_label(data: GedcomData, ego: str, subject: str) -> str | None:
    """Sibling of an ancestor: aunt/uncle, grandaunt/granduncle, etc."""
    for anc, d in _ancestors_depth_map(data, ego).items():
        if subject not in _birth_siblings(data, anc):
            continue
        ind = data.individuals.get(subject)
        if d == 1:
            return _sex_word(ind, "Uncle", "Aunt", "Aunt/uncle")
        if d == 2:
            return _sex_word(ind, "Granduncle", "Grandaunt", "Grandaunt/uncle")
        if d == 3:
            return _sex_word(ind, "Great-granduncle", "Great-grandaunt", "Great-grandaunt/uncle")
        ord_word = _ordinal(d - 2)
        base = _sex_word(ind, "great-granduncle", "great-grandaunt", "great-grandaunt/uncle")
        return f"{ord_word} {base}"
    return None


def _niece_nephew_label(data: GedcomData, ego: str, subject: str) -> str | None:
    for sib in _birth_siblings(data, ego):
        depths = _descendant_depth_map(data, sib)
        d = depths.get(subject)
        if d is None:
            continue
        ind = data.individuals.get(subject)
        if d == 1:
            return _sex_word(ind, "Nephew", "Niece", "Niece/nephew")
        if d == 2:
            return _sex_word(ind, "Grandnephew", "Grandniece", "Grandniece/nephew")
        if d == 3:
            return _sex_word(ind, "Great-grandnephew", "Great-grandniece", "Great-grandniece/nephew")
        ord_word = _ordinal(d - 2)
        base = _sex_word(ind, "great-grandnephew", "great-grandniece", "great-grandniece/nephew")
        return f"{ord_word} {base}"
    return None


def _niece_nephew_spouse_label(data: GedcomData, ego: str, subject: str) -> str | None:
    """Spouse of ego's niece or nephew (gendered in-law when married, else partner)."""
    for sib in _birth_siblings(data, ego):
        for nn in _children_of(data, sib):
            fam = _couple_family(data, nn, subject)
            if fam is None:
                continue
            nn_ind = data.individuals.get(nn)
            subject_ind = data.individuals.get(subject)
            nn_sex = (nn_ind.sex or "").upper()[:1] if nn_ind else ""
            if _fam_married(fam):
                if nn_sex == "F":
                    return _sex_word(
                        subject_ind, "Husband of niece", "Wife of niece", "Spouse of niece"
                    )
                if nn_sex == "M":
                    return _sex_word(
                        subject_ind, "Husband of nephew", "Wife of nephew", "Spouse of nephew"
                    )
                return _sex_word(
                    subject_ind,
                    "Husband of niece/nephew",
                    "Wife of niece/nephew",
                    "Spouse of niece/nephew",
                )
            if nn_sex == "F":
                return "Partner of niece"
            if nn_sex == "M":
                return "Partner of nephew"
            return "Partner of niece/nephew"
    return None


def _children_of(data: GedcomData, xref: str) -> set[str]:
    ch: set[str] = set()
    ind = data.individuals.get(xref)
    if ind is None:
        return ch
    for fam_xref in ind.fams:
        fam = data.families.get(fam_xref)
        if fam is None:
            continue
        for c in fam.children:
            if c:
                ch.add(c)
    return ch


def _cousin_label(data: GedcomData, ego: str, subject: str) -> str | None:
    ego_anc = _ancestors_depth_map(data, ego)
    subj_anc = _ancestors_depth_map(data, subject)
    common = set(ego_anc) & set(subj_anc)
    if not common:
        return None
    best: tuple[int, int, int] | None = None
    for a in common:
        ce, cs = ego_anc[a], subj_anc[a]
        if ce == 0 or cs == 0:
            continue
        score = ce + cs
        if best is None or score < best[0]:
            best = (score, ce, cs)
    if best is None:
        return None
    _, ce, cs = best
    deg = min(ce, cs) - 1
    if deg < 1:
        return None
    removal = abs(ce - cs)
    return _cousin_phrase(deg, removal)


def _bfs_path_edges(data: GedcomData, ego: str, subject: str) -> list[Edge] | None:
    """Shortest path ego→subject as edges U/D/S."""
    if ego == subject:
        return []
    ind_e = data.individuals.get(ego)
    ind_s = data.individuals.get(subject)
    if ind_e is None or ind_s is None:
        return None

    def neighbors(x: str) -> list[tuple[str, Edge]]:
        out: list[tuple[str, Edge]] = []
        ix = data.individuals.get(x)
        if ix is None:
            return out
        for fam_xref in ix.famc:
            fam = data.families.get(fam_xref)
            if fam is None:
                continue
            for p in (fam.husb, fam.wife):
                if p and p != x:
                    out.append((p, "U"))
        for fam_xref in ix.fams:
            fam = data.families.get(fam_xref)
            if fam is None:
                continue
            if fam.husb and fam.husb != x:
                out.append((fam.husb, "S"))
            if fam.wife and fam.wife != x:
                out.append((fam.wife, "S"))
            for ch in fam.children:
                if ch and ch != x:
                    out.append((ch, "D"))
        return out

    prev: dict[str, tuple[str, Edge]] = {}
    q: deque[str] = deque([ego])
    seen = {ego}
    while q:
        cur = q.popleft()
        if cur == subject:
            edges: list[Edge] = []
            node = subject
            while node != ego:
                pnode, edge = prev[node]
                edges.append(edge)
                node = pnode
            edges.reverse()
            return edges
        for nex, edge in neighbors(cur):
            if nex not in seen:
                seen.add(nex)
                prev[nex] = (cur, edge)
                q.append(nex)
    return None


def _interpret_path(data: GedcomData, ego: str, subject: str, edges: list[Edge]) -> str | None:
    """Recognise common shortest-path shapes that include marriage hops."""
    if not edges:
        return None

    path_str = "".join(edges)

    if path_str == "S":
        return _spouse_label(data, ego, subject)

    if path_str == "DS":
        return _child_spouse_label(data, ego, subject)

    if path_str == "UDDS":
        return _niece_nephew_spouse_label(data, ego, subject)

    if path_str == "UDDD":
        return _niece_nephew_label(data, ego, subject)

    if path_str in ("UUD", "UUUD", "UUUUD"):
        return _aunt_uncle_label(data, ego, subject)

    if path_str == "SU":
        return _parent_in_law_label(data, ego, subject)

    if path_str == "US":
        for p in _parents(data, ego):
            if subject in _parents(data, ego):
                continue
            fam = _couple_family(data, p, subject)
            if fam is None:
                continue
            ind = data.individuals.get(subject)
            if _fam_married(fam):
                return _sex_word(ind, "Stepfather", "Stepmother", "Step-parent")
            return "Partner"
        return None

    if path_str in ("SUD", "UDS"):
        return _sibling_in_law_label(data, ego, subject)

    if path_str == "SUU":
        subject_ind = data.individuals.get(subject)
        for fam_xref in data.individuals[ego].fams:
            fam = data.families.get(fam_xref)
            if fam is None or not _fam_married(fam):
                continue
            sp = fam.husb if fam.wife == ego else fam.wife if fam.husb == ego else None
            if not sp:
                continue
            anc = _ancestors_depth_map(data, sp)
            if subject in anc and anc[subject] == 2:
                return _sex_word(
                    subject_ind,
                    "Grandfather-in-law",
                    "Grandmother-in-law",
                    "Grandparent-in-law",
                )
        return None

    return None


def relationship_label(data: GedcomData, ego_xref: str, subject_xref: str) -> str:
    """English kinship phrase from ego to subject; empty if unrelated in modeled graph."""
    if ego_xref not in data.individuals or subject_xref not in data.individuals:
        return ""
    if ego_xref == subject_xref:
        return ""

    for fn in (
        _ancestor_label,
        _descendant_label,
        _sibling_label,
        _aunt_uncle_label,
        _niece_nephew_label,
        _niece_nephew_spouse_label,
        _cousin_label,
        _spouse_label,
        _child_spouse_label,
        _parent_in_law_label,
        _sibling_in_law_label,
    ):
        lab = fn(data, ego_xref, subject_xref)
        if lab:
            return lab.lower()

    path = _bfs_path_edges(data, ego_xref, subject_xref)
    if path is None:
        return ""

    interp = _interpret_path(data, ego_xref, subject_xref, path)
    return interp.lower() if interp else ""
