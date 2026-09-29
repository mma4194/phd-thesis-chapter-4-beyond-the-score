
# ============================================================
# 10. Precompute task-admission and P0 contexts
# ============================================================
ACTIVE_SCENARIOS=[x for x in SCENARIOS if x["scenario_id"] in ACTIVE_SCENARIO_IDS]
REQUIRED_CONTEXTS=sorted({task_context(x) for x in ACTIVE_SCENARIOS})
REQUIRED_P0=sorted({x["p0_context"] for x in ACTIVE_SCENARIOS if x["p0_context"] in {"stable","no_order","regime_unstable","regime_mild"}})
ADMISSION_CACHE={}; P0_CACHE={}
for fixture_seed in ACTIVE_FIXTURE_REPLICATES:
    frames={}
    for context in REQUIRED_CONTEXTS:
        fixture_context="stable" if context=="no_order" else context
        if fixture_context not in frames: frames[fixture_context]=make_fixture(fixture_seed,fixture_context)
        frame,_,times=frames[fixture_context]; ADMISSION_CACHE[(context,fixture_seed)]=run_admission(context,fixture_seed,frame,times)
    for context in REQUIRED_P0:
        fixture_context="stable" if context=="no_order" else context; frame,_,times=frames[fixture_context]; _,cards=ADMISSION_CACHE[(context,fixture_seed)]
        if not cards: P0_CACHE[(context,fixture_seed)]={"licences":{},"not_estimable_reason":"no_admitted_task_models"}
        else: P0_CACHE[(context,fixture_seed)]=run_p0(context,fixture_seed,frame,times,cards)
        print("P0",context,fixture_seed,"capabilities",list(P0_CACHE[(context,fixture_seed)].get("licences",{})))
    del frames; gc.collect()
