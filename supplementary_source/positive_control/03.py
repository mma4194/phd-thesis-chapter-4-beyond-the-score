
# Frozen evidence needed for P0 permissions and anchor C2ST comparison.
def read_evidence_csv(member):
    with zipfile.ZipFile(EVIDENCE_ZIP) as z:
        return pd.read_csv(z.open(member),low_memory=False)

P0_LICENSES=read_evidence_csv("tables/table_p0_capability_licences.csv")
FROZEN_METRICS=read_evidence_csv("tables/table_all_metrics_current_plan.csv")

P0_LICENSE_BY_CAPABILITY={}
for _,r in P0_LICENSES.iterrows():
    P0_LICENSE_BY_CAPABILITY.setdefault(str(r["capability"]),{})[str(r["suite"])]=r.to_dict()

VALID_TASK_MODELS=[]
for item in TASK_REGISTRY_MANIFEST["valid_cards"]:
    t=dict(item["task"])
    t["lags"]=tuple(t.get("lags",[]))
    t["predictors"]=tuple(t.get("predictors",[]))
    VALID_TASK_MODELS.append(TaskModelCard(task=TaskCard(**t),model_id=item["model_id"]))

print("Task-model cards:",len(VALID_TASK_MODELS))
