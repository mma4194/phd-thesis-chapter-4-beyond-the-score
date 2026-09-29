# Prepared content verification

`artifact/prepared_content.py` compares all six generated tables against portable content fingerprints in `protocols/toniot_prepared_content.json`. Exact hashes, schema, indices, missingness, and numerical hashes are checked as defined there.

The additional immutable completion receipt is documented in [PREPARATION_VERIFICATION.md](PREPARATION_VERIFICATION.md). Original author-run results are preserved in `previously_verified/`. They do not replace newly generated preparation or prediction checks.
