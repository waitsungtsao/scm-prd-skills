"""
conftest.py — pytest configuration for SCM PRD skills test suite.

Adds script directories to sys.path so test modules can import
yaml2drawio, check-prd-consistency, check-knowledge-consistency, and diagram_core.
"""

import sys
import os

# Add both script directories to the import path
PRD_SCRIPTS = os.path.join(os.path.dirname(__file__), '..', 'scm-prd-workflow', 'scripts')
KC_SCRIPTS = os.path.join(os.path.dirname(__file__), '..', 'scm-knowledge-curator', 'scripts')

sys.path.insert(0, os.path.abspath(PRD_SCRIPTS))
sys.path.insert(0, os.path.abspath(KC_SCRIPTS))
