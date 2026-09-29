# Required data

## Residential: reuse the Chapter 3 release

[Download the existing Parquet](https://github.com/mma4194/phd-thesis-chapter-3-synthetic-fusion/releases/download/residential-input-v1/cps_unified_1s_FULLGRID_FINAL_WITH_IOT_STATEFUL_STRICTMASKED_TRIMMED.parquet) or reuse the copy already on Falcon. Its [release page](https://github.com/mma4194/phd-thesis-chapter-3-synthetic-fusion/releases/tag/residential-input-v1) and [dataset metadata](../datasets/residential/dataset.json) identify the shared asset. The release asset metadata was checked on 29 September 2026.

| Property | Required value |
|---|---|
| Bytes | 238,609,923 |
| Rows | 1,277,694 |
| Stored columns | 740 |
| SHA-256 | `a4d7446daba0e46dab2dc21607a99c5a734a5366a6c24018a82ef2ef35fc4bda` |

The stored width is distinct from Chapter 4's engineered 1,010-column corrected working matrix and the original canonical supplementary scope. Do not substitute another similarly named table.

Verify an existing file:

```bash
python tools/residential_data.py --output ~/data/cps_unified_1s_FULLGRID_FINAL_WITH_IOT_STATEFUL_STRICTMASKED_TRIMMED.parquet
```

Download only if no verified local copy exists:

```bash
python tools/residential_data.py --download --output /shared/scratch/SCWF00162/shared_data/cps_unified_1s_FULLGRID_FINAL_WITH_IOT_STATEFUL_STRICTMASKED_TRIMMED.parquet
```

The downloader checks size and SHA-256 before accepting the new file. Chapter 4 does not re-upload or embed the asset. A release download link can change if its owner replaces/removes an asset; the hash remains the acceptance criterion. The Chapter 3 metadata does not declare a dataset licence, so this repository does not invent one.

## TON_IoT: raw normal telemetry and captures

Obtain the source files from the [UNSW TON_IoT project](https://research.unsw.edu.au/projects/toniot-datasets). Keep them outside the Git repository. Set `toniot_data_root` to the directory whose immediate children are:

| Relative location | Content |
|---|---|
| `TON_IOT_IOT_DATA.zip` | 21 filtered normal telemetry CSVs plus their 21 paired original logs |
| `pcap_files/normal_1.pcap` through `normal_13.pcap` | Thirteen general normal captures; `.pcapng` is also supported |
| `pcap_files/normal_IoT_2.pcap` and `normal_IoT_3.pcap` | Two IoT-labelled normal captures |

Capture subdirectories are accepted, but each expected basename must appear exactly once. The full acquisition identity table is `reference/toniot/preparation_protocol.json`; telemetry member names, sizes and hashes are in `protocols/telemetry_members.json`. Equivalent telemetry ZIP repackaging is accepted only after all 42 decompressed member hashes match. Capture identities are exact.

Processed classification CSVs such as `IoT_Fridge.csv` cannot replace these raw logs/captures. Attack files are not mixed into this normal-data reproduction. Source files are read without modification. The documented 28,200 fridge date corrections are performed in derived preparation, while recorded-time coordinates are not treated as independently synchronized physical clocks.

Preparation should yield 28,752 rows and 64 value features on a regular five-second grid. The reported 31,287,177 complete packet records and two incomplete capture endings follow the supplied complete-prefix policy. Six prepared tables are checked using portable content fingerprints and a separate immutable completion receipt.

The raw captures were not available in this recovery workspace. The telemetry ZIP and residential Parquet were available and checked. A reviewer must obtain the missing captures to execute the complete external pipeline.

## Smart* and excluded files

Smart* is part of Chapter 3, not this chapter's recovered pipeline. No Smart* acquisition is required for Chapter 4. Neither raw Smart* nor raw TON_IoT data is distributed here. The repository also excludes newly generated private arrays, fitted models, environments and local paths/configurations from normal Git tracking.
