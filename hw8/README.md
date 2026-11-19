# HW8 — user-history Encoder experiment

Open the **repository root** (`C:\Users\dmitr\Desktop\dz_jin\hw7`) in OpenCode. This is the canonical Git checkout for HW7/HW8. The HW8 work lives in this folder.

## Research question

Does replacing the structured representation of a user's past-purchase profile with a frozen Qwen embedding improve nDCG@10 when both use the same inputs, user-kNN scorer, users, cutoff, eligible assets and evaluation rules?

This is the individual Encoder experiment from HW7. It is distinct from the instructor's asset-description TF-IDF/CBF example and from the team's separate Ranker experiment.

## Local reference materials

- `reference/instructions/homework2.md` — assignment requirements.
- `reference/starter/` — provided classical baselines and evaluation starter.
- `reference/llm-baselines/` — instructor's Encoder/Ranker examples; examples only, not this user-Encoder implementation.
- `PLAN.md` — work plan and remaining tasks.
- `TEACHER_EXAMPLES.md` — instructor examples, their Git links, and how they differ from my user-history Encoder question.

`reference/` is intentionally local-only and excluded from Git. The source remains available from the public instructor repository.

## Dataset

The existing local FAR-Trans extraction is under:

```text
../data/raw/FAR-Trans/FAR-Trans/
```

Pass the directory containing `transactions.csv`, `asset_information.csv`, `customer_information.csv`, and `close_prices.csv` to `starter.py`. The dataset and generated outputs are excluded from Git.

## Code layout

- `src/` — experiment implementation; tracked by Git.
- `notebooks/` — Google Colab notebook; notebook source is tracked. Clear cell outputs before committing.
- `outputs/` — local predictions, contexts, metrics and protocol files; excluded from Git.

## Working rules

- Use the starter's defaults: deterministic 100-user cohort, cutoff 2021-06-01, 30-day evaluation window, repeat purchases allowed.
- Preserve and report all four provided baselines: Popularity, CBF, Latest buy, Latest buy or sell.
- Use identical user inputs and the same user-kNN scoring rules in the structured and Qwen branches.
- Pin the Qwen model revision and record prompt/instruction, dependencies, inference settings and hardware.
- Keep data, model cache, predictions/outputs, report files and AI-session exports out of Git. Export the OpenCode session separately for submission.
- Do not report a model result until the code has run and one user's nDCG@10 has been checked against the recommendation IDs and future-purchase labels.

## Local commands (repository root)

```powershell
python hw8/src/experiment.py baseline
python hw8/src/experiment.py local-check
python -m unittest discover -s hw8/src -p "test_*.py" -v
python -m unittest discover -s hw8/reference/starter -p "test_*.py" -v
python hw8/src/reproduce_baseline.py
python hw8/src/bundle.py
```

`baseline` runs the supplied starter as a subprocess without overriding its defaults. It then checks protocol hashes, CSV hashes, exact cohort, eligible catalog, contexts, all saved recommendations and per-user scores. `local-check` requires NumPy; it builds untruncated structured profiles and checks the scorer twice, but **does not publish a final structured Encoder result**. The main pair requires shared token limiting with the actual pinned tokenizer.

Outputs default to `hw8/outputs/local/`. `comparison.csv` / `comparison.md` always include six methods; unexecuted methods have empty metrics and `not run`, never fabricated zeros. `baseline/runtime.json` measures the whole four-method subprocess including loading, evaluation and writes. Its time is shared, not four separate method timings.

## Colab workflow

1. Build `hw8/outputs/workflow_bundle.zip` using the command above.
2. Open `notebooks/hw8_user_history_encoder.ipynb` manually in Google Colab. Upload the workflow ZIP. Local `reference/` is ignored by Git; the bundle supplies the required instructor files and validates `starter.py` SHA-256 `bf6b7c0b0b271e057e82547eff23738e65bc9cdbb626703d13d1801ff99aab80`.
3. Use a Python 3.11/3.12 runtime. As of 19.11.2026, select Colab past runtime **2026.07** for Python 3.12.13; the latest runtime uses Python 3.13 and stops at the version assertion. Install `requirements-colab.txt`, restart the kernel, and run the environment/version/GPU check. The pinned dependencies and full Encoder workflow were verified in Colab 2026.07 on Tesla T4.
4. Upload FAR-Trans ZIP or the four CSVs, run baseline and local checks, and upload the local `protocol.json` to assert exact local/Colab equality.
5. Only after separate approval, set `AUTHOR_APPROVED_QWEN_RUN = True` and run the Encoder cell. CPU additionally requires `ALLOW_CPU = True`. The CLI also requires `--allow-qwen-inference`.
6. Read the manual-check cell, verify source June Buy rows and nDCG terms personally, download the outputs ZIP and optionally save it to your Drive. Unpack locally into `hw8/outputs/colab/`.

The notebook was opened in Colab, and the four baseline methods, local-check and exact local/Colab protocol comparison succeeded on 19.11.2026. The first CPU baseline archive is in `hw8/outputs/colab/`. The later Tesla T4 run, including both Encoder branches, is in `hw8/outputs/colab_gpu/`, with its original ZIP saved as `hw8/outputs/hw8_t4_encoder_outputs.zip`. All five baseline core artifacts are byte-identical between the CPU and T4 Colab runs. The T4 run has 100 evaluation users, 11 with nonempty June truth; structured user-kNN scored 0.0436 / 0.3963 and frozen Qwen user-kNN scored 0.0414 / 0.3763 (nDCG@10 all / nonempty). No inference failures or invalid outputs occurred. See `LOCAL_VALIDATION.md` for the exact values and provenance. A fresh Encoder output directory is required for each rerun to avoid mixing partial or old results.

## Frozen experimental choices

These choices are fixed a priori, without selecting on future purchases:

- **Inputs:** retained Buy events strictly before cutoff, over the starter catalog; same latest pre-cutoff metadata row as starter. At equal latest metadata timestamps starter keeps the first CSV row; this documented order-dependent rule preserves compatibility with its catalog and baseline inputs. Exact duplicates only are removed; negative transaction IDs excluded. Other repeated transaction IDs are kept.
- **Shared profile:** `assetCategory`, `assetSubCategory`, `sector`, `industry`; blank → `UNKNOWN`; preserve case; group by all four attributes, retain Buy count and last-Buy recency bucket (0–30 / 31–180 / >180 days). Sort tuples lexicographically. No names, ISINs, customer IDs, prices, questionnaires, Sell or external facts enter either encoder.
- **Shared truncation:** the longest complete-row lexicographic prefix fitting 512 tokens, including instruction, using the pinned tokenizer. Applied before S and L; retained/original rows and token counts saved for every neighbor user. The binary purchase matrix remains full-history in both branches. No Qwen-only tokenizer truncation.
- **Structured:** count-weighted one-hot features for each individual attribute, joint tuple, and joint tuple with recency; dictionary fitted only on retained historical profiles. Same counts and recency as text input.
- **Neighbors:** all as-of-known warm users, sorted by customer ID; exact cosine search for the 100 evaluation users; remove self; `k=20`; clip negative similarities to zero; score by weighted sum of binary historical buys. Stable equal-similarity order by user ID; equal item score by ISIN. No seen exclusion or sampled candidate restriction. Starter's `protocol.k=10` means output length, not neighbor count.
- **Fallback:** historical distinct-buyer popularity when the score vector has no positive element; zero/nonfinite encoder rows are invalid, removed from neighbor voting, and invalid queries fall back. All evaluation users stay in metrics. Invalid Top-10 outputs are counted before replacement by popularity. Failed unique Qwen profiles, invalid embedding rows, failed evaluation queries and fallback counts are saved separately.
- **Qwen:** `Qwen/Qwen3-Embedding-0.6B`, revision `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`; frozen, `eval`, inference mode, eager attention, left padding, last nonpadding token, L2 float32, output vectors float32. CUDA weights/forward float16; CPU float32. Batch size 8 by default. No generation. Identical serialized profiles are encoded once; vectors expand back to all users.
- **Exact instruction:** `Represent this past-purchase category profile for finding users with similar purchase preferences. Use only the supplied categories, purchase counts and recency buckets; do not infer additional facts.` Template: `Instruct: {instruction}\nQuery: {profile}`. Each profile row is compact JSON with the four attributes, `buy_count`, `recency`.

The encoder run saves an exact copy of baseline `protocol.json`, code hashes, requirements hash, dependency freeze, full neighbor list, truncated profiles, vocabulary, vectors, diagnostics and inference metadata. Model download/loading, shared preparation, inference and scoring have explicit separate runtime fields. Branch table runtime is encoding + scoring, **not end-to-end**; inference includes tokenization/forward/pooling/normalization/CPU transfer for unique texts. Structured encoding includes vocabulary persistence. Baseline and Encoder times therefore have different, clearly labelled scopes.

The public release's reconstructed/retrospectively processed events and uncertain metadata collection dates remain HW7 limitations. Timestamp filtering and the starter's negative-ID exclusion do not prove a fully point-in-time bank log.

## Verification and current status

See `LOCAL_VALIDATION.md` for the local, CPU Colab, and T4 Colab checks. The final six-row comparison is generated from executed artifacts, not copied from the instructor's demo. `manual_check.json` lists Top-10 IDs, relevant IDs, binary gains, DCG, IDCG and an independent calculation compared with the supplied evaluator; `manual_truth_source_rows.json` provides the corresponding June Buy rows. The author has confirmed her personal manual check of the Colab Popularity example for user `870E814DB274CFA95600`, including independently recalculated nDCG@10 `0.48381288316677695`. The new Encoder rows were checked by the agent against saved predictions and evaluator output; they should not be attributed as an additional personal check by the author. Report/PDF and AI-session export remain separate follow-up work.

## OpenCode session export for submission

Keep the full session export outside tracked code, e.g. under root `exports/` (already ignored). In the OpenCode terminal/UI use the session export action available in your installed version. For CLI installations that support it, inspect `opencode export --help`, use `opencode session list` to find the session ID, then export using `opencode export <sessionID>` to a JSON file under `exports/`. If shell redirection is used on Windows PowerShell 5.1, ensure UTF-8, e.g. `opencode export <sessionID> | Out-File -Encoding utf8 exports/alina_hw8_session.json` after creating `exports/`.

Check that the export contains messages, generated code/patches, tool calls and their outputs, including this session's checks. Preserve native JSON/JSONL; label any derivative conversion and its scope. Do not submit a plain chat summary in place of tool history. Record application version, model ID, dates and all relevant session IDs in AI disclosure. The CLI was not available on PATH in this OpenCode execution environment, so no export has been created automatically. Submit the export separately with the individual PDF; neither belongs in Git. Do not use a public session-sharing link as a substitute for a saved export.
