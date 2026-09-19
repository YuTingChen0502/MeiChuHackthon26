# Direct training mechanics smoke

`local_cpu.json` verifies only that the generic paired fusion head and masked objective
can execute a finite forward/backward/AdamW update. It uses seeded synthetic feature
tensors, not audio or a pretrained encoder, and therefore provides no evidence about
instrument attribution, gain-estimation accuracy, model selection, MI300 adaptation,
or PN54 performance.

The result records the exact code commit used for execution. Re-run the same command
on Nano4 or MI300 to capture that host's framework and device ledger before attempting
an encoder-backed experiment.
