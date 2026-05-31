# ga4gh2studio

Convert GA4GH Pedigree Standard and Phenopackets Family files into Pedigree Studio session JSON.

The reverse complement of `studio2ga4gh`. Together they provide bidirectional interoperability between Pedigree Studio and the GA4GH ecosystem.

## Installation

```bash
pip install ga4gh2studio
```

## Usage

### Command line

```bash
# From GA4GH Pedigree only
ga4gh2studio -g pedigree_ga4gh.json -o session.json

# From Phenopackets Family only
ga4gh2studio -p family_phenopackets.json -o session.json

# From both (GA4GH for structure, Phenopackets for disease labels)
ga4gh2studio -g pedigree_ga4gh.json -p family_phenopackets.json -o session.json
```

### Python API

```python
import ga4gh2studio, json

# From GA4GH Pedigree
with open("pedigree_ga4gh.json") as f:
    ga4gh = json.load(f)
result = ga4gh2studio.convert(ga4gh_data=ga4gh)
with open("session.json", "w") as f:
    json.dump(result.session, f, indent=2)

# From both sources
with open("family_phenopackets.json") as f:
    pp = json.load(f)
result = ga4gh2studio.convert(ga4gh_data=ga4gh, phenopackets_data=pp)
print(result.summary)
```

## Input Handling

| Input | What it provides |
|-------|-----------------|
| GA4GH Pedigree only | Full structure: parent-child (biological + adoptive), twins, sex, deceased status, proband |
| Phenopackets Family only | PED-compatible structure (parents, sex, affected status) + disease labels |
| Both (recommended) | GA4GH provides rich structure; Phenopackets enriches with disease names and vital status |

## Feature Mapping

| GA4GH / Phenopackets | Pedigree Studio |
|---------------------|-----------------|
| KIN:027 isBiologicalMotherOf | Partnership + solid child link |
| KIN:028 isBiologicalFatherOf | Partnership + solid child link |
| KIN:022 isAdoptiveParentOf | Partnership + dashed child link |
| KIN:010 isMonozygoticTwin | Identical twin link |
| KIN:011 isDizygoticTwin | Non-identical twin link |
| indexPatients | Proband arrow |
| Individual.deceased | Deceased diagonal line |
| Individual.name / dateOfBirth | Annotation text ("Name\nb. 1985") |
| Disease term labels | Legend entries with distinct colours |
| Shared ancestors | Consanguineous partnership (double line) |

## License

MIT
