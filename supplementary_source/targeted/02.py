
# ============================================================
# 1. Frozen configuration and manifests
# ============================================================
CFG = json.loads((ARTIFACT / "manifests" / "effective_config.json").read_text(encoding="utf-8"))
SCHEMA_MANIFEST = json.loads((ARTIFACT / "manifests" / "schema_and_scopes.json").read_text(encoding="utf-8"))
TASK_REGISTRY_MANIFEST = json.loads((ARTIFACT / "manifests" / "task_registry.json").read_text(encoding="utf-8"))

# The canonical executed run used this source dataset. Environment override is permitted
# only to point to an identical local copy; the notebook records the chosen path.
CANONICAL_DATASET_DEFAULT = Path(
    "/shared/home1/c.c21126547/data/cps_unified_1s_FULLGRID_FINAL_WITH_IOT_STATEFUL_STRICTMASKED_TRIMMED.parquet"
)
DATASET_PATH = Path(os.environ.get("TIOT_DATASET_PARQUET", str(CANONICAL_DATASET_DEFAULT))).expanduser().resolve()

SEEDS = list(map(int, CFG["seeds"]))
SEED0 = int(SEEDS[0])
MODE = "real"
ROW_LIMIT = 0

# Post-hoc outputs are isolated from the frozen artifact.
DIRS = {
    "root": OUT,
    "manifests": OUT / "manifests",
    "tables": OUT / "tables",
    "figures": OUT / "figures",
    "cache": OUT / "cache",
    "logs": OUT / "logs",
    "job_state": OUT / "job_state",
}
for d in DIRS.values():
    d.mkdir(parents=True, exist_ok=True)

RUN_FINGERPRINT = {}
TIER_ALIASES = dict(CFG.get("tier_aliases", {
    "router":"router","rtr":"router","eth":"router","wan":"router","net":"router",
    "ota":"ota","ota24":"ota","ota5":"ota","ota2":"ota","wifi":"ota","wlan":"ota","otawifi":"ota",
    "zigbee":"zigbee","zb":"zigbee","zwave":"zwave","zw":"zwave",
    "iot":"iot","dev":"iot","sensor":"iot","plug":"iot","actuator":"iot",
    "telemetry_in_sec":"iot","telemetry":"iot","events_in_sec":"iot","events":"iot","state_in_sec":"iot",
}))

print("Engine:", CFG.get("engine_version"))
print("Audit patch:", CFG.get("audit_patch_level"))
print("Seeds:", SEEDS)
print("Dataset candidate:", DATASET_PATH)
print("Active frozen tiers:", SCHEMA_MANIFEST.get("active_tiers"))
