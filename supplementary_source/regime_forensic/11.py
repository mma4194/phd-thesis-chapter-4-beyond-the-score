
# ============================================================
# 8. Forensic determination
# ============================================================
all_cross=bool(PAIR_AUDIT.cross_regime.all())
all_sign_flip=bool(SEMANTIC.relationship_sign_flip.all())
all_dependency_present=bool(SEMANTIC.contemporaneous_dependency_present_in_both_regimes.all())
all_abs_bad=bool(SEMANTIC.absolute_cross_regime_transfer_bad.all())
all_identity_pass=bool(DERIVATION.identity_passed.all())
all_property_pass=bool(DERIVATION.property_passed.all())

# Check whether frozen decision arithmetic agrees with its own stated criterion.
# We use the decision table's own passed flags and CI/threshold rows; no threshold is altered.
implementation_consistent=bool(all_identity_pass and all_property_pass)

if not implementation_consistent:
    diagnosis="implementation_error"
    rationale="At least one completed decision does not reproduce the frozen Stage-3 pass state."
elif all_cross and all_sign_flip and all_abs_bad and all_identity_pass and all_property_pass:
    # There are two layers to the diagnosis:
    # (a) The fixture clearly violates cross-regime transportability;
    # (b) The current relative Stage-3 statistics can still pass because both numerator and
    #     matched reference fail similarly in absolute terms.
    diagnosis="protocol_blind_spot_with_semantic_scope_mismatch"
    rationale=(
        "KT10 successfully plants a cross-regime relationship reversal and real source-to-target "
        "transfer is poor, but Stage 3 tests relative identity/resample equivalence rather than an "
        "absolute real-block transfer skill floor or coefficient-invariance predicate. "
        "At the same time, the capability label denotes contemporaneous dependency, which remains "
        "present within both regimes; therefore the frozen PROPERTY_UNLICENSED truth label implicitly "
        "assumes a stronger transportability meaning than the literal capability name states."
    )
elif all_dependency_present and all_identity_pass and all_property_pass:
    diagnosis="fixture_truth_mismatch"
    rationale=(
        "The planted change does not eliminate contemporaneous dependency and the implemented "
        "Stage-3 contract is internally satisfied; the frozen truth expectation is stronger than "
        "the literal capability semantics."
    )
else:
    diagnosis="requires_manual_review"
    rationale="The evidence does not map cleanly to the prespecified forensic categories."

DETERMINATION={
    "forensic_version":"KT10-forensic-v1",
    "source_protocol_hash":EXPECTED_PROTOCOL_HASH,
    "source_v1_notebook_sha256_actual":ACTUAL_V1_NOTEBOOK_SHA256,
    "source_v1_whole_file_hash_matches_source_build":V1_WHOLE_FILE_HASH_MATCH,
    "source_v1_function_hashes_verified":SOURCE_FUNCTION_HASHES_VERIFIED,
    "canonical_notebook_sha256":EXPECTED_CANONICAL_SHA256,
    "scenario_id":"KT10",
    "diagnosis":diagnosis,
    "rationale":rationale,
    "facts":{
        "all_matched_pairs_cross_regime":all_cross,
        "relationship_sign_flip_all_fixtures":all_sign_flip,
        "within_regime_dependency_present_all_fixtures":all_dependency_present,
        "absolute_cross_regime_reference_transfer_bad_all_fixtures":all_abs_bad,
        "identity_ok_all_fixtures":all_identity_pass,
        "property_ok_all_fixtures":all_property_pass,
        "implementation_consistent_with_frozen_relative_decision_rules":implementation_consistent,
    },
    "answer_to_question_1":{
        "regime0_formula":"iot_power = 20 + 3.2*router_packets + 1.5*ota24_frames + N(0,0.7)",
        "regime1_formula":"iot_power = 20 + 3.2*max(0,q995_router-router_packets) + 1.5*max(0,q995_ota-ota24_frames) + N(0,0.7)",
        "train_change_point_row":36000,
        "val_and_test_regime":1,
    },
    "answer_to_question_2":(
        "The intervention violates cross-regime relationship invariance/transportability, "
        "but contemporaneous dependence remains present within each regime. Thus the frozen "
        "PROPERTY_UNLICENSED truth is valid only if the intended Stage-3 semantics include "
        "stable transportability across matched real blocks."
    ),
    "answer_to_question_3":{
        "identity_ok":"crossed pair-seed CI of real_identity log_loss_ratio inside +/-0.03",
        "property_ok":"crossed pair-seed qualification CI of real_resample log_loss_ratio inside TRAIN-calibrated +/- contemporaneous margin",
        "missing_direct_test":"no absolute reference skill/R2 floor or explicit coefficient/regime-invariance predicate in this KT10 path",
    },
    "answer_to_question_4":(
        "real_identity has synthetic_loss == reference_loss by construction, so its log loss ratio "
        "is essentially zero even when both absolute cross-regime predictions are poor. "
        "real_resample is compared to the same poor matched reference, so its loss ratio also stays "
        "near one. Relative equivalence therefore passes while absolute reference skill can be negative."
    ),
    "recommended_action":(
        "Do not relabel KT-v1 retrospectively. Preserve the mismatch. For a KT-v2 protocol, decide "
        "explicitly whether Stage 3 is intended to license mere within-regime contemporaneous "
        "dependence or cross-regime transportability. If transportability is intended, add an "
        "absolute matched-real transfer requirement (e.g., positive reference skill / acceptable "
        "reference loss versus naive) before relative resample equivalence, then freeze and rerun "
        "the complete known-truth campaign."
    )
}
(FORENSIC_ROOT/"KT10_FORENSIC_SUMMARY.json").write_text(
    json.dumps(DETERMINATION,indent=2),encoding="utf-8"
)
print(json.dumps(DETERMINATION,indent=2))
