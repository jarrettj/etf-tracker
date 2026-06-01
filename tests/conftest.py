"""Pytest configuration — ensures server module is importable."""
import sys
from pathlib import Path

# Add project root to sys.path so `import server.main` works
sys.path.insert(0, str(Path(__file__).parent.parent))
