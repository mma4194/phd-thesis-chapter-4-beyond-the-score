
# ============================================================
# 3. Frozen evidence-table loader
# ============================================================
def read_evidence_csv(member: str) -> pd.DataFrame:
    with zipfile.ZipFile(EVIDENCE_ZIP) as z:
        with z.open(member) as f:
            return pd.read_csv(f, low_memory=False)

METRICS = read_evidence_csv("tables/table_all_metrics_current_plan.csv")
UTILITY_FROZEN = read_evidence_csv("tables/table_all_utility_current_plan.csv")
P0_LICENSES = read_evidence_csv("tables/table_p0_capability_licences.csv")
INSTRUMENT_SEED = read_evidence_csv("tables/table_controlled_instrument_ladder_seed_level.csv")
INSTRUMENT_QUAL = read_evidence_csv("tables/table_controlled_instrument_qualification.csv")

P0_LICENSE_BY_CAPABILITY = {}
for _, r in P0_LICENSES.iterrows():
    P0_LICENSE_BY_CAPABILITY.setdefault(str(r["capability"]), {})[str(r["suite"])] = r.to_dict()

# Rehydrate exact TaskCard / TaskModelCard objects from the frozen task registry.
VALID_TASK_MODELS = []
for item in TASK_REGISTRY_MANIFEST["valid_cards"]:
    t = dict(item["task"])
    t["lags"] = tuple(t.get("lags", []))
    t["predictors"] = tuple(t.get("predictors", []))
    VALID_TASK_MODELS.append(TaskModelCard(task=TaskCard(**t), model_id=item["model_id"]))

print("Frozen metrics rows:", len(METRICS))
print("Frozen utility rows:", len(UTILITY_FROZEN))
print("Frozen valid task-model cards:", len(VALID_TASK_MODELS))
