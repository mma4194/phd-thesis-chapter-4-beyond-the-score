# Update the existing Chapter 4 repository with GitHub Desktop

Target: https://github.com/mma4194/phd-thesis-chapter-4-beyond-the-score

## 1. Prepare a clean replacement

1. Download and extract the new ZIP outside your existing repository.
2. In GitHub Desktop select the Chapter 4 repository. Use Repository → Show in Explorer to locate its root. Fetch/pull remote changes first if applicable.
3. Make a backup of that whole local repository outside its folder, especially any uncommitted work.
4. Preserve `.git`, which contains repository history. If the repository contains your own additions, preserve and review those too.
5. Replace the earlier generated package with the contents of the new extracted repository folder. Do not simply overlay and leave obsolete notebooks, entry points or old validation instructions beside the new ones. Remove superseded generated files in the Changes view after checking the backup. Never delete `.git`.
6. The main notebook and README must be at the repository root, not inside a second nested folder. Copy `.github`, `.gitignore` and `.gitattributes` as well. The supplementary folder must contain exactly one PDF.

## 2. Verify locally

From a terminal in the repository root:

```powershell
python verify_package.py
```

This requires only Python’s standard library. Review the Changes list for unintended deletions or raw data. Do not copy Falcon scratch runs, virtual environments, PCAPs or the residential Parquet into GitHub. Included result CSV/JSON and identity manifests belong in the repository.

The `results/falcon_20261002/` files document the completed author run. The root notebook is deliberately clean, with `MODE = "evidence"` as its first-review default. Use `MODE = "fresh"` for a new raw-input execution.

## 3. Commit and push

Use this commit summary:

`Release Chapter 4 reproduction v1.0.1 with verified Falcon results`

Commit to your working branch, then Push origin. If the repository has not been published, choose Publish repository and the intended owner/name. Use a public repository for direct reviewer access.

On GitHub check the README links, notebook rendering, supplementary PDF and Actions → Package integrity. This automation checks file integrity only; it does not execute the raw scientific experiments.

## 4. Create a stable release

On GitHub open Releases → Draft a new release. Use tag `chapter4-reproduction-v1.0.1` at the commit you just pushed, title `Chapter 4 reproduction v1.0.1`, and the summary in CHANGELOG.md. Attach the delivered ZIP as a release asset if desired. Do not commit the ZIP inside the repository.

The thesis repository URL stays the same. Record the release tag and commit hash so reviewers can cite the exact version. Future substantive edits should use a new version and an updated integrity manifest, with their validation recorded.

No live GitHub changes are made by extracting this package; publication occurs when you commit/push using your account.
