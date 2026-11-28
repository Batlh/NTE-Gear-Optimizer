"""CI-only same-process ABBA+BAAB input-journal maintenance comparison."""

import os
import runpy

os.environ['NTE_A6_MAINTENANCE_COMPARE'] = '1'
runpy.run_path('tools/a5_profile_windows.py', run_name='__main__')
