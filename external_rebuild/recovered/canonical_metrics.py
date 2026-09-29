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
