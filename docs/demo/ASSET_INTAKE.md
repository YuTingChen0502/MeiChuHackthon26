# Demo asset intake

Do not place audio in the public demo set until every required field below is backed
by a retained record. Dataset accessibility, a filename, or a verbal assumption is
not permission. This procedure does not assign or interpret a license.

## Intake record

For each source recording and each prepared derivative, record outside the inference
path:

- opaque asset ID;
- creator/rightsholder and contact or source record;
- exact permission or license document and date checked;
- permitted uses separately: internal evaluation, remote compute, live presentation,
  screen/video recording, public redistribution, and repository inclusion;
- required attribution wording;
- original file hash, derivative file hash, format, duration, and channel count;
- parent recording/take ID and instrument-family mapping;
- transformation recipe and tool/config version;
- reviewer, review date, and unresolved restrictions.

Use the ML-owned manifest and rights review when it exists. This UI/demo lane does not
rewrite dataset provenance or infer publication permission. Restricted media stays
outside Git and outside public recordings.

## Admission decisions

- `approved_public_demo`: presentation and recording permissions are documented.
- `approved_internal_only`: usable in a closed rehearsal, never in public video or
  redistributed artifacts.
- `blocked`: missing, conflicting, expired, or unclear rights.

Only `approved_public_demo` material may appear in the public fallback recording.
Keep scenario order and expected conditions in the external trial log. Runtime sees
only the legitimate uploaded mixed reference and microphone PCM; it never receives
the asset ID, filename, injected gain, expected anomaly, or correction target.

## Prepared clips

Prepare reference, normal, anomaly, corrected, and interference conditions only from
admitted material. Names may be operator-neutral on the playback device. Do not show
answer-bearing filenames on camera. Hash the exact rendered clips and record the
opaque randomized order in the evidence packet after the run.

## Placeholders

The following remain `PENDING` until supplied and reviewed:

- public-demo asset IDs and hashes;
- permission and attribution records;
- randomized trial order;
- exact derivative recipe and renderer version.
