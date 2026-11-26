"""I/O adapter for native parity, not part of the pure calculation core."""
import sys,runpy
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root/'src'),str(root/'tests')]
runpy.run_path(str(root/'tests/parity_suite.py'),run_name='__main__')
