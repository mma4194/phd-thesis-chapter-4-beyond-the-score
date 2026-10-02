from pathlib import Path
import hashlib, json
root = Path(__file__).resolve().parent
manifest = json.loads((root / "PACKAGE_SHA256.json").read_text())
bad = [name for name, expected in manifest.items() if not (root / name).is_file() or hashlib.sha256((root / name).read_bytes()).hexdigest() != expected]
if bad:
    raise SystemExit("Integrity differences: " + ", ".join(bad))
print(f"PASS: {len(manifest)} packaged files match their SHA256 values.")
