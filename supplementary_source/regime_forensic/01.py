
# ============================================================
# 0. Imports, immutable bindings, and discovery
# ============================================================
from pathlib import Path
import os, json, math, hashlib, zipfile, ast, re, shutil, tempfile
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, Markdown
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score

EXPECTED_V1_NOTEBOOK_SHA256 = "60a7f79121866814953e05219c627c66b1b424dcf2fdead7a43e9a784d3ca978"
EXPECTED_CANONICAL_SHA256 = "636feab5a35e7586073e65594dba0b9b7ebb3d3ac110eba43d7acb0cf8a47f63"
EXPECTED_PROTOCOL_HASH = "3a6fcbb1aaacf1fe42b11587dd4c4da02a88ee9f4c1b85371bb5352d9c2bb4b2"
EXPECTED_KT10_CAPABILITY = "contemporaneous_dependency|regime_power"
FIXTURE_SEEDS = [1101,1201,1301,1401]

def sha256_file(path, chunk=1024*1024):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda:f.read(chunk),b""):
            h.update(b)
    return h.hexdigest()

def stable_hash_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

PROJECT_ROOT=Path.cwd().resolve()

def ancestors(start):
    return [start,*list(start.parents)[:8]]

def find_file(names):
    for p in ancestors(PROJECT_ROOT):
        for name in names:
            q=p/name
            if q.exists(): return q.resolve()
    return None

def find_final_root():
    for p in ancestors(PROJECT_ROOT):
        for q in [p,p/"TIOT_FINALISATION",p/"TIOT_FINALISATION(1)"]:
            if (q/"01_CANONICAL_RUN"/"TIOT_v7_14_5_CANONICAL_EXECUTED.ipynb").exists():
                return q.resolve()
    return None

FINAL_ROOT=find_final_root()
V1_NOTEBOOK=find_file([
    "TIOT_FULL_STACK_KNOWN_TRUTH_VALIDATION_v1.ipynb",
    "TIOT_FULL_STACK_KNOWN_TRUTH_VALIDATION_v1_FROZEN_BEFORE_FULL_RUN.ipynb",
])
KT_OUTPUT = None
if FINAL_ROOT and (FINAL_ROOT/"TIOT_KNOWN_TRUTH_VALIDATION_V1").exists():
    KT_OUTPUT=(FINAL_ROOT/"TIOT_KNOWN_TRUTH_VALIDATION_V1").resolve()
else:
    for p in ancestors(PROJECT_ROOT):
        q=p/"TIOT_KNOWN_TRUTH_VALIDATION_V1"
        if q.exists():
            KT_OUTPUT=q.resolve(); break

BOOT=PROJECT_ROOT/".kt10_forensic_inputs"
BOOT.mkdir(parents=True,exist_ok=True)

# If only the uploaded output ZIP is available, extract it read-only into a forensic cache.
if KT_OUTPUT is None:
    zpath=find_file(["TIOT_KNOWN_TRUTH_VALIDATION_V1 (1).zip","TIOT_KNOWN_TRUTH_VALIDATION_V1.zip"])
    if zpath is None:
        raise FileNotFoundError("Could not find TIOT_KNOWN_TRUTH_VALIDATION_V1 or its ZIP.")
    ext=BOOT/"kt_v1_outputs"
    if not (ext/"full"/"KNOWN_TRUTH_VALIDATION_SUMMARY.json").exists():
        if ext.exists(): shutil.rmtree(ext)
        ext.mkdir(parents=True)
        with zipfile.ZipFile(zpath) as z: z.extractall(ext)
    KT_OUTPUT=ext

# Canonical notebook: prefer extracted finalisation tree, otherwise extract from finalisation ZIP.
if FINAL_ROOT:
    CANONICAL_NOTEBOOK=FINAL_ROOT/"01_CANONICAL_RUN"/"TIOT_v7_14_5_CANONICAL_EXECUTED.ipynb"
else:
    fzip=find_file(["TIOT_FINALISATION(1).zip","TIOT_FINALISATION.zip"])
    if fzip is None:
        raise FileNotFoundError("Could not find the canonical finalisation tree or ZIP.")
    CANONICAL_NOTEBOOK=BOOT/"TIOT_v7_14_5_CANONICAL_EXECUTED.ipynb"
    if not CANONICAL_NOTEBOOK.exists():
        with zipfile.ZipFile(fzip) as z:
            CANONICAL_NOTEBOOK.write_bytes(
                z.read("01_CANONICAL_RUN/TIOT_v7_14_5_CANONICAL_EXECUTED.ipynb")
            )

if V1_NOTEBOOK is None:
    raise FileNotFoundError("Place TIOT_FULL_STACK_KNOWN_TRUTH_VALIDATION_v1.ipynb beside this notebook.")

ACTUAL_V1_NOTEBOOK_SHA256 = sha256_file(V1_NOTEBOOK)
V1_WHOLE_FILE_HASH_MATCH = (ACTUAL_V1_NOTEBOOK_SHA256 == EXPECTED_V1_NOTEBOOK_SHA256)
if not V1_WHOLE_FILE_HASH_MATCH:
    print(
        "NOTE: KT-v1 whole-notebook SHA differs from the source-build SHA. "
        "That can happen when the notebook has been executed, RUN_PROFILE changed, "
        "or outputs/execution metadata changed. Scientific binding is enforced below "
        "using exact frozen function-level hashes."
    )

assert sha256_file(CANONICAL_NOTEBOOK)==EXPECTED_CANONICAL_SHA256, "Canonical v7.14.5 hash mismatch."

FULL=KT_OUTPUT/"full"
SUMMARY=json.loads((FULL/"KNOWN_TRUTH_VALIDATION_SUMMARY.json").read_text(encoding="utf-8"))
assert SUMMARY["run_profile"]=="full"
assert SUMMARY["protocol_hash"]==EXPECTED_PROTOCOL_HASH
assert SUMMARY["scientific_interpretation_allowed"] is True

FORENSIC_ROOT=(KT_OUTPUT/"forensic_KT10_v1").resolve()
for rel in ["tables","figures","figure_data","manifests"]:
    (FORENSIC_ROOT/rel).mkdir(parents=True,exist_ok=True)

print("KT-v1 notebook:",V1_NOTEBOOK)
print("KT-v1 SHA256 (actual):",ACTUAL_V1_NOTEBOOK_SHA256)
print("KT-v1 whole-file source-build SHA match:",V1_WHOLE_FILE_HASH_MATCH)
print("Canonical:",CANONICAL_NOTEBOOK)
print("Canonical SHA256:",sha256_file(CANONICAL_NOTEBOOK))
print("KT-v1 output:",KT_OUTPUT)
print("Protocol hash:",SUMMARY["protocol_hash"])
print("Forensic output:",FORENSIC_ROOT)
