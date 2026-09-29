
# ============================================================
# 0. Project/artifact auto-detection
# ============================================================
from pathlib import Path
import os, sys, json, math, time, copy, random, pickle, hashlib, inspect, functools, warnings, zipfile, io, ast, gc
from dataclasses import dataclass, field, asdict
from typing import Any, Sequence, Iterable
from collections import Counter, defaultdict

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, Markdown

from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score, average_precision_score, balanced_accuracy_score,
    brier_score_loss, mean_absolute_error, r2_score, roc_auc_score
)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.base import clone

try:
    from scipy import stats
    from scipy.stats import wasserstein_distance
except Exception:
    stats = None
    wasserstein_distance = None
