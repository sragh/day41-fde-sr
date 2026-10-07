"""Verify the audit-log hash chain. Exit code 1 if tampering is detected."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services import audit  # noqa: E402

path = Path(sys.argv[1]) if len(sys.argv) > 1 else audit.AUDIT
result = audit.verify_chain(path)
print(json.dumps(result))
sys.exit(0 if result["valid"] else 1)
