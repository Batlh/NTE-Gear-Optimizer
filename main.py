"""Desktop/Android entry point; no saving or export UI."""

import sys
from pathlib import Path

source = Path(__file__).resolve().parent / 'src'
if source.is_dir():
    sys.path.insert(0, str(source))
from nte_gear_optimizer_app.app import run

if __name__ == '__main__':
    run()
