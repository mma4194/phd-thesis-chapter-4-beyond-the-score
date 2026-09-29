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
    nonzero = finite[np.abs(finite) > 1e-12]
    # Sparse continuous sensors must not be declared integer-like merely because
    # more than 99.5% of their observations are zero. Type the active support.
    integer_reference = nonzero if len(nonzero) else finite
    return {
        "binary": bool(np.all((finite == 0.0) | (finite == 1.0))),
        "integer_like": bool(
            len(integer_reference)
            and np.mean(np.isclose(integer_reference, np.round(integer_reference), atol=1e-6)) >= 0.995
        ),
        "nonnegative": bool(np.min(finite) >= 0),
        "minimum": float(np.min(finite)),
        "maximum": float(np.max(finite)),
        "zero_rate": float(np.mean(finite == 0)),
    }

def empirical_hurdle_draw(values: np.ndarray, n: int, rng: np.random.Generator) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    support = infer_column_support(values)
    if support["binary"]:
        return (rng.random(n) >= support["zero_rate"]).astype(np.float32)
    nonzero = values[values != 0]
    active = rng.random(n) >= support["zero_rate"]
    output = np.zeros(n, dtype=np.float64)
    if len(nonzero) and active.any():
        sorted_values = np.sort(nonzero)
        positions = rng.random(int(active.sum())) * max(0, len(sorted_values) - 1)
        lower = np.floor(positions).astype(int)
        upper = np.ceil(positions).astype(int)
        weight = positions - lower
        drawn = sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight
        if support["integer_like"]:
            drawn = np.round(drawn)
        output[active] = drawn
    output = np.clip(output, support["minimum"], support["maximum"])
    if support["nonnegative"]:
        output = np.maximum(output, 0)
    return output.astype(np.float32)

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

def rank_restore_empirical_marginals(
    raw_output: np.ndarray,
    train_values: np.ndarray,
    seed: int,
) -> np.ndarray:
    """Map learned temporal ranks onto TRAIN-only empirical hurdle marginals.

    This support-aware calibration preserves the temporal ordering learned by a
    latent model while preventing unconstrained decoders from inventing negative
    counts, impossible binary values, or incorrect zero inflation. It operates
    feature-wise and therefore cannot reproduce complete training rows by design.
    """
    raw_output = np.asarray(raw_output, dtype=np.float64)
    train_values = np.asarray(train_values, dtype=np.float64)
    if raw_output.ndim != 2 or train_values.ndim != 2:
        raise ValueError("rank_restore_empirical_marginals expects two matrices")
    if raw_output.shape[1] != train_values.shape[1]:
        raise ValueError("Learned output and TRAIN matrices have different widths")
    rng = np.random.default_rng(seed)
    n, m = raw_output.shape
    restored = np.empty((n, m), dtype=np.float32)
    for column_index in range(m):
        draws = empirical_hurdle_draw(train_values[:, column_index], n, rng).astype(np.float64)
        values = np.nan_to_num(
            raw_output[:, column_index], nan=0.0, posinf=0.0, neginf=0.0
        )
        ranks = np.argsort(np.argsort(values, kind="stable"), kind="stable")
        restored[:, column_index] = np.sort(draws)[ranks].astype(np.float32)
    return restored

def _rank_stitch(
    sampled: np.ndarray,
    template_source: np.ndarray,
    seed: int,
    mode: str,
    block_length: int,
) -> np.ndarray:
    if mode == "none":
        return sampled
    rng = np.random.default_rng(seed)
    n, m = sampled.shape
    blocks = math.ceil(n / block_length)
    common_starts = rng.integers(0, max(1, len(template_source) - block_length + 1), size=blocks)
    independent_starts = rng.integers(
        0,
        max(1, len(template_source) - block_length + 1),
        size=(blocks, m),
    )
    output = np.empty_like(sampled)
    for block_index in range(blocks):
        lo = block_index * block_length
        hi = min(n, (block_index + 1) * block_length)
        width = hi - lo
        if width <= 1:
            output[lo:hi] = sampled[lo:hi]
            continue
        for column_index in range(m):
            if mode == "shared":
                start = int(common_starts[block_index])
            elif mode == "independent":
                start = int(independent_starts[block_index, column_index])
            else:
                raise ValueError(mode)
            template = template_source[start:start + width, column_index]
            if len(template) < width:
                template = np.resize(template, width)
            ranks = np.argsort(np.argsort(template, kind="stable"), kind="stable")
            output[lo:hi, column_index] = np.sort(sampled[lo:hi, column_index])[ranks]
    return output

def hurdle_rank_stitch_generator(
    train: pd.DataFrame,
    n: int,
    seed: int,
    columns: Sequence[str],
    params: dict[str, Any],
) -> pd.DataFrame:
    """Empirical hurdle values plus an explicit rank-trajectory mechanism.

    The three core modes form a measured mechanism ladder:
      none        -> marginals only;
      independent -> per-column temporal structure without cross-column alignment;
      shared      -> per-column temporal structure and shared cross-column alignment.

    This replaces the v6 Gaussian-copula label because instrumentation showed that
    the stitch, not the copula, supplied the observed dependence.
    """
    rng = np.random.default_rng(seed)
    columns = list(columns)
    train_values = train[columns].to_numpy(dtype=np.float32)
    sampled = np.column_stack([
        empirical_hurdle_draw(train_values[:, index], n, rng)
        for index in range(len(columns))
    ]).astype(np.float32, copy=False)
    mode = str(params.get("stitch_mode", "shared"))
    block_length = int(params.get("block_length", block_length_for_output(n, float(params.get("block_multiplier", 1.0)))))
    output = _rank_stitch(sampled, train_values, seed + 991, mode, block_length)
    return pd.DataFrame(output, columns=columns)

def signed_log1p(values: np.ndarray) -> np.ndarray:
    return np.sign(values) * np.log1p(np.abs(values))

def signed_expm1(values: np.ndarray) -> np.ndarray:
    return np.sign(values) * np.expm1(np.abs(values))

def _learned_fit_matrix(train: pd.DataFrame, columns: Sequence[str], fit_rows: int) -> np.ndarray:
    n = min(len(train), int(fit_rows))
    if n < 1000:
        raise ScientificInvalidFit("Learned comparator has fewer than 1000 fitting rows")
    indices = deterministic_subsample_indices(len(train), n)
    return train.iloc[indices][list(columns)].to_numpy(dtype=np.float64)

def _overlay_frame(base: pd.DataFrame, columns: Sequence[str], values: np.ndarray) -> pd.DataFrame:
    result = base.copy()
    result.loc[:, list(columns)] = np.asarray(values, dtype=np.float32)
    return result

def learned_gmm_overlay_generator(
    train: pd.DataFrame,
    n: int,
    seed: int,
    columns: Sequence[str],
    params: dict[str, Any],
) -> pd.DataFrame:
    """Row-exchangeable learned joint control with empirical support restoration.

    This comparator is deliberately not granted temporal-property eligibility. It
    learns a multivariate latent mixture over a TRAIN-frozen value scope and overlays
    it on hurdle marginals for the remaining fields.
    """
    rng = np.random.default_rng(seed)
    modeled_columns = [column for column in LEARNED_MODEL_COLS if column in train.columns]
    X_raw = _learned_fit_matrix(train, modeled_columns, params.get("fit_rows", CFG["learned_fit_rows"]))
    X_transformed = signed_log1p(X_raw)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_transformed)
    components = int(min(
        params.get("pca_components", CFG["learned_pca_components"]),
        X_scaled.shape[1], max(2, X_scaled.shape[0] - 2),
    ))
    pca = PCA(n_components=components, svd_solver="randomized", random_state=seed)
    latent = pca.fit_transform(X_scaled)
    gmm_components = int(min(params.get("gmm_components", CFG["learned_gmm_components"]), max(2, len(latent) // 500)))
    if gmm_components < 2:
        raise ScientificInvalidFit("GMM comparator has fewer than two viable mixture components")
    gmm = GaussianMixture(
        n_components=gmm_components,
        covariance_type="diag",
        reg_covar=1e-5,
        max_iter=250,
        n_init=2,
        random_state=seed,
    )
    gmm.fit(latent)
    if not bool(gmm.converged_):
        raise ScientificInvalidFit(
            "GMM comparator did not converge",
            diagnostics={"iterations": int(gmm.n_iter_)},
        )
    latent_sample, _ = gmm.sample(int(n))
    raw_sample = signed_expm1(scaler.inverse_transform(pca.inverse_transform(latent_sample)))
    restored = rank_restore_empirical_marginals(raw_sample, X_raw, seed + 911)
    base = hurdle_rank_stitch_generator(
        train, n, seed + 17, columns, {"stitch_mode": "none"}
    )
    frame = _overlay_frame(base, modeled_columns, restored)
    frame = project_frame_to_train_support(frame, train, columns)
    frame.attrs["health"] = {
        "model_kind": "support_aware_pca_gmm_overlay",
        "modeled_columns": modeled_columns,
        "n_modeled_columns": len(modeled_columns),
        "pca_components": components,
        "pca_explained_variance": float(np.sum(pca.explained_variance_ratio_)),
        "gmm_components": gmm_components,
        "gmm_converged": bool(gmm.converged_),
        "gmm_iterations": int(gmm.n_iter_),
        "order_preserving": False,
        "empirical_support_restoration": True,
    }
    return frame

def _latent_var_design(latent: np.ndarray, lags: Sequence[int]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    lags = tuple(sorted(set(int(lag) for lag in lags if int(lag) > 0)))
    max_lag = max(lags)
    times = np.arange(max_lag, len(latent), dtype=np.int64)
    X = np.concatenate([latent[times - lag] for lag in lags], axis=1)
    y = latent[times]
    return X, y, times

def learned_latent_var_overlay_generator(
    train: pd.DataFrame,
    n: int,
    seed: int,
    columns: Sequence[str],
    params: dict[str, Any],
) -> pd.DataFrame:
    """Order-preserving support-aware learned temporal comparator.

    A regularised multi-lag VAR is learned in a PCA latent space from genuinely
    adjacent TRAIN rows. The simulated latent trajectory is mapped onto TRAIN-only
    empirical hurdle marginals, then overlaid on the transparent shared-stitch base.
    This preserves valid support while ensuring the modeled columns' temporal ranks
    originate from the learned dynamical model rather than copied complete rows.
    """
    rng = np.random.default_rng(seed)
    modeled_columns = [column for column in LEARNED_MODEL_COLS if column in train.columns]
    fit_rows = min(len(train), int(params.get("fit_rows", CFG["learned_fit_rows"])))
    if fit_rows < 2000:
        raise ScientificInvalidFit("Latent VAR comparator has fewer than 2000 contiguous fitting rows")
    # Use a deterministic contiguous TRAIN window, not row subsampling, so every lag
    # and transition is genuine. Different seeds change the start position only.
    max_start = max(0, len(train) - fit_rows)
    start = int(rng.integers(0, max_start + 1)) if max_start else 0
    X_raw = train.iloc[start:start + fit_rows][modeled_columns].to_numpy(dtype=np.float64)
    split_at = max(1000, int(0.80 * len(X_raw)))
    if len(X_raw) - split_at < 500:
        split_at = len(X_raw) - 500
    fit_raw = X_raw[:split_at]
    transformed = signed_log1p(fit_raw)
    scaler = StandardScaler()
    scaled = scaler.fit_transform(transformed)
    components = int(min(
        params.get("pca_components", CFG["learned_pca_components"]),
        scaled.shape[1], max(2, scaled.shape[0] - 2),
    ))
    if components < 2:
        raise ScientificInvalidFit("Latent VAR comparator has fewer than two PCA components")
    pca = PCA(n_components=components, svd_solver="randomized", random_state=seed)
    fit_latent = pca.fit_transform(scaled)
    full_latent = pca.transform(scaler.transform(signed_log1p(X_raw)))
    explained = float(np.sum(pca.explained_variance_ratio_))
    if explained < CFG["learned_min_modeled_variance_fraction"]:
        raise ScientificInvalidFit(
            "Latent VAR PCA scope explains too little TRAIN variance",
            diagnostics={
                "explained_variance": explained,
                "minimum": CFG["learned_min_modeled_variance_fraction"],
                "components": components,
            },
        )
    lags = tuple(int(value) for value in params.get("lags", CFG["learned_var_lags"]))
    X_design, y_design, times = _latent_var_design(full_latent, lags)
    train_mask = times < split_at
    val_mask = times >= split_at
    if train_mask.sum() < 1000 or val_mask.sum() < 300:
        raise ScientificInvalidFit("Latent VAR comparator lacks train/validation transition pairs")
    model = Ridge(alpha=float(params.get("ridge", 1.0)), solver="lsqr", tol=1e-6, max_iter=10000)
    model.fit(X_design[train_mask], y_design[train_mask])
    pred_train = model.predict(X_design[train_mask])
    residuals = y_design[train_mask] - pred_train
    pred_val = model.predict(X_design[val_mask])
    y_val = y_design[val_mask]
    model_mae = float(np.mean(np.abs(y_val - pred_val)))
    max_lag = max(lags)
    val_times = times[val_mask]
    persistence = full_latent[val_times - 1]
    persistence_mae = float(np.mean(np.abs(y_val - persistence)))
    mean_baseline = np.repeat(fit_latent.mean(axis=0, keepdims=True), len(y_val), axis=0)
    mean_mae = float(np.mean(np.abs(y_val - mean_baseline)))
    denominator = max(min(persistence_mae, mean_mae), 1e-8)
    validation_ratio = float(model_mae / denominator)
    if not np.isfinite(validation_ratio) or validation_ratio > CFG["learned_validation_ratio_max"]:
        raise ScientificInvalidFit(
            "Latent VAR comparator failed its held-out TRAIN validation-health gate",
            diagnostics={
                "model_mae": model_mae,
                "persistence_mae": persistence_mae,
                "mean_mae": mean_mae,
                "validation_ratio": validation_ratio,
                "maximum_ratio": CFG["learned_validation_ratio_max"],
            },
        )
    latent_lo = np.quantile(fit_latent, 0.005, axis=0)
    latent_hi = np.quantile(fit_latent, 0.995, axis=0)
    simulated = np.empty((n, components), dtype=np.float64)
    seed_start = int(rng.integers(max_lag, len(fit_latent)))
    # Fill the initial lag state from a contiguous real latent prefix, then every
    # generated step is model prediction plus a bootstrapped TRAIN residual.
    if seed_start - max_lag < 0:
        seed_start = max_lag
    initial = fit_latent[seed_start - max_lag:seed_start]
    simulated[:max_lag] = initial[-max_lag:]
    coef = np.asarray(model.coef_, dtype=np.float64)
    intercept = np.asarray(model.intercept_, dtype=np.float64)
    for index in range(max_lag, n):
        x = np.concatenate([simulated[index - lag] for lag in lags])
        prediction = x @ coef.T + intercept
        innovation = residuals[int(rng.integers(0, len(residuals)))]
        simulated[index] = np.clip(prediction + innovation, latent_lo, latent_hi)
    raw_sample = signed_expm1(scaler.inverse_transform(pca.inverse_transform(simulated)))
    # Temporal dynamics are learned from the contiguous fitting window, but
    # feature activity and magnitude marginals are restored against the complete
    # TRAIN split. This prevents a seed-specific temporal window from imposing
    # its local sparse-event prevalence on the full deployment estimand.
    full_train_modeled = train[modeled_columns].to_numpy(dtype=np.float32)
    restored = rank_restore_empirical_marginals(
        raw_sample,
        full_train_modeled,
        seed + 2718,
    )
    base = hurdle_rank_stitch_generator(
        train, n, seed + 23, columns, {"stitch_mode": "shared"}
    )
    frame = _overlay_frame(base, modeled_columns, restored)
    frame = project_frame_to_train_support(frame, train, columns)
    frame.attrs["health"] = {
        "model_kind": "support_aware_pca_multilag_var_overlay",
        "modeled_columns": modeled_columns,
        "n_modeled_columns": len(modeled_columns),
        "fit_window_start": start,
        "fit_rows": fit_rows,
        "temporal_fit_reference": "deterministic_contiguous_train_window",
        "marginal_restore_reference": "complete_train_split",
        "marginal_reference_rows": int(len(full_train_modeled)),
        "pca_components": components,
        "pca_explained_variance": explained,
        "lags": list(lags),
        "model_mae": model_mae,
        "persistence_mae": persistence_mae,
        "mean_mae": mean_mae,
        "validation_ratio": validation_ratio,
        "validation_ratio_max": CFG["learned_validation_ratio_max"],
        "residual_rows": int(len(residuals)),
        "empirical_support_restoration": True,
        "order_preserving": True,
        "release_eligible": True,
    }
    return frame