# Files needed from the successful Falcon run

The supplied archives contain the recovered pipeline and fixed manifests. What is still missing is evidence from **your latest actual successful Falcon execution**, including any fixes you made locally. Do not send raw Smart* or TON_IoT files for inclusion in GitHub.

Please send:

1. The **executed full notebook** from `~/Thesis_Reproduction/` (including its saved output cells). In Jupyter, save it after the final report, then download the `.ipynb`.
2. Your actual source/configuration snapshot, including changed `master_workflow.py`, `artifact/`, `external_rebuild/`, setup/configuration helpers and any new manifest files. The collector below captures text/code from that folder.
3. The actual `master_config.json`, `master_status/`, `logs/`, final report and comparison tables under `/shared/scratch/SCWF00162/Thesis_Reproduction_runs/` (or your actual configured run root).
4. Preparation metadata/manifests and copied input-check JSON reports from that run. Prepared raw tables and prediction arrays need not be uploaded for this review.
5. Exact `pip freeze` and Python versions for **both** interpreter paths that produced the successful run, plus the TShark version if used. The collector captures Python information; separately run `tshark --version > tshark-version.txt` when TShark is installed.
6. Any additional scripts/reports used for supplementary-only health/range checks that are not already in the recovered code. Include the commands and input/output paths you used. If none were used, say so.

From this new repository's root on Falcon, collect the old run with:

```bash
python collect_run.py \
  --config /shared/scratch/SCWF00162/Thesis_Reproduction_runs/master_config.json \
  --source-root ~/Thesis_Reproduction \
  --output /shared/scratch/SCWF00162/FALCON_RESULTS_TO_RETURN.zip
```

Substitute your actual run directory if different. This reads the interpreter paths from the old configuration. It does not install packages or rerun experiments. It excludes raw datasets and large arrays; files over 25 MiB are omitted, so send a large executed notebook separately. Review the archive for personal paths or private log content before sharing publicly. Upload the archive and notebook here first; they can then be checked and incorporated as dated execution evidence.

If collection fails, send `master_config.json`, the error, and the executed notebook. Do not change the old run to make it fit the new package.
