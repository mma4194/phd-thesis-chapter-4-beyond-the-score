
# ============================================================
# 0. Imports and run profile
# ============================================================
from pathlib import Path
import os
for _name in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","VECLIB_MAXIMUM_THREADS","NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_name,"1")

import sys, json, math, time, copy, random, pickle, hashlib, inspect, functools
import warnings, zipfile, io, ast, gc, platform, subprocess, textwrap
from dataclasses import dataclass, field, asdict
from typing import Any, Sequence, Iterable
from collections import Counter, defaultdict

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
try:
    from IPython.display import display, Markdown
except ImportError:
    def display(x): print(x)
    def Markdown(x): return x

from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (accuracy_score, average_precision_score, balanced_accuracy_score,
                             brier_score_loss, mean_absolute_error, r2_score, roc_auc_score)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.base import clone
from scipy import stats
from scipy.stats import wasserstein_distance

PROJECT_START=time.time()
EXPERIMENT_VERSION='TIOT-KT-v2'
