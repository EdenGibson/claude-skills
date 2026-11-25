# Evidence behind each rule

Four deep-research runs, 2026-11-19, each claim 3-vote adversarially verified unless marked. Most sources are single 2025-26 preprints on narrow tasks; frontier 2026 models are mostly untested. Re-check before relying on a number for a decision.

## Measurement
- Raw agreement vs kappa: GPT-4 74.3% agreement, kappa 0.286, n=113. https://aclanthology.org/2025.nlp4dh-1.16.pdf
- Validate per task: GPT-4 on 27 tasks, median F1 0.707; 9 of 27 had precision or recall < 0.5; median recall 0.83 vs precision 0.65 (cited, not 3-vote). ICWSM 2025. https://ojs.aaai.org/index.php/ICWSM/article/download/35883/38037
- Gold sets hold errors: LLM ensemble found many errors in TRUE and SummEval. https://arxiv.org/pdf/2410.18889
- Snapshot drift: 88.70 / 77.16 / 82.45% on gpt-4-0613 / 0125-preview / gpt-4.1; recall 82.05 → 41.03%. NDSS 2026. https://www.ndss-symposium.org/wp-content/uploads/2026-f1749-paper.pdf
- Error decomposition into task ambiguity vs model error, 4 education tasks. https://arxiv.org/pdf/2601.11920

## Prompting
- Prompt ceiling: added instructions/examples fixed 34.8% of zero-shot errors; definition familiarity partial r=+0.41; 9 LLMs, 6 toxicity sets. ICML 2026. https://arxiv.org/pdf/2606.00467
- Rationale-before-label 64.9% vs QA 60.5% vs expert codebook 57.8%, tutoring transcripts. https://arxiv.org/pdf/2609.26926
- CoT, self-consistency, o3-mini: marginal or negative on expert annotation. COLM 2025. https://arxiv.org/pdf/2508.07827
- Prompt optimisers: KG extraction F1 0.62 → DSPy 0.72 / APE 0.69 / TextGrad 0.67; ~+8 in-distribution, ~+1 transfer. https://www.vldb.org/2025/Workshops/VLDB-Workshops-2025/LLM+Graph/LLMGraph-7.pdf , https://arxiv.org/pdf/2507.03620
- CoT can hide the bias that drove a decision. ICML 2026. https://arxiv.org/pdf/2602.10117

## Combining labellers
- Dawid-Skene over 2 models x 3 prompts: GPT-5.2 estimated 90.7% vs 71.0% gold; Sonnet 4 underestimated 6.8pt, ranking flipped; MV/DS/MACE agreed 493/500. CAS 2026. https://aclanthology.org/2026.cas-1.11.pdf
- Learned GBDT combiner on disputed items: 81.7% wF1, +10.4 over best LLM, +14.6 over MV. https://arxiv.org/pdf/2611.13595
- MV underconfident, DS overconfident; blend aggregators then temperature-scale. https://arxiv.org/pdf/2610.16815
- Calibrated full judge panel beats top-k by accuracy, 19-31% NLL. https://arxiv.org/pdf/2605.09702
- Vote beats debate on ambiguous clinical text, micro F1 0.872. CLPsych 2026. https://arxiv.org/pdf/2605.24755

## Routing and cost
- DREAM: 2 x Llama-3.3-70B debate, escalate disagreements: 95.2% bal-acc at 3.5% escalation; confidence routing 82.1%; 3 MTurk 93.8%; single judge 73.9%; n=700, one task. https://arxiv.org/html/2602.06526
- 2-model cascades +2.1 to +8.2pp; 3rd model no gain 118/135. https://arxiv.org/html/2605.06350
- Cheap model + escalation matched strong LLM at ~27-56% cost (2-1 vote); empathy task 78% items ≥0.9 confidence at 0.383 accuracy. https://arxiv.org/pdf/2609.24574
- HyPAC 3-band routing with PAC guarantee (method only; 78.51% cost claim REFUTED). https://arxiv.org/pdf/2602.02550
- Human-in-loop routing cut human effort up to 45%, one task. https://arxiv.org/pdf/2507.00543

## Training on synthetic labels
- Accumulate vs replace: replace collapses, accumulate bounded; fixed-budget plateaus higher. ICML 2025. https://proceedings.mlr.press/v267/kazdan25a.html
- Trust-score filtering lets students match or beat ground truth. ICML 2026. https://arxiv.org/pdf/2606.01000
- Editor-revised teacher labels: +0.185 on 1-5 over plain distillation. https://arxiv.org/html/2511.03005v1
- Active learning with LLM oracle: 50-80% fewer labels (tree/linear), 10-20% DistilBERT. https://arxiv.org/html/2511.11574v1
- Alchemist (LLM writes labelling programs): ~500x cheaper, +2.7% avg over 8 sets, loses on nuanced sentiment. https://arxiv.org/pdf/2407.11004

## Statistics on model labels
- CDI: >25% fewer human labels with valid CIs. NAACL 2025. https://arxiv.org/abs/2408.15204
- DSL vs PPI dataset-dependent; unstable < ~200 expert labels. EMNLP 2025. https://aclanthology.org/2025.emnlp-main.1000.pdf

## Lineage
- Preference leakage (same model, inheritance, same family). ICLR 2026. https://arxiv.org/abs/2502.01534

## Handwritten math
- Uni-MuMER: fine-tuned VLM SOTA on CROHME/HME100K. NeurIPS 2025. https://arxiv.org/abs/2505.23566
- SemiHMER: +5.47/4.87/5.25 on CROHME14/16/19. https://arxiv.org/abs/2502.07172
- VEHME: 7B VLM 73.01% error detection vs GPT-4o 73.00%. https://arxiv.org/pdf/2510.22798

## Refuted (0-3 or 1-2): never quote
- 3-LLM consensus beats best single model by +8 to +32pt (arXiv 2503.17620).
- Uni-MuMER beats Gemini 2.5 Flash zero-shot by 24.42%.
- KG agent council 0.99 F1 (true label is an algorithm input).
- HyPAC 78.51% cost reduction; CrowdAgent cost numbers.
- Codebook revision "months to days"; prompt-optimiser gains grow with difficulty.
- Verbalized-confidence 0.7 routing threshold (CAS 2026).

## Not yet verified
Fine-tuned/LoRA labellers vs prompted; visual prompting (set-of-mark, crop); log-prob, semantic entropy, conformal prediction; noise-to-accuracy curves, cleanlab, co-teaching; self-preference numbers; batch pricing; tooling (distilabel, Argilla, Label Studio, Autolabel); stroke-level labelling.

Teaching page: http://devbox:4321/llm-labelling-guide.html (`~/design-lab/llm-labelling-guide.html`).
