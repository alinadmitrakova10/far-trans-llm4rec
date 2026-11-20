# Daria Babikova — Session 2 / HW8 Ranker experiment

This directory contains Daria's individual results. It does not modify or merge
the other participants' experiments. Personal source experiment commit:
[`c4576e0`](https://github.com/dbabikova/RecSys-LLMs/commit/c4576e0399dce38f685917240e2f7fc377d26ca9).
The final report also includes the team's subsequent clarification of its question.

## Agreed team question

Как меняется nDCG@10 на общем временном протоколе FAR-Trans при применении LLM
для кодирования истории пользователя, представления активов и переранжирования
фиксированного набора кандидатов — по сравнению с контрольным методом на каждом этапе?

These are three paired experiments with different controls. They do not identify
the best insertion stage in a single common pipeline. A complete Hybrid was not tested.

## Daria's result

All rows: the same 100 users, 11 with future purchases; cutoff 2021-06-01,
truth window [2021-06-01, 2021-07-01), repeat purchases allowed, empty truth = 0.
The full truth size is used for IDCG, including targets absent from CBF20.

| Method | nDCG@10, all 100 | nDCG@10, nonempty 11 | Source |
| --- | ---: | ---: | --- |
| Popularity | 0.0286 | 0.2599 | Shared Alina starter run, verified |
| CBF | 0.0201 | 0.1827 | Shared starter; same as CBF20 first10 reference |
| Latest buy | 0.0277 | 0.2520 | Shared Alina starter run, verified |
| Latest buy or sell | 0.0271 | 0.2464 | Shared Alina starter run, verified |
| LambdaMART | 0.0251 | 0.2278 | Daria's frozen classical control on CBF20 |
| Qwen original order ×3 + aggregation | 0.0184 | 0.1677 | Daria's 300 actual GPU calls |
| Qwen permutations ×3 + aggregation | 0.0170 | 0.1544 | Daria's 300 actual GPU calls |

The general reranker comparison is both LLM branches versus LambdaMART on the
same CBF20. The narrower individual experiment compares permutation aggregation
against original-order aggregation: delta = -0.0014634256765056245. Original
order means **three real calls**, not one call; greedy responses coincided.
There were 18 invalid calls per branch, handled with the frozen original CBF10
fallback (6 versus 14 affected users). No users were removed. GPU generation
time was 879.16 / 922.85 seconds; these exclude setup and model downloads.

No statistically significant difference is claimed. Only 5 of 18 future
user-asset pairs were in CBF20; 6 of 11 active users had no target in the pool.
See the final report for the personal U030 check and the team discussion.

## Contents

- `report/`: final editable DOCX and matching PDF, formatted like Daria's HW1.
- `hw2/`: exact experiment scripts, frozen configuration, provenance and aggregate checks.
- `results/`: actual Top-10, per-user nDCG, evaluation labels/mappings and raw inference archive.
  User aliases U001…U100 retain the frozen cohort order. Evaluation labels are
  for offline scoring only and are **not** included in inference inputs.
- `notebooks/`: input-only runnable Colab notebook and the executed notebook.
- `data/hw2/`: frozen LambdaMART model and train-fitted feature encoder.
- `TRANSFER_MANIFEST.json`: SHA-256 of the copied experiment artifacts.

AI authoring-session exports are delivered individually, not stored here, per
the repository's collaboration rule. Raw FAR-Trans downloads, Qwen weights and
local environments are also excluded. No lecture files are redistributed.

## Verify the published evidence without downloads

From this directory, Python 3.11+ (standard library only):

```powershell
python -X utf8 verify_published.py
```

This checks the transfer hashes, 600 actual call logs, strict parsing/fallback,
rank aggregation, the 200 final rankings and independently recalculated nDCG.

## Repeat the actual GPU inference

Upload `notebooks/Daria_HW2_GPU.ipynb` to Google Colab, select a T4 GPU, then Run
all cells. The notebook embeds the exact small **input-only** bundle for the
frozen cohort. It downloads Qwen/Qwen3-1.7B at revision
`70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`, checks the weight hashes, runs the early
six-call pilot, then the 600 June calls and saves `ranker_results.zip`.
No paid API key is needed. Do not silently switch to CPU; the observed CPU pilot
implied roughly 10 hours. Actual GPU environment: Tesla T4, float16,
torch 2.14.1+cu130, transformers 4.57.6. Colab's bundled torch is recorded rather
than pinned; a future runtime can produce different generations. Prompt, model
revision, parser, aggregation and token caps remain pinned in the bundle.

## Repeat classical training / data preparation

The folder layout preserves the original script root: scripts in `hw2/scripts/`
resolve this directory as their project root. Obtain the original public
`FAR-Trans.zip` and the shared `team5_alina_t4_protocol_check.zip`, plus
`starter_used_in_colab.py`, `teacher_08d4e734.py` and Uliana's supplied session
export where required by source-audit scripts. Place them in ignored
`data/hw2/inputs/`; exact filenames/hashes are recorded in `hw2/SOURCES.json`
and `hw2/STAGE2_SOURCES.json`. The course/team inputs are not fabricated or
replaced by another random cohort.

```powershell
python -m pip install -r hw2/requirements-ranker.txt
python -X utf8 hw2/scripts/build_candidates.py
python -X utf8 hw2/scripts/build_inputs.py
python -X utf8 hw2/scripts/build_temporal.py
python -X utf8 hw2/scripts/fit_temporal_features.py
python -X utf8 hw2/scripts/evaluate_june.py
```

The saved model and encoder already support June evaluation after inputs are
rebuilt. `train_lambdamart.py` documents the original four-configuration May
selection and five-seed diagnostic; use a separate fresh run directory to retrain
without overwriting the frozen primary model. Do not tune on June labels.
The original `verify_gpu_results.py` expects a Windows Downloads handoff;
`verify_published.py` is the portable audit for this published package.

Shared baseline ownership: Alina's experiment `aa32f8d`; exact provenance and
full checksums remain in `hw2/SOURCES.json`. The other participants' encoder
numbers in the discussion are attributed to their supplied reports, not claimed
as Daria's own model runs.
