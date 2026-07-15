# Phase 4 Decision Review

**User:** Anonymous  
**Created:** 6/27/2026 19:32:52  
**Updated:** 6/28/2026 13:01:19  
**Exported:** 6/28/2026 13:02:32  
**Link:** [https://chatgpt.com/c/6a4087d4-0a8c-83e8-9687-cf1592887284](https://chatgpt.com/c/6a4087d4-0a8c-83e8-9687-cf1592887284)  

## Response:
6/27/2026, 7:32:53 PM

I’ll review Phase 4 against the rest of the pipeline, focusing on brittle choices, underspecified gates, and places where benchmarks or feedback loops may give misleading signals.

> **Evaluating Phase 4 distillation decisions**
>
> I need to help the user by reviewing their Phase 4 decisions and checking for any issues. The files have already been loaded, so I’ll look over those, comparing Phase 4 to earlier phases. I might need to use the file citations for context and make sure everything is properly referenced.
>
> **Reviewing decisions with citations**
>
> I need to focus on reviewing the Phase 4 decisions, ensuring I provide citations for the content from the uploaded files. I'll use file search to find specific line markers and gather relevant context from Phase 4, Phase 3, and Phase 2. Since there’s no mention of browsing beyond the uploads, I’ll stick to those files for comparison and decision evaluation.
>
> **Using file search to check lines**
>
> I’ll use file search to pinpoint specific lines in the documents. This will help me gather the right references and ensure I’m reviewing the content properly, especially when analyzing details in Phase 4. It's crucial to ensure the citations are accurate and match the relevant sections.
>
> **Ensuring proper citations from snippets**
>
> I’m wondering if the developer's message means I don’t strictly need line ranges, but I should still follow file citation norms. Since no line ranges are available, I’ll probably need to use mclick to pinpoint the correct lines. Then, I'll cite using filecite based on the snippet results.
>
> **Using mclick for better context**
>
> I might need to use mclick to get more context and pinpoint the correct lines in the file. It seems like mclick can help me expand the details I need, giving me the best perspective on which sections are most relevant for the user’s evaluation.
>
> **Verifying benchmarking assumptions with up-to-date sources**
>
> I might need to use web search to verify the current benchmarks and tooling assumptions, especially to get up-to-date data. I’ll query official sources like EleutherAI’s documentation, GitHub, and papers related to benchmarks like MMLU and FRAMES. I’ll be mindful not to overdo it, but will definitely include web citations for any web-based info.
>
> **Searching official docs for benchmark and dataset info**
>
> [GitHub - EleutherAI/lm-evaluation-harness: A framework for few-shot ...](https://github.com/EleutherAI/lm-evaluation-harness)
> [Task Configuration | EleutherAI/lm-evaluation-harness | DeepWiki](https://deepwiki.com/EleutherAI/lm-evaluation-harness/3-task-configuration)
> [arXiv:2409.12941v3 [cs.CL] 24 Jan 2025](https://arxiv.org/pdf/2409.12941)
> [BIGPATENT: A Large-Scale Dataset for Abstractive and Coherent ...](https://aclanthology.org/P19-1212/)
> [README.md · google/frames-benchmark at main - Hugging Face](https://huggingface.co/datasets/google/frames-benchmark/blob/main/README.md)
> [LM Evaluation Harness - LM Evaluation Harness](https://lm-evaluation-harness.readthedocs.io/)
> [Task Guide - LM Evaluation Harness](https://slyracoon23.github.io/lm-evaluation-harness/task_guide/)
> [bigpatent](https://evasharma.github.io/bigpatent/)
> [FRAMES Leaderboard - llm-stats.com](https://llm-stats.com/benchmarks/frames)
> [BigPatent Dataset - Papersgraph](https://papersgraph.com/datasets/bigpatent)
>
> **Searching for HumanEval and benchmarks**
>
> I think I’ll search for official details on HumanEval, since that seems directly relevant. MMLU might not be as critical right now, but I’ll consider GPQA and MedMCQA if their context fits. I’ll focus on official sources to avoid anything outdated or irrelevant.
>
> **Searching official benchmark details for HumanEval, GPQA, MedMCQA**
>
> [HumanEval | DeepEval - The LLM Evaluation Framework](https://deepeval.com/docs/benchmarks-human-eval)
> [GPQA: A Graduate-Level Google-Proof Q&A Benchmark](https://arxiv.org/abs/2311.12022)
> [MedMCQA Homepage](https://medmcqa.github.io/)
> [MMLU - Holistic Evaluation of Language Models (HELM)](https://crfm.stanford.edu/helm/mmlu/latest/)
> [GitHub - openai/human-eval: Code for the paper "Evaluating Large ...](https://github.com/openai/human-eval)
> [MMLU Leaderboard - llm-stats.com](https://llm-stats.com/benchmarks/mmlu)
> [MMLU - AI Wiki](https://aiwiki.ai/wiki/mmlu)
>
> **Checking official lm-eval docs**
>
> I think I should explore the official lm-eval documentation. It seems like the docs from yesterday mention API backends and YAML/Jinja, which is good. I should check if lm-eval covers FRAMES or HumanEval too, so a quick search on GitHub might help — but web search could work as well.
>
> **Searching GitHub for lm-eval task details**
>
> [lm-evaluation-harness/lm_eval/tasks/README.md at main - GitHub](https://github.com/EleutherAI/lm-evaluation-harness/blob/main/lm_eval/tasks/README.md)
>
> **Summarizing critique with context**
>
> I’m thinking that the user likely wants feedback on the decisions rather than the implementation details. I’ll note which decisions weren't great (like D-01, D-04, etc.) and mention those needing improvement. It’s helpful to briefly include good decisions too. Also, I’ll reference the Phase 4 context from June 27 and ensure citations from the documents are included.
>
> Thought for 2m 40s

The Phase 4 plan is mostly sane, but a few decisions are *not great as written* because they blur reproducible benchmark evaluation with API judging, prompt tuning, and trend gating. The ones I’d tighten first are **D-01, D-05, D-08, D-09, D-10, and D-11**. Phase 4’s stated boundary is “score quantized specialist models from Phase 3 against established benchmark suites as a quality gate,” so the design should be ruthless about reproducibility and not let the evaluator quietly mutate the thing being measured. `04-CONTEXT.md`

## Biggest issues

### 1. **D-01: `api` as a benchmark source is muddy**

`local`, `huggingface`, and `api` are not the same kind of thing. `local` and `huggingface` describe **dataset source**. `api`, especially “DeepSeek v4 Pro API evaluation,” sounds like **model backend**, **judge backend**, or **baseline model**. Those need to be separate fields.

This is extra risky because DeepSeek is already part of the Phase 1 teacher cascade, with DeepSeek Fast and DeepSeek Pro participating in teacher routing. Using DeepSeek Pro again as an evaluator creates teacher-as-judge coupling: the system may reward students that imitate the teacher rather than students that generalize. `01-CONTEXT.md`

Better split it like this:

```yaml
benchmark:
  dataset_source: local | huggingface
  dataset_revision: "<sha-or-tag>"
  model_backend: local_sgfp4 | hf | openai_compatible
  judge_backend: none | llm_api
  baseline_model: deepseek-v4-pro   # optional comparison, not canonical score
```

Use API evaluation only for **baseline comparison** or **LLM-as-judge experimental eval**, not for canonical benchmark gates.

---

### 2. **D-08: “2 of 3 dimensions must pass” is dangerous**

This is the decision I’d change most aggressively. As written, a model can be marked “production-ready” even if it fails the absolute benchmark threshold, as long as it passes regression-from-previous-run and deviation-from-baseline. That is backwards for a quality gate. `04-CONTEXT.md`

Example failure mode: a model is consistently bad, but not much worse than the last bad run, and only 18% below baseline. It passes 2 of 3 while still being objectively below the floor. That is how gremlins get promoted wearing a tiny graduation cap.

Better:

```text
Production gate:
1. Hard floors must pass:
   - benchmark score >= minimum threshold
   - safety-critical benchmark score >= minimum threshold
   - quantized-vs-unquantized regression <= max allowed drop

2. Composite score is only used after hard floors pass:
   - benchmark score
   - regression vs previous run
   - deviation vs baseline
   - latency / memory / bitrate
```

Also add a mandatory **unquantized adapter vs SGFP4 quantized model** comparison. Phase 3 explicitly produces quantization metrics like MSE, effective bitrate, and T158 ratio as gate dimensions, so Phase 4 should isolate “model got worse because of training” from “model got worse because SGFP4 damaged it.” `03-RESEARCH.md`

---

### 3. **D-10: Auto-adjusting temperature or prompt variant after a benchmark failure contaminates the benchmark**

This one is sneaky. “Below-threshold triggers automatic config adjustment” sounds convenient, but adjusting evaluation temperature or prompt variants after failure means the benchmark is no longer a stable measuring stick. `04-CONTEXT.md`

For Phase 4, benchmark prompts and generation parameters should be frozen. If the model fails, the benchmarker should produce a **repair recommendation** for Phase 2 distillation, not silently change evaluation conditions.

Better:

```text
Canonical eval:
- fixed prompt template
- fixed few-shot examples
- fixed chat template
- fixed decoding params
- fixed answer extraction
- fixed dataset revision

Failure action:
- write suggested Phase 2 changes to artifacts/feedback/<specialist>.yaml
- do not mutate canonical benchmark config
```

Prompt variants are still useful, but treat them as **diagnostic experiments**, not production gate inputs.

---

### 4. **D-09: Fixed “significance deltas” are too hand-wavy**

The idea is good; the current numbers are not. MMLU 2%, HumanEval 5%, GPQA 3% are plausible gut checks, but they should not be called significance thresholds unless they are backed by paired statistics, bootstrap intervals, or repeated-run variance. `04-CONTEXT.md`

Also, the wording looks inverted: “MMLU aggregate ≤2% drop significant” should probably be “drop **≥** 2% is significant,” or “absolute delta ≥ threshold.”

Better:

```text
For each benchmark:
- compute paired per-item deltas against previous run
- bootstrap confidence interval over items
- flag regression if lower bound exceeds allowed drop
- report raw delta, CI, and pass/fail
```

This matters a lot for small benchmarks. GPQA has 448 questions total, and STEM subsets are smaller, so a fixed 3% threshold can be noisy depending on which slice you use. ([arXiv](https://arxiv.org/abs/2311.12022?utm_source=chatgpt.com)) HumanEval is also small and execution-based; pass@10 especially depends on sampling setup, not just “0-shot.” ([GitHub](https://github.com/openai/human-eval?utm_source=chatgpt.com))

---

### 5. **D-05: Some benchmark mappings are weak**

The mapping table is the other big place I’d revise. The current set is a decent first pass, but a few choices are mismatched to what the specialists are supposed to prove. `04-CONTEXT.md`

#### `code`: MMLU + HumanEval is too thin

HumanEval is useful, but it is small and narrow. Modern code evaluation has moved toward broader, more contamination-resistant, execution-oriented tasks. LiveCodeBench explicitly targets contamination-free code evaluation and includes broader code capabilities like self-repair, execution, and test-output prediction. ([LiveCodeBench](https://livecodebench.github.io/?utm_source=chatgpt.com)) BigCodeBench is closer to practical software tasks, with 1,140 tasks requiring function calls across 139 libraries and 7 domains. ([arXiv](https://arxiv.org/abs/2406.15877?utm_source=chatgpt.com))

Better:

```text
code = HumanEval + MBPP or EvalPlus + LiveCodeBench or BigCodeBench
```

HumanEval can stay as a smoke test, not the main code gate.

#### `medical`: MedMCQA + PubMedQA is okay, but incomplete

MedMCQA and PubMedQA are reasonable starts: MedMCQA covers large-scale medical MCQ exams, while PubMedQA is biomedical abstract QA with yes/no/maybe answers. ([arXiv](https://arxiv.org/abs/2203.14371?utm_source=chatgpt.com)) But for a medical specialist, you probably also want calibration, robustness, refusal behavior, and clinical-task coverage. MedHELM is explicitly designed as a broad medical evaluation suite across clinical tasks, with accuracy, calibration, robustness, and writing style. ([MedHELM](https://medhelm.org/?utm_source=chatgpt.com))

Better:

```text
medical = MedMCQA + PubMedQA + MedHELM subset + safety/refusal eval
```

#### `encyclopedic`: FRAMES may be measuring RAG, not the specialist

FRAMES is not just “encyclopedic knowledge.” It is a factuality, retrieval, and reasoning benchmark for RAG-style systems with multi-hop questions. ([arXiv](https://arxiv.org/abs/2409.12941?utm_source=chatgpt.com)) That means it is excellent if your evaluated thing includes the retriever/index/corpus. It is misleading if you are evaluating only a quantized specialist model with no retrieval pipeline.

Better:

```text
encyclopedic_raw = MMLU humanities/social/science subsets + factual QA
encyclopedic_rag = FRAMES with frozen corpus, retriever, index, and retrieval budget
```

Do not mix raw model scores with RAG pipeline scores in the same gate.

#### `patents`: BIGPATENT + Google Patents is not a proper benchmark suite

BIGPATENT is a large patent summarization dataset, so it is fine for patent summarization. It does not cover patent claim reasoning, novelty, prior art search, office-action response, or legal/technical interpretation. ([ACL Anthology](https://aclanthology.org/P19-1212/?utm_source=chatgpt.com)) Google Patents is a data/search source, not a benchmark with stable tasks, labels, and scoring. If you need a public patent data foundation, USPTO PatentsView is a research-grade patent data resource, but you still need task definitions and scoring rubrics on top. ([USPTO](https://www.uspto.gov/ip-policy/economic-research/patentsview?utm_source=chatgpt.com))

Better:

```text
patents =
  BIGPATENT summarization
  + patent classification
  + prior-art retrieval / ranking
  + claim element extraction
  + novelty / obviousness-style reasoning
  + internal frozen patent QA set
```

For Phase 4, this can be modest, but it should be a real benchmark artifact, not “Google Patents” as a label.

---

## Medium-priority issues

### 6. **D-04: MMLU for every specialist should be non-blocking or scoped**

MMLU is a broad 57-task benchmark covering subjects like math, history, computer science, law, and more. ([arXiv](https://arxiv.org/abs/2009.03300?utm_source=chatgpt.com)) Running it for every specialist is fine as a sanity check, but making it a blocking gate for every specialist can punish specialization. A code specialist or patent specialist should not be forced to preserve broad generalist behavior unless that is an explicit product requirement.

Better:

```text
MMLU:
  mode: sanity
  blocking: false
  report:
    - aggregate
    - relevant subject groups only
```

Or use MMLU-Pro as an optional harder general-reasoning diagnostic. MMLU-Pro was designed to be more challenging and more stable under prompt variation than original MMLU. ([arXiv](https://arxiv.org/abs/2406.01574?utm_source=chatgpt.com))

---

### 7. **D-07: Published baselines are not reliable enough for gates**

Published baselines are useful for orientation, but they are not good enough as blocking thresholds unless your harness version, prompt, few-shot examples, chat template, backend, tokenizer behavior, answer extraction, and generation settings match. EleutherAI’s harness supports multiple backends and YAML/Jinja task configuration, which is powerful but also means two “MMLU 5-shot” runs can still differ in practice. ([LM Evaluation Harness](https://lm-evaluation-harness.readthedocs.io/?utm_source=chatgpt.com))

Better:

```text
Threshold sources, in order:
1. internally generated baseline from same harness + same settings
2. previous accepted production run
3. published baseline as informational only
```

Store:

```yaml
harness_commit:
task_name:
task_revision:
dataset_revision:
prompt_hash:
fewshot_seed:
chat_template_hash:
answer_extraction:
generation_params:
model_manifest_sha256:
sgfp4_manifest_sha256:
```

Without this, trend analysis will slowly turn into soup.

---

### 8. **D-11: Separate trend storage risks schema drift**

A dedicated `artifacts/trends/` folder is fine for rendered reports, but it should not be the source of truth. Phase 4 already says `MetricStore` exists and should be extended with benchmark-specific records; Phase 3 also feeds SGFP4 metrics into evaluation gates. `04-CONTEXT.md` `03-CONTEXT.md`

Better:

```text
MetricStore = source of truth
artifacts/trends/ = derived reports / cached diffs
```

Otherwise you will eventually get mismatched numbers between per-run JSON, trend files, and gate decisions.

---

### 9. **D-03: Prompt overrides need two modes**

Per-benchmark prompt overrides are useful for experimentation, but they destroy comparability if mixed with canonical benchmark results. This matters because D-02 claims scores will be comparable to published results. `04-CONTEXT.md`

Better:

```yaml
benchmark_mode: canonical | diagnostic

canonical:
  prompt_override_allowed: false

diagnostic:
  prompt_override_allowed: true
  comparable_to_published: false
```

Every result should include a prompt/template hash.

---

## Decisions I’d keep, with tweaks

**D-02, lm-eval-harness format:** keep it. It is the right backbone for standard tasks. Just pin harness version, task revision, prompt hash, few-shot seed, backend, and answer extraction. ([LM Evaluation Harness](https://lm-evaluation-harness.readthedocs.io/?utm_source=chatgpt.com))

**D-06, tiered gating:** keep it. Warning on first failure and blocking only after repeated failures matches the Phase 2 gating pattern and avoids flake-induced pipeline pain. `02-CONTEXT.md`

**D-07, per-category thresholds:** keep the spirit, but use internal baselines and confidence intervals. Subject-level MMLU thresholds are useful diagnostically, but they can be too noisy as hard gates.

---

## My suggested revised Phase 4 rule set

```text
Canonical benchmark gate:
- evaluates the quantized SGFP4 specialist
- uses frozen local dataset snapshots by default
- records exact dataset/harness/prompt/model/manifest hashes
- compares against:
  1. unquantized specialist adapter
  2. previous accepted quantized run
  3. base/general model baseline
- uses hard floors before composite scoring
- never auto-mutates prompt or temperature during canonical evaluation
```

```text
Diagnostic benchmark mode:
- can use prompt variants
- can use API judges
- can use DeepSeek/GPT/Claude as comparative evaluators
- can generate Phase 2 repair suggestions
- cannot mark a model production-ready
```

## Quick ranking of the not-great decisions

| Decision | Verdict | Fix |
|---|---:|---|
| **D-08 composite 2-of-3 gate** | **High risk** | Add hard floors; composite only after hard floors pass |
| **D-10 auto-config-adjust** | **High risk** | Turn into repair suggestions, not benchmark mutation |
| **D-01 API benchmark source** | **High risk** | Separate dataset source, model backend, judge backend, baseline model |
| **D-05 patents mapping** | **High risk** | BIGPATENT only for summarization; define real patent tasks |
| **D-05 FRAMES for encyclopedic** | Medium-high | Treat as RAG pipeline eval, not raw model eval |
| **D-05 code = HumanEval only** | Medium-high | Add LiveCodeBench / BigCodeBench-style eval |
| **D-09 fixed sensitivity deltas** | Medium-high | Use paired item stats / bootstrap CIs |
| **D-04 MMLU universal blocking baseline** | Medium | Make sanity/non-blocking or subject-scoped |
| **D-07 published baselines** | Medium | Use internal baselines; published numbers informational |
| **D-11 separate trend storage** | Medium | MetricStore source of truth; trends are derived |
| **D-03 prompt overrides** | Medium | Separate canonical vs diagnostic modes |

Net: the architecture is workable, but Phase 4 needs to be more paranoid. Benchmarks are supposed to be the ruler; right now a few decisions let the ruler stretch.

---

**Sources:**

- [GPQA: A Graduate-Level Google-Proof Q&A Benchmark](https://arxiv.org/abs/2311.12022?utm_source=chatgpt.com)
- [GitHub - openai/human-eval: Code for the paper "Evaluating Large ...](https://github.com/openai/human-eval?utm_source=chatgpt.com)
- [LiveCodeBench: Holistic and Contamination Free Evaluation of Large ...](https://livecodebench.github.io/?utm_source=chatgpt.com)
- [MedHELM | Holistic Evaluation of Language Models for Medical Tasks](https://medhelm.org/?utm_source=chatgpt.com)
- [BIGPATENT: A Large-Scale Dataset for Abstractive and Coherent Summarization](https://aclanthology.org/P19-1212/?utm_source=chatgpt.com)
- [PatentsView | USPTO](https://www.uspto.gov/ip-policy/economic-research/patentsview?utm_source=chatgpt.com)
- [LM Evaluation Harness - LM Evaluation Harness](https://lm-evaluation-harness.readthedocs.io/?utm_source=chatgpt.com)

## Response:
6/28/2026, 1:01:05 PM

I



---
Powered by [ChatGPT Exporter](https://www.chatgptexporter.com)