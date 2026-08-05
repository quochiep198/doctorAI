import sys
from pathlib import Path

# Add the root directory to sys.path so Vercel can resolve local modules
root_dir = Path(__file__).parent.parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from AIDoctor.backend.index import app
