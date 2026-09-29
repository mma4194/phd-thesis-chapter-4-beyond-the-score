def crossed_pair_seed_ci(
    frame: pd.DataFrame,
    *,
    seed: int,
    draws: int | None = None,
) -> dict[str, Any]:
    """Two-way cluster bootstrap over independent block pairs and stochastic seeds.

    P0 block pairs and generator seeds are crossed factors. Treating every
    pair-by-seed cell as independent is pseudo-replication; this bootstrap resamples
    the pair and seed axes independently and averages the full sampled crossing.
    """
    if draws is None:
        draws = int(CFG["p0_bootstrap_draws"])
    if frame.empty:
        return {
            "estimate": np.nan, "ci_lo": np.nan, "ci_hi": np.nan,
            "n_pairs": 0, "n_seeds": 0, "n_cells": 0,
        }
    working = frame[["pair_id", "seed", "value"]].copy()
    working["value"] = pd.to_numeric(working["value"], errors="coerce")
    working = working.dropna(subset=["value", "pair_id", "seed"])
    if working.empty:
        return {
            "estimate": np.nan, "ci_lo": np.nan, "ci_hi": np.nan,
            "n_pairs": 0, "n_seeds": 0, "n_cells": 0,
        }
    matrix = working.pivot_table(
        index="pair_id", columns="seed", values="value", aggfunc="mean"
    ).to_numpy(dtype=float)
    n_pairs, n_seeds = matrix.shape
    finite_matrix = np.isfinite(matrix)
    estimate = float(
        np.where(finite_matrix, matrix, 0.0).sum() / finite_matrix.sum()
    )
    if n_pairs == 1 and n_seeds == 1:
        return {
            "estimate": estimate, "ci_lo": estimate, "ci_hi": estimate,
            "n_pairs": 1, "n_seeds": 1, "n_cells": int(np.isfinite(matrix).sum()),
        }
    rng = np.random.default_rng(seed)
    pair_draw = rng.integers(0, n_pairs, size=(int(draws), n_pairs))
    seed_draw = rng.integers(0, n_seeds, size=(int(draws), n_seeds))
    sampled = matrix[pair_draw[:, :, None], seed_draw[:, None, :]]
    sampled_finite = np.isfinite(sampled)
    sampled_counts = sampled_finite.sum(axis=(1, 2))
    sampled_sums = np.where(sampled_finite, sampled, 0.0).sum(axis=(1, 2))
    # Algebraically identical to nanmean for nonempty resamples, while
    # structurally empty pair-by-seed draws are discarded without warnings.
    boot = np.divide(
        sampled_sums,
        sampled_counts,
        out=np.full(sampled_sums.shape, np.nan, dtype=float),
        where=sampled_counts > 0,
    )
    boot = boot[sampled_counts > 0]
    return {
        "estimate": estimate,
        "ci_lo": float(np.quantile(boot, 0.025)) if len(boot) else np.nan,
        "ci_hi": float(np.quantile(boot, 0.975)) if len(boot) else np.nan,
        "n_pairs": int(n_pairs),
        "n_seeds": int(n_seeds),
        "n_cells": int(np.isfinite(matrix).sum()),
        "bootstrap_draws_requested": int(draws),
        "bootstrap_draws_effective": int(len(boot)),
        "bootstrap_draws_structurally_empty": int(draws - len(boot)),
    }

def _hierarchical_calibration_quantile(
    frame: pd.DataFrame,
    quantile: float,
) -> tuple[float, int, int, int]:
    """Pair-balanced upper quantile for a non-negative calibration quantity."""
    if frame.empty:
        return np.nan, 0, 0, 0
    matrix = frame.pivot_table(
        index="pair_id", columns="seed", values="value", aggfunc="mean"
    ).to_numpy(dtype=float)
    if not matrix.size:
        return np.nan, 0, 0, 0
    per_pair = np.nanquantile(matrix, quantile, axis=1)
    per_pair = per_pair[np.isfinite(per_pair)]
    value = float(np.quantile(per_pair, quantile)) if len(per_pair) else np.nan
    return value, int(matrix.shape[0]), int(matrix.shape[1]), int(np.isfinite(matrix).sum())
