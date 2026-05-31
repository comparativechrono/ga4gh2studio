#!/usr/bin/env python3
"""ga4gh2studio_standalone.py - Convert GA4GH Pedigree and Phenopackets to Pedigree Studio sessions."""

from __future__ import annotations
import argparse, json, os, re, sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

__version__ = "0.1.0"

__version__ = "0.1.0"

# ── Pedigree Studio layout constants ──────────────────────────────────────
SHAPE_SIZE = 52
SHAPE_HALF = 26
PARTNER_GAP = SHAPE_SIZE * 2
CHILD_HEIGHT = SHAPE_SIZE * 2.5
CHILD_SPACING = 104
MIN_BLOCK_GAP = 60
STROKE_COLOR = "#1a2332"

# Colour palette for disease phenotypes
DISEASE_PALETTE = [
    '#c0392b', '#2980b9', '#27ae60', '#e67e22',
    '#8e44ad', '#f1c40f', '#16a085', '#d35400', '#7f8c8d',
]

# ── KIN code mapping ──────────────────────────────────────────────────────
# Maps KIN IDs to semantic meaning
KIN_MOTHER = {"KIN:027"}       # isBiologicalMotherOf
KIN_FATHER = {"KIN:028"}       # isBiologicalFatherOf
KIN_ADOPTIVE = {"KIN:022"}     # isAdoptiveParentOf
KIN_MONO_TWIN = {"KIN:010"}    # isMonozygoticMultipleBirthSiblingOf
KIN_DI_TWIN = {"KIN:011"}      # isDizygoticMultipleBirthSiblingOf

SEX_GA4GH_TO_CODE = {"MALE": 1, "FEMALE": 2, "UNKNOWN_SEX": 0, "OTHER_SEX": 0}
SEX_CODE_TO_SHAPE = {1: "male", 2: "female", 0: "unknown"}


# ── Internal data models ─────────────────────────────────────────────────

@dataclass
class Individual:
    id: str
    sex: int                         # 1=male, 2=female, 0=unknown
    name: str = ""
    date_of_birth: str = ""
    deceased: bool = False
    affected: bool = False
    proband: bool = False
    diseases: list[str] = field(default_factory=list)  # disease label strings
    father_id: Optional[str] = None
    mother_id: Optional[str] = None
    is_adopted: bool = False
    generation: int = -1
    x: float = 0.0
    y: float = 0.0
    partners: list[str] = field(default_factory=list)
    mating_units: list[str] = field(default_factory=list)


@dataclass
class MatingUnit:
    key: str
    father_id: str
    mother_id: str
    child_ids: list[str] = field(default_factory=list)


@dataclass
class TwinPair:
    child1_id: str
    child2_id: str
    type: str  # 'identical' or 'non-identical'


# ── GA4GH Pedigree parser ────────────────────────────────────────────────

def parse_ga4gh(data: dict) -> tuple[dict[str, Individual], list[TwinPair]]:
    """Parse a GA4GH Pedigree Standard JSON.

    Extracts individuals from the individuals array and derives parent-child
    and twin relationships from the relationships array using KIN ontology codes.

    Returns (individuals dict, twin pairs list).
    """
    inds: dict[str, Individual] = {}
    twins: list[TwinPair] = []

    # Parse individuals
    for ind_data in data.get("individuals", []):
        iid = ind_data.get("id", "")
        if not iid:
            continue
        sex_str = ind_data.get("sex", "UNKNOWN_SEX")
        inds[iid] = Individual(
            id=iid,
            sex=SEX_GA4GH_TO_CODE.get(sex_str, 0),
            name=ind_data.get("name", ""),
            date_of_birth=ind_data.get("dateOfBirth", ""),
            deceased=ind_data.get("deceased", False),
            affected=ind_data.get("affected", False),
            proband=False,
        )

    # Mark probands from indexPatients
    for pid in data.get("indexPatients", []):
        if pid in inds:
            inds[pid].proband = True

    # Parse relationships
    for rel in data.get("relationships", []):
        subject = rel.get("individual", "")
        obj = rel.get("relative", "")
        kin_id = rel.get("relation", {}).get("id", "")

        if not subject or not obj:
            continue

        if kin_id in KIN_MOTHER:
            # subject isBiologicalMotherOf obj → obj's mother is subject
            if obj in inds:
                inds[obj].mother_id = subject
        elif kin_id in KIN_FATHER:
            # subject isBiologicalFatherOf obj → obj's father is subject
            if obj in inds:
                inds[obj].father_id = subject
        elif kin_id in KIN_ADOPTIVE:
            # subject isAdoptiveParentOf obj
            if obj in inds:
                parent = inds.get(subject)
                if parent:
                    if parent.sex == 2:
                        inds[obj].mother_id = subject
                    else:
                        inds[obj].father_id = subject
                    inds[obj].is_adopted = True
        elif kin_id in KIN_MONO_TWIN:
            twins.append(TwinPair(child1_id=subject, child2_id=obj, type="identical"))
        elif kin_id in KIN_DI_TWIN:
            twins.append(TwinPair(child1_id=subject, child2_id=obj, type="non-identical"))

    return inds, twins


# ── Phenopackets parser ───────────────────────────────────────────────────

def parse_phenopackets(data: dict) -> tuple[dict[str, Individual], list[str]]:
    """Parse a Phenopackets Family JSON.

    Extracts individuals from the pedigree block and disease labels from
    proband and relative Phenopackets.

    Returns (individuals dict, disease names list).
    """
    inds: dict[str, Individual] = {}
    disease_names: list[str] = []
    seen_diseases: set[str] = set()

    # Parse pedigree block
    pedigree = data.get("pedigree", {})
    for person in pedigree.get("persons", []):
        iid = person.get("individualId", "")
        if not iid:
            continue
        sex_str = person.get("sex", "UNKNOWN_SEX")
        father = person.get("paternalId", "0")
        mother = person.get("maternalId", "0")
        status = person.get("affectedStatus", "MISSING")

        inds[iid] = Individual(
            id=iid,
            sex=SEX_GA4GH_TO_CODE.get(sex_str, 0),
            father_id=father if father != "0" else None,
            mother_id=mother if mother != "0" else None,
            affected=(status == "AFFECTED"),
        )

    # Extract diseases from proband
    proband = data.get("proband", {})
    proband_id = proband.get("subject", {}).get("id", "")
    if proband_id and proband_id in inds:
        inds[proband_id].proband = True
        vs = proband.get("subject", {}).get("vitalStatus", {})
        if vs.get("status") == "DECEASED":
            inds[proband_id].deceased = True
        for disease in proband.get("diseases", []):
            label = disease.get("term", {}).get("label", "")
            if label and label not in seen_diseases:
                seen_diseases.add(label)
                disease_names.append(label)
            if label and proband_id in inds:
                inds[proband_id].diseases.append(label)

    # Extract diseases from relatives
    for rel in data.get("relatives", []):
        rel_id = rel.get("subject", {}).get("id", "")
        if rel_id and rel_id in inds:
            vs = rel.get("subject", {}).get("vitalStatus", {})
            if vs.get("status") == "DECEASED":
                inds[rel_id].deceased = True
            for disease in rel.get("diseases", []):
                label = disease.get("term", {}).get("label", "")
                if label and label not in seen_diseases:
                    seen_diseases.add(label)
                    disease_names.append(label)
                if label:
                    inds[rel_id].diseases.append(label)

    # Consanguinity flag
    # (stored on result but not on individuals — used when building session)

    return inds, disease_names


# ── Merge GA4GH + Phenopackets ────────────────────────────────────────────

def merge_inputs(
    ga4gh_inds: Optional[dict[str, Individual]],
    ga4gh_twins: Optional[list[TwinPair]],
    pp_inds: Optional[dict[str, Individual]],
    pp_diseases: Optional[list[str]],
) -> tuple[dict[str, Individual], list[TwinPair], list[str]]:
    """Merge GA4GH and Phenopackets inputs into a single individual set.

    GA4GH is primary for structure (parent-child, twins, adoption).
    Phenopackets enriches with disease labels and vital status.
    """
    if ga4gh_inds and pp_inds:
        # GA4GH is the structural source
        inds = ga4gh_inds
        twins = ga4gh_twins or []
        diseases = pp_diseases or []

        # Enrich from Phenopackets
        for iid, pp_ind in pp_inds.items():
            if iid in inds:
                if pp_ind.diseases:
                    inds[iid].diseases = pp_ind.diseases
                if pp_ind.deceased:
                    inds[iid].deceased = True
                if pp_ind.proband:
                    inds[iid].proband = True
            # Don't add individuals only in Phenopackets — GA4GH is authoritative

        return inds, twins, diseases

    elif ga4gh_inds:
        return ga4gh_inds, ga4gh_twins or [], []

    elif pp_inds:
        return pp_inds, [], pp_diseases or []

    else:
        return {}, [], []


# ── Graph analysis (from ped2studio) ──────────────────────────────────────

def build_mating_units(inds: dict[str, Individual]) -> dict[str, MatingUnit]:
    units: dict[str, MatingUnit] = {}
    for ind in inds.values():
        if ind.father_id and ind.mother_id:
            key = f"{ind.father_id}+{ind.mother_id}"
            if key not in units:
                units[key] = MatingUnit(key=key, father_id=ind.father_id, mother_id=ind.mother_id)
            units[key].child_ids.append(ind.id)
            if ind.father_id in inds:
                if ind.mother_id not in inds[ind.father_id].partners:
                    inds[ind.father_id].partners.append(ind.mother_id)
                if key not in inds[ind.father_id].mating_units:
                    inds[ind.father_id].mating_units.append(key)
            if ind.mother_id in inds:
                if ind.father_id not in inds[ind.mother_id].partners:
                    inds[ind.mother_id].partners.append(ind.father_id)
                if key not in inds[ind.mother_id].mating_units:
                    inds[ind.mother_id].mating_units.append(key)
    return units


def assign_generations(inds: dict[str, Individual]) -> int:
    for ind in inds.values():
        has_f = ind.father_id and ind.father_id in inds
        has_m = ind.mother_id and ind.mother_id in inds
        if not has_f and not has_m:
            ind.generation = 0

    changed = True
    while changed:
        changed = False
        for ind in inds.values():
            if ind.generation >= 0:
                continue
            fg = inds[ind.father_id].generation if (ind.father_id and ind.father_id in inds) else -1
            mg = inds[ind.mother_id].generation if (ind.mother_id and ind.mother_id in inds) else -1
            if fg >= 0 and mg >= 0:
                ind.generation = max(fg, mg) + 1; changed = True
            elif fg >= 0 and not (ind.mother_id and ind.mother_id in inds):
                ind.generation = fg + 1; changed = True
            elif mg >= 0 and not (ind.father_id and ind.father_id in inds):
                ind.generation = mg + 1; changed = True

    for ind in inds.values():
        if ind.generation >= 0 and ind.partners:
            has_parent = (ind.father_id and ind.father_id in inds) or (ind.mother_id and ind.mother_id in inds)
            if has_parent:
                continue
            for pid in ind.partners:
                if pid in inds and inds[pid].generation > ind.generation:
                    ind.generation = inds[pid].generation; break

    for ind in inds.values():
        if ind.generation < 0:
            ind.generation = 0

    return max(ind.generation for ind in inds.values()) + 1 if inds else 0


def get_ancestors(inds, ind_id):
    ancestors = set()
    stack = [ind_id]
    visited = set()
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        ind = inds.get(current)
        if not ind:
            continue
        for p in (ind.father_id, ind.mother_id):
            if p and p in inds and p not in ancestors:
                ancestors.add(p)
                stack.append(p)
    return ancestors


def is_consanguineous(inds, id1, id2):
    return bool(get_ancestors(inds, id1) & get_ancestors(inds, id2))


def get_mating_unit_for_child(units, child_id):
    for mk, mu in units.items():
        if child_id in mu.child_ids:
            return mk
    return None


# ── Layout engine (from ped2studio) ───────────────────────────────────────

def compute_layout(inds, units, num_gens):
    gen_members = defaultdict(list)
    for ind in inds.values():
        gen_members[ind.generation].append(ind.id)

    placed = set()

    # Gen 0
    y0 = 100.0
    cursor = 200.0
    gen0_couples = []
    gen0_coupled = set()
    for mu in units.values():
        f, m = mu.father_id, mu.mother_id
        if f in inds and m in inds:
            if inds[f].generation == 0 and inds[m].generation == 0:
                pair = (min(f, m), max(f, m))
                if pair[0] not in gen0_coupled:
                    gen0_couples.append((f, m))
                    gen0_coupled.add(f); gen0_coupled.add(m)

    for f, m in gen0_couples:
        inds[f].x, inds[f].y = cursor, y0; cursor += PARTNER_GAP
        inds[m].x, inds[m].y = cursor, y0; cursor += SHAPE_SIZE + MIN_BLOCK_GAP
        placed.add(f); placed.add(m)

    for iid in gen_members.get(0, []):
        if iid not in placed:
            inds[iid].x, inds[iid].y = cursor, y0
            cursor += SHAPE_SIZE + MIN_BLOCK_GAP; placed.add(iid)

    # Gen 1+
    for gen in range(1, num_gens):
        y = 100 + gen * CHILD_HEIGHT
        mu_children = {}
        orphans = []
        for iid in gen_members.get(gen, []):
            found = get_mating_unit_for_child(units, iid)
            if found:
                mu_children.setdefault(found, []).append(iid)
            else:
                orphans.append(iid)

        consang_pairs = set()
        all_children = set()
        for clist in mu_children.values():
            all_children.update(clist)
        for iid in all_children:
            for pid in inds[iid].partners:
                if pid in all_children:
                    consang_pairs.add((min(iid, pid), max(iid, pid)))

        def mu_sort_key(mk):
            mu = units[mk]
            xs = []
            if mu.father_id in inds and inds[mu.father_id].generation < gen: xs.append(inds[mu.father_id].x)
            if mu.mother_id in inds and inds[mu.mother_id].generation < gen: xs.append(inds[mu.mother_id].x)
            return (sum(xs) / len(xs)) if xs else 0

        mu_order = sorted(mu_children.keys(), key=mu_sort_key)
        used_ranges = []

        for mk in mu_order:
            mu = units[mk]
            children = mu_children[mk]
            if not children:
                continue
            fx = (inds[mu.father_id].x + SHAPE_HALF) if mu.father_id in inds else 0
            mx = (inds[mu.mother_id].x + SHAPE_HALF) if mu.mother_id in inds else 0
            parent_mid = (fx + mx) / 2

            child_infos = []
            for cid in children:
                partner_id = None
                partner_is_consang = False
                for pid in inds[cid].partners:
                    if pid in inds and inds[pid].generation == gen and pid not in children:
                        partner_id = pid
                        partner_is_consang = (min(cid, pid), max(cid, pid)) in consang_pairs
                        break
                child_infos.append((cid, partner_id is not None, partner_id, partner_is_consang))

            partnered = [e for e in child_infos if e[1]]
            unpartnered = [e for e in child_infos if not e[1]]
            left_p, right_p = [], []
            for entry in partnered:
                cid, p, pid, pc = entry
                if pc and pid and pid in placed:
                    (left_p if inds[pid].x < parent_mid else right_p).append(entry)
                elif pc:
                    right_p.append(entry)
                else:
                    right_p.append(entry)
            marry_ins = [e for e in right_p if not e[3]]
            consang_right = [e for e in right_p if e[3]]
            if len(marry_ins) > 1:
                half = len(marry_ins) // 2
                left_p = left_p + marry_ins[:half]; right_p = consang_right + marry_ins[half:]
            else:
                right_p = consang_right + marry_ins

            ordered = left_p + unpartnered + right_p
            n_slots = len(ordered)
            total_width = (n_slots - 1) * CHILD_SPACING if n_slots > 1 else 0
            start_x = parent_mid - total_width / 2 - SHAPE_HALF
            positions = []
            for i, (cid, has_partner, partner_id, partner_is_consang) in enumerate(ordered):
                cx = start_x + i * CHILD_SPACING
                if has_partner and partner_id:
                    if partner_is_consang:
                        positions.append((cid, cx))
                    else:
                        child_centre = cx + SHAPE_HALF
                        if child_centre <= parent_mid:
                            positions.append((partner_id, cx - PARTNER_GAP)); positions.append((cid, cx))
                        else:
                            positions.append((cid, cx)); positions.append((partner_id, cx + PARTNER_GAP))
                else:
                    positions.append((cid, cx))

            if positions:
                min_x = min(px for _, px in positions); max_x = max(px for _, px in positions) + SHAPE_SIZE
                for rng_min, rng_max in used_ranges:
                    if min_x < rng_max + MIN_BLOCK_GAP and max_x > rng_min - MIN_BLOCK_GAP:
                        shift = rng_max + MIN_BLOCK_GAP - min_x
                        positions = [(pid, px + shift) for pid, px in positions]
                        min_x += shift; max_x += shift
                used_ranges.append((min_x, max_x))
                for pid, px in positions:
                    if pid and pid in inds:
                        inds[pid].x = px; inds[pid].y = y; placed.add(pid)

        orphan_cursor = (used_ranges[-1][1] + MIN_BLOCK_GAP) if used_ranges else 100.0
        for iid in orphans:
            if iid not in placed:
                inds[iid].x = orphan_cursor; inds[iid].y = y
                orphan_cursor += SHAPE_SIZE + MIN_BLOCK_GAP; placed.add(iid)

    if inds:
        min_x_global = min(ind.x for ind in inds.values())
        if min_x_global < 100:
            shift = 100 - min_x_global
            for ind in inds.values():
                ind.x += shift


# ── Session builder ───────────────────────────────────────────────────────

def build_session(
    inds: dict[str, Individual],
    units: dict[str, MatingUnit],
    twins: list[TwinPair],
    diseases: list[str],
    consanguineous_flag: bool = False,
) -> dict:
    """Build a Pedigree Studio v4 session dict."""
    persons, partnerships, child_links, twin_links = [], [], [], []
    legend_labels = {}

    # Assign colours to diseases
    disease_colors = {}
    for i, d in enumerate(diseases):
        disease_colors[d] = DISEASE_PALETTE[i % len(DISEASE_PALETTE)]

    # ID map (ga4gh IDs may not match person-N pattern)
    pid_counter = 0
    id_map = {}
    for ind in inds.values():
        pid_counter += 1
        id_map[ind.id] = f"person-{pid_counter}"

    for ind in inds.values():
        ps_id = id_map[ind.id]
        shape = SEX_CODE_TO_SHAPE.get(ind.sex, "unknown")

        # Annotation text
        text_parts = []
        if ind.name:
            text_parts.append(ind.name)
        elif ind.id:
            text_parts.append(ind.id)
        if ind.date_of_birth:
            text_parts.append(f"b. {ind.date_of_birth}")
        text = "\n".join(text_parts)

        # Fill based on diseases
        fill_mode = "none"
        fill_color = STROKE_COLOR
        halves = [None, None]
        quarters = [None, None, None, None]

        if len(ind.diseases) >= 4:
            fill_mode = "quartered"
            for qi in range(min(4, len(ind.diseases))):
                quarters[qi] = disease_colors.get(ind.diseases[qi], STROKE_COLOR)
        elif len(ind.diseases) >= 2:
            fill_mode = "quartered"
            for qi, d in enumerate(ind.diseases[:4]):
                quarters[qi] = disease_colors.get(d, STROKE_COLOR)
        elif len(ind.diseases) == 1:
            fill_mode = "solid"
            fill_color = disease_colors.get(ind.diseases[0], STROKE_COLOR)
        elif ind.affected and not diseases:
            # Affected but no disease labels — use default
            fill_mode = "solid"
            fill_color = STROKE_COLOR

        persons.append({
            "id": ps_id, "shape": shape,
            "x": round(ind.x, 1), "y": round(ind.y, 1),
            "text": text, "deceased": ind.deceased, "proband": ind.proband,
            "fillMode": fill_mode, "fillColor": fill_color,
            "quarters": quarters, "halves": halves,
            "shadingPattern": "stripes", "shadingCoverage": "full",
            "centerText": "", "miscarriageSex": "unknown",
            "noSnap": False, "siblingFixed": False, "customLabel": "Lbl",
        })

    # Partnerships
    pship_counter = 0
    pship_id_map = {}
    for mk, mu in units.items():
        if mu.father_id in id_map and mu.mother_id in id_map:
            pship_counter += 1
            ps_id = f"pship-{pship_counter}"
            pship_id_map[mk] = ps_id
            ptype = "consanguineous" if is_consanguineous(inds, mu.father_id, mu.mother_id) else "normal"
            partnerships.append({
                "id": ps_id,
                "fromId": id_map[mu.father_id],
                "toId": id_map[mu.mother_id],
                "type": ptype,
            })

    # Child links
    cl_counter = 0
    for mk, mu in units.items():
        if mk not in pship_id_map:
            continue
        for cid in mu.child_ids:
            if cid in id_map:
                cl_counter += 1
                child_links.append({
                    "id": f"child-{cl_counter}",
                    "partnershipId": pship_id_map[mk],
                    "childId": id_map[cid],
                    "branchYOffset": 0,
                    "dashed": inds[cid].is_adopted,
                })

    # Twin links
    tl_counter = 0
    for tp in twins:
        if tp.child1_id in id_map and tp.child2_id in id_map:
            # Find the partnership for these twins
            pship_id = ""
            for mk, mu in units.items():
                if tp.child1_id in mu.child_ids and tp.child2_id in mu.child_ids:
                    pship_id = pship_id_map.get(mk, "")
                    break
            if pship_id:
                tl_counter += 1
                twin_links.append({
                    "id": f"twin-{tl_counter}",
                    "child1Id": id_map[tp.child1_id],
                    "child2Id": id_map[tp.child2_id],
                    "type": tp.type,
                    "partnershipId": pship_id,
                })

    # Legend
    for d_name, d_color in disease_colors.items():
        any_has = any(d_name in ind.diseases for ind in inds.values())
        if any_has:
            legend_labels[d_color] = d_name

    return {
        "version": 4,
        "personIdCounter": pid_counter,
        "labelIdCounter": 0,
        "lineIdCounter": max(pship_counter, cl_counter, tl_counter) if any([pship_counter, cl_counter, tl_counter]) else 0,
        "persons": persons, "labels": [],
        "partnerships": partnerships, "childLinks": child_links,
        "twinLinks": twin_links,
        "legendLabels": legend_labels,
        "legendVisible": bool(legend_labels),
        "legendX": 50, "legendY": 80,
        "zoom": 1, "panX": 0, "panY": 0,
        "numberingMode": "numbers",
        "partnerGapMultiplier": 2, "childHeightMultiplier": 2.5,
    }


# ── Public API ────────────────────────────────────────────────────────────

@dataclass
class ConversionResult:
    session: dict
    summary: str


def convert(
    ga4gh_data: Optional[dict] = None,
    phenopackets_data: Optional[dict] = None,
) -> ConversionResult:
    """Convert GA4GH Pedigree and/or Phenopackets Family to a Pedigree Studio session.

    Parameters
    ----------
    ga4gh_data : dict, optional
        Parsed GA4GH Pedigree Standard JSON.
    phenopackets_data : dict, optional
        Parsed Phenopackets Family JSON.

    At least one must be provided. If both are provided, GA4GH is used for
    structure and Phenopackets enriches with disease labels.
    """
    if not ga4gh_data and not phenopackets_data:
        return ConversionResult(session={}, summary="No input provided.")

    ga4gh_inds, ga4gh_twins = None, None
    pp_inds, pp_diseases = None, None

    if ga4gh_data:
        ga4gh_inds, ga4gh_twins = parse_ga4gh(ga4gh_data)
    if phenopackets_data:
        pp_inds, pp_diseases = parse_phenopackets(phenopackets_data)

    inds, twins, diseases = merge_inputs(ga4gh_inds, ga4gh_twins, pp_inds, pp_diseases)

    if not inds:
        return ConversionResult(session={}, summary="No individuals found in input.")

    units = build_mating_units(inds)
    num_gens = assign_generations(inds)
    compute_layout(inds, units, num_gens)

    consang = any(is_consanguineous(inds, mu.father_id, mu.mother_id)
                  for mu in units.values()
                  if mu.father_id in inds and mu.mother_id in inds)

    session = build_session(inds, units, twins, diseases, consang)

    sources = []
    if ga4gh_data:
        sources.append("GA4GH Pedigree")
    if phenopackets_data:
        sources.append("Phenopackets Family")

    summary = (
        f"Converted from {' + '.join(sources)}. "
        f"{len(inds)} individuals, {len(units)} partnerships, "
        f"{len(twins)} twin pairs. "
        f"Diseases: {', '.join(diseases) if diseases else 'none'}."
    )

    return ConversionResult(session=session, summary=summary)


def convert_file(
    ga4gh_path: Optional[str] = None,
    phenopackets_path: Optional[str] = None,
    output_path: str = "pedigree_session.json",
) -> ConversionResult:
    """Read GA4GH and/or Phenopackets files and write a Pedigree Studio session.

    At least one input path must be provided.
    """
    ga4gh_data = None
    pp_data = None

    if ga4gh_path:
        with open(ga4gh_path) as f:
            ga4gh_data = json.load(f)
    if phenopackets_path:
        with open(phenopackets_path) as f:
            pp_data = json.load(f)

    result = convert(ga4gh_data, pp_data)

    if result.session:
        with open(output_path, "w") as f:
            json.dump(result.session, f, indent=2)

    return result


def main(argv=None):
    parser = argparse.ArgumentParser(prog="ga4gh2studio",
        description="Convert GA4GH Pedigree and/or Phenopackets to Pedigree Studio session JSON.")
    parser.add_argument("-g", "--ga4gh", default=None, help="GA4GH Pedigree JSON file")
    parser.add_argument("-p", "--phenopackets", default=None, help="Phenopackets Family JSON file")
    parser.add_argument("-o", "--output", default="pedigree_session.json", help="Output session JSON path")
    args = parser.parse_args(argv)
    if not args.ga4gh and not args.phenopackets:
        parser.error("At least one of --ga4gh or --phenopackets must be provided")
    try:
        result = convert_file(ga4gh_path=args.ga4gh, phenopackets_path=args.phenopackets, output_path=args.output)
        print(result.summary)
        print(f"  Written: {args.output}")
        return 0
    except FileNotFoundError as e: print(f"Error: {e}", file=sys.stderr); return 1
    except Exception as e: print(f"Error: {e}", file=sys.stderr); return 1

if __name__ == "__main__": sys.exit(main())
