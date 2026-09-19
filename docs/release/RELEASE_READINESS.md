# Source release and evidence policy

This repository is a private development source until a reviewed source-only export
is published. Do not change its visibility or push its existing history to a public
remote. An organizer workshop PDF contained an embedded login credential. The local
authority copy is retained but untracked; earlier private Git objects still contain
it. No credential is reproduced in this report. Credential validity is not assumed.
The team should inform its owner through the authorized private channel; no automatic
credential use, rotation, message or destructive history rewrite is performed here.

## Public source route

Use the implemented source-only export, which has no `.git` history, local settings,
raw datasets, checkpoints, authority PDFs, or recordings. The export does not grant
rights to organizer documents, third-party assets, or upstream model weights.

```text
python scripts/release_audit.py --self-test --report <outside-repo>/audit.json
python scripts/release_audit.py --export <new-outside-repo-path>/pa-source.zip
```

Export requires a clean committed tree and a passing scan. It scans the resulting
archive again and emits a SHA-256 and included-file hashes. Initialize a fresh public
repository from that reviewed archive when publication is authorized; do not import
private history. A scan is a bounded check, not a guarantee against unknown secrets.
Any added model/data/media requires a separate rights and secret review before it
can be distributed. An empirical bundle is handed off separately with its manifest.

## Rights and attribution

The team has not selected a permissive license for original project code. Source
availability is not an implied license grant. Preserve author notices; do not claim
third-party rights. Dependencies retain their own licenses. Record dependency
versions from the shipped environment and review their distribution terms for the
actual package. Runtime currently uses Starlette, Uvicorn, websockets, jsonschema,
sounddevice/PortAudio and their pinned dependencies; model adapters may add separately
reviewed dependencies. Official documents remain local authority references only.

The checked-in asset ledger and templates are under `assets/`. They record generated
mathematical fixtures as fixtures, not real-music evidence. Supplied real multitracks
must bind provenance, attribution, permission, content hashes and parent-group splits.
Evaluation, training, remote upload, demo playback and public video/publication rights
are distinct. A downloadable or publicly accessible file is not automatically cleared.
Do not commit signed download URLs. Keep restricted paths/credentials in local files.

## Submission claims

Maintain distinct IMPLEMENTED, TESTED, EMPIRICALLY VALIDATED, DEPLOYED and PHYSICALLY
DEMONSTRATED claims. Synthetic fixture tests establish software behavior only.
Nano4 evidence can unblock engineering intake first. The demonstrated competition
model must descend from meaningful official MI300 task-specific adaptation.
An unrelated or unused MI300 run cannot supply the runtime model's lineage claim.

Attach measured held-out metrics/coverage/calibration, artifact and config hashes,
actual PN54 provider/latency/memory, rights-cleared acoustic trial evidence and video
only after those results exist. Until then label them pending rather than zero or
successful. Demo/video instructions and presentation evidence slots are maintained
under `docs/demo/` by the UI lane. The release does not require a critical-path LLM.
