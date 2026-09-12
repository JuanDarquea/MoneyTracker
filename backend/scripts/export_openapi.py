import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402

if __name__ == "__main__":
    schema = app.openapi()
    output_path = Path(__file__).resolve().parents[2] / "docs" / "api" / "openapi.json"
    output_path.write_text(json.dumps(schema, indent=2))
    print(f"Wrote {output_path}")
