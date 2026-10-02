
# ============================================================
# 10. Final gate
# ============================================================
required=[
    FORENSIC_ROOT/"KT10_FORENSIC_SUMMARY.json",
    FORENSIC_ROOT/"tables"/"KT10_DGP_regime_audit.csv",
    FORENSIC_ROOT/"tables"/"KT10_matched_pair_regime_audit.csv",
    FORENSIC_ROOT/"tables"/"KT10_stage3_derivation.csv",
    FORENSIC_ROOT/"tables"/"KT10_semantic_contract_audit.csv",
    FORENSIC_ROOT/"figures"/"fig_KT10_regime_slope_reversal.pdf",
    FORENSIC_ROOT/"figures"/"fig_KT10_relative_vs_absolute.pdf",
]
missing=[str(p) for p in required if not p.exists()]
GATE={
    "forensic_complete":not missing,
    "missing_outputs":missing,
    "source_v1_whole_file_hash_matches_source_build":V1_WHOLE_FILE_HASH_MATCH,
    "source_v1_function_hashes_verified":SOURCE_FUNCTION_HASHES_VERIFIED,
    "canonical_hash_verified":sha256_file(CANONICAL_NOTEBOOK)==EXPECTED_CANONICAL_SHA256,
    "protocol_hash_verified":SUMMARY["protocol_hash"]==EXPECTED_PROTOCOL_HASH,
    "original_KT_v1_modified":False,
    "diagnosis":DETERMINATION["diagnosis"],
}
(FORENSIC_ROOT/"KT10_FORENSIC_GATE.json").write_text(json.dumps(GATE,indent=2),encoding="utf-8")
print(json.dumps(GATE,indent=2))
print("\nKT10 FORENSIC COMPLETE. Return the executed notebook/HTML and the forensic_KT10_v1 directory.")
