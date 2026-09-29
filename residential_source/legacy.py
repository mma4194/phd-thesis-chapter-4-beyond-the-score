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