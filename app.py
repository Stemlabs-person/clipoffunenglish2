"""Hugging Face Spaces entrypoint.

Spaces looks for app.py at the repo root and runs it directly. The real
app lives in funclip/launch.py, which is normally started from the command
line (see README.md). This just runs it the same way, with the flags
needed for it to work inside a Spaces container (listen on 0.0.0.0, use
the port Spaces assigns), so nothing about the local dev workflow changes.
"""
import os
import runpy
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
FUNCLIP_DIR = os.path.join(ROOT, "funclip")

# Stay in the repo root: launch.py's own relative paths (e.g. "funclip/utils/
# theme.json", "examples/...") assume that cwd, the same as running it via
# `python funclip/launch.py` from the repo root on the command line.
os.chdir(ROOT)

# launch.py imports sibling modules (videoclipper, launch_config, etc.) as if
# funclip/ were on sys.path, the way `python funclip/launch.py` puts it there.
sys.path.insert(0, FUNCLIP_DIR)

sys.argv = [
    "launch.py",
    "--listen",
    "--lang", "en",
    "--port", str(int(os.environ.get("PORT", 7860))),
]

runpy.run_path(os.path.join(FUNCLIP_DIR, "launch.py"), run_name="__main__")
