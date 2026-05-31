"""ga4gh2studio — Convert GA4GH Pedigree and Phenopackets to Pedigree Studio sessions."""
__version__ = "0.1.0"
from .converter import convert, convert_file, ConversionResult
__all__ = ["convert", "convert_file", "ConversionResult"]
