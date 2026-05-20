"""GEDCOM maintenance audit — orphans, disconnected branches, duplicates."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any, TextIO

from leaflet.gedcom import (
    GedcomData,
    Family,
    Individual,
    parse_gedcom,
    year_from_gedcom_date,
)

DEFAULT_ROOT_INDI = "@I32269883966@"

CSV_COLUMNS = [
    "category",
    "priority",
    "group_id",
    "record_type",
    "xref",
    "display_name",
    "birth_date",
    "death_date",
    "sex",
    "famc",
    "fams",
    "related_xrefs",
    "detail",
    "recommended_action",
]


def _norm_name(name: str) -> str:
    return " ".join(name.replace("/", " ").split()).strip().upper()


def _display_name(ind: Individual | None) -> str:
    if ind is None:
        return ""
    return ind.name.replace("/", " ").strip() or ind.xref


def _fam_display(fam: Family, individuals: dict[str, Individual]) -> str:
    h = _display_name(individuals.get(fam.husb)) if fam.husb else "—"
    w = _display_name(individuals.get(fam.wife)) if fam.wife else "—"
    return f"{h} + {w}"


def _join_refs(refs: list[str]) -> str:
    return "; ".join(refs)


def _build_indi_graph(data: GedcomData) -> dict[str, set[str]]:
    adj: dict[str, set[str]] = defaultdict(set)

    def link(a: str | None, b: str | None) -> None:
        if a and b and a != b:
            adj[a].add(b)
            adj[b].add(a)

    for fam in data.families.values():
        members = [x for x in [fam.husb, fam.wife, *fam.children] if x]
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                link(members[i], members[j])
    return adj


def _root_component(data: GedcomData, root: str) -> set[str]:
    if root not in data.individuals:
        return set()
    adj = _build_indi_graph(data)
    comp: set[str] = set()
    q = deque([root])
    comp.add(root)
    while q:
        n = q.popleft()
        for nb in adj.get(n, ()):
            if nb not in comp:
                comp.add(nb)
                q.append(nb)
    return comp


def _row(**kwargs: Any) -> dict[str, str]:
    return {col: str(kwargs.get(col, "")) for col in CSV_COLUMNS}


class AuditReport:
    def __init__(self) -> None:
        self.rows: list[dict[str, str]] = []
        self._group_counters: Counter[str] = Counter()

    def _next_group(self, prefix: str) -> str:
        self._group_counters[prefix] += 1
        return f"{prefix}-{self._group_counters[prefix]:03d}"

    def add(self, row: dict[str, str]) -> None:
        self.rows.append(row)


def collect_audit_rows(
    data: GedcomData,
    *,
    root_indi: str = DEFAULT_ROOT_INDI,
) -> AuditReport:
    report = AuditReport()
    individuals = data.individuals
    root_comp = _root_component(data, root_indi)
    root_ok = root_indi in individuals

    # --- Strict orphans ---
    for ind in individuals.values():
        if ind.famc or ind.fams:
            continue
        in_fam_role: list[str] = []
        for fam in data.families.values():
            if fam.husb == ind.xref:
                in_fam_role.append(f"{fam.xref} HUSB")
            if fam.wife == ind.xref:
                in_fam_role.append(f"{fam.xref} WIFE")
            if ind.xref in fam.children:
                in_fam_role.append(f"{fam.xref} CHIL")
        report.add(
            _row(
                category="strict_orphan",
                priority="high",
                group_id=report._next_group("ORPH"),
                record_type="INDI",
                xref=ind.xref,
                display_name=_display_name(ind),
                birth_date=ind.birth.date,
                death_date=ind.death.date,
                sex=ind.sex,
                famc="",
                fams="",
                related_xrefs=_join_refs(in_fam_role),
                detail="No FAMC or FAMS on INDI record",
                recommended_action="Link to family or remove record",
            )
        )

    # --- Disconnected from root ---
    if root_ok:
        for xref in sorted(individuals.keys() - root_comp):
            ind = individuals[xref]
            gid = report._next_group("DISC")
            report.add(
                _row(
                    category="disconnected_individual",
                    priority="medium",
                    group_id=gid,
                    record_type="INDI",
                    xref=xref,
                    display_name=_display_name(ind),
                    birth_date=ind.birth.date,
                    death_date=ind.death.date,
                    sex=ind.sex,
                    famc=_join_refs(ind.famc),
                    fams=_join_refs(ind.fams),
                    related_xrefs=root_indi,
                    detail=f"Not connected to root {_display_name(individuals.get(root_indi))}",
                    recommended_action="Merge into main tree or confirm intentional branch",
                )
            )

        for fam in data.families.values():
            members = [x for x in [fam.husb, fam.wife, *fam.children] if x]
            if members and all(m not in root_comp for m in members):
                gid = report._next_group("DFAM")
                report.add(
                    _row(
                        category="disconnected_family",
                        priority="medium",
                        group_id=gid,
                        record_type="FAM",
                        xref=fam.xref,
                        display_name=_fam_display(fam, individuals),
                        birth_date="",
                        death_date="",
                        sex="",
                        famc="",
                        fams="",
                        related_xrefs=_join_refs(members),
                        detail=f"All members outside root tree ({len(members)} people)",
                        recommended_action="Link branch to root or remove if duplicate",
                    )
                )
    else:
        report.add(
            _row(
                category="audit_warning",
                priority="high",
                group_id="WARN-001",
                record_type="INDI",
                xref=root_indi,
                display_name="",
                detail="Root individual not found in GEDCOM",
                recommended_action="Set --root to a valid INDI xref",
            )
        )

    # --- Exact duplicate INDI (name + birth date + sex) ---
    by_exact: dict[tuple[str, str, str], list[Individual]] = defaultdict(list)
    for ind in individuals.values():
        if ind.name:
            by_exact[(_norm_name(ind.name), (ind.birth.date or "").strip().upper(), ind.sex or "?")].append(
                ind
            )
    for key, group in by_exact.items():
        if len(group) < 2:
            continue
        gid = report._next_group("DUPX")
        name, bdate, sex = key
        xrefs = [g.xref for g in group]
        ambiguous = not bdate.strip()
        for ind in sorted(group, key=lambda i: i.xref):
            others = [x for x in xrefs if x != ind.xref]
            famc_set = {tuple(ind.famc)}
            parallel = len({tuple(g.famc) for g in group}) > 1
            detail = f"Exact match: {name.title()} ({sex}, b. {bdate or '—'})"
            if parallel and ind.famc:
                detail += "; parallel parent families across duplicates"
            action = (
                "Review — common forename, may be different people"
                if ambiguous
                else "Merge duplicate INDI or unify FAMC/FAMS"
            )
            report.add(
                _row(
                    category="duplicate_individual_exact",
                    priority="low" if ambiguous else "high",
                    group_id=gid,
                    record_type="INDI",
                    xref=ind.xref,
                    display_name=_display_name(ind),
                    birth_date=ind.birth.date,
                    death_date=ind.death.date,
                    sex=ind.sex,
                    famc=_join_refs(ind.famc),
                    fams=_join_refs(ind.fams),
                    related_xrefs=_join_refs(others),
                    detail=detail,
                    recommended_action=action,
                )
            )

    # --- Same name + birth year + sex (date text may differ) ---
    by_year: dict[tuple[str, str, str], list[Individual]] = defaultdict(list)
    for ind in individuals.values():
        if not ind.name:
            continue
        year = year_from_gedcom_date(ind.birth.date)
        if not year:
            continue
        by_year[(_norm_name(ind.name), year, ind.sex or "?")].append(ind)
    for key, group in by_year.items():
        if len(group) < 2:
            continue
        births = {(g.birth.date or "").strip() for g in group}
        if len(births) <= 1:
            continue
        gid = report._next_group("DUPY")
        name, year, sex = key
        xrefs = [g.xref for g in group]
        for ind in sorted(group, key=lambda i: i.xref):
            others = [x for x in xrefs if x != ind.xref]
            report.add(
                _row(
                    category="duplicate_individual_year",
                    priority="medium",
                    group_id=gid,
                    record_type="INDI",
                    xref=ind.xref,
                    display_name=_display_name(ind),
                    birth_date=ind.birth.date,
                    death_date=ind.death.date,
                    sex=ind.sex,
                    famc=_join_refs(ind.famc),
                    fams=_join_refs(ind.fams),
                    related_xrefs=_join_refs(others),
                    detail=f"Same name/year/sex; {len(births)} birth date wordings ({year})",
                    recommended_action="Likely one person — merge and keep one date form",
                )
            )

    # --- Multiple FAM for same couple ---
    by_pair: dict[tuple[str, str], list[Family]] = defaultdict(list)
    for fam in data.families.values():
        if fam.husb and fam.wife:
            by_pair[tuple(sorted([fam.husb, fam.wife]))].append(fam)
    for pair, fams in by_pair.items():
        if len(fams) < 2:
            continue
        gid = report._next_group("DUPF")
        for fam in sorted(fams, key=lambda f: f.xref):
            others = [f.xref for f in fams if f.xref != fam.xref]
            report.add(
                _row(
                    category="duplicate_couple_family",
                    priority="high",
                    group_id=gid,
                    record_type="FAM",
                    xref=fam.xref,
                    display_name=_fam_display(fam, individuals),
                    birth_date="",
                    death_date="",
                    sex="",
                    famc="",
                    fams="",
                    related_xrefs=_join_refs(others),
                    detail=f"Same couple, {len(fams)} FAM records; {len(fam.children)} children here",
                    recommended_action="Merge into one FAM record",
                )
            )

    # --- Exact duplicate FAM (husb, wife, children set) ---
    def fam_sig(fam: Family) -> tuple[str, str, tuple[str, ...]]:
        h, w = fam.husb or "", fam.wife or ""
        kids = tuple(sorted(fam.children))
        return (h, w, kids) if h <= w else (w, h, kids)

    by_fam_sig: dict[tuple[str, str, tuple[str, ...]], list[Family]] = defaultdict(list)
    for fam in data.families.values():
        if fam.husb or fam.wife or fam.children:
            by_fam_sig[fam_sig(fam)].append(fam)
    for sig, fams in by_fam_sig.items():
        if len(fams) < 2:
            continue
        gid = report._next_group("DUPS")
        for fam in sorted(fams, key=lambda f: f.xref):
            others = [f.xref for f in fams if f.xref != fam.xref]
            report.add(
                _row(
                    category="duplicate_family_exact",
                    priority="high",
                    group_id=gid,
                    record_type="FAM",
                    xref=fam.xref,
                    display_name=_fam_display(fam, individuals),
                    birth_date="",
                    death_date="",
                    sex="",
                    famc="",
                    fams="",
                    related_xrefs=_join_refs(others),
                    detail="Identical HUSB, WIFE, and CHIL list",
                    recommended_action="Delete duplicate FAM; keep one",
                )
            )

    # --- Duplicate CHIL line in same FAM ---
    for fam in data.families.values():
        counts = Counter(fam.children)
        dup_children = [ch for ch, n in counts.items() if n > 1]
        if not dup_children:
            continue
        gid = report._next_group("CHIL")
        for ch in dup_children:
            report.add(
                _row(
                    category="duplicate_child_tag",
                    priority="medium",
                    group_id=gid,
                    record_type="FAM",
                    xref=fam.xref,
                    display_name=_fam_display(fam, individuals),
                    related_xrefs=ch,
                    detail=f"CHIL {ch} listed {counts[ch]} times",
                    recommended_action="Remove duplicate CHIL line",
                )
            )

    # --- INDI in FAM role but no FAMC/FAMS (data inconsistency) ---
    for fam in data.families.values():
        for xref, role in [
            (fam.husb, "HUSB"),
            (fam.wife, "WIFE"),
        ]:
            if not xref or xref not in individuals:
                continue
            ind = individuals[xref]
            if fam.xref in ind.fams or fam.xref in ind.famc:
                continue
            report.add(
                _row(
                    category="missing_fams_link",
                    priority="medium",
                    group_id=report._next_group("LINK"),
                    record_type="INDI",
                    xref=xref,
                    display_name=_display_name(ind),
                    birth_date=ind.birth.date,
                    sex=ind.sex,
                    famc=_join_refs(ind.famc),
                    fams=_join_refs(ind.fams),
                    related_xrefs=fam.xref,
                    detail=f"Listed as {role} on {fam.xref} but FAMS/FAMC missing that family",
                    recommended_action=f"Add FAMS {fam.xref} on INDI",
                )
            )
        for ch in fam.children:
            if ch not in individuals:
                report.add(
                    _row(
                        category="broken_reference",
                        priority="high",
                        group_id=report._next_group("BREF"),
                        record_type="FAM",
                        xref=fam.xref,
                        display_name=_fam_display(fam, individuals),
                        related_xrefs=ch,
                        detail="CHIL points to missing INDI",
                        recommended_action="Fix or remove CHIL reference",
                    )
                )
                continue
            ind = individuals[ch]
            if fam.xref not in ind.famc:
                report.add(
                    _row(
                        category="missing_famc_link",
                        priority="medium",
                        group_id=report._next_group("LINK"),
                        record_type="INDI",
                        xref=ch,
                        display_name=_display_name(ind),
                        birth_date=ind.birth.date,
                        sex=ind.sex,
                        famc=_join_refs(ind.famc),
                        fams=_join_refs(ind.fams),
                        related_xrefs=fam.xref,
                        detail=f"CHIL on {fam.xref} but FAMC missing that family",
                        recommended_action=f"Add FAMC {fam.xref} on INDI",
                    )
                )

    return report


def write_audit_csv(
    path: Path | str,
    data: GedcomData,
    *,
    root_indi: str = DEFAULT_ROOT_INDI,
) -> int:
    """Write maintenance audit rows to CSV; returns row count."""
    report = collect_audit_rows(data, root_indi=root_indi)
    p = Path(path)
    with p.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(report.rows)
    return len(report.rows)


def print_audit_summary(report: AuditReport, fh: TextIO | None = None) -> None:
    import sys

    out = fh or sys.stderr
    counts: Counter[str] = Counter()
    for row in report.rows:
        counts[row["category"]] += 1
    print(f"Audit rows: {len(report.rows)}", file=out)
    for cat, n in counts.most_common():
        print(f"  {cat}: {n}", file=out)


def audit_gedcom(
    gedcom_path: Path | str,
    output_csv: Path | str,
    *,
    encoding: str = "utf-8",
    root_indi: str = DEFAULT_ROOT_INDI,
) -> int:
    data = parse_gedcom(gedcom_path, encoding=encoding)
    report = collect_audit_rows(data, root_indi=root_indi)
    p = Path(output_csv)
    with p.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(report.rows)
    print_audit_summary(report)
    return len(report.rows)
