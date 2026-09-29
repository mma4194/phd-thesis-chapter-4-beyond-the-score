
def read_evidence_csv(member):
    with zipfile.ZipFile(EVIDENCE_ZIP) as z:
        with z.open(member) as f:
            return pd.read_csv(f, low_memory=False)

P0_UTILITY = read_evidence_csv("tables/table_p0_utility_rows.csv")
P0_MARGINS = read_evidence_csv("tables/table_p0_train_calibrated_margins.csv")
P0_HARNESS = read_evidence_csv("tables/table_p0_harness_qualification.csv")
P0_LICENSES = read_evidence_csv("tables/table_p0_capability_licences.csv")
UTILITY = read_evidence_csv("tables/table_all_utility_current_plan.csv")
TASKS = read_evidence_csv("tables/table_task_model_admissibility.csv")
TASK_LEAK = read_evidence_csv("tables/table_task_leakage_audit.csv")
TASK_BREADTH = read_evidence_csv("tables/table_task_capability_breadth.csv")
INST_SEED = read_evidence_csv("tables/table_controlled_instrument_ladder_seed_level.csv")
INST_QUAL = read_evidence_csv("tables/table_controlled_instrument_qualification.csv")

print("Loaded exact frozen tables.")
print("P0 utility:", P0_UTILITY.shape)
print("All utility:", UTILITY.shape)
print("Task cards:", TASKS.shape)
