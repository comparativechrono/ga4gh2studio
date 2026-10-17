"""Tests for ga4gh2studio: GA4GH files are drawn as the families they describe.

The GA4GH files in tests/data were written by studio2ga4gh 0.4.0 from fictional families: four from the Hearn
lab's pedigree practical, and one with every kind of symbol and line Pedigree Studio draws.
"""
import contextlib
import io
import json
import os
from collections import Counter

import ga4gh2studio
from ga4gh2studio.cli import main
from pedigree_ga4gh import from_document, kin, loads

DATA = os.path.join(os.path.dirname(__file__), "data")
EXAMPLES = ["okafor", "price", "lynch", "cf-cousins", "features"]


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as fh:
        return loads(fh.read())


def test_every_example_is_drawn():
    for name in EXAMPLES:
        ped = load(name + "_ga4gh-pedigree.json")
        r = ga4gh2studio.convert(ped)
        s = r.session
        people = [p for p in s["persons"] if p["shape"] not in ("no-offspring", "infertile")]
        assert len(people) >= len(ped["individuals"]), name
        assert s["partnerships"] and s["childLinks"], name
        assert sum(1 for p in s["persons"] if p.get("proband")) == len(ped["indexPatients"]), name


def test_conditions_go_into_the_colour_key_with_their_terms():
    r = ga4gh2studio.convert(load("okafor_ga4gh-pedigree.json"))
    labels = set(r.session["legendLabels"].values())
    assert any("[HP:0000365]" in lab for lab in labels)
    assert any("[MONDO:0007254]" in lab for lab in labels)


def test_twins_and_couples_are_drawn():
    r = ga4gh2studio.convert(load("features_ga4gh-pedigree.json"))
    s = r.session
    assert Counter(t["type"] for t in s["twinLinks"]) == Counter({"identical": 1, "nonidentical": 1})
    types = Counter(p["type"] for p in s["partnerships"])
    assert types["separated"] == 1 and types["consanguineous-separated"] == 1
    assert any(c.get("dashed") for c in s["childLinks"])          # the adopted child


def test_round_trip_ga4gh_studio_ga4gh():
    """Drawn again by studio2ga4gh, every example gives the same family: the same people, relationships,
    terms and index patient (people are compared by sex, since their ids are numbered afresh)."""
    import studio2ga4gh

    def signature(doc):
        k, _ = from_document(doc)
        sex = {m.id: m.sex for m in k.members}

        def key(r):
            a, b = sex[r.individual], sex[r.relative]
            if kin.TERMS[r.kin].symmetric:      # the direction of a symmetric relation does not matter
                a, b = sorted((a, b))
            return a, r.kin, b
        return (len(k.members), Counter(key(r) for r in k.relations),
                Counter(t.id for m in k.members for t in m.terms), sum(m.index for m in k.members))

    with open(os.path.join(DATA, "example-terms.json"), encoding="utf-8") as fh:
        terms = json.load(fh)
    for name in EXAMPLES:
        ped1 = load(name + "_ga4gh-pedigree.json")
        drawn = ga4gh2studio.convert(ped1)
        r2 = studio2ga4gh.convert(drawn.session, name, terms=terms)
        ped2 = loads(r2.files[0][1])
        assert signature(ped1) == signature(ped2), name


def test_a_family_file_is_drawn():
    fam = load("price_phenopackets-family.json")
    drawn = ga4gh2studio.convert(None, fam).session
    shapes = Counter(p["shape"] for p in drawn["persons"])
    assert drawn["childLinks"] and drawn["partnerships"]
    assert sum(shapes.values()) >= len(fam["pedigree"]["persons"])


def test_older_files_are_refused_with_a_clear_message():
    for name in ("legacy/studio2ga4gh-0.3_ga4gh.json", "legacy/abusua2ga4gh-0.2_family.json"):
        with open(os.path.join(DATA, name), encoding="utf-8") as fh:
            old = json.load(fh)
        try:
            ga4gh2studio.convert(old) if "ga4gh.json" in name else ga4gh2studio.convert(None, old)
        except ga4gh2studio.LegacyFileError as exc:
            assert "pedigree-ga4gh upgrade" in str(exc)
        else:
            raise AssertionError("an old file was accepted: " + name)


def test_the_draft_of_version_1_is_refused():
    draft = {"id": "FAM1", "individuals": [{"id": "MOTHER", "sexAssignedAtBirth": "ASSIGNED_FEMALE"},
                                           {"id": "CHILD", "eggParentId": "MOTHER"}],
             "relationships": [{"individual": "MOTHER", "relative": "CHILD",
                                "biologicalRelationship": [{"id": "KIN:027", "label": "isBiologicalMotherOf"}]}]}
    try:
        ga4gh2studio.convert(draft)
    except ga4gh2studio.LegacyFileError as exc:
        assert "draft of version 1" in str(exc) and "upgrade" not in str(exc)
    else:
        raise AssertionError("a file in the draft's form was accepted")


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def test_command_line(tmp_path):
    src = tmp_path / "okafor_ga4gh-pedigree.json"
    src.write_text(open(os.path.join(DATA, "okafor_ga4gh-pedigree.json"), encoding="utf-8").read(), encoding="utf-8")
    code, out, err = run_cli(str(src))
    assert code == 0, err
    drawn = tmp_path / "okafor.studio.json"          # the name of the input, without _ga4gh-pedigree.json
    assert drawn.exists() and json.loads(drawn.read_text(encoding="utf-8"))["persons"]
    # version 0.3's options
    code, out, err = run_cli("-p", os.path.join(DATA, "price_phenopackets-family.json"),
                             "-o", str(tmp_path / "price.studio.json"))
    assert code == 0 and (tmp_path / "price.studio.json").exists()
    code, out, err = run_cli(os.path.join(DATA, "legacy", "studio2ga4gh-0.3_ga4gh.json"), "-o", str(tmp_path / "x.json"))
    assert code == 2 and "upgrade" in err
