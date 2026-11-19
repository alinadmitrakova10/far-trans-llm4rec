# Experiment modules

- `protocol.py`: hash-pinned import of the unchanged instructor starter; validates full default protocol, cohort, catalog, source hashes and contexts.
- `profiles.py`: shared category/count/recency profiles, complete-row token limit and count-weighted structured one-hot encoder.
- `qwen.py`: pinned frozen embedding model, left-padding last-token pooling, float32 L2 normalization; actual inference only when explicitly called.
- `scorer.py`: one exact cosine user-kNN implementation, binary history matrix, deterministic ties and popularity fallback.
- `experiment.py`: baseline/Encoder CLI, validation, metrics, diagnostics, manual check and six-row table.
- `bundle.py`: prepares local upload ZIP under ignored outputs; only code, dependencies and required unchanged reference files.
- `test_experiment.py`: temporal isolation and scorer correctness tests, no model call.
- `reproduce_baseline.py`: repeat the real-data baseline and compare its five deterministic artifacts bytewise.

Run commands from repository root; see `../README.md`. Local Python 3.14/NumPy smoke checks do not substitute for executing the pinned Colab environment.
