
from pathlib import Path
import zipfile, io, json, math, os
import numpy as np
import pandas as pd

PROJECT_ROOT = Path.cwd().resolve()

def find_artifact(start):
    candidates = []
    for p in [start, *list(start.parents)[:5]]:
        candidates += [
            p / "02_ARTIFACT" / "artifact",
            p / "TIOT_FINALISATION" / "02_ARTIFACT" / "artifact",
            p / "TIOT_FINALISATION(1)" / "02_ARTIFACT" / "artifact",
        ]
    for c in candidates:
        if (c / "VALIDATION_RESULT.json").exists():
            return c.resolve()
    raise FileNotFoundError("Could not find 02_ARTIFACT/artifact. Run from the extracted TIOT_FINALISATION folder.")

ARTIFACT = find_artifact(PROJECT_ROOT)
EVIDENCE_ZIP = ARTIFACT / "tiot_v7_14_5_measurement_admissibility_evidence_package_real.zip"
OUTPUT = PROJECT_ROOT / "TIOT_RED_TEAM_OUTPUTS_V3"
OUTPUT.mkdir(exist_ok=True)

print("ARTIFACT =", ARTIFACT)
print("EVIDENCE_ZIP =", EVIDENCE_ZIP)
print("Exists =", EVIDENCE_ZIP.exists())
