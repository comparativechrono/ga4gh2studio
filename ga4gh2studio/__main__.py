"""Allow running as `python -m ga4gh2studio`."""
import sys
from .cli import main
sys.exit(main())
