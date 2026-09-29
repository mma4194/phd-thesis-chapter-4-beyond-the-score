# Publish Chapter 4 with GitHub Desktop

Target: **mma4194/phd-thesis-chapter-4-beyond-the-score**

This package prepares the repository; it does not create or publish it on your account. Complete the evidence review below before describing a release as a verified full Falcon reproduction.

## 1. Keep an original copy

Download and retain the delivered repository ZIP. Extract it to a normal folder on your computer. The extracted repository root contains `README.md`, `run.py`, `notebooks/`, `docs/` and `.github/`. Keep the outer ZIP elsewhere. Do not copy raw datasets or your Falcon environment into this folder.

## 2. Create the local repository

Sign in to GitHub Desktop as `mma4194`. Choose **File → New repository**. Enter the name `phd-thesis-chapter-4-beyond-the-score`, a description such as “Chapter 4 thesis reproducibility: Beyond the Score”, and a local parent directory. Desktop creates a subfolder with the repository name. Leave automatic README, Git ignore and license choices unset/None because the package already supplies the relevant project files; no software license has been chosen on your behalf. Click **Create repository**.

Copy **the contents** of the extracted repository into that newly created repository folder. Avoid a second nested folder with the same name. Include hidden `.github`, `.gitignore` and `.gitattributes` files, but never replace the `.git` folder Desktop created. Use **Repository → Show in Explorer/Finder** to confirm the location.

Alternative: if Desktop offers to create a repository when you add the extracted folder, use that route. The final root layout must be the same.

## 3. Inspect and commit

In Desktop's Changes view, inspect the pending files. The `supplementary` directory must contain exactly one PDF. Confirm there is no Parquet, PCAP, raw TON_IoT directory, Smart* dataset, virtual environment, access token or large scratch run. Reference CSVs, fixed protocol manifests and dated validation records belong in the repository.

Where Python is available, run from the repository root:

```bash
python verify_package.py
```

The delivered clean package should pass. If you intentionally edit files, record the changes and rebuild the manifest with `python tools/build_manifest.py`, then verify again. Do not rebuild the manifest merely to conceal accidental damage.

Commit with a descriptive summary, for example `Prepare Chapter 4 reproducibility package`. Desktop may have an earlier empty initialization commit; that is harmless.

## 4. Publish to GitHub

Click **Publish repository**. Confirm the owner is `mma4194` and the exact repository name. For public reviewer access, clear **Keep this code private**. Click **Publish repository**. If the name already exists, do not overwrite another project: open that repository and decide whether it is the intended destination.

Open **Repository → View on GitHub**. Your intended URL is:

https://github.com/mma4194/phd-thesis-chapter-4-beyond-the-score

Check that README links open, the notebook renders, the supplement PDF opens and the residential download points to the Chapter 3 release. GitHub's notebook preview does not execute cells.

## 5. Check automation and a clean checkout

Open **Actions** and inspect the `checks` workflow. A green job verifies package integrity, environment checks and unit tests. It does **not** download restricted raw data or certify the full scientific experiment.

Clone the public repository into a separate clean folder and run `python verify_package.py`. Follow `docs/REPRODUCIBILITY.md` on Falcon: code and environments in home, outputs in scratch, existing matching residential interpreter, separate matching public interpreter. Run a `records` trial in its own run directory; then run `full` with all required data and sufficient allocations.

## 6. Add the actual Falcon evidence

Follow `docs/FALCON_FILES_TO_SEND.md`. Preserve the original completed run and exact source snapshot. Check its final report, stage statuses, inputs and environment closure before adding a dated summary under `validation/`. Do not commit whole raw-data or scratch directories. Update `docs/EXECUTION_STATUS.md` and `docs/RESULTS.md` with exactly what was executed and what passed or differed. Rebuild `MANIFEST.json`, run integrity checks, commit and **Push origin**.

If a numerical comparison differs, publish the discrepancy honestly. Do not silently change methods, tolerances, seeds or reference results. A repository may be public before this step, but its README must retain the explicit evidence limitation.

## 7. Make a stable thesis release

After reviewing the final files and evidence, open the GitHub repository → **Releases → Draft a new release**. Create tag `v1.0.0` at the reviewed commit. Give the release a clear title and notes stating the notebook version, supplementary version, dataset release link, environment versions, tests executed, full-run evidence and any unresolved differences. Publish the release. GitHub provides source archives for the tag; do not attach the residential Parquet again.

Do not move a published thesis tag to different code. Issue `v1.0.1` or another version for later changes and document the differences. For a DOI, archive the reviewed release through your chosen research repository separately; no DOI is assigned by this package.

## 8. Cite the frozen version in Chapter 4

Use the repository URL and identify the release tag and full commit SHA. A suitable sentence after publishing and checking the release is:

> The Chapter 4 implementation, reproduction notebook, environment specifications, fixed protocol inputs and supplementary PDF are available at https://github.com/mma4194/phd-thesis-chapter-4-beyond-the-score (release v1.0.0; commit INSERT_FULL_COMMIT_SHA). Residential input data are linked to the shared Chapter 3 dataset release; raw TON_IoT data must be obtained from the original provider.

Replace the placeholder with the actual release commit. Never describe a pending or partial run as a full reproduction. Keep the release accessible to examiners throughout the review period.

## Final reviewer checklist

- A fresh clone passes package verification.
- The notebook has no journal branding and configuration instructions match Falcon.
- `supplementary/` contains only the compiled PDF.
- The shared residential asset is accessible and matches its SHA-256.
- Raw-data acquisition and exact expected layout are documented.
- Both execution environments and their evidence are identified.
- Historical, newly executed and not-yet-supplied results are distinguished.
- The supplementary population/value corrections are explicit.
- The thesis cites a stable tag and commit, not only a moving branch.

Official GitHub Desktop guidance: https://docs.github.com/en/desktop/overview/creating-your-first-repository-using-github-desktop

Official releases guidance: https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository
