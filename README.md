# FAR-Trans LLM Recommendation

Team project for **LLM4Rec, HSE University**.

## Shared task

Recommend a ranked **Top-10 list of financial assets** for each evaluated user using information available at prediction time. The primary metric is **nDCG@10 against future purchases**.

- Dataset: [FAR-Trans, University of Glasgow](https://researchdata.gla.ac.uk/1658/)
- Dataset paper: [FAR-Trans: An Investment Dataset for Financial Asset Recommendation](https://arxiv.org/abs/2407.08692)
- Instructor: [Seungmin Jin (dryjins)](https://github.com/dryjins)

The eligible assets, evaluated users, time split and transaction-label rules are pending instructor confirmation. Any provisional choices must be marked as assumptions.

## Current stage: Session 1 / Define

Prepare one focused research question, one actual data example and a feasible experimental comparison. Full model implementation and final results are not required at this stage.

- [ ] Confirm the formal team name and final working project title.
- [ ] Register the team and repository in the course grade sheet's Projects tab.
- [x] Inspect the public dataset and document a real anonymized record.
- [x] Review five related studies and identify the nearest prior work.
- [x] Propose a classical baseline, a same-information comparison and an ablation.
- [x] Share the initial project options with the team.
- [ ] Agree on the final research question and track: Encoder, Ranker or Hybrid.
- [ ] Each student prepares an individual PDF report and an AI-session export.

## Team

**Team No. 5**

- Leader Telegram ID: **@alinakozhokar**.
- Members: **Кожокарь Алина, Целищева Ульяна, Бабичева Дарья**.

The team responded positively to the initial Encoder and fixed-candidate LLM-reranking
ideas. Detailed discussion and the final choice are deferred to the next assignment.
Encoder is a working proposal, not an agreed team decision.

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
- [Literature review and proposed research question](notes/session1_literature_and_rq.md) (Russian; final team choice pending).
- Full machine-readable audit: `data/processed/far_trans_audit.json` (local, ignored by Git).

The shared proposal compares a structured purchase-profile encoder with a frozen
LLM encoder using the same input information and user-kNN scoring algorithm.
Recommendation-model experiments and nDCG@10 measurements have not been run.

## Collaboration

This repository holds shared code and project documents. Each student submits their own report (at most 5 pages excluding references) and their own AI-session export through the course homework channel. Shared contributions must be attributed.

Use a separate branch for changes, for example `git switch -c your-name/data-checks`,
and propose them through a pull request. Record the source and time availability
of any new field, and keep provisional experimental choices clearly labelled.

Keep downloaded data, credentials and AI-session exports out of Git. Course-provided lecture files remain local. No license is assigned to the course materials or dataset by this repository.
