"""Desktop/Android entry point; no saving or export UI."""

import sys
import os
from pathlib import Path

source = Path(__file__).resolve().parent / 'src'
if source.is_dir():
    sys.path.insert(0, str(source))
if os.environ.get('NTE_TEST_MODE') == 'smoke':
    output = Path(os.environ['NTE_TEST_OUTPUT'])
    sys.stdout = (output / 'native_stdout.txt').open(
        'x', encoding='utf-8', newline='\n'
    )
    sys.stderr = (output / 'native_stderr.txt').open(
        'x', encoding='utf-8', newline='\n'
    )

# ANGLE provides a real GLES context even on Windows without a desktop GL driver.
if sys.platform == 'win32':
    os.environ.setdefault('KIVY_GL_BACKEND', 'angle_sdl2')

from nte_gear_optimizer_app.app import run

if __name__ == '__main__':
    run()
