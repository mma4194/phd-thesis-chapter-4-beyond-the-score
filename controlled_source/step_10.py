
# ============================================================
# 6. Frozen task cards
# ============================================================
CAP_CONTEMP="contemporaneous_dependency|iot_power"; CAP_TEMP="forecast|router_bytes"; CAP_NO_ORDER="forecast|nominal_non_temporal_power"; CAP_REGIME="contemporaneous_dependency|regime_power"; CAP_RARE="event_onset|zigbee_events"
def task_defs(context):
    contemp=TaskCard("kt_contemporaneous_power","regression","contemporaneous","iot__power",0,(0,),("router__packets","ota24__frames","zigbee__packets","iot__state","iot__sensor"),None,"iot","known_truth_contemporaneous_power",CAP_CONTEMP,"continuous","iot__power")
    temporal=TaskCard("kt_temporal_router_bytes","regression","temporal","router__bytes",1,(1,5,30),("router__bytes","router__packets","ota24__frames","iot__power"),None,"router","known_truth_temporal_router_bytes",CAP_TEMP,"continuous","router__bytes")
    no_order=TaskCard("kt_nominal_temporal_power","regression","temporal","iot__power",0,(0,),("router__packets","ota24__frames","zigbee__packets","iot__state","iot__sensor"),None,"iot","known_truth_nominal_temporal_power",CAP_NO_ORDER,"continuous","iot__power")
    regime=TaskCard("kt_regime_power","regression","contemporaneous","iot__power",0,(0,),("router__packets","ota24__frames","zigbee__packets","iot__state","iot__sensor","iot__regime","iot__regime_interaction"),None,"iot","known_truth_regime_power",CAP_REGIME,"continuous","iot__power")
    rare=TaskCard("event_onset__kt_rare_zigbee","classification","temporal","zigbee__events",1,(0,1,5),("iot__state","router__packets","ota24__frames","zigbee__packets"),.5,"zigbee","known_truth_rare_zigbee_event",CAP_RARE,"event","zigbee__events",label_window_steps=0,threshold_kind="binary")
    return {"stable":[contemp,temporal],"no_order":[no_order],"regime_unstable":[regime],"regime_mild":[regime],"constant_target":[contemp],"rare_class":[rare],"session_shift":[contemp]}[context]
def candidate_cards(context): return [TaskModelCard(t,m) for t in task_defs(context) for m in ACTIVE_MODEL_IDS]
def task_context(s): return s["p0_context"] if s["p0_context"] in {"stable","no_order","regime_unstable","regime_mild"} else s["fixture_context"]
def cards_for(s,cards): return [c for c in cards if c.task.capability==s["capability"] and c.task.suite==s["suite"]]
