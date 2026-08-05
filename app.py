import os
import sys
from pathlib import Path

# Add root directory to sys.path so backend can resolve local modules
root_dir = Path(__file__).parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

import uvicorn
from AIDoctor.backend.index import app

if __name__ == "__main__":
    # Hugging Face Spaces runs on port 7860 by default
    port = int(os.getenv("PORT", 7860))
    print(f"Starting Doctor AI FastAPI server on port {port}...")
    uvicorn.run("AIDoctor.backend.index:app", host="0.0.0.0", port=port, log_level="info")
