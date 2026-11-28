"""Isolated CI GC factorial experiment and 200 actual OS drags."""

import os
import runpy

os.environ['NTE_A6_GC_COMPARE'] = '1'
os.environ['NTE_A6_GC_MEMORY'] = '1'
runpy.run_path('tools/a5_profile_windows.py', run_name='__main__')
