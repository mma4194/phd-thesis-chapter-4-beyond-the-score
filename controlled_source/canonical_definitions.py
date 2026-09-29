class ScientificInvalidFit(RuntimeError):
    """Expected model failure: execution completed, scientific result is unusable."""
    def __init__(self, message: str, diagnostics: dict[str, Any] | None = None):
        super().__init__(message)
        self.diagnostics = diagnostics or {}

def deterministic_subsample_indices(n: int, cap: int | None) -> np.ndarray:
    if cap is None or n <= cap:
        return np.arange(n, dtype=int)
    step = max(1, n // cap)
    return np.arange(0, n, step, dtype=int)[:cap]

def robust_iqr(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if not len(x):
        return 0.0
    return float(np.quantile(x, 0.75) - np.quantile(x, 0.25))

def safe_corr(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 10 or np.std(a[ok]) <= 1e-12 or np.std(b[ok]) <= 1e-12:
        return np.nan
    return float(np.corrcoef(a[ok], b[ok])[0, 1])

def marginal_profile(real: pd.DataFrame, synthetic: pd.DataFrame, columns: Sequence[str]) -> dict[str, float]:
    ks_values: list[float] = []
    zero_errors: list[float] = []
    wasserstein_values: list[float] = []
    for column in columns:
        if column not in real or column not in synthetic:
            continue
        a = real[column].to_numpy(dtype=float)
        b = synthetic[column].to_numpy(dtype=float)
        a = a[np.isfinite(a)]
        b = b[np.isfinite(b)]
        if len(a) < 10 or len(b) < 10:
            continue
        if stats is not None:
            ks_values.append(float(stats.ks_2samp(a, b, method="asymp").statistic))
        else:
            quantiles = np.quantile(np.concatenate([a, b]), np.linspace(0, 1, 101))
            ks_values.append(float(max(abs((a <= q).mean() - (b <= q).mean()) for q in quantiles)))
        zero_errors.append(abs(float((a == 0).mean()) - float((b == 0).mean())))
        if wasserstein_distance is not None:
            scale = max(robust_iqr(a), 1e-6)
            wasserstein_values.append(float(wasserstein_distance(a, b) / scale))
    return {
        "marginal_ks_mean": float(np.mean(ks_values)) if ks_values else np.nan,
        "marginal_ks_median": float(np.median(ks_values)) if ks_values else np.nan,
        "zero_rate_mae": float(np.mean(zero_errors)) if zero_errors else np.nan,
        "wasserstein_iqr_mean": float(np.mean(wasserstein_values)) if wasserstein_values else np.nan,
        "marginal_n_features": int(len(ks_values)),
    }

def autocorrelation(x: np.ndarray, lag: int) -> float:
    x = np.asarray(x, dtype=float)
    if lag <= 0 or len(x) <= lag + 10:
        return np.nan
    return safe_corr(x[:-lag], x[lag:])

def temporal_profile(
    real: pd.DataFrame,
    synthetic: pd.DataFrame,
    columns: Sequence[str],
    lags: Sequence[int] | None = None,
    max_len: int = 65536,
) -> dict[str, float]:
    lags = list(lags or CFG["acf_lags"])
    acf_errors: list[float] = []
    spectral_errors: list[float] = []
    transition_errors: list[float] = []
    for column in columns:
        if column not in real or column not in synthetic:
            continue
        a = real[column].to_numpy(dtype=float)[:max_len]
        b = synthetic[column].to_numpy(dtype=float)[:max_len]
        n = min(len(a), len(b))
        if n < max(lags, default=1) + 20:
            continue
        a, b = a[:n], b[:n]
        for lag in lags:
            ra = autocorrelation(a, lag)
            rb = autocorrelation(b, lag)
            if np.isfinite(ra) and np.isfinite(rb):
                acf_errors.append(abs(ra - rb))
        aa = a - np.mean(a)
        bb = b - np.mean(b)
        pa = np.abs(np.fft.rfft(aa)) ** 2
        pb = np.abs(np.fft.rfft(bb)) ** 2
        if pa.sum() > 0 and pb.sum() > 0:
            pa = pa / pa.sum()
            pb = pb / pb.sum()
            spectral_errors.append(float(np.abs(pa - pb).sum()))
        # State-transition rate captures sparse event persistence without assuming a distribution.
        za = (a != 0).astype(np.int8)
        zb = (b != 0).astype(np.int8)
        transition_errors.append(abs(float(np.mean(za[1:] != za[:-1])) - float(np.mean(zb[1:] != zb[:-1]))))
    return {
        "acf_abs_error_mean": float(np.mean(acf_errors)) if acf_errors else np.nan,
        "acf_abs_error_median": float(np.median(acf_errors)) if acf_errors else np.nan,
        "spectral_l1_mean": float(np.mean(spectral_errors)) if spectral_errors else np.nan,
        "transition_rate_mae": float(np.mean(transition_errors)) if transition_errors else np.nan,
        "temporal_n_feature_lags": int(len(acf_errors)),
    }

def coupling_profile_from_pairs(
    real: pd.DataFrame,
    synthetic: pd.DataFrame,
    pairs: Sequence[tuple[str, str]],
    lag: int = 0,
) -> dict[str, float]:
    real_corr: list[float] = []
    synthetic_corr: list[float] = []
    coactivation_errors: list[float] = []
    for left, right in pairs:
        if left not in real or right not in real or left not in synthetic or right not in synthetic:
            continue
        ar = real[left].to_numpy(dtype=float)
        br = real[right].to_numpy(dtype=float)
        ass = synthetic[left].to_numpy(dtype=float)
        bs = synthetic[right].to_numpy(dtype=float)
        n = min(len(ar), len(br), len(ass), len(bs))
        if lag > 0:
            ar, br = ar[: n - lag], br[lag:n]
            ass, bs = ass[: n - lag], bs[lag:n]
        else:
            ar, br, ass, bs = ar[:n], br[:n], ass[:n], bs[:n]
        rr = safe_corr(ar, br)
        rs = safe_corr(ass, bs)
        if np.isfinite(rr) and np.isfinite(rs):
            real_corr.append(rr)
            synthetic_corr.append(rs)
        co_r = float(np.mean((ar != 0) & (br != 0)))
        co_s = float(np.mean((ass != 0) & (bs != 0)))
        coactivation_errors.append(abs(co_r - co_s))
    if real_corr:
        r = np.asarray(real_corr)
        s = np.asarray(synthetic_corr)
        corr_mae = float(np.mean(np.abs(r - s)))
        corr_rel = float(np.linalg.norm(r - s) / (np.linalg.norm(r) + 1e-12))
        sign_agreement = float(np.mean(np.sign(r) == np.sign(s)))
    else:
        corr_mae = corr_rel = sign_agreement = np.nan
    return {
        "coupling_corr_mae": corr_mae,
        "coupling_corr_relative_l2": corr_rel,
        "coupling_sign_agreement": sign_agreement,
        "coupling_coactivation_mae": float(np.mean(coactivation_errors)) if coactivation_errors else np.nan,
        "coupling_n_pairs": int(len(real_corr)),
        "coupling_lag": int(lag),
    }

def _valid_group_split(X: np.ndarray, y: np.ndarray, groups: np.ndarray, seed: int):
    splitter = GroupShuffleSplit(n_splits=20, test_size=0.35, random_state=seed)
    for train_idx, test_idx in splitter.split(X, y, groups):
        if len(np.unique(y[train_idx])) == 2 and len(np.unique(y[test_idx])) == 2:
            return train_idx, test_idx
    raise RuntimeError("Unable to form a grouped two-class C2ST split")

def _c2st_auc_once(
    X: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    seed: int,
    classifier: str,
    n_estimators: int | None = None,
) -> float:
    train_idx, test_idx = _valid_group_split(X, y, groups, seed)
    if classifier in {"rf", "rf_null"}:
        model = RandomForestClassifier(
            n_estimators=int(
                n_estimators
                if n_estimators is not None
                else (CFG["c2st_trees"] if classifier == "rf" else CFG["c2st_null_trees"])
            ),
            max_depth=CFG["c2st_max_depth"],
            min_samples_leaf=3,
            n_jobs=CFG["n_jobs"],
            random_state=seed,
            class_weight="balanced_subsample",
        )
    elif classifier == "linear":
        model = make_pipeline(
            StandardScaler(),
            LogisticRegression(
                max_iter=300,
                class_weight="balanced",
                random_state=seed,
                solver="lbfgs",
            ),
        )
    else:
        raise ValueError(classifier)
    model.fit(X[train_idx], y[train_idx])
    probability = model.predict_proba(X[test_idx])[:, 1]
    auc = float(roc_auc_score(y[test_idx], probability))
    return max(auc, 1.0 - auc)

def _permute_labels_within_groups(
    y: np.ndarray,
    groups: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """Conditional label randomisation preserving temporal-block membership."""
    result = np.asarray(y, dtype=np.int8).copy()
    for group in np.unique(groups):
        idx = np.flatnonzero(groups == group)
        if len(idx) > 1:
            result[idx] = rng.permutation(result[idx])
    return result

def c2st_profile(
    real: pd.DataFrame,
    synthetic: pd.DataFrame,
    columns: Sequence[str],
    seed: int,
    row_cap: int | None = None,
    n_splits: int | None = None,
    n_permutations: int | None = None,
    rf_trees: int | None = None,
    null_trees: int | None = None,
) -> dict[str, float]:
    columns = [column for column in columns if column in real and column in synthetic]
    if not columns:
        return {"c2st_rf_auc": np.nan, "c2st_linear_auc": np.nan, "c2st_max_auc": np.nan}
    rng = np.random.default_rng(seed)
    n = min(len(real), len(synthetic))
    if row_cap:
        n = min(n, max(1000, row_cap // 2))
    ir = np.sort(rng.choice(len(real), n, replace=False)) if len(real) > n else np.arange(len(real))
    isyn = np.sort(rng.choice(len(synthetic), n, replace=False)) if len(synthetic) > n else np.arange(len(synthetic))
    X = np.vstack([
        real.iloc[ir][columns].to_numpy(dtype=np.float32),
        synthetic.iloc[isyn][columns].to_numpy(dtype=np.float32),
    ])
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    y = np.concatenate([np.zeros(len(ir), dtype=np.int8), np.ones(len(isyn), dtype=np.int8)])
    block_size = max(1, int(CFG["c2st_block_size"]))
    # Match real and synthetic observations by temporal block. Shared block IDs
    # keep both classes from the same period in one train/test partition.
    gr = ir // block_size
    gs = isyn // block_size
    groups = np.concatenate([gr, gs])
    splits = int(n_splits or CFG["c2st_splits"])
    rf = np.asarray([
        _c2st_auc_once(X, y, groups, seed + 17 * i, "rf", n_estimators=rf_trees)
        for i in range(splits)
    ])
    linear = np.asarray([_c2st_auc_once(X, y, groups, seed + 101 + 17 * i, "linear") for i in range(splits)])
    permutations = int(n_permutations if n_permutations is not None else CFG["c2st_permutations"])
    null_values: list[float] = []
    for i in range(permutations):
        yp = _permute_labels_within_groups(y, groups, rng)
        null_values.append(_c2st_auc_once(
            X, yp, groups, seed + 1000 + i, "rf_null", n_estimators=null_trees
        ))
    null = np.asarray(null_values, dtype=float)
    observed = float(max(rf.mean(), linear.mean()))
    return {
        "c2st_rf_auc": float(rf.mean()),
        "c2st_rf_sd": float(rf.std(ddof=1)) if len(rf) > 1 else 0.0,
        "c2st_linear_auc": float(linear.mean()),
        "c2st_linear_sd": float(linear.std(ddof=1)) if len(linear) > 1 else 0.0,
        "c2st_max_auc": observed,
        "c2st_null_mean": float(null.mean()) if len(null) else np.nan,
        "c2st_null_p95": float(np.quantile(null, 0.95)) if len(null) else np.nan,
        "c2st_excess_over_null_mean": (
            float(observed - null.mean()) if len(null) else np.nan
        ),
        "c2st_excess_over_null_p95": (
            float(max(0.0, observed - np.quantile(null, 0.95)))
            if len(null) else np.nan
        ),
        "c2st_permutation_p": float((1 + np.sum(null >= observed)) / (len(null) + 1)) if len(null) else np.nan,
        "c2st_n_per_class": int(n),
        "c2st_n_groups": int(len(np.unique(groups))),
        "c2st_block_size": int(block_size),
    }

def build_controlled_iot_fixture(n: int, seed: int = 19) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    daily = 0.5 + 0.5 * np.sin(2 * np.pi * t / 3600.0)
    latent = np.zeros(n, dtype=float)
    for i in range(1, n):
        latent[i] = 0.96 * latent[i - 1] + rng.normal(0, 0.25)
    latent = (latent - latent.mean()) / (latent.std() + 1e-9)
    occupancy = (latent + 0.8 * daily + rng.normal(0, 0.35, n) > 0.45).astype(float)
    router_packets = rng.poisson(np.clip(2 + 8 * occupancy + 2 * daily, 0.1, None)).astype(float)
    router_bytes = router_packets * rng.lognormal(5.2, 0.35, n)
    ota_frames = rng.poisson(np.clip(1 + 5 * occupancy + 0.35 * router_packets, 0.1, None)).astype(float)
    ota_retries = rng.binomial(np.maximum(ota_frames.astype(int), 0), np.clip(0.03 + 0.15 * occupancy, 0, 0.7)).astype(float)
    zigbee_packets = rng.poisson(np.clip(0.2 + 1.8 * occupancy + 0.15 * ota_frames, 0.05, None)).astype(float)
    zigbee_events = (rng.random(n) < np.clip(0.005 + 0.035 * occupancy, 0, 0.4)).astype(float)
    iot_power = np.maximum(0, 8 + 22 * occupancy + 0.8 * router_packets + rng.normal(0, 2.5, n))
    iot_state = occupancy.copy()
    # Add an explicitly masked sensor to test observability fidelity.
    sensor = 20 + 2.5 * daily + 0.7 * latent + rng.normal(0, 0.4, n)
    miss = rng.random(n) < (0.01 + 0.04 * (1 - occupancy))
    sensor[miss] = 0.0
    return pd.DataFrame({
        "router__packets": router_packets,
        "router__bytes": router_bytes,
        "ota24__frames": ota_frames,
        "ota24__retries": ota_retries,
        "zigbee__packets": zigbee_packets,
        "zigbee__events": zigbee_events,
        "iot__power": iot_power,
        "iot__state": iot_state,
        "iot__sensor": sensor,
        "iot__sensor__nonfinite_mask": miss.astype(float),
    })

def perturb_fixture(df: pd.DataFrame, kind: str, severity: float, seed: int) -> pd.DataFrame:
    severity = float(np.clip(severity, 0, 1))
    rng = np.random.default_rng(seed)
    out = df.copy()
    n = len(out)
    if severity == 0:
        return out
    if kind == "marginal":
        columns = ["router__bytes", "iot__power", "iot__sensor"]
        for column in columns:
            original = out[column].to_numpy(dtype=float)
            shifted = original * (1 + 1.5 * severity) + severity * robust_iqr(original)
            out[column] = shifted
        # Also perturb zero inflation monotonically on sparse channels, so the
        # zero-rate instrument is qualified against a known ground-truth change.
        for column in ("ota24__retries", "zigbee__events"):
            values = out[column].to_numpy(dtype=float, copy=True)
            active = np.flatnonzero(values != 0)
            count = int(round(severity * 0.60 * len(active)))
            if count > 0:
                selected = rng.choice(active, count, replace=False)
                values[selected] = 0.0
            out[column] = values
    elif kind == "order":
        # A global row permutation preserves marginals and same-row coupling but destroys chronology.
        permutation = rng.permutation(n)
        count = int(round(severity * n))
        chosen = np.sort(rng.choice(n, count, replace=False))
        source = permutation[:count]
        out.iloc[chosen] = out.iloc[source].to_numpy()
    elif kind == "coupling":
        # Independent per-column replacement preserves each marginal but breaks cross-column alignment.
        count = int(round(severity * n))
        chosen = np.sort(rng.choice(n, count, replace=False))
        for column in out.columns:
            source = rng.choice(n, count, replace=False)
            values = out[column].to_numpy(copy=True)
            values[chosen] = values[source]
            out[column] = values
    else:
        raise ValueError(kind)
    return out

def rank_correlation(x: Sequence[float], y: Sequence[float]) -> float:
    if stats is not None:
        return float(stats.spearmanr(x, y).statistic)
    xr = pd.Series(x).rank().to_numpy()
    yr = pd.Series(y).rank().to_numpy()
    return safe_corr(xr, yr)

def qualify_metrics_on_controlled_fixture() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Qualify every headline instrument on repeated fixtures with known damage.

    A metric is not allowed to issue generator claims merely because it is
    conventional. It must respond monotonically and materially to a perturbation
    whose target property and severity are known by construction. Repeating the
    exercise across independently generated fixtures prevents a single convenient
    synthetic realisation from licensing an instrument.
    """
    # Instrument qualification is itself a scientific contract.  It must not
    # inherit the deliberately cheap C2ST shortcuts used by downstream smoke
    # benchmarking, because those shortcuts can change the pass/fail result.
    n = 24000
    instrument_c2st_contract = {
        "row_cap": 12000,
        "n_splits": 3,
        "rf_trees": 100,
        "null_trees": 25,
    }
    fixture_seeds = list(CFG["instrument_fixture_seeds"])
    known_pairs = [
        ("router__packets", "ota24__frames"),
        ("router__packets", "iot__power"),
        ("ota24__frames", "zigbee__packets"),
        ("iot__state", "zigbee__events"),
    ]
    severities = [0.0, 0.25, 0.50, 0.75, 1.0]
    rows: list[dict[str, Any]] = []
    for fixture_seed in fixture_seeds:
        base = build_controlled_iot_fixture(n=n, seed=int(fixture_seed))
        columns = [c for c in base.columns if not c.endswith("__nonfinite_mask")]
        for kind in ("marginal", "order", "coupling"):
            for severity in severities:
                perturbed = perturb_fixture(
                    base,
                    kind,
                    severity,
                    seed=int(fixture_seed) + int(100 * severity) + len(kind),
                )
                row = {
                    "fixture_seed": int(fixture_seed),
                    "perturbation": kind,
                    "severity": severity,
                }
                row.update(marginal_profile(base, perturbed, columns))
                row.update(temporal_profile(base, perturbed, columns, lags=[1, 5, 30, 60], max_len=n))
                row.update(coupling_profile_from_pairs(base, perturbed, known_pairs, lag=0))
                # Exchangeable row classifiers are not expected to detect a pure
                # chronology perturbation, so C2ST is qualified only where row
                # distributions/couplings are deliberately changed.
                if kind in {"marginal", "coupling"}:
                    row.update(c2st_profile(
                        base,
                        perturbed,
                        columns,
                        seed=int(fixture_seed) + int(1000 * severity) + len(kind),
                        row_cap=instrument_c2st_contract["row_cap"],
                        n_splits=instrument_c2st_contract["n_splits"],
                        n_permutations=(
                            9 if severity == 0.0 else 3
                        ),
                        rf_trees=instrument_c2st_contract["rf_trees"],
                        null_trees=instrument_c2st_contract["null_trees"],
                    ))
                rows.append(row)

    table = pd.DataFrame(rows)
    aggregate = (
        table.groupby(["perturbation", "severity"], as_index=False)
        .mean(numeric_only=True)
        .sort_values(["perturbation", "severity"])
    )

    target_metrics = {
        "marginal": [
            "marginal_ks_mean",
            "wasserstein_iqr_mean",
            "zero_rate_mae",
            "c2st_max_auc",
        ],
        "order": [
            "acf_abs_error_mean",
            "spectral_l1_mean",
            "transition_rate_mae",
        ],
        "coupling": [
            "coupling_corr_mae",
            "coupling_coactivation_mae",
            "c2st_max_auc",
        ],
    }
    endpoint_minimum = {
        "marginal_ks_mean": 0.02,
        "wasserstein_iqr_mean": 0.05,
        "zero_rate_mae": 0.002,
        "c2st_max_auc": 0.02,
        "acf_abs_error_mean": 0.01,
        "spectral_l1_mean": 0.03,
        "transition_rate_mae": 0.0005,
        "coupling_corr_mae": 0.02,
        "coupling_coactivation_mae": 0.0005,
    }

    checks: list[dict[str, Any]] = []
    for kind, metrics in target_metrics.items():
        subset = aggregate[aggregate["perturbation"] == kind].sort_values("severity")
        for metric in metrics:
            values = pd.to_numeric(subset[metric], errors="coerce")
            rho = rank_correlation(subset["severity"], values)
            endpoint = float(values.iloc[-1] - values.iloc[0])
            minimum = float(endpoint_minimum[metric])
            checks.append({
                "instrument": metric,
                "target_perturbation": kind,
                "spearman_rho": rho,
                "endpoint_effect": endpoint,
                "minimum_endpoint_effect": minimum,
                "threshold": CFG["instrument_monotonicity_min"],
                "fixture_seeds": fixture_seeds,
                "passed": bool(
                    np.isfinite(rho)
                    and rho >= CFG["instrument_monotonicity_min"]
                    and endpoint > minimum
                ),
            })

    # Same-distribution C2ST must remain close to chance. This is a separate
    # negative control from monotone sensitivity to deliberate damage.
    null_rows = table[
        (table["severity"] == 0.0)
        & table["perturbation"].isin(["marginal", "coupling"])
    ]
    # Raw orientation-corrected AUC is biased upward because max(AUC, 1-AUC)
    # and max(RF, linear) are selected. Qualify the null by excess over its own
    # conditional-randomisation reference instead of an arbitrary raw-AUC cutoff.
    null_excess = pd.to_numeric(
        null_rows["c2st_excess_over_null_p95"], errors="coerce"
    )
    null_excess_mean = float(null_excess.mean())
    null_raw_auc = float(
        pd.to_numeric(null_rows["c2st_max_auc"], errors="coerce").mean()
    )
    checks.append({
        "instrument": "c2st_same_distribution_negative_control",
        "target_perturbation": "none",
        "spearman_rho": np.nan,
        "endpoint_effect": null_excess_mean,
        "raw_auc_diagnostic": null_raw_auc,
        "minimum_endpoint_effect": np.nan,
        "threshold": CFG["instrument_null_excess_max"],
        "fixture_seeds": fixture_seeds,
        "passed": bool(
            np.isfinite(null_excess_mean)
            and null_excess_mean <= CFG["instrument_null_excess_max"]
        ),
    })

    checks_df = pd.DataFrame(checks)
    table.to_csv(DIRS["tables"] / "table_controlled_instrument_ladder_seed_level.csv", index=False)
    aggregate.to_csv(DIRS["tables"] / "table_controlled_instrument_ladder.csv", index=False)
    checks_df.to_csv(DIRS["tables"] / "table_controlled_instrument_qualification.csv", index=False)
    write_json(DIRS["manifests"] / "controlled_fixture_contract.json", {
        "fixture_seeds": fixture_seeds,
        "rows_per_fixture": n,
        "severities": severities,
        "target_metrics": target_metrics,
        "endpoint_minimum": endpoint_minimum,
        "qualification_threshold": CFG["instrument_monotonicity_min"],
        "c2st_null_auc_max_legacy_diagnostic": CFG["instrument_null_auc_max"],
        "c2st_null_excess_max": CFG["instrument_null_excess_max"],
        "c2st_contract": instrument_c2st_contract,
        "c2st_grouping_contract": (
            "real and synthetic observations sharing a temporal block use the "
            "same group ID; labels are randomised within blocks"
        ),
    })

    fig, ax = plt.subplots(figsize=(8.4, 5.0))
    for kind, metrics in target_metrics.items():
        metric = metrics[0]
        subset = aggregate[aggregate["perturbation"] == kind].sort_values("severity")
        values = subset[metric].to_numpy(dtype=float)
        scale = max(np.nanmax(values), 1e-12)
        ax.plot(subset["severity"], values / scale, marker="o", label=f"{kind}: {metric}")
    ax.set_xlabel("Controlled perturbation severity")
    ax.set_ylabel("Target metric (normalised to its endpoint)")
    ax.set_title("Repeated controlled qualification of evaluation instruments")
    ax.set_ylim(bottom=-0.02)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(DIRS["figures"] / "figure_controlled_instrument_qualification.pdf", bbox_inches="tight")
    fig.savefig(DIRS["figures"] / "figure_controlled_instrument_qualification.png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    return table, checks_df

def column_prefix(column: str) -> str:
    return column.split("__", 1)[0].lower() if "__" in column else ""

def infer_tier(column: str) -> str:
    prefix = column_prefix(column)
    if not prefix:
        return "other"
    if prefix in TIER_ALIASES:
        return TIER_ALIASES[prefix]
    for alias in sorted(TIER_ALIASES, key=len, reverse=True):
        suffix = prefix[len(alias):] if prefix.startswith(alias) else ""
        if suffix and suffix.isdigit():
            return TIER_ALIASES[alias]
    return "other"

def family_key(column: str) -> str:
    """Canonical tier plus first semantic feature token.

    Band/device aliases such as ota24 and ota5 must not create artificial task
    families or inflate breadth counts.
    """
    tier = infer_tier(column)
    rest = column.split("__", 1)[1] if "__" in column else column
    root = rest.split("__", 1)[0]
    return f"{tier}__{root}"

def signal_class(column: str) -> str:
    """Semantic signal class used for capability breadth and balanced estimands."""
    value = column.lower()
    if column.endswith("__nonfinite_mask"):
        return "observability"
    if any(token in value for token in ("byte", "octet", "payload_len", "frame_len")):
        return "byte_volume"
    if any(token in value for token in (
        "mgmt", "management", "assoc", "deauth", "disassoc", "probe",
        "auth", "beacon", "channel", "permit_join", "route_request",
    )):
        return "management_control"
    if any(token in value for token in (
        "state", "event", "onoff", "open", "close", "motion", "occupancy",
        "switch", "contact", "presence", "alarm",
    )):
        return "state_event"
    if any(token in value for token in (
        "reset", "retrans", "retry", "lost", "drop", "error", "failure",
        "unreachable", "timeout", "duplicate_ack",
    )):
        return "reliability"
    if any(token in value for token in ("rssi", "lqi", "snr", "noise", "signal_strength")):
        return "radio_quality"
    if any(token in value for token in (
        "temperature", "humidity", "power", "voltage", "current", "energy",
        "pressure", "co2", "light", "illuminance",
    )):
        return "physical_context"
    if any(token in value for token in (
        "packet", "frame", "segment", "datagram", "count", "request", "response",
        "syn", "ack", "icmp", "dns", "tcp", "udp", "quic",
    )):
        return "packet_count"
    return "protocol_other"

def contiguous_indices(start: int, stop: int) -> np.ndarray:
    return np.arange(max(0, int(start)), max(0, int(stop)), dtype=np.int64)

def split_signature(split: dict[str, Any]) -> dict[str, Any]:
    signature: dict[str, Any] = {
        "fold_id": split["fold_id"],
        "embargo_steps": CFG["embargo_steps"],
    }
    for name in ("train", "val", "test", "inner_fit", "inner_calib"):
        values = np.asarray(split.get(name, []), dtype=np.int64)
        signature[f"{name}_start"] = int(values[0]) if len(values) else None
        signature[f"{name}_end"] = int(values[-1]) + 1 if len(values) else None
        signature[f"{name}_n"] = int(len(values))
        signature[f"{name}_hash"] = stable_hash(values.tolist())
    return signature

@dataclass(frozen=True)
class TaskCard:
    task_id: str
    task_type: str  # regression | classification
    suite: str  # temporal | contemporaneous
    target: str
    horizon: int
    lags: tuple[int, ...]
    predictors: tuple[str, ...]
    threshold: float | None
    tier: str
    family: str  # semantic task family, not target lineage
    capability: str  # reviewer-facing capability bucket
    signal_class: str
    target_family: str  # lineage guard
    driver_tier: str = ""
    label_window_steps: int = 0
    threshold_kind: str = ""

    def key(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "suite": self.suite,
            "target": self.target,
            "horizon": self.horizon,
            "lags": list(self.lags),
            "predictors": list(self.predictors),
            "threshold": self.threshold,
            "tier": self.tier,
            "family": self.family,
            "capability": self.capability,
            "signal_class": self.signal_class,
            "target_family": self.target_family,
            "driver_tier": self.driver_tier,
            "label_window_steps": self.label_window_steps,
            "threshold_kind": self.threshold_kind,
        }

@dataclass(frozen=True)
class TaskModelCard:
    task: TaskCard
    model_id: str  # rf | linear

    @property
    def card_id(self) -> str:
        return f"{self.task.task_id}__model_{self.model_id}"

    def key(self) -> dict[str, Any]:
        return {"task": self.task.key(), "model_id": self.model_id}

def task_family_key(kind: str, tier: str, signal: str, driver_tier: str = "") -> str:
    if driver_tier:
        return f"{kind}|{driver_tier}_to_{tier}|{signal}"
    return f"{kind}|{tier}|{signal}"

def capability_key(kind: str, signal: str) -> str:
    """Reviewer-facing capability bucket; collapses tier clones deliberately."""
    if kind in {"forecast", "burst"} and signal == "byte_volume":
        return f"{kind}|byte_volume"
    if kind in {"cross_tier_response", "cross_tier_forecast"}:
        return f"cross_tier_response|{signal}"
    if kind in {"event_onset", "state_transition"}:
        return f"device_event_state|{signal}"
    if kind == "contemporaneous_dependency":
        return f"contemporaneous_dependency|{signal}"
    return f"{kind}|{signal}"

def _forward_window_indicator(indicator: np.ndarray, window: int) -> np.ndarray:
    """Whether a binary event occurs strictly after t and within the horizon."""
    indicator = np.asarray(indicator, dtype=np.int8)
    reversed_max = (
        pd.Series(indicator[::-1])
        .rolling(window=max(1, int(window)), min_periods=1)
        .max()
        .to_numpy()[::-1]
    )
    output = np.zeros(len(indicator), dtype=np.int8)
    if len(indicator) > 1:
        output[:-1] = reversed_max[1:]
    return output

def _forward_window_any(values: np.ndarray, threshold: float, window: int) -> np.ndarray:
    """Future threshold exceedance in (t, t+window]."""
    active = (np.asarray(values, dtype=float) > float(threshold)).astype(np.int8)
    return _forward_window_indicator(active, window)

def _forward_window_onset(
    values: np.ndarray,
    threshold: float,
    window: int,
    any_transition: bool = False,
) -> np.ndarray:
    """Future onset/transition, not future occupancy or persistent activity."""
    active = (np.asarray(values, dtype=float) > float(threshold)).astype(np.int8)
    previous = np.r_[active[0], active[:-1]]
    event = (active != previous) if any_transition else ((active == 1) & (previous == 0))
    return _forward_window_indicator(event.astype(np.int8), window)

def build_task_frame(
    frame: pd.DataFrame,
    task: TaskCard,
    indices: np.ndarray,
    max_rows: int | None,
    bound: int | None = None,
) -> tuple[pd.DataFrame, pd.Series]:
    """Build a task frame without crossing either edge of the supplied segment."""
    predictors = [column for column in task.predictors if column in frame.columns]
    if task.target not in frame.columns or not predictors:
        return pd.DataFrame(), pd.Series(dtype=float)
    raw_indices = np.asarray(indices, dtype=np.int64)
    if not len(raw_indices):
        return pd.DataFrame(), pd.Series(dtype=float)
    segment_start = int(raw_indices.min())
    segment_stop = int(raw_indices.max()) + 1
    if bound is not None:
        segment_stop = min(segment_stop, int(bound))
    maximum_lag = max(task.lags, default=0)
    target_span = int(task.label_window_steps or task.horizon)
    valid = raw_indices[
        (raw_indices - maximum_lag >= segment_start)
        & (raw_indices + target_span < segment_stop)
    ]
    if max_rows and len(valid) > max_rows:
        valid = valid[deterministic_subsample_indices(len(valid), max_rows)]
    if not len(valid):
        return pd.DataFrame(), pd.Series(dtype=float)
    arrays = {column: frame[column].to_numpy() for column in predictors}
    features = {
        f"{column}__lag{lag}": arrays[column][valid - lag]
        for lag in task.lags
        for column in predictors
    }
    X = pd.DataFrame(features).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    target_values = frame[task.target].to_numpy()
    if task.task_type == "classification" and task.label_window_steps > 0:
        threshold = float(task.threshold if task.threshold is not None else 0.0)
        if task.task_id.startswith("state_transition__"):
            labels = _forward_window_onset(
                target_values, threshold, int(task.label_window_steps), any_transition=True
            )
        elif task.task_id.startswith("event_onset__") or task.threshold_kind == "binary_onset":
            labels = _forward_window_onset(
                target_values, threshold, int(task.label_window_steps), any_transition=False
            )
        else:
            labels = _forward_window_any(
                target_values, threshold, int(task.label_window_steps)
            )
        y = labels[valid]
    else:
        y = target_values[valid + task.horizon]
        if task.task_type == "classification":
            y = (y > float(task.threshold)).astype(np.int8)
    return X, pd.Series(y)

def train_threshold(target: str, quantile: float, binary_aware: bool = True) -> float:
    values = CANON_DF.iloc[PRIMARY_SPLIT["train"]][target].to_numpy(dtype=float)
    unique = np.unique(values[: min(len(values), 100000)])
    if binary_aware and set(unique.tolist()).issubset({0.0, 1.0}):
        return 0.5
    return float(np.quantile(values, quantile))

def model_for(task_type: str, model_id: str, seed: int):
    if task_type == "regression" and model_id == "rf":
        return RandomForestRegressor(
            n_estimators=CFG["rf_trees"],
            max_depth=CFG["rf_max_depth"],
            min_samples_leaf=2,
            n_jobs=CFG["n_jobs"],
            random_state=seed,
        )
    if task_type == "classification" and model_id == "rf":
        return RandomForestClassifier(
            n_estimators=CFG["rf_trees"],
            max_depth=CFG["rf_max_depth"],
            min_samples_leaf=2,
            n_jobs=CFG["n_jobs"],
            random_state=seed,
            # Probabilities are evaluated with the proper Brier score. Class
            # weighting changes the fitted class prior and can manufacture poor
            # calibration even when ranking is useful, so the publication
            # contract uses unweighted probability models and reports AP/AUC
            # separately for rare-event discrimination.
            class_weight=None,
        )
    if task_type == "regression" and model_id == "linear":
        return make_pipeline(
            StandardScaler(),
            Ridge(alpha=1.0, solver="lsqr", tol=1e-6, max_iter=10000),
        )
    if task_type == "classification" and model_id == "linear":
        return make_pipeline(
            StandardScaler(),
            LogisticRegression(
                max_iter=600,
                class_weight=None,
                random_state=seed,
                solver="lbfgs",
            ),
        )
    raise ValueError((task_type, model_id))

def fit_predict(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    task_type: str,
    model_id: str,
    seed: int,
) -> np.ndarray:
    model = model_for(task_type, model_id, seed)
    model.fit(X_train, y_train)
    if task_type == "classification":
        return model.predict_proba(X_test)[:, 1]
    return np.asarray(model.predict(X_test), dtype=float)

def calibration_error(y_true: np.ndarray, prediction: np.ndarray, bins: int = 10) -> float:
    y_true = np.asarray(y_true, dtype=float)
    prediction = np.clip(np.asarray(prediction, dtype=float), 0, 1)
    edges = np.linspace(0, 1, bins + 1)
    values: list[float] = []
    weights: list[float] = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (prediction >= lo) & (prediction < hi if hi < 1 else prediction <= hi)
        if mask.any():
            values.append(abs(float(y_true[mask].mean()) - float(prediction[mask].mean())))
            weights.append(float(mask.mean()))
    return float(np.average(values, weights=weights)) if values else np.nan

def task_loss_and_diagnostics(
    y_train: pd.Series,
    y_test: pd.Series,
    prediction: np.ndarray,
    task_type: str,
) -> dict[str, float]:
    ytr = y_train.to_numpy(dtype=float)
    yte = y_test.to_numpy(dtype=float)
    if task_type == "classification":
        prevalence = float(np.mean(ytr))
        naive = np.full(len(yte), prevalence, dtype=float)
        loss = float(brier_score_loss(yte, prediction))
        naive_loss = float(brier_score_loss(yte, naive))
        result = {
            "loss": loss,
            "naive_loss": naive_loss,
            "roc_auc": float(roc_auc_score(yte, prediction)) if len(np.unique(yte)) == 2 else np.nan,
            "average_precision": float(average_precision_score(yte, prediction)) if len(np.unique(yte)) == 2 else np.nan,
            "balanced_accuracy": float(balanced_accuracy_score(yte, (prediction >= 0.5).astype(int))) if len(np.unique(yte)) == 2 else np.nan,
            "calibration_error": calibration_error(yte, prediction),
            "brier_skill_score": float(1 - loss / max(naive_loss, 1e-12)),
            "prevalence_train": prevalence,
            "prevalence_test": float(np.mean(yte)),
        }
    else:
        scale = max(robust_iqr(yte), 1e-6)
        median = float(np.median(ytr))
        naive = np.full(len(yte), median, dtype=float)
        result = {
            "loss": float(mean_absolute_error(yte, prediction) / scale),
            "naive_loss": float(mean_absolute_error(yte, naive) / scale),
            "r2": float(r2_score(yte, prediction)),
            "target_iqr_test": scale,
        }
    result["skill_gain"] = float(
        (result["naive_loss"] - result["loss"]) / max(result["naive_loss"], 1e-12)
    )
    return result

@cached("task_admissibility_v7_14_5")
def assess_task_model(card: TaskModelCard, seed: int) -> dict[str, Any]:
    task = card.task
    X_train, y_train = build_task_frame(
        CANON_DF, task, PRIMARY_SPLIT["train"], CFG["row_cap_task_train"]
    )
    X_val, y_val = build_task_frame(
        CANON_DF, task, PRIMARY_SPLIT["val"], CFG["row_cap_task_test"]
    )
    base = {
        "card_id": card.card_id,
        "task_id": task.task_id,
        "model_id": card.model_id,
        "task_type": task.task_type,
        "suite": task.suite,
        "target": task.target,
        "tier": task.tier,
        "family": task.family,
        "capability": task.capability,
        "signal_class": task.signal_class,
        "target_family": task.target_family,
        "driver_tier": task.driver_tier,
        "label_window_steps": task.label_window_steps,
        "threshold_kind": task.threshold_kind,
        "n_train": len(X_train),
        "n_val": len(X_val),
    }
    if len(X_train) < 300 or len(X_val) < 300:
        return {**base, "admissible": False, "reason": "too_few_rows"}
    if task.task_type == "classification":
        if len(np.unique(y_train)) < 2 or len(np.unique(y_val)) < 2:
            return {**base, "admissible": False, "reason": "single_class"}
        prevalence = float(np.mean(y_val))
        if not (CFG["min_task_prevalence"] <= prevalence <= CFG["max_task_prevalence"]):
            return {**base, "admissible": False, "reason": f"prevalence={prevalence:.6f}"}
    prediction = fit_predict(X_train, y_train, X_val, task.task_type, card.model_id, seed)
    diagnostics = task_loss_and_diagnostics(y_train, y_val, prediction, task.task_type)
    admissible = diagnostics["skill_gain"] >= CFG["min_reference_skill_gain"]
    if task.task_type == "classification":
        ap_gain = float(diagnostics["average_precision"] - diagnostics["prevalence_test"])
        diagnostics["average_precision_gain"] = ap_gain
        admissible = bool(
            admissible
            and diagnostics["roc_auc"] >= CFG["min_reference_auc"]
            and ap_gain >= CFG["min_reference_ap_gain"]
        )
    return {
        **base,
        **diagnostics,
        "admissible": bool(admissible),
        "reason": "" if admissible else "reference_did_not_clear_pre_registered_skill_gate",
    }

@dataclass(frozen=True)
class GeneratorSpec:
    generator_id: str
    family: str
    cost_kind: str
    order_preserving: bool
    release_eligible: bool
    required_for_core: bool
    params: dict[str, Any] = field(default_factory=dict)

    def key(self) -> dict[str, Any]:
        return asdict(self)

def sample_rows(frame: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    indices = rng.choice(len(frame), n, replace=True)
    return frame.iloc[indices].reset_index(drop=True)

def block_length_for_output(n: int, multiplier: float = 1.0) -> int:
    floor = max(4 * CFG["max_window_span"], 120)
    target = max(floor, n // 30)
    return int(np.clip(round(target * multiplier), floor, max(floor, n // 4)))

def real_resample_generator(train: pd.DataFrame, n: int, seed: int, columns: Sequence[str], params: dict[str, Any]) -> pd.DataFrame:
    return sample_rows(train[list(columns)], n, seed)

def real_block_generator(train: pd.DataFrame, n: int, seed: int, columns: Sequence[str], params: dict[str, Any]) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    block_length = int(params.get("block_length", block_length_for_output(n)))
    starts = rng.integers(0, max(1, len(train) - block_length + 1), size=math.ceil(n / block_length))
    indices = np.concatenate([np.arange(start, start + block_length) for start in starts])[:n]
    indices = np.clip(indices, 0, len(train) - 1)
    return train.iloc[indices][list(columns)].reset_index(drop=True)

def independent_marginal_generator(train: pd.DataFrame, n: int, seed: int, columns: Sequence[str], params: dict[str, Any]) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        column: rng.choice(train[column].to_numpy(), n, replace=True)
        for column in columns
    })

def column_shuffle_generator(train: pd.DataFrame, n: int, seed: int, columns: Sequence[str], params: dict[str, Any]) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    base = sample_rows(train[list(columns)], n, seed)
    return pd.DataFrame({column: rng.permutation(base[column].to_numpy()) for column in columns})

def infer_column_support(values: np.ndarray) -> dict[str, Any]:
    values = np.asarray(values, dtype=float)
    finite = values[np.isfinite(values)]
    if not len(finite):
        return {
            "binary": False, "integer_like": False, "nonnegative": False,
            "minimum": 0.0, "maximum": 0.0, "zero_rate": 1.0,
        }
    unique = np.unique(finite[: min(len(finite), 100000)])
    nonzero = finite[np.abs(finite) > 1e-12]
    # Sparse continuous sensors must not be declared integer-like merely because
    # more than 99.5% of their observations are zero. Type the active support.
    integer_reference = nonzero if len(nonzero) else finite
    return {
        "binary": bool(set(unique.tolist()).issubset({0.0, 1.0}) and len(unique) <= 2),
        "integer_like": bool(
            len(integer_reference)
            and np.mean(np.isclose(integer_reference, np.round(integer_reference), atol=1e-6)) >= 0.995
        ),
        "nonnegative": bool(np.min(finite) >= 0),
        "minimum": float(np.min(finite)),
        "maximum": float(np.max(finite)),
        "zero_rate": float(np.mean(finite == 0)),
    }

def project_to_empirical_train_support(
    generated: np.ndarray,
    train_values: np.ndarray,
    discrete_support_limit: int = 32,
) -> np.ndarray:
    """Project output to the empirical TRAIN support in the storage dtype.

    The scientific support contract is defined in ``float32`` because generated
    frames are stored and evaluated in that dtype. Using float64 TRAIN extrema
    after casting valid projected values to float32 can create false boundary
    violations. Binary restoration is allowed only when the float32 empirical
    support is a subset of {0, 1}. Low-cardinality non-binary variables are
    mapped to their exact observed float32 support.
    """
    generated32 = np.asarray(generated, dtype=np.float32)
    train32 = np.asarray(train_values, dtype=np.float32)
    finite_train = train32[np.isfinite(train32)]

    if not len(finite_train):
        return np.zeros_like(generated32, dtype=np.float32)

    support_info = infer_column_support(finite_train)
    unique32 = np.unique(finite_train).astype(np.float32, copy=False)
    minimum32 = np.float32(np.min(finite_train))
    maximum32 = np.float32(np.max(finite_train))

    values = np.nan_to_num(
        generated32,
        nan=np.float32(0.0),
        posinf=maximum32,
        neginf=minimum32,
    ).astype(np.float32, copy=False)

    if support_info["binary"]:
        values = (values >= np.float32(0.5)).astype(np.float32)
    elif len(unique32) <= int(discrete_support_limit):
        # Exact projection onto observed float32 TRAIN support.
        distances = np.abs(
            values.astype(np.float64)[:, None]
            - unique32.astype(np.float64)[None, :]
        )
        values = unique32[np.argmin(distances, axis=1)]
    else:
        values = np.clip(values, minimum32, maximum32).astype(np.float32)
        if support_info["integer_like"]:
            values = np.rint(values).astype(np.float32)
            values = np.clip(values, minimum32, maximum32).astype(np.float32)

    if support_info["nonnegative"]:
        values = np.maximum(values, np.float32(0.0)).astype(np.float32)

    # Final storage-dtype projection is deliberate and idempotent.
    return np.clip(values, minimum32, maximum32).astype(np.float32, copy=False)

def project_frame_to_train_support(
    frame: pd.DataFrame,
    train: pd.DataFrame,
    columns: Sequence[str],
) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        result.loc[:, column] = project_to_empirical_train_support(
            result[column].to_numpy(dtype=float),
            train[column].to_numpy(dtype=float),
        )
    return result

def generator_output_health(spec: GeneratorSpec, train: pd.DataFrame, synthetic: pd.DataFrame) -> dict[str, Any]:
    columns = list(FEATURE_SCOPES["generator_v2"])
    values = synthetic[columns].to_numpy(dtype=np.float32)
    finite = bool(np.isfinite(values).all())
    feature_rows: list[dict[str, Any]] = []
    for column in columns:
        # Validate support in the same dtype used for storage and metric input.
        real = train[column].to_numpy(dtype=np.float32)
        syn = synthetic[column].to_numpy(dtype=np.float32)
        real_std = float(np.std(real, dtype=np.float64))
        syn_std = float(np.std(syn, dtype=np.float64))
        lo32 = np.float32(np.min(real))
        hi32 = np.float32(np.max(real))
        scale = max(1.0, abs(float(lo32)), abs(float(hi32)))
        support_tolerance = float(
            8.0 * np.finfo(np.float32).eps * scale
        )
        unsupported = float(np.mean(
            (syn < np.float32(float(lo32) - support_tolerance))
            | (syn > np.float32(float(hi32) + support_tolerance))
            | ~np.isfinite(syn)
        ))
        zero_error = abs(float(np.mean(real == 0)) - float(np.mean(syn == 0)))
        real_variable = bool(real_std > 1e-8)
        syn_variable = bool(syn_std > 1e-8)
        feature_rows.append({
            "column": column,
            "tier": infer_tier(column),
            "signal_class": signal_class(column),
            "modeled": bool(column in LEARNED_MODEL_COLS),
            "real_std": real_std,
            "synthetic_std": syn_std,
            "real_variable": real_variable,
            "synthetic_variable": syn_variable,
            "variance_ratio": syn_std / real_std if real_std > 1e-12 else np.nan,
            "real_zero_rate": float(np.mean(real == 0)),
            "synthetic_zero_rate": float(np.mean(syn == 0)),
            "zero_rate_abs_error": zero_error,
            "support_dtype": "float32",
            "support_minimum": float(lo32),
            "support_maximum": float(hi32),
            "support_tolerance": support_tolerance,
            "unsupported_fraction": unsupported,
        })
    feature_health = pd.DataFrame(feature_rows)
    real_variable = feature_health[feature_health["real_variable"]]
    modeled_variable = feature_health[
        feature_health["modeled"] & feature_health["real_variable"]
    ]
    variable_fraction = float(
        real_variable["synthetic_variable"].mean()
    ) if len(real_variable) else 1.0
    modeled_variable_fraction = float(
        modeled_variable["synthetic_variable"].mean()
    ) if len(modeled_variable) else 1.0
    unsupported_value_fraction = float(
        feature_health["unsupported_fraction"].mean()
    )
    modeled_zero_errors = feature_health.loc[
        feature_health["modeled"], "zero_rate_abs_error"
    ].to_numpy(dtype=float)
    learned_zero_rate_mae = float(np.mean(modeled_zero_errors)) if len(modeled_zero_errors) else np.nan
    learned_zero_rate_p95 = float(np.quantile(modeled_zero_errors, 0.95)) if len(modeled_zero_errors) else np.nan
    learned_zero_rate_max = float(np.max(modeled_zero_errors)) if len(modeled_zero_errors) else np.nan
    health = {
        "finite": finite,
        "variable_feature_fraction_among_real_variable": variable_fraction,
        "modeled_variable_feature_fraction": modeled_variable_fraction,
        "unsupported_value_fraction": unsupported_value_fraction,
        "learned_scope_zero_rate_mae": learned_zero_rate_mae,
        "learned_scope_zero_rate_p95": learned_zero_rate_p95,
        "learned_scope_zero_rate_max": learned_zero_rate_max,
        "feature_health": feature_health.to_dict("records"),
        "model_health": synthetic.attrs.get("health", {}),
    }
    if spec.family.startswith("learned"):
        failed = []
        if not finite:
            failed.append("nonfinite_output")
        if modeled_variable_fraction < CFG["learned_min_modeled_variable_fraction"]:
            failed.append("modeled_variation_collapse")
        if unsupported_value_fraction > 1e-4:
            failed.append("empirical_support_violation")
        if np.isfinite(learned_zero_rate_mae) and learned_zero_rate_mae > CFG["learned_max_zero_rate_mae"]:
            failed.append("mean_activity_rate_error")
        if np.isfinite(learned_zero_rate_p95) and learned_zero_rate_p95 > CFG["learned_zero_rate_p95_max"]:
            failed.append("p95_activity_rate_error")
        if np.isfinite(learned_zero_rate_max) and learned_zero_rate_max > CFG["learned_zero_rate_feature_max"]:
            failed.append("maximum_activity_rate_error")
        if failed:
            health["failed_predicates"] = failed
            raise ScientificInvalidFit(
                "Learned generator failed feature-level support/output-health checks: "
                + ", ".join(failed),
                diagnostics=health,
            )
    return health

@cached("trtr_reference_v7_14_5")
def _reference_task_result(card: TaskModelCard, split_sig: dict[str, Any], seed: int) -> dict[str, Any]:
    train_indices = np.asarray(split_sig["train_indices"], dtype=np.int64)
    test_indices = np.asarray(split_sig["test_indices"], dtype=np.int64)
    train_bound = int(train_indices[-1]) + 1
    test_bound = int(test_indices[-1]) + 1
    X_train, y_train = build_task_frame(
        CANON_DF,
        card.task,
        train_indices,
        CFG["row_cap_task_train"],
        train_bound,
    )
    X_test, y_test = build_task_frame(
        CANON_DF,
        card.task,
        test_indices,
        CFG["row_cap_task_test"],
        test_bound,
    )
    if len(X_train) < 300 or len(X_test) < 300:
        return {"status": "too_few_rows"}
    if card.task.task_type == "classification" and (
        len(np.unique(y_train)) < 2 or len(np.unique(y_test)) < 2
    ):
        return {"status": "single_class"}
    prediction = fit_predict(X_train, y_train, X_test, card.task.task_type, card.model_id, seed)
    diagnostics = task_loss_and_diagnostics(y_train, y_test, prediction, card.task.task_type)
    return {
        "status": "ok",
        **diagnostics,
        "n_train": len(X_train),
        "n_test": len(X_test),
    }

def reference_task_result(card: TaskModelCard, split: dict[str, Any], seed: int) -> dict[str, Any]:
    signature = {
        "fold_id": split["fold_id"],
        "train_indices": split["train"].tolist(),
        "test_indices": split["test"].tolist(),
    }
    return _reference_task_result(
        card,
        signature,
        seed,
        _key={
            "card": card.key(),
            "fold": split_signature(split),
            "seed": int(seed),
            "dataset": RUN_FINGERPRINT["dataset"],
            "scopes": RUN_FINGERPRINT["scopes"],
        },
    )

def evaluate_utility(
    synthetic_train: pd.DataFrame,
    spec: GeneratorSpec,
    split: dict[str, Any],
    seed: int,
    force_all_suites: bool = False,
    evaluation_axis: str = "future",
    reported_fold_id: str | None = None,
    task_models: Sequence[TaskModelCard] | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    test_bound = int(split["test"][-1]) + 1
    synthetic_indices = np.arange(len(synthetic_train), dtype=np.int64)
    cards = list(task_models) if task_models is not None else list(VALID_TASK_MODELS)
    for card in cards:
        task = card.task
        base = {
            "generator_id": spec.generator_id,
            "family": spec.family,
            "fold_id": str(reported_fold_id or split["fold_id"]),
            "reference_fold_id": str(split["fold_id"]),
            "evaluation_axis": str(evaluation_axis),
            "seed": int(seed),
            "card_id": card.card_id,
            "task_id": task.task_id,
            "model_id": card.model_id,
            "suite": task.suite,
            "task_type": task.task_type,
            "tier": task.tier,
            "task_family": task.family,
            "capability": task.capability,
            "target_family": task.target_family,
            "driver_tier": task.driver_tier,
            "signal_class": task.signal_class,
        }
        if task.suite == "temporal" and not spec.order_preserving and not force_all_suites:
            rows.append({**base, "status": "not_licensed_for_source_property"})
            continue
        try:
            X_train, y_train = build_task_frame(
                synthetic_train,
                task,
                synthetic_indices,
                CFG["row_cap_task_train"],
                len(synthetic_train),
            )
            X_test, y_test = build_task_frame(
                CANON_DF,
                task,
                split["test"],
                CFG["row_cap_task_test"],
                test_bound,
            )
            if len(X_train) < 300 or len(X_test) < 300:
                rows.append({**base, "status": "too_few_rows"})
                continue
            if task.task_type == "classification" and (
                len(np.unique(y_train)) < 2 or len(np.unique(y_test)) < 2
            ):
                rows.append({**base, "status": "single_class"})
                continue
            prediction = fit_predict(X_train, y_train, X_test, task.task_type, card.model_id, seed)
            synthetic_result = task_loss_and_diagnostics(y_train, y_test, prediction, task.task_type)
            reference = reference_task_result(card, split, seed)
            if reference.get("status") != "ok":
                rows.append({**base, "status": f"reference_{reference.get('status')}"})
                continue
            reference_loss = float(reference["loss"])
            synthetic_loss = float(synthetic_result["loss"])
            naive_loss = float(reference["naive_loss"])
            n_reference_train = int(reference.get("n_train", 0))
            sample_size_ratio = float(len(X_train) / max(1, n_reference_train))
            if not (0.95 <= sample_size_ratio <= 1.05):
                rows.append({
                    **base,
                    "status": "training_sample_mismatch",
                    "n_train": int(len(X_train)),
                    "n_reference_train": n_reference_train,
                    "training_sample_size_ratio": sample_size_ratio,
                })
                continue
            if not np.isfinite(reference_loss) or reference_loss < CFG["min_reference_loss"]:
                rows.append({
                    **base,
                    "status": "reference_loss_below_floor",
                    "reference_loss": reference_loss,
                    "minimum_reference_loss": CFG["min_reference_loss"],
                    "n_train": int(len(X_train)),
                    "n_reference_train": n_reference_train,
                })
                continue
            if not np.isfinite(naive_loss) or naive_loss <= 0:
                rows.append({**base, "status": "invalid_naive_loss", "naive_loss": naive_loss})
                continue
            if (
                task.task_type == "regression"
                and float(reference.get("target_iqr_test", np.nan)) < CFG["min_regression_target_iqr"]
            ):
                rows.append({
                    **base,
                    "status": "target_iqr_below_floor",
                    "target_iqr_test": float(reference.get("target_iqr_test", np.nan)),
                })
                continue

            loss_ratio = float(synthetic_loss / reference_loss)
            log_loss_ratio = float(math.log(loss_ratio)) if loss_ratio > 0 else np.nan
            relative_excess_loss_vs_naive = float((synthetic_loss - reference_loss) / naive_loss)
            reference_advantage = float(naive_loss - reference_loss)
            fraction_reference_advantage_lost = (
                float((synthetic_loss - reference_loss) / reference_advantage)
                if reference_advantage > 1e-12 else np.nan
            )
            rows.append({
                **base,
                "status": "ok",
                "synthetic_loss": synthetic_loss,
                "reference_loss": reference_loss,
                "naive_loss": naive_loss,
                "loss_ratio": loss_ratio,
                "log_loss_ratio": log_loss_ratio,
                "relative_excess_loss_vs_naive": relative_excess_loss_vs_naive,
                "fraction_reference_advantage_lost": fraction_reference_advantage_lost,
                "noninferior": bool(loss_ratio <= CFG["utility_noninferiority_ratio"]),
                "synthetic_skill_gain": float(synthetic_result["skill_gain"]),
                "reference_skill_gain": float(reference["skill_gain"]),
                "synthetic_roc_auc": synthetic_result.get("roc_auc", np.nan),
                "reference_roc_auc": reference.get("roc_auc", np.nan),
                "synthetic_r2": synthetic_result.get("r2", np.nan),
                "reference_r2": reference.get("r2", np.nan),
                "n_train": int(len(X_train)),
                "n_reference_train": n_reference_train,
                "training_sample_size_ratio": sample_size_ratio,
                "n_test": int(len(X_test)),
            })
        except Exception as exc:
            rows.append({
                **base,
                "status": f"error:{type(exc).__name__}",
                "error": str(exc),
            })
    return pd.DataFrame(rows)

def bootstrap_mean_ci(
    values: Sequence[float],
    seed: int = 991,
    draws: int = 10000,
) -> tuple[float, float, float]:
    values = np.asarray([value for value in values if np.isfinite(value)], dtype=float)
    if not len(values):
        return np.nan, np.nan, np.nan
    if len(values) == 1:
        return float(values[0]), float(values[0]), float(values[0])
    rng = np.random.default_rng(seed)
    samples = values[rng.integers(0, len(values), size=(draws, len(values)))].mean(axis=1)
    return float(values.mean()), float(np.quantile(samples, 0.025)), float(np.quantile(samples, 0.975))

def make_p0_blocks() -> list[np.ndarray]:
    train_indices = np.asarray(PRIMARY_SPLIT["train"], dtype=np.int64)
    requested_pairs = max(2, int(CFG["p0_pairs"]))
    minimum_width = max(600, 6 * CFG["max_window_span"])
    width = min(
        int(CFG["p0_block_rows"]),
        max(minimum_width, len(train_indices) // max(2 * requested_pairs, 2)),
    )
    maximum_blocks = len(train_indices) // max(1, width)
    count = min(int(CFG["p0_candidate_blocks"]), maximum_blocks)
    count = max(2 * requested_pairs, count) if maximum_blocks >= 2 * requested_pairs else maximum_blocks
    if count < 4:
        raise RuntimeError(
            f"PRIMARY TRAIN is too short for matched-block P0: width={width}, blocks={count}."
        )
    # Evenly spaced non-overlapping blocks use the entire TRAIN period without
    # privileging one contiguous regime.
    starts = np.linspace(0, len(train_indices) - width, num=count, dtype=int)
    blocks: list[np.ndarray] = []
    previous_stop = -1
    for start in starts:
        start = max(int(start), previous_stop)
        stop = min(len(train_indices), start + width)
        if stop - start < minimum_width:
            continue
        block = train_indices[start:stop]
        blocks.append(block)
        previous_stop = stop
    return blocks

def p0_block_profile(indices: np.ndarray) -> dict[str, float]:
    frame = CANON_DF.iloc[indices]
    profile: dict[str, float] = {}
    for tier in sorted(ACTIVE_TIERS):
        columns = [column for column in FEATURE_SCOPES["all_value_v3"] if infer_tier(column) == tier]
        if columns:
            values = frame[columns].to_numpy(dtype=np.float32)
            profile[f"tier_active__{tier}"] = float(np.mean(values != 0))
    for signal in sorted({signal_class(column) for column in P0_PROFILE_COLS}):
        columns = [column for column in P0_PROFILE_COLS if signal_class(column) == signal]
        if columns:
            values = frame[columns].to_numpy(dtype=np.float32)
            profile[f"signal_active__{signal}"] = float(np.mean(values != 0))
    for column in P0_PROFILE_COLS:
        values = frame[column].to_numpy(dtype=float)
        scale = max(robust_iqr(values), 1e-6)
        profile[f"mean__{column}"] = float(np.mean(values) / scale)
        profile[f"zero__{column}"] = float(np.mean(values == 0))
    seconds = time_sorted[indices]
    phase = (seconds % 86400.0) / 86400.0 * 2 * np.pi
    profile["tod_sin"] = float(np.mean(np.sin(phase)))
    profile["tod_cos"] = float(np.mean(np.cos(phase)))
    return profile

def match_p0_blocks(blocks: Sequence[np.ndarray]) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    profiles = [p0_block_profile(block) for block in blocks]
    columns = sorted(set().union(*(profile.keys() for profile in profiles)))
    matrix = np.asarray([[profile.get(column, 0.0) for column in columns] for profile in profiles], dtype=float)
    center = np.median(matrix, axis=0)
    scale = np.median(np.abs(matrix - center), axis=0) * 1.4826
    scale[scale < 1e-8] = 1.0
    z = (matrix - center) / scale
    midpoint = len(blocks) // 2
    left = list(range(midpoint))
    available_right = set(range(midpoint, len(blocks)))
    pairs: list[dict[str, Any]] = []
    for left_index in left:
        if not available_right:
            break
        right_index = min(
            available_right,
            key=lambda candidate: (float(np.linalg.norm(z[left_index] - z[candidate])), candidate),
        )
        available_right.remove(right_index)
        pairs.append({
            "pair_id": f"pair{len(pairs)}",
            "source_block": left_index,
            "target_block": right_index,
            "profile_distance": float(np.linalg.norm(z[left_index] - z[right_index])),
            "source_start": int(blocks[left_index][0]),
            "source_end": int(blocks[left_index][-1]) + 1,
            "target_start": int(blocks[right_index][0]),
            "target_end": int(blocks[right_index][-1]) + 1,
        })
        if len(pairs) >= int(CFG["p0_pairs"]):
            break
    if len(pairs) < 2:
        raise RuntimeError("Matched-block P0 produced fewer than two block pairs")
    calibration_count = max(1, int(round(len(pairs) * CFG["p0_calibration_fraction"])))
    calibration_count = min(calibration_count, len(pairs) - 1)
    pairs = sorted(pairs, key=lambda row: (row["profile_distance"], row["pair_id"]))
    # Balance profile distance across calibration and qualification. Assigning all
    # closest pairs to calibration would under-estimate natural real-to-real
    # variation and make the held-out qualification set systematically harder.
    calibration_indices = list(range(0, len(pairs), 2))[:calibration_count]
    if len(calibration_indices) < calibration_count:
        calibration_indices.extend(
            index for index in range(len(pairs))
            if index not in set(calibration_indices)
        )
        calibration_indices = calibration_indices[:calibration_count]
    calibration_indices = set(calibration_indices)
    for index, pair in enumerate(pairs):
        pair["phase"] = "calibration" if index in calibration_indices else "qualification"
    return pd.DataFrame(profiles), pairs

def p0_capability_summary(utility: pd.DataFrame) -> list[dict[str, Any]]:
    valid = utility[(utility["status"] == "ok") & utility["log_loss_ratio"].notna()].copy()
    if not len(valid):
        return []
    family = valid.groupby(
        ["p0_anchor", "suite", "capability", "task_family"], dropna=False
    ).agg(
        log_loss_ratio=("log_loss_ratio", "median"),
        noninferior=("noninferior", "mean"),
    ).reset_index()
    capability = family.groupby(
        ["p0_anchor", "suite", "capability"], dropna=False
    ).agg(
        log_loss_ratio=("log_loss_ratio", "mean"),
        noninferiority_rate=("noninferior", "mean"),
        n_families=("task_family", "nunique"),
    ).reset_index()
    return capability.to_dict("records")

def _summary_frame(
    phase: str,
    anchor: str,
    suite: str,
    capability: str,
    column: str,
) -> pd.DataFrame:
    subset = P0_SEED_SUMMARY[
        (P0_SEED_SUMMARY["phase"] == phase)
        & (P0_SEED_SUMMARY["p0_anchor"] == anchor)
        & (P0_SEED_SUMMARY["suite"] == suite)
        & (P0_SEED_SUMMARY["capability"] == capability)
    ][["pair_id", "seed", column]].copy()
    subset["value"] = pd.to_numeric(subset[column], errors="coerce")
    subset["seed"] = pd.to_numeric(subset["seed"], errors="coerce")
    return subset[["pair_id", "seed", "value"]].dropna()

def _anchor_pivot(
    phase: str,
    suite: str,
    capability: str,
    column: str,
) -> pd.DataFrame:
    subset = P0_SEED_SUMMARY[
        (P0_SEED_SUMMARY["phase"] == phase)
        & (P0_SEED_SUMMARY["suite"] == suite)
        & (P0_SEED_SUMMARY["capability"] == capability)
    ][["pair_id", "seed", "p0_anchor", column]].copy()
    subset[column] = pd.to_numeric(subset[column], errors="coerce")
    subset["seed"] = pd.to_numeric(subset["seed"], errors="coerce")
    subset = subset.dropna(subset=[column, "seed"])
    if subset.empty:
        return pd.DataFrame(columns=["pair_id", "seed"])
    return (
        subset.pivot_table(
            index=["pair_id", "seed"],
            columns="p0_anchor",
            values=column,
            aggfunc="mean",
        )
        .reset_index()
        .rename_axis(columns=None)
    )

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

def valid_metric_rows(frame: pd.DataFrame) -> pd.DataFrame:
    if not len(frame):
        return frame.copy()
    status = frame.get("scientific_status", pd.Series("valid", index=frame.index)).astype(str)
    return frame[status == "valid"].copy()

def valid_utility_rows(frame: pd.DataFrame) -> pd.DataFrame:
    if not len(frame):
        return frame.copy()
    scientific = frame.get("scientific_status", pd.Series("valid", index=frame.index)).astype(str)
    return frame[(scientific == "valid") & (frame["status"].astype(str) == "ok")].copy()

def utility_point_estimate(frame: pd.DataFrame) -> dict[str, float]:
    valid = valid_utility_rows(frame)
    valid = valid[valid["log_loss_ratio"].notna()].copy() if len(valid) else valid
    if not len(valid):
        return {
            "log_loss_ratio": np.nan,
            "noninferiority_rate": np.nan,
            "relative_excess_loss_vs_naive": np.nan,
        }
    family = valid.groupby(
        ["seed", "capability", "task_family"], dropna=False
    ).agg(
        log_loss_ratio=("log_loss_ratio", "median"),
        noninferiority=("noninferior", "mean"),
        relative_excess_loss_vs_naive=("relative_excess_loss_vs_naive", "median"),
    ).reset_index()
    capability = family.groupby(["seed", "capability"], dropna=False).agg(
        log_loss_ratio=("log_loss_ratio", "mean"),
        noninferiority_rate=("noninferiority", "mean"),
        relative_excess_loss_vs_naive=("relative_excess_loss_vs_naive", "mean"),
    ).reset_index()
    per_seed = capability.groupby("seed", dropna=False).agg(
        log_loss_ratio=("log_loss_ratio", "mean"),
        noninferiority_rate=("noninferiority_rate", "mean"),
        relative_excess_loss_vs_naive=("relative_excess_loss_vs_naive", "mean"),
    )
    return {
        "log_loss_ratio": float(per_seed["log_loss_ratio"].mean()),
        "noninferiority_rate": float(per_seed["noninferiority_rate"].mean()),
        "relative_excess_loss_vs_naive": float(per_seed["relative_excess_loss_vs_naive"].mean()),
    }

def hierarchical_utility_bootstrap(
    frame: pd.DataFrame,
    seed: int = 9191,
    draws: int | None = None,
) -> dict[str, Any]:
    """Hierarchical bootstrap: seed -> capability -> family -> task-model card."""
    if draws is None:
        draws = 300 if MODE == "smoke" else (1200 if MODE == "calibrate" else 5000)
    valid = valid_utility_rows(frame)
    valid = valid[valid["log_loss_ratio"].notna()].copy() if len(valid) else valid
    empty = {
        "geometric_mean_loss_ratio": np.nan,
        "loss_ratio_ci_lo": np.nan,
        "loss_ratio_ci_hi": np.nan,
        "noninferiority_rate": np.nan,
        "noninferiority_ci_lo": np.nan,
        "noninferiority_ci_hi": np.nan,
        "capability_mean_relative_excess_loss_vs_naive": np.nan,
        "relative_excess_ci_lo": np.nan,
        "relative_excess_ci_hi": np.nan,
        "n_rows": 0,
        "n_seeds": 0,
        "n_capabilities": 0,
        "n_families": 0,
        "n_tiers": 0,
        "n_models": 0,
        "bootstrap_draws": int(draws),
    }
    if not len(valid):
        return empty
    prepared: dict[int, list[list[tuple[np.ndarray, np.ndarray, np.ndarray]]]] = {}
    for seed_value, seed_rows in valid.groupby("seed", sort=True):
        capabilities: list[list[tuple[np.ndarray, np.ndarray, np.ndarray]]] = []
        for _, capability_rows in seed_rows.groupby("capability", sort=True):
            families: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
            for _, family_rows in capability_rows.groupby("task_family", sort=True):
                logs = family_rows["log_loss_ratio"].to_numpy(dtype=float)
                ni = family_rows["noninferior"].astype(float).to_numpy(dtype=float)
                excess = family_rows["relative_excess_loss_vs_naive"].to_numpy(dtype=float)
                finite = np.isfinite(logs) & np.isfinite(excess)
                if finite.any():
                    families.append((logs[finite], ni[finite], excess[finite]))
            if families:
                capabilities.append(families)
        if capabilities:
            prepared[int(seed_value)] = capabilities
    seed_values = np.asarray(sorted(prepared), dtype=int)
    if not len(seed_values):
        return empty
    rng = np.random.default_rng(seed)
    log_draws = np.empty(draws, dtype=float)
    ni_draws = np.empty(draws, dtype=float)
    excess_draws = np.empty(draws, dtype=float)
    for draw in range(draws):
        sampled_seeds = rng.choice(seed_values, len(seed_values), replace=True)
        seed_logs: list[float] = []
        seed_ni: list[float] = []
        seed_excess: list[float] = []
        for sampled_seed in sampled_seeds:
            capabilities = prepared[int(sampled_seed)]
            capability_indices = rng.integers(0, len(capabilities), len(capabilities))
            capability_logs: list[float] = []
            capability_ni: list[float] = []
            capability_excess: list[float] = []
            for capability_index in capability_indices:
                families = capabilities[int(capability_index)]
                family_indices = rng.integers(0, len(families), len(families))
                family_logs: list[float] = []
                family_ni: list[float] = []
                family_excess: list[float] = []
                for family_index in family_indices:
                    logs, nis, excesses = families[int(family_index)]
                    row_indices = rng.integers(0, len(logs), len(logs))
                    family_logs.append(float(np.median(logs[row_indices])))
                    family_ni.append(float(np.mean(nis[row_indices])))
                    family_excess.append(float(np.median(excesses[row_indices])))
                capability_logs.append(float(np.mean(family_logs)))
                capability_ni.append(float(np.mean(family_ni)))
                capability_excess.append(float(np.mean(family_excess)))
            seed_logs.append(float(np.mean(capability_logs)))
            seed_ni.append(float(np.mean(capability_ni)))
            seed_excess.append(float(np.mean(capability_excess)))
        log_draws[draw] = float(np.mean(seed_logs))
        ni_draws[draw] = float(np.mean(seed_ni))
        excess_draws[draw] = float(np.mean(seed_excess))
    point = utility_point_estimate(valid)
    result = dict(empty)
    result.update({
        "geometric_mean_loss_ratio": float(math.exp(point["log_loss_ratio"])),
        "loss_ratio_ci_lo": float(math.exp(np.quantile(log_draws, 0.025))),
        "loss_ratio_ci_hi": float(math.exp(np.quantile(log_draws, 0.975))),
        "median_log_loss_ratio": float(np.median(valid["log_loss_ratio"])),
        "noninferiority_rate": point["noninferiority_rate"],
        "noninferiority_ci_lo": float(np.quantile(ni_draws, 0.025)),
        "noninferiority_ci_hi": float(np.quantile(ni_draws, 0.975)),
        "capability_mean_relative_excess_loss_vs_naive": point["relative_excess_loss_vs_naive"],
        "relative_excess_ci_lo": float(np.quantile(excess_draws, 0.025)),
        "relative_excess_ci_hi": float(np.quantile(excess_draws, 0.975)),
        "n_rows": int(len(valid)),
        "n_seeds": int(len(seed_values)),
        "n_capabilities": int(valid["capability"].nunique()),
        "n_families": int(valid["task_family"].nunique()),
        "n_tiers": int(valid["tier"].nunique()),
        "n_models": int(valid["model_id"].nunique()),
        "maximum_task_loss_ratio": float(valid["loss_ratio"].max()),
        "training_sample_ratio_min": float(valid["training_sample_size_ratio"].min()),
        "training_sample_ratio_max": float(valid["training_sample_size_ratio"].max()),
    })
    return result

def paired_seed_ci(
    frame: pd.DataFrame,
    value_column: str,
    arm_a: str,
    arm_b: str,
    seed: int = 4242,
    draws: int = 10000,
) -> dict[str, Any]:
    valid = valid_metric_rows(frame)
    if value_column not in valid:
        return {
            "metric": value_column, "arm_a": arm_a, "arm_b": arm_b,
            "estimand": "mean paired primary-seed difference (A-B)",
            "delta": np.nan, "ci_lo": np.nan, "ci_hi": np.nan,
            "n": 0, "paired_seeds": [], "excludes_zero": False,
        }
    a = valid[valid["generator_id"] == arm_a].set_index("seed")[value_column]
    b = valid[valid["generator_id"] == arm_b].set_index("seed")[value_column]
    common = sorted(set(a.index) & set(b.index))
    values = a.loc[common].to_numpy(dtype=float) - b.loc[common].to_numpy(dtype=float)
    finite_mask = np.isfinite(values)
    finite_seeds = [int(seed_value) for seed_value, ok in zip(common, finite_mask) if ok]
    values = values[finite_mask]
    estimate, ci_lo, ci_hi = bootstrap_mean_ci(values, seed=seed, draws=draws)
    return {
        "metric": value_column,
        "arm_a": arm_a,
        "arm_b": arm_b,
        "estimand": "mean paired primary-seed difference (A-B)",
        "delta": estimate,
        "ci_lo": ci_lo,
        "ci_hi": ci_hi,
        "n": int(len(values)),
        "paired_seeds": finite_seeds,
        "excludes_zero": bool(
            np.isfinite(ci_lo) and np.isfinite(ci_hi) and (ci_lo > 0 or ci_hi < 0)
        ),
    }

def fidelity_permission(
    ci_lo: float,
    ci_hi: float,
    candidate_peak_auc: float,
    anchor_peak_auc: float,
) -> str:
    if not np.isfinite(ci_lo) or not np.isfinite(ci_hi):
        return "NOT_ESTIMABLE"
    if not np.isfinite(candidate_peak_auc) or not np.isfinite(anchor_peak_auc):
        return "NOT_ESTIMABLE"
    candidate_at_ceiling = bool(
        candidate_peak_auc >= CFG["degenerate_c2st_threshold"]
    )
    anchor_at_ceiling = bool(
        anchor_peak_auc >= CFG["degenerate_c2st_threshold"]
    )
    # A clearly positive lower bound remains valid evidence of inferiority
    # when the anchor itself is not saturated. Candidate saturation then
    # strengthens, rather than conceals, the directional negative result.
    if (
        not anchor_at_ceiling
        and ci_lo > CFG["c2st_excess_practical_margin"]
    ):
        return "LICENSED_INFERIOR"
    # Ceiling compression cannot support closeness/noninferiority. This is
    # axis- and scope-specific because each C2ST comparison has its own raw
    # candidate and real-resample anchor AUC.
    if candidate_at_ceiling or anchor_at_ceiling:
        return "NOT_ESTIMABLE"
    if ci_hi <= CFG["c2st_excess_practical_margin"]:
        return "LICENSED_NONINFERIOR"
    return "LICENSED_INCONCLUSIVE"

def utility_permission(ci_lo: float, ci_hi: float) -> str:
    if not np.isfinite(ci_lo) or not np.isfinite(ci_hi):
        return "NOT_ESTIMABLE"
    if ci_hi <= CFG["utility_noninferiority_ratio"]:
        return "LICENSED_NONINFERIOR"
    if ci_lo > CFG["utility_noninferiority_ratio"]:
        return "LICENSED_INFERIOR"
    return "LICENSED_INCONCLUSIVE"