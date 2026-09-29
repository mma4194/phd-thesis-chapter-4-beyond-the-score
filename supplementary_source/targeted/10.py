
# Classifier-selection operating audit:
# compare canonical max(RF,linear) against each constituent classifier and record
# which rows change ceiling-resolution status.
SEL=[]
for ceiling in [0.9945,0.9950]:
    for rule in ["rf","linear","max"]:
        ca = C2ST27[f"candidate_{rule}_auc"]
        aa = C2ST27[f"anchor_{rule}_auc"]
        resolved = (ca<ceiling)&(aa<ceiling)
        SEL.append({
            "ceiling":ceiling,"selection_rule":rule,
            "resolved_rows":int(resolved.sum()),
            "ceiling_limited_rows":int((~resolved).sum()),
        })
SEL = pd.DataFrame(SEL)
display(SEL)
SEL.to_csv(OUT/"C2ST2_classifier_selection_sensitivity.csv",index=False)

# Near-boundary rows under the frozen convention.
near = C2ST27[
    (C2ST27["candidate_max_auc"].sub(0.995).abs() <= 0.0015) |
    (C2ST27["anchor_max_auc"].sub(0.995).abs() <= 0.0015)
].sort_values(["scope","candidate_max_auc"])
display(near)
near.to_csv(OUT/"C2ST2_near_boundary_rows.csv",index=False)
