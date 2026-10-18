# ga4gh2studio

Draw a GA4GH Pedigree or a Phenopackets Family in
[Pedigree Studio](https://github.com/comparativechrono/PedigreeStudio). It is
the reverse of [studio2ga4gh](https://github.com/comparativechrono/studio2ga4gh):
a family drawn, converted to GA4GH and drawn again comes back as the same
family.

Files are read through [pedigree-ga4gh](https://github.com/comparativechrono/pedigree-ga4gh),
the one GA4GH implementation that the lab's pedigree tools share, so
ga4gh2studio reads exactly the form that studio2ga4gh, the phenopacket toolkit
and the Pedigree workbench write, in either JSON spelling (`indexPatients` or
`index_patients`).

## Installation

```bash
pip install ga4gh2studio
```

It needs Python 3.9 or later and installs pedigree-ga4gh with it.

## Usage

```bash
ga4gh2studio okafor_ga4gh-pedigree.json                 # writes okafor.studio.json
ga4gh2studio okafor_phenopackets-family.json -o okafor.studio.json
```

Give either file. A GA4GH Pedigree holds everything a Family does, and more
(adoptions, donors, partners), so if you have both, give the Pedigree. The
`-g FILE` and `-p FILE` options of version 0.3 still work.

Without `-o`, the drawing is written beside the file, named after it:
`okafor.studio.json` for `okafor_ga4gh-pedigree.json`. That is often the name
of the drawing the GA4GH files were made from, which holds names and notes
that they do not, so ga4gh2studio never replaces a file of that name unasked.
If one exists, it stops (with exit code 2) and says so: choose another name
with `-o`, or give `--force` to replace it. A file you name with `-o` is
replaced if it exists, but never the file being read.

Open the result in Pedigree Studio and press **Tidy**: ga4gh2studio lays the
family out simply, and Tidy arranges it properly.

## What the files become

| In the GA4GH files | In Pedigree Studio |
|---|---|
| biological mother and father (`KIN:027`, `KIN:028`, `KIN:003`) | a couple with a solid line to the child |
| sperm or egg donor (`KIN:004`, `KIN:038`) | a parent with D in the symbol |
| gestational carrier (`KIN:005`) with no genetic mother recorded | drawn in the mother's place, with S in the symbol |
| adoptive or foster parent (`KIN:022`, `KIN:021`) | a dashed line, and the child's symbol in brackets |
| identical or non-identical twins (`KIN:010`, `KIN:011`, `KIN:009`) | the matching twin line |
| partners, consanguineous or separated partners | the matching partnership line |
| `indexPatients`, or the Family's proband | the proband arrow |
| vital status `DECEASED` | the slash |
| diseases and phenotypic features | colours named in the colour key, with their term: `breast cancer [MONDO:0007254]` |
| carriers, pregnancies and the like, in the narrative | the matching marks |

The ontology id written in the colour key is what lets studio2ga4gh give the
condition the same term when the drawing is converted back.

A child with only one parent recorded gets an "unknown parent" partner, so
that the line of descent can be drawn. Relationships Pedigree Studio can't
draw without the people in between (cousins or grandparents on their own, for
instance) are listed in the notes.

## Older files

Files written by studio2ga4gh up to 0.3 or abusua2ga4gh up to 0.2 are not in
the standard's form. ga4gh2studio recognises them and asks you to upgrade them
first, once, with `pedigree-ga4gh upgrade FILE -o NEW.json`. Files in the form
of the draft of version 1 of the standard, which is not yet approved, are
recognised and refused with a message saying so.

## In Python

```python
import json
import ga4gh2studio

with open("okafor_ga4gh-pedigree.json") as fh:
    pedigree = json.load(fh)

result = ga4gh2studio.convert(pedigree)        # or convert(None, family)
print(result.summary)
with open("okafor.studio.json", "w") as fh:
    json.dump(result.session, fh, indent=2)
```

## Changes from 0.3

Version 0.3 read only the JSON that studio2ga4gh 0.3 wrote, which was not the
standard's form. 0.4 reads the GA4GH Pedigree and the Phenopackets Family
through pedigree-ga4gh, takes the file as its argument, writes
`<name>.studio.json` by default, and draws partnerships, adoptions, donors,
twins and the marks noted in the narrative. See [CHANGELOG.md](CHANGELOG.md).

## Licence

MIT
