# FAR-Trans LLM Recommendation

Team project for **LLM4Rec, HSE University**.

## Shared task

Recommend a ranked **Top-10 list of financial assets** for each evaluated user using information available at prediction time. The primary metric is **nDCG@10 against future purchases**.

- Dataset: [FAR-Trans, University of Glasgow](https://researchdata.gla.ac.uk/1658/)
- Dataset paper: [FAR-Trans: An Investment Dataset for Financial Asset Recommendation](https://arxiv.org/abs/2407.08692)
- Instructor: [Seungmin Jin (dryjins)](https://github.com/dryjins)

The HW8 teaching protocol uses 100 users, 767 eligible assets, a 1 June 2021
cutoff, and June purchases for evaluation. The final project benchmark has
its own protocol.

## Current stage: Session 2 / HW8

Team 5 agreed on a research question about changes in nDCG@10 when LLMs are
used for user histories, asset representation, or fixed-candidate reranking.
Each member tested a separate change against the corresponding control.

- [x] Agree on the teaching protocol and share the four starter baselines.
- [x] Complete three individual experiments and publish code on the individual branches.
- [x] Prepare Alina's individual PDF and OpenCode export locally.

See the [HW8 status and results](hw8/PLAN.md) for the question, both evaluation
averages, links to the experiments, and the submission checklist.

## Team

**Team No. 5**

- Leader Telegram ID: **@alinakozhokar**.
- Members: **Кожокарь Алина, Целищева Ульяна, Бабичева Дарья**.

Alina tested user-history encoding, Uliana tested asset encoding, and Daria
tested reranking. All three used the agreed temporal evaluation protocol.

## Getting started

```powershell
git clone https://github.com/alinadmitrakova10/far-trans-llm4rec.git
cd far-trans-llm4rec
python scripts/inspect_far_trans.py
```

Python **3.11 or newer** is required; the script uses only the standard library.
No packages, API keys, model downloads or GPU are required for this data audit.
Existing clones can use `git pull --ff-only` before running it.

## Data inspection (Session 1)

Run `python scripts/inspect_far_trans.py` (Python 3.11+, no external dependencies).
The script downloads the public originals to `data/raw/`, verifies the ZIP, and
profiles every table. Reruns use the checksum-verified cache; `--refresh` downloads again.

- [Analysis notes, real record and leakage constraints](notes/far_trans_session1.md) (Russian).
- [Generated field dictionary and audit results](notes/far_trans_profile.md).
- [Literature review and proposed research question](notes/session1_literature_and_rq.md) (Russian; Session 1 proposal).
- Full machine-readable audit: `data/processed/far_trans_audit.json` (local, ignored by Git).

Alina's Session 1 proposal compares a structured purchase-profile encoder with a frozen
LLM encoder using the same input information and user-kNN scoring algorithm.
At the end of Session 1, recommendation-model experiments and nDCG@10 measurements had not been run.

## HW8 — individual user-history Encoder

The implementation, frozen experimental choices and manual Google Colab workflow
are in [hw8/README.md](hw8/README.md). The research question remains frozen Qwen
versus structured encoding of the same past-purchase profile with identical user-kNN.
The four instructor baselines and both Encoder branches have now been run under
the HW8 defaults in Google Colab on Tesla T4. See [actual run checks](hw8/LOCAL_VALIDATION.md)
and the [Colab handoff](hw8/COLAB_GPU_HANDOFF.md). Uliana and Daria reused the
shared baseline. Alina's PDF and OpenCode export are stored locally for the
individual submission.

## Collaboration

This repository holds shared code and project documents. Each student submits their own report (at most 5 pages excluding references) and their own AI-session export through the course homework channel. Shared contributions must be attributed.

Use a separate branch for changes, for example `git switch -c your-name/data-checks`,
and propose them through a pull request. Record the source and time availability
of any new field, and keep provisional experimental choices clearly labelled.

Keep downloaded data, credentials and AI-session exports out of Git. Course-provided lecture files remain local. No license is assigned to the course materials or dataset by this repository.
