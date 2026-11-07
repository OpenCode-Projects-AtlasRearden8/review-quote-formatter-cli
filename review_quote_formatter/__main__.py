"""Entry point for ``python -m review_quote_formatter``."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
