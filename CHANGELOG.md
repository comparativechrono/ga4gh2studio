# Changelog

## 0.4.0

ga4gh2studio now reads GA4GH files through
[pedigree-ga4gh](https://github.com/comparativechrono/pedigree-ga4gh), the one
GA4GH implementation shared by the lab's pedigree tools, and depends on it.

- It reads the GA4GH Pedigree in the Phenopackets form of the published
  standard and the Phenopackets v2 Family, in either JSON spelling. Version
  0.3 read only the JSON that studio2ga4gh 0.3 wrote, which neither form of
  the standard uses.
- It draws partnerships (consanguineous and separated too), adoptions,
  sperm and egg donors, gestational carriers, twins, and the marks that
  studio2ga4gh notes in the narrative, and puts each condition's ontology id
  in the colour key, so that converting the drawing back gives the same
  terms.
- A child with one recorded parent gets an "unknown parent" partner, so the
  line of descent can be drawn.
- Files written by studio2ga4gh 0.3 or abusua2ga4gh 0.2 are refused with a
  message saying to upgrade them first (`pedigree-ga4gh upgrade`); files in
  the form of the draft of version 1 of the standard are refused with a
  message saying what they are.
- The command takes the file as its argument (`ga4gh2studio FILE`) and writes
  `<name>.studio.json` by default; `-g` and `-p` still work. As that is often
  the name of the drawing the file was made from, an existing file of that
  name is not replaced: the command stops with exit code 2 and says to choose
  another name with `-o` or to replace it with the new `--force`. A file named
  with `-o` is replaced, but never the file being read.
- `ga4gh2studio_standalone.py` is removed: it was version 0.1.0, read only
  the old form, and could not work without pedigree-ga4gh.
- `__version__` now matches the release (0.3.0 reported 0.1.0), and there are
  tests, run on Python 3.9 to 3.14, including a round trip through
  studio2ga4gh.

## 0.3.0

Released on PyPI on 1 June 2026.
