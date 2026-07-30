# -*- coding: utf-8 -*-
import subprocess, sys, os
_scripts = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'PYTHON_SCRIPTS')
sys.exit(subprocess.run([sys.executable, os.path.join(_scripts, 'orchestrator.py')] + sys.argv[1:], cwd=_scripts).returncode)
