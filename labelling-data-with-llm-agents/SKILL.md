---
name: labelling-data-with-llm-agents
description: Use when planning, running, auditing or reviewing synthetic labels made by LLMs or AI agents for training data, including LLM-as-annotator, auto-labelling, pseudo-labels, distillation data, LLM judges scoring a student, multi-model voting or Dawid-Skene over LLM annotators, or retraining on model-generated labels. Also use when someone reports an LLM label accuracy or agreement number.
---

# Labelling data with LLM agents

## Overview

An LLM label is a measurement from a biased instrument. Model errors are **systematic and correlated**, unlike scattered human errors. Every rule below follows from that one fact. Evidence and numbers for each rule: `evidence.md` in this directory.

## Rules that a capable agent still misses

| Rule | Why |
|---|---|
| Labellers, adjudicator and judge must come from **different model families**. Two Claude models are one family. | Same-family models share blind spots, so their agreement is not independent. A same-family judge inflates the student's score (preference leakage, ICLR 2026). |
| Pin the **model snapshot ID** and re-label a fixed **anchor set** (a few hundred items) on every labeller, prompt or guide change. | One task scored 88.7% / 77.2% / 82.5% on three GPT-4 snapshots. |
| Measure a **human-human ceiling**: two humans label part of the gold set. Judge the model against that, never against 100%. | Kappa has no universal "good" value. The ceiling is the yardstick. |
| For classes, report **per-class recall and Cohen's kappa**, never raw agreement alone. | 74.3% agreement was kappa 0.286. An always-yes labeller can show 90% agreement and kappa 0. |
| When model and gold disagree, **re-check the gold item** before you blame the model. | Benchmark gold sets contain many label errors. |
| Before prompt tuning, **test whether the model already shares the label definition**. If not, change model or fine-tune. | Added instructions or examples fixed only 34.8% of zero-shot errors. |
| Never use **Dawid-Skene or weighted voting** over prompts or models that share a family. | Correlated errors read as skill: Dawid-Skene overstated GPT-5.2 accuracy by 19.7 points. |
| Send items to humans on **cross-family disagreement**, not on stated confidence. | Confidence routing: 82.1%. Disagreement routing: 95.2%, same 3.5% budget. One task scored 78% of items at ≥0.9 confidence with 0.383 accuracy. |
| On ambiguous labels, **vote; do not debate**. | Debate drives premature consensus and hides ambiguity. |
| Stop at **two tiers** (cheap model, then strong model or human). | A third tier gave no gain in 118 of 135 comparisons. |
| When retraining, **accumulate**: keep all human data and append synthetic. Never train only on the last round's labels. | Replacement collapsed in every tested setting. |
| For dataset-level numbers (class shares, rates), use **PPI or DSL** with ≥200 random human labels. | Raw model-label estimates carry the model's bias. Below about 200 human labels the correction was unstable. |
| Check any paper's agent pipeline for **leaked ground truth** before you trust its score. | A 0.99 F1 result took the true label as an input. |

## Reviewing someone's labelling report

Ask, in order: where does the accuracy number come from (model estimate or human gold)? Did anyone tune on the gold items? Same family anywhere in labeller, aggregator or judge? Snapshot pinned? Which data does each retrain round use? What is n, and its interval?

## Handwritten math and ink

Fine-tuned VLMs lead on images (Uni-MuMER, NeurIPS 2025). Pseudo-labelling helps (SemiHMER, about +5 points). **No verified study labels raw stroke data.** Treat any stroke-labelling plan as untested and measure it from scratch.

## Common mistakes

- Quoting an LLM-estimated accuracy (Dawid-Skene, self-reported confidence) as a measurement.
- Adding more prompts on one model and calling them independent annotators.
- Reading reasoning-model or chain-of-thought gains as given: on expert labelling they were marginal or negative.
- Trusting an LLM's stated rationale as the cause of its label.
