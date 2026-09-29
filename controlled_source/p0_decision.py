capabilities = sorted(P0_SEED_SUMMARY["capability"].dropna().astype(str).unique())
margin_rows: list[dict[str, Any]] = []
P0_CALIBRATED_MARGINS: dict[str, dict[str, float]] = {}
for capability in capabilities:
    xs = _anchor_pivot("calibration", "contemporaneous", capability, "log_loss_ratio")
    if {"real_block_a", "real_block_b"}.issubset(xs.columns):
        xs_noise = xs[["pair_id", "seed"]].copy()
        xs_noise["value"] = np.abs(xs["real_block_a"] - xs["real_block_b"])
        xs_noise = xs_noise.dropna(subset=["value"])
    else:
        xs_noise = pd.DataFrame(columns=["pair_id", "seed", "value"])
    calibrated_xs, xs_pairs, xs_seeds, xs_cells = _hierarchical_calibration_quantile(
        xs_noise, CFG["p0_margin_quantile"]
    )
    if not np.isfinite(calibrated_xs):
        calibrated_xs = CFG["p0_contemporaneous_margin_floor"]
    xs_margin = float(np.clip(
        calibrated_xs,
        CFG["p0_contemporaneous_margin_floor"],
        CFG["p0_contemporaneous_margin_ceiling"],
    ))

    temporal = _anchor_pivot("calibration", "temporal", capability, "log_loss_ratio")
    if {"real_block_a", "real_block_b"}.issubset(temporal.columns):
        temporal_block = temporal[["pair_id", "seed"]].copy()
        temporal_block["value"] = 0.5 * (
            temporal["real_block_a"] + temporal["real_block_b"]
        )
        temporal_block = temporal_block.dropna(subset=["value"])
    else:
        temporal_block = pd.DataFrame(columns=["pair_id", "seed", "value"])
    calibrated_log_ratio, temporal_pairs, temporal_seeds, temporal_cells = (
        _hierarchical_calibration_quantile(
            temporal_block, CFG["p0_margin_quantile"]
        )
    )
    calibrated_ratio = (
        float(math.exp(calibrated_log_ratio))
        if np.isfinite(calibrated_log_ratio)
        else CFG["p0_temporal_ratio_floor"]
    )
    temporal_ratio = float(np.clip(
        calibrated_ratio,
        CFG["p0_temporal_ratio_floor"],
        CFG["p0_temporal_ratio_ceiling"],
    ))
    P0_CALIBRATED_MARGINS[capability] = {
        "contemporaneous_log_margin": xs_margin,
        "temporal_loss_ratio_max": temporal_ratio,
    }
    margin_rows.append({
        "capability": capability,
        "calibration_xs_pairs": xs_pairs,
        "calibration_xs_seeds": xs_seeds,
        "calibration_xs_cells": xs_cells,
        "calibration_temporal_pairs": temporal_pairs,
        "calibration_temporal_seeds": temporal_seeds,
        "calibration_temporal_cells": temporal_cells,
        "contemporaneous_log_margin": xs_margin,
        "temporal_loss_ratio_max": temporal_ratio,
        "calibration_quantile": CFG["p0_margin_quantile"],
        "xs_floor": CFG["p0_contemporaneous_margin_floor"],
        "xs_ceiling": CFG["p0_contemporaneous_margin_ceiling"],
        "temporal_floor": CFG["p0_temporal_ratio_floor"],
        "temporal_ceiling": CFG["p0_temporal_ratio_ceiling"],
    })
P0_MARGIN_TABLE = pd.DataFrame(margin_rows)
P0_MARGIN_TABLE.to_csv(
    DIRS["tables"] / "table_p0_train_calibrated_margins.csv", index=False
)


p0_decision_rows: list[dict[str, Any]] = []
P0_LICENSE_BY_CAPABILITY: dict[str, dict[str, Any]] = {}
identity_failures: list[str] = []
for capability in capabilities:
    margins = P0_CALIBRATED_MARGINS[capability]
    capability_result: dict[str, Any] = {}
    for suite in ("contemporaneous", "temporal"):
        identity = _summary_frame(
            "qualification", "real_identity", suite, capability, "log_loss_ratio"
        )
        id_stats = crossed_pair_seed_ci(
            identity, seed=SEED0 + len(p0_decision_rows)
        )
        identity_estimable = bool(
            id_stats["n_pairs"] >= CFG["p0_min_qualification_pairs"]
        )
        identity_ok = bool(
            identity_estimable
            and np.isfinite(id_stats["ci_lo"])
            and id_stats["ci_lo"] >= -CFG["p0_identity_equivalence_log_margin"]
            and id_stats["ci_hi"] <= CFG["p0_identity_equivalence_log_margin"]
        )
        p0_decision_rows.append({
            "capability": capability,
            "suite": suite,
            "criterion": "identity_equivalence",
            "estimate": id_stats["estimate"],
            "ci_lo": id_stats["ci_lo"],
            "ci_hi": id_stats["ci_hi"],
            "n_pairs": id_stats["n_pairs"],
            "n_seeds": id_stats["n_seeds"],
            "n_units": id_stats["n_cells"],
            "threshold": f"crossed pair-seed CI inside +/-{CFG['p0_identity_equivalence_log_margin']}",
            "passed": identity_ok,
        })
        # Underpowered capabilities are ineligible, not plumbing failures. A
        # plumbing failure is declared only when the prespecified minimum
        # number of independent qualification pairs exists and identity still
        # departs from equivalence.
        if identity_estimable and not identity_ok:
            identity_failures.append(f"{capability}:{suite}")

        anchors = _anchor_pivot(
            "qualification", suite, capability, "log_loss_ratio"
        )
        required = {"real_resample", "real_block_a", "real_block_b"}
        if required.issubset(anchors.columns):
            anchor_values = anchors.dropna(subset=sorted(required)).copy()
            block_values = 0.5 * (
                anchor_values["real_block_a"] + anchor_values["real_block_b"]
            )
        else:
            anchor_values = pd.DataFrame(columns=["pair_id", "seed"])
            block_values = pd.Series(dtype=float)

        if suite == "contemporaneous":
            difference = anchor_values[["pair_id", "seed"]].copy()
            difference["value"] = anchor_values.get(
                "real_resample", pd.Series(dtype=float)
            ) - block_values
            difference = difference.dropna(subset=["value"])
            stats_ = crossed_pair_seed_ci(
                difference, seed=SEED0 + 1000 + len(p0_decision_rows)
            )
            margin = margins["contemporaneous_log_margin"]
            property_ok = bool(
                stats_["n_pairs"] >= CFG["p0_min_qualification_pairs"]
                and np.isfinite(stats_["ci_lo"])
                and stats_["ci_lo"] >= -margin
                and stats_["ci_hi"] <= margin
            )
            p0_decision_rows.append({
                "capability": capability,
                "suite": suite,
                "criterion": "matched_block_resample_equivalence",
                "estimate": stats_["estimate"],
                "ci_lo": stats_["ci_lo"],
                "ci_hi": stats_["ci_hi"],
                "n_pairs": stats_["n_pairs"],
                "n_seeds": stats_["n_seeds"],
                "n_units": stats_["n_cells"],
                "threshold": (
                    "crossed pair-seed qualification CI inside TRAIN-calibrated "
                    f"+/-{margin:.4f}"
                ),
                "passed": property_ok,
            })
            capability_result[suite] = {
                "eligible": bool(
                    identity_estimable
                    and stats_["n_pairs"] >= CFG["p0_min_qualification_pairs"]
                ),
                "licensed": bool(identity_ok and property_ok),
                "identity_ok": identity_ok,
                "property_ok": property_ok,
                "n_qualification_pairs": stats_["n_pairs"],
                "n_seed_units": stats_["n_seeds"],
                "margin": margin,
            }
        else:
            block = anchor_values[["pair_id", "seed"]].copy()
            block["value"] = block_values
            block = block.dropna(subset=["value"])
            order_effect = anchor_values[["pair_id", "seed"]].copy()
            order_effect["value"] = anchor_values.get(
                "real_resample", pd.Series(dtype=float)
            ) - block_values
            order_effect = order_effect.dropna(subset=["value"])
            block_stats = crossed_pair_seed_ci(
                block, seed=SEED0 + 2000 + len(p0_decision_rows)
            )
            order_stats = crossed_pair_seed_ci(
                order_effect, seed=SEED0 + 3000 + len(p0_decision_rows)
            )
            ratio_max = margins["temporal_loss_ratio_max"]

            ni_pivot = _anchor_pivot(
                "qualification", suite, capability, "noninferiority_rate"
            )
            if {"real_block_a", "real_block_b"}.issubset(ni_pivot.columns):
                ni_frame = ni_pivot[["pair_id", "seed"]].copy()
                ni_frame["value"] = 0.5 * (
                    ni_pivot["real_block_a"] + ni_pivot["real_block_b"]
                )
                ni_frame = ni_frame.dropna(subset=["value"])
            else:
                ni_frame = pd.DataFrame(columns=["pair_id", "seed", "value"])
            ni_stats = crossed_pair_seed_ci(
                ni_frame, seed=SEED0 + 4000 + len(p0_decision_rows)
            )
            ni = ni_stats["estimate"]
            block_ok = bool(
                block_stats["n_pairs"] >= CFG["p0_min_qualification_pairs"]
                and np.isfinite(block_stats["ci_hi"])
                and math.exp(block_stats["ci_hi"]) <= ratio_max
                and np.isfinite(ni)
                and ni >= CFG["p0_min_noninferiority_rate"]
            )
            order_ok = bool(
                order_stats["n_pairs"] >= CFG["p0_min_qualification_pairs"]
                and np.isfinite(order_stats["ci_lo"])
                and order_stats["ci_lo"] >= CFG["p0_temporal_order_effect_min"]
            )
            p0_decision_rows.extend([
                {
                    "capability": capability,
                    "suite": suite,
                    "criterion": "matched_block_temporal_transfer",
                    "estimate": math.exp(block_stats["estimate"])
                    if np.isfinite(block_stats["estimate"]) else np.nan,
                    "ci_lo": math.exp(block_stats["ci_lo"])
                    if np.isfinite(block_stats["ci_lo"]) else np.nan,
                    "ci_hi": math.exp(block_stats["ci_hi"])
                    if np.isfinite(block_stats["ci_hi"]) else np.nan,
                    "n_pairs": block_stats["n_pairs"],
                    "n_seeds": block_stats["n_seeds"],
                    "n_units": block_stats["n_cells"],
                    "threshold": (
                        f"crossed pair-seed upper CI <= TRAIN-calibrated ratio {ratio_max:.4f}; "
                        f"NI rate >= {CFG['p0_min_noninferiority_rate']}"
                    ),
                    "passed": block_ok,
                    "noninferiority_rate": ni,
                    "noninferiority_ci_lo": ni_stats["ci_lo"],
                    "noninferiority_ci_hi": ni_stats["ci_hi"],
                },
                {
                    "capability": capability,
                    "suite": suite,
                    "criterion": "row_resample_order_destruction",
                    "estimate": order_stats["estimate"],
                    "ci_lo": order_stats["ci_lo"],
                    "ci_hi": order_stats["ci_hi"],
                    "n_pairs": order_stats["n_pairs"],
                    "n_seeds": order_stats["n_seeds"],
                    "n_units": order_stats["n_cells"],
                    "threshold": (
                        f"crossed pair-seed lower CI >= {CFG['p0_temporal_order_effect_min']:.4f}"
                    ),
                    "passed": order_ok,
                },
            ])
            capability_result[suite] = {
                "eligible": bool(
                    identity_estimable
                    and block_stats["n_pairs"] >= CFG["p0_min_qualification_pairs"]
                    and order_stats["n_pairs"] >= CFG["p0_min_qualification_pairs"]
                ),
                "licensed": bool(identity_ok and block_ok and order_ok),
                "identity_ok": identity_ok,
                "block_transfer_ok": block_ok,
                "order_effect_ok": order_ok,
                "n_qualification_pairs": block_stats["n_pairs"],
                "n_seed_units": block_stats["n_seeds"],
                "temporal_loss_ratio_max": ratio_max,
                "noninferiority_rate": ni,
            }
    P0_LICENSE_BY_CAPABILITY[capability] = capability_result


def _global_p0_suite(suite: str) -> dict[str, Any]:
    eligible = [
        capability for capability, payload in P0_LICENSE_BY_CAPABILITY.items()
        if payload.get(suite, {}).get("eligible")
    ]
    licensed = [
        capability for capability in eligible
        if P0_LICENSE_BY_CAPABILITY[capability][suite].get("licensed")
    ]
    fraction = float(len(licensed) / max(1, len(eligible)))
    passed = bool(
        len(licensed) >= min(CFG["p0_min_licensed_capabilities"], max(1, len(eligible)))
        and fraction >= CFG["p0_min_licensed_fraction"]
    )
    return {
        "passed": passed,
        "eligible_capabilities": eligible,
        "licensed_capabilities": licensed,
        "n_eligible": len(eligible),
        "n_licensed": len(licensed),
        "licensed_fraction": fraction,
        "minimum_licensed_capabilities": CFG["p0_min_licensed_capabilities"],
        "minimum_licensed_fraction": CFG["p0_min_licensed_fraction"],
    }


P0_GLOBAL_BY_SUITE = {
    suite: _global_p0_suite(suite) for suite in ("contemporaneous", "temporal")
}
P0_LICENSE = {
    "contemporaneous": bool(P0_GLOBAL_BY_SUITE["contemporaneous"]["passed"]),
    "temporal": bool(P0_GLOBAL_BY_SUITE["temporal"]["passed"]),
    "temporal_requires_order_preservation": True,
    "global_by_suite": P0_GLOBAL_BY_SUITE,
}

# Capability-specific temporal-property classification. Stable transfer without
# a qualifying order effect establishes only that order dependence was not
# demonstrated; it does not establish order independence.
TEMPORAL_PROPERTY_ROWS = []
for capability, payload in P0_LICENSE_BY_CAPABILITY.items():
    temporal = payload.get("temporal", {})
    if not temporal.get("eligible", False):
        state = "NOT_ESTIMABLE"
    elif temporal.get("licensed", False):
        state = "ORDER_DEPENDENT_LICENSED"
    elif temporal.get("block_transfer_ok", False) and not temporal.get("order_effect_ok", False):
        state = "ORDER_DEPENDENCE_NOT_DEMONSTRATED"
    elif not temporal.get("block_transfer_ok", False):
        state = "REGIME_UNSTABLE"
    else:
        state = "PROPERTY_UNLICENSED"
    TEMPORAL_PROPERTY_ROWS.append({
        "capability": capability,
        "state": state,
        "eligible": bool(temporal.get("eligible", False)),
        "licensed": bool(temporal.get("licensed", False)),
        "block_transfer_ok": bool(temporal.get("block_transfer_ok", False)),
        "order_effect_ok": bool(temporal.get("order_effect_ok", False)),
        "allowed_interpretation": {
            "ORDER_DEPENDENT_LICENSED": "temporal utility claims allowed for this capability",
            "ORDER_DEPENDENCE_NOT_DEMONSTRATED": (
                "no qualifying order-dependence evidence was observed; this is not evidence of order independence"
            ),
            "REGIME_UNSTABLE": "report real-block instability; no generator temporal attribution",
            "NOT_ESTIMABLE": "insufficient frozen TRAIN power or valid task units",
            "PROPERTY_UNLICENSED": "temporal claim prohibited",
        }[state],
    })
TEMPORAL_PROPERTY_CLASSIFICATION = pd.DataFrame(TEMPORAL_PROPERTY_ROWS)
TEMPORAL_PROPERTY_CLASSIFICATION.to_csv(
    DIRS["tables"] / "table_temporal_property_classification.csv", index=False
)
write_json(
    DIRS["manifests"] / "temporal_property_ablation_contract.json",
    {
        "primary_order_destruction": "row-resampled TRAIN anchor",
        "required_followup_diagnostics": [
            "lag-permuted predictors", "feature-lag ablation", "persistence-only baseline"
        ],
        "classification_table": "table_temporal_property_classification.csv",
        "test_used_for_task_reclassification": False,
    },
)
P0_DECISIONS = pd.DataFrame(p0_decision_rows)
P0_DECISIONS.to_csv(DIRS["tables"] / "table_p0_harness_qualification.csv", index=False)
P0_LICENSE_TABLE = pd.DataFrame([
    {
        "capability": capability,
        "suite": suite,
        **payload[suite],
    }
    for capability, payload in P0_LICENSE_BY_CAPABILITY.items()
    for suite in ("contemporaneous", "temporal")
    if suite in payload
])
P0_LICENSE_TABLE.to_csv(DIRS["tables"] / "table_p0_capability_licences.csv", index=False)
