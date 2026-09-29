# Repository handover

Start with README.md and docs/REPRODUCIBILITY.md. This repository reorganizes the recovered master package for Chapter 4 publication and adopts the latest supplied supplementary targets. Historical evidence remains separately dated.

The critical preparation verification fix is retained: immutable prepared tables and copied input-check reports are hashed; mutable evaluation progress is excluded. Use docs/FALCON_FILES_TO_SEND.md to archive each Falcon execution with its exact environment closure.

The source remains in home; run outputs belong in scratch. Do not use the recorded Python 3.12 lockfiles to install a Python 3.11 environment. See docs/ENVIRONMENT.md.
