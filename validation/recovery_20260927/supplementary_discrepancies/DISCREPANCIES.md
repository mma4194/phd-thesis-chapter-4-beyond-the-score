# Supplementary discrepancies

These are newly recalculated comparisons of archived records, not newly fitted classifier results. No expected value, tolerance, or decision threshold has been changed.

## Wasserstein median population

At severity one, the all-feature population contains 27 feature/seed rows (nine features across three seeds). The mean of the within-seed feature medians is 0.268861111111, which prints as 0.269. Excluding zero-IQR features leaves 24 rows (eight features across three seeds). Its mean is 2.804650384067 (2.805), but its mean of within-seed medians is 0.134430555556 (0.134). The statement that both 2.805 and 0.269 describe the excluded population is incorrect.

Suggested wording: Excluding features with zero reference IQR gives a mean endpoint response of 2.805 and a mean within-seed median feature response of 0.134. The corresponding median summary over all features is 0.269.

The all-feature endpoint mean is 1463.912775650032, which rounds to 1463.913. This reproduces the arithmetic. It does not make the sparse-feature-dominated quantity a typical effect size.

## Table S14: two archived result snapshots

All 20 printed endpoints match the original canonical seed-level table in the finalisation evidence archive. Three printed classifier values differ from the newer controlled reproduction reference bundled with the executable artifact. These are differences between documented snapshots, not three unsupported values in the original table. A software-version explanation has not been established by this record-only comparison.

| Endpoint | Manuscript and canonical record | Newer controlled reference |
|---|---:|---:|
| marginal, severity 0 | 0.505879 | 0.505968 |
| coupling, severity 0 | 0.505879 | 0.505968 |
| coupling, severity 1 | 0.987818 | 0.987874 |

The changes are below 0.0001 AUC. They still fail exact six-decimal agreement and must remain visible. Preserve the canonical values when reporting that original experiment, or explicitly identify the newer run and use its values consistently. The master notebook checks newly executed fits against their own frozen reference and compares manuscript precision separately.
