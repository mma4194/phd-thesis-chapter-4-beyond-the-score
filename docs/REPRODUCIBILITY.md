# Beyond the Score — Chapter 4 reported results

Open **Chapter4_Reported_Results.ipynb** from this folder. The notebook follows the reported chapter experiments. It has no post-hoc positive-control, solver-investigation or historical supplementary-discrepancy workflow cells.

## First review

Use `MODE = "evidence"` and Run All. This reads the supplied complete author-run reports, checks every selected comparison, and recalculates all 45 registered headline values from the supplied residential losses and external summaries. No raw datasets are needed for this mode. The outputs explicitly identify previously executed evidence. Use a Python kernel with NumPy, pandas, SciPy, scikit-learn and matplotlib; the public pinned environment is recommended.

The original Falcon HTML is preserved in `results/falcon_20261002/`. The main notebook is clean and unexecuted. Evidence mode reviews the latest completed author run.

## New raw-input run

1. Keep this project and Python environments in Home on Falcon. Do not overwrite the existing `Thesis_Reproduction` project or its results. Extract this package alongside it.
2. Use the existing public interpreter `~/venvs/thesis-public/bin/python` and residential interpreter `~/venvs/tiot-v5/bin/python` if they still match `protocols/expected_environments.json`. Environment checks execute before every fresh scientific stage.
3. In the configuration cell set `MODE = "fresh"`, the input paths and scratch output location. The full run uses original scientific methods, not the later stability solvers.
4. Run All inside an allocated compute session. Large data preparation and model stages can take hours. Allow the memory previously required for the complete residential and external runs.
5. Read the final chapter report and `chapter_headline_comparison.csv`. A PASS means the declared chapter workflow and mapped values agree under their stated rules. It is not a statement that every exploratory experiment in the project has identical numbers.

If creating environments, use Python 3.11 and the platform-resolved files `environment/public-py311-resolved.lock.txt` and `environment/residential-py311-resolved.lock.txt`. The Python 3.12 historical snapshots are retained as provenance and should not be installed into Python 3.11. No environment is installed into scratch by this notebook. Exact core scientific versions are checked by the original stage code; pins do not guarantee cross-hardware bitwise equality.

```bash
python3.11 -m venv "$HOME/venvs/chapter4-public"
"$HOME/venvs/chapter4-public/bin/python" -m pip install -r environment/public-py311-resolved.lock.txt
python3.11 -m venv "$HOME/venvs/chapter4-residential"
"$HOME/venvs/chapter4-residential/bin/python" -m pip install -r environment/residential-py311-resolved.lock.txt
```

Set these interpreter paths in the notebook. A working notebook kernel can coordinate both children.

## Data

The residential input is shared with Chapter 3; do not upload a duplicate:

https://github.com/mma4194/phd-thesis-chapter-3-synthetic-fusion/releases/download/residential-input-v1/cps_unified_1s_FULLGRID_FINAL_WITH_IOT_STATEFUL_STRICTMASKED_TRIMMED.parquet

The original SHA256 is required by `protocols/residential_assets.json`. The prepared Parquet, fixed task cards, splits and observation contracts are part of the original experimental definition. Earlier exploratory task discovery is not rerun.

Obtain TON_IoT raw data from its provider under the applicable terms. Set `toniot_data_root` to a folder with:

```
raw_TON_IoT/
  TON_IOT_IOT_DATA.zip
  pcap_files/
    normal_1.pcap ... normal_13.pcap
    normal_IoT_2.pcap
    normal_IoT_3.pcap
```

Use the exact original filenames and capture hashes listed in `evidence/preparation_protocol.json`; the illustrative suffixes above must not be used to rename original files. `pcap_files` can contain the normal-capture subfolder. Symlinks to the existing dataset locations are acceptable. On the author's Falcon account the telemetry ZIP is under `/shared/scratch/SCWF00162/PAPER_04/`. Smart* is not used by this Chapter 4 pipeline. No raw third-party dataset is redistributed here.

## Independent decoder check

The included receipt records a separate completed Windows/TShark execution on all 15 hash-verified captures. Reviewing it is not claimed as newly executing TShark. To reproduce that check locally, install TShark where permitted and run:

```powershell
python chapter_support/check_decoder_locally.py --captures "C:\Datasets\TON_IoT\pcap_files\normal_pcaps" --output "C:\Users\admin\Documents\Chapter4_Decoder_Check"
```

Use `--help` for the explicit TShark path option. Set `DECODER_RECEIPT` in the notebook to the new `local_decoder_receipt.json`. The helper checks the first 10,000 packets per capture and documents its field coverage. This is not exhaustive payload verification.

## Recovery and outputs

`budget_hours = None` disables the six-hour application deadline. Cluster wall-time limits still apply. Operational deadline handling accepts `None` at the preparation wrapper, Project configuration and evaluation guards; scientific algorithms and comparisons are preserved. Old source/configuration-bound runs should be kept with their original project.

Run the same fresh configuration again after interruption. The original residential and external job checkpoints are reused where valid. Completed stages may perform validation or reconstruction again; not all setup work is checkpointed. Output goes to scratch and large predictions remain there. No existing experiment directory is deleted, rewritten, or imported as a new run.

Scientific child logs are saved under the configured output folder, keeping notebook output concise. A failed or different chapter comparison stops execution and gives its real status and log location. No failing rows are removed. The report includes evidence mode, data scope and historical task-registry dependence.

## Coverage and scientific history

`CHAPTER_COVERAGE.csv` maps the scope to the chapter's experiment and figure labels. Conceptual diagrams, literature claims and every prose numeral are not executable result assertions. The registered 45 values supplement full selected-stage comparisons; they are not a claim that only 45 numbers appear in the chapter.

The later positive-control extension and numerical-stability investigation are outside this notebook. Their original differing results and versioned methods remain in the earlier supplied archives; this scoped notebook does not turn them into passing comparisons. Only supplementary sources and reference files needed by the chapter methods are retained for provenance and dependencies. The corrected thesis supplementary PDF is the only file in `supplementary/`.

## Repository use

This is a self-contained notebook package for the Chapter 4 repository. Copy its contents into a separate working folder first. Do not overwrite an active Falcon project or push the embedded raw-run evidence as if it was newly produced by the reviewer. The package manifest covers executable code, source inputs, reference tables and bundled evidence; notebook outputs are generated review artifacts.
