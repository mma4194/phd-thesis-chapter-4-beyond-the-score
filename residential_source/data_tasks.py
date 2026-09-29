from dataclasses import replace
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.decomposition import PCA
from sklearn.mixture import GaussianMixture
from scipy.optimize import linear_sum_assignment
import gc, re

class ScientificInvalidFit(RuntimeError):

    def __init__(self, message, diagnostics=None):
        super().__init__(message)
        self.diagnostics = diagnostics or {}

def card_from(d):
    t = d['task']
    return TaskModelCard(TaskCard(**{**t, 'lags': tuple(t['lags']), 'predictors': tuple(t['predictors'])}), d['model_id'])

def load_raw():
    """A column-wise RAM matrix keeps NaN. It never changes the input parquet."""
    sec = pd.read_parquet(DATA_PATH, columns=['sec'])['sec'].to_numpy(float)
    if len(sec) != ASSETS['raw_dataset_manifest']['rows'] or not np.isfinite(sec).all():
        raise RuntimeError('Unexpected time axis.')
    order = np.argsort(sec, kind='stable')
    sec = sec[order]
    if not np.all(np.diff(sec) == 1):
        raise RuntimeError('Expected unique one-second rows.')
    needed = len(sec) * len(COLS) * np.dtype(np.float32).itemsize
    msg(f'Raw numerical matrix: {needed / 1024 ** 3:.2f} GiB in RAM. No raw-values disk cache will be written.')
    arr = np.empty((len(sec), len(COLS)), dtype=np.float32, order='F')
    ci = {c: i for i, c in enumerate(COLS)}
    audit = []
    for no, c in enumerate(sorted({REVERSE_MASK.get(c, c) for c in COLS})):
        raw = pd.read_parquet(DATA_PATH, columns=[c])[c].to_numpy(dtype=float, na_value=np.nan)[order]
        with np.errstate(over='ignore', invalid='ignore'):
            v = raw.astype(np.float32)
        finite = np.isfinite(v)
        v[~finite] = np.nan
        if c in ci:
            arr[:, ci[c]] = v
        mask = MASK_MAP.get(c)
        if mask in ci:
            arr[:, ci[mask]] = (~finite).astype(np.float32)
        for name, lo, hi in [('TRAIN', SPLIT['train_start'], SPLIT['train_end']), ('VAL', SPLIT['val_start'], SPLIT['val_end']), ('TEST', SPLIT['test_start'], SPLIT['test_end'])]:
            x = raw[lo:hi]
            f = finite[lo:hi]
            audit.append({'split': name, 'feature': c, 'rows': len(x), 'missing_nonfinite': int((~np.isfinite(x)).sum()), 'float32_overflow': int((np.isfinite(x) & ~f).sum()), 'stored_zero': int((np.isfinite(x) & (x == 0)).sum()), 'float32_underflow_to_zero': int((np.isfinite(x) & (x != 0) & f & (v[lo:hi] == 0)).sum()), 'physical_units_verified': False})
        if (no + 1) % 50 == 0:
            msg(f'Prepared {no + 1} raw columns.')
    save_csv(RUN / 'input_value_audit.csv', audit)
    save_json(RUN / 'raw_storage.json', {'mode': 'RAM', 'shape': arr.shape, 'bytes': arr.nbytes, 'disk_array_written': False})
    return (pd.DataFrame(arr, columns=COLS, copy=False), sec)

def observed(frame, col):
    x = frame[col].to_numpy()
    ok = np.isfinite(x)
    mask = MASK_MAP.get(col)
    if mask in frame:
        ok &= frame[mask].to_numpy() < 0.5
    return ok

def task_arrays(frame, task, cap=None, segments=None):
    """Drop unobserved target contexts before subsampling. Leave predictors missing."""
    n = len(frame)
    lag = max(task.lags, default=0)
    span = int(task.label_window_steps or task.horizon)
    ix = np.arange(lag, max(lag, n - span), dtype=int)
    target = frame[task.target].to_numpy(float)
    ok = observed(frame, task.target)
    if task.task_type == 'classification' and task.label_window_steps > 0:
        onset = task.task_id.startswith(('state_transition__', 'event_onset__')) or task.threshold_kind == 'binary_onset'
        start = ix if onset else ix + 1
        end = ix + span + 1
        cum = np.r_[0, np.cumsum(~ok)]
        valid = cum[end] - cum[start] == 0
        safe = np.where(ok, target, 0.0)
        labels = (_forward_window_onset(safe, float(task.threshold), span, task.task_id.startswith('state_transition__')) if onset else _forward_window_any(safe, float(task.threshold), span))[ix]
    else:
        valid = ok[ix + task.horizon]
        labels = target[ix + task.horizon]
        if task.task_type == 'classification':
            labels = (labels > float(task.threshold)).astype(np.int8)
    missing = int((~valid).sum())
    boundary = 0
    if segments is not None:
        continuous = np.asarray(segments)[ix - lag] == np.asarray(segments)[ix + span]
        boundary = int((valid & ~continuous).sum())
        valid &= continuous
    ix = ix[valid]
    labels = labels[valid]
    before = len(ix)
    take = deterministic_subsample_indices(len(ix), cap)
    ix = ix[take]
    labels = labels[take]
    cols = []
    xx = []
    vectors = {c: frame[c].to_numpy() for c in task.predictors}
    availability = {c: observed(frame, c) for c in task.predictors}
    for lag in task.lags:
        for c in task.predictors:
            z = vectors[c][ix - lag].astype(float)
            z[~availability[c][ix - lag]] = np.nan
            xx.append(z)
            cols.append(f'{c}__lag{lag}')
    X = pd.DataFrame(np.column_stack(xx) if xx else np.empty((len(ix), 0)), columns=cols)
    audit = {'possible_contexts': max(0, n - max(task.lags, default=0) - span), 'missing_target_contexts': missing, 'join_contexts_removed': boundary, 'available_before_cap': before, 'used': len(ix), 'predictor_missing_fraction': float(X.isna().to_numpy().mean()) if X.size else None, 'used_target_missing': 0}
    return (X, pd.Series(labels, dtype=float), audit)

class TrainingMedianWithIndicators(BaseEstimator, TransformerMixin):
    """One fixed output column per input plus its missing indicator, learned on fit only."""

    def fit(self, X, y=None):
        x = np.asarray(X, float)
        self.n_features_in_ = x.shape[1]
        self.medians_ = np.array([np.median(c[np.isfinite(c)]) if np.isfinite(c).any() else 0.0 for c in x.T])
        self.all_missing_ = ~np.isfinite(x).any(axis=0)
        return self

    def transform(self, X):
        x = np.asarray(X, float)
        if x.shape[1] != self.n_features_in_:
            raise ValueError('Predictor width changed.')
        bad = ~np.isfinite(x)
        return np.column_stack([np.where(bad, self.medians_, x), bad.astype(float)])

def corrected_model(task, model_id, seed):
    return make_pipeline(TrainingMedianWithIndicators(), model_for(task.task_type, model_id, seed))

def revise_thresholds(raw):
    global ALL_CARDS, CARDS
    changes = {}
    rows = []
    for c in ALL_CARDS + CARDS:
        t = c.task
        if t.task_id in changes:
            continue
        x = raw.iloc[:SPLIT['train_end']][t.target].to_numpy(float)
        valid = observed(raw.iloc[:SPLIT['train_end']], t.target)
        x = x[valid]
        threshold = t.threshold
        reason = 'original numeric threshold retained'
        q = re.search('train_q([0-9.]+)', t.threshold_kind)
        if q and len(x):
            threshold = float(np.quantile(x, float(q.group(1))))
            reason = 'same quantile, observed TRAIN values only'
        elif t.task_type == 'classification' and len(x) and set(np.unique(x)).issubset({0.0, 1.0}):
            threshold = 0.5
            reason = 'midpoint separates observed binary states'
        changes[t.task_id] = replace(t, threshold=threshold)
        rows.append({'task_id': t.task_id, 'target': t.target, 'old_threshold': t.threshold, 'new_threshold': threshold, 'finite_train_values': len(x), 'reason': reason})
    ALL_CARDS = [TaskModelCard(changes[c.task.task_id], c.model_id) for c in ALL_CARDS]
    CARDS = [TaskModelCard(changes[c.task.task_id], c.model_id) for c in CARDS]
    save_csv(RUN / 'threshold_changes.csv', rows)

def fit_model_checked(X, y, card, seed):
    if len(y) < 300:
        return (None, {'status': 'too_few_training_rows'})
    if X.shape[1] == 0:
        return (None, {'status': 'no_predictors'})
    if card.task.task_type == 'classification' and y.nunique() < 2:
        return (None, {'status': 'single_training_class'})
    with warnings.catch_warnings(record=True) as ws:
        warnings.simplefilter('always')
        m = corrected_model(card.task, card.model_id, seed)
        m.fit(X, y)
    notes = [{'category': w.category.__name__, 'message': str(w.message)} for w in ws]
    if any((w['category'] == 'ConvergenceWarning' for w in notes)):
        return (None, {'status': 'model_did_not_converge', 'warnings': notes})
    return (m, {'status': 'ok', 'warnings': notes, 'all_missing_predictors': int(m.steps[0][1].all_missing_.sum())})

def score_model(m, ytrain, X, y, card):
    if len(y) < 300:
        return {'status': 'too_few_test_rows'}
    if card.task.task_type == 'classification' and y.nunique() < 2:
        return {'status': 'single_test_class'}
    if card.task.task_type == 'regression' and robust_iqr(y) < CFG['min_regression_target_iqr']:
        return {'status': 'unobserved_or_constant_target'}
    pred = m.predict_proba(X)[:, 1] if card.task.task_type == 'classification' else m.predict(X)
    if not np.isfinite(pred).all():
        return {'status': 'nonfinite_prediction'}
    d = task_loss_and_diagnostics(ytrain, y, pred, card.task.task_type)
    return {'status': 'ok', **d}

def recheck_admission(raw):
    rows = []
    fit = raw.iloc[SPLIT['train_start']:SPLIT['train_end']]
    val = raw.iloc[SPLIT['val_start']:SPLIT['val_end']]
    for i, c in enumerate(ALL_CARDS):

        def run(c=c):
            X, y, a = task_arrays(fit, c.task, CFG['row_cap_task_train'])
            V, z, b = task_arrays(val, c.task, CFG['row_cap_task_test'])
            m, health = fit_model_checked(X, y, c, CFG['seeds'][0])
            d = score_model(m, y, V, z, c) if m is not None else health
            good = d['status'] == 'ok' and d['skill_gain'] >= CFG['min_reference_skill_gain']
            if c.task.task_type == 'classification':
                good = bool(good and CFG['min_task_prevalence'] <= z.mean() <= CFG['max_task_prevalence'] and (d.get('roc_auc', 0) >= CFG['min_reference_auc']) and (d.get('average_precision', 0) - z.mean() >= CFG['min_reference_ap_gain']))
            return {'card_id': c.card_id, 'suite': c.task.suite, 'capability': c.task.capability, 'task_family': c.task.family, 'target': c.task.target, 'model_id': c.model_id, 'admitted': bool(good), 'train_audit': a, 'val_audit': b, **d, 'fit_warnings': health.get('warnings', [])}
        rows.append(cache('task_admission', c.key(), run))
        if (i + 1) % 10 == 0:
            msg(f'Observed-target task checks {i + 1}/{len(ALL_CARDS)}.')
    save_json(RUN / 'task_admission.json', rows)
    save_csv(RUN / 'task_admission.csv', rows)
    admitted = {r['card_id'] for r in rows if r['admitted']}
    return admitted
