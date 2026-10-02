# Recovery and preparation budget fix

Version 1.0.1 fixes `artifact/toniot.py`, which previously called `float(budget_hours)` even when the notebook set `budget_hours = None`. The permanent expression is:

```python
budget_hours=(None if budget_hours is None else float(budget_hours))
```

`Project` and the downstream deadline guards already support `None`. Numerical methods, comparison references and tolerances are unchanged by this correction.

## Existing completed Falcon run

Keep the original project and output folder. The successful resumed run already used this patch and does not need another full rerun solely to publish the package. Extract the GitHub release into a separate folder. Never replace source files while a run is active.

## Resume an interrupted new run

Keep the same code version, configuration and output directory. If the kernel is still alive, rerun the failed stage cell and continue downward. If the kernel was lost, restart the notebook from its configuration and Run All so stage locations are reconstructed; underlying residential and external job checkpoints are reused where valid. Some setup, validation and other stages may run again. There is no promise that every completed stage is skipped.

Do not remove checkpoints, edit historical status JSON, weaken comparison tolerances, or regenerate a manifest merely to make an unexplained difference disappear. Inspect `logs/<stage>.log` and the reported comparison files. A source/configuration binding change can prevent reuse and should be handled in a separate run directory.

`budget_hours = None` disables the application’s time budget, but cannot extend a scheduler allocation. Use a compute allocation long enough for the measured workload.

## Package integrity

`PACKAGE_SHA256.json` checks executable sources, reference tables and evidence. Notebook and HTML files are excluded from that runtime manifest so users can configure and save notebooks. The clean notebook is additionally recorded in `RELEASE_FILES_SHA256.json`, which is a release inventory rather than a runtime editing restriction. Git line-ending conversion is disabled to preserve exact bytes.
