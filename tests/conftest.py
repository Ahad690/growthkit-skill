"""Make the skill's scripts importable from tests without installation."""
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO_ROOT, "skills", "growthkit", "scripts")
FEDERATION = os.path.join(SCRIPTS, "federation")
EXAMPLES = os.path.join(REPO_ROOT, "examples")
REFERENCES = os.path.join(REPO_ROOT, "skills", "growthkit", "references")

for path in (SCRIPTS, FEDERATION):
    if path not in sys.path:
        sys.path.insert(0, path)
