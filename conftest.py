# conftest.py
# D:\mcp-agent-project\conftest.py — PROJECT ROOT

import sys
import os

# Add project root to path — must happen before any collection
ROOT = os.path.abspath(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Add to os.environ so subprocess calls also find it
os.environ.setdefault("PYTHONPATH", ROOT)

collect_ignore = [
    "tests/tools/test_directory_lister.py",
    "tests/tools/test_file_reader.py",
]