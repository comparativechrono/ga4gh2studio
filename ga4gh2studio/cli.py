"""Command-line interface for ga4gh2studio."""
from __future__ import annotations
import argparse, sys
from .converter import convert_file

def main(argv=None):
    parser = argparse.ArgumentParser(prog="ga4gh2studio",
        description="Convert GA4GH Pedigree and/or Phenopackets Family to Pedigree Studio session JSON.")
    parser.add_argument("-g", "--ga4gh", default=None,
        help="Path to GA4GH Pedigree JSON file")
    parser.add_argument("-p", "--phenopackets", default=None,
        help="Path to Phenopackets Family JSON file")
    parser.add_argument("-o", "--output", default="pedigree_session.json",
        help="Output Pedigree Studio session JSON path (default: pedigree_session.json)")
    args = parser.parse_args(argv)

    if not args.ga4gh and not args.phenopackets:
        parser.error("At least one of --ga4gh or --phenopackets must be provided")

    try:
        result = convert_file(ga4gh_path=args.ga4gh, phenopackets_path=args.phenopackets,
                             output_path=args.output)
        print(result.summary)
        print(f"  Written: {args.output}")
        return 0
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr); return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr); return 1

if __name__ == "__main__":
    sys.exit(main())
