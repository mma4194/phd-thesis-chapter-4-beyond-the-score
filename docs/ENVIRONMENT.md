# Environment and Falcon setup

The notebook kernel coordinates child interpreters. It need not itself contain both scientific version sets. Keep installed environments in Home on Falcon and generated outputs in scratch. No GPU is required by these recovered CPU methods.

| Package | Public / controlled / classifier capacity | Residential / other canonical supplementary |
|---|---:|---:|
| NumPy | 2.3.5 | 2.4.6 |
| pandas | 2.2.3 | 2.3.3 |
| SciPy | 1.17.0 | 1.17.1 |
| scikit-learn | 1.8.0 | 1.9.0 |
| Matplotlib | 3.10.8 | 3.11.1 |
| PyArrow | 25.0.0 | 25.0.0 |
| joblib | 1.5.3 | 1.5.3 |
| threadpoolctl | 3.6.0 | 3.6.0 |

Exact scientific versions are enforced from `protocols/expected_environments.json`. Python/platform identity and dependency closure are recorded separately. Historical runs used Python 3.11.11 on Linux and a separate external Windows environment. Recovery checks used Python 3.12.14. These are not claimed as byte-identical systems.

## Reuse an existing environment first

In the existing notebook, print `sys.executable`. In the terminal, use that exact executable:

```bash
/shared/home1/c.c21126547/venvs/tiot-v5/bin/python tools/check_environment.py --group residential
```

A successful check reports `passed: true`. To check an existing public interpreter, run the same command with its path and `--group public`. The provided user diagnostic matched residential, not public. Do not downgrade the working residential kernel to satisfy public stages.

## Install only the missing public environment on Python 3.11

From the repository root, using the verified Python 3.11.11 interpreter:

```bash
/shared/home1/c.c21126547/venvs/tiot-v5/bin/python tools/setup_environments.py --only public --base-dir ~/venvs/beyond-the-score
```

The new executable will be `~/venvs/beyond-the-score/public/bin/python`. Existing installations at `~/venvs/thesis-public/bin/python` can also be used if the version check passes. Set the actual chosen path in `config/local.json`; no kernel reinstall is required for the coordinator.

A new reviewer can create both environments with a Python 3.11/3.12 interpreter:

```bash
python tools/setup_environments.py --base-dir ~/venvs/beyond-the-score
```

The helper uses `environment/public.in` and `environment/residential.in`, pins the direct scientific packages, resolves supporting dependencies for the current Python, disables the download cache, runs `pip check`, checks the exact scientific versions and saves the actual installed closure inside each environment. The environment itself still consumes Home quota; no installation into scratch is attempted.

## Important correction to the earlier package

The older instructions recommended Python 3.11 but distributed a dependency closure captured under Python 3.12. In particular, its ContourPy 1.4.0 pin is incompatible with Python 3.11. This repository labels those records `public-py312-recorded.lock.txt` and `residential-py312-recorded.lock.txt`. They are provenance, not default Python 3.11 requirements.

On Python 3.12, `--recorded-locks` explicitly selects that captured closure. On other versions the helper refuses this option. The direct `.in` route retains scientific version pins, but supporting dependencies are not claimed fully frozen until the actual Falcon freeze is collected. The latest full Falcon dependency closure is an outstanding evidence item listed in `FALCON_FILES_TO_SEND.md`.

Do not edit `expected_environments.json` to silence a version mismatch. Resolve the interpreter path or install the correct separate environment. A printed Python version alone does not establish numerical compatibility.

## Threading and external decoder

The controller fixes BLAS/OpenMP thread limits to one and supplies the configured worker count to supported stages. Install/provide TShark using the institution's supported route, and make `tshark --version` work in the compute session. Its actual version is written in the decoder report. No TShark version is invented as the historical original.

References: [Python venv](https://docs.python.org/3/library/venv.html), [pip repeatable installs](https://pip.pypa.io/en/stable/topics/repeatable-installs/), [NumPy reproducibility](https://numpy.org/doc/stable/reference/random/compatibility.html).

## Additional Python 3.11 resolved snapshots

`environment/*-py311-resolved.lock.txt` pin the complete dependency sets obtained by a Python 3.11 binary-wheel resolution on 29 September 2026. They avoid the incompatible contourpy 1.4 pin. These are optional installation snapshots, **not** your actual Falcon freezes and not newly executed Python 3.11 experiment evidence. The default helper installs the fixed direct requirements and records the resulting local closure. To use a resolved snapshot explicitly, install its requirements into an isolated Python 3.11 environment, then run the environment check and preserve `pip freeze`.
