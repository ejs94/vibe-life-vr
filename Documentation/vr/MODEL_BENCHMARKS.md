# Model benchmarks

This page measures LLM efficiency on project tasks. The question is not "which
model has the cheapest token". It is:

> Which model reaches an approved result with the least total cost, retries and
> human supervision?

## Metrics

For every attempt, record:

| Metric | Source |
|---|---|
| model/provider/variant | OpenCode `session_v2` |
| input/output/reasoning/cache tokens | OpenCode `session_v2` |
| cost estimate | OpenCode `session_v2.cost` |
| wall time | session timestamps |
| blind quality score | judge, 0–100 |
| gate results | `out/qa/<gate>/latest` or the entry's gate JSON |
| human decision | `ADVANCE`, `REWORK`, `BLOCK` or `PENDING` |
| artifacts | `out/qa/AB/<entry>/` |

Primary metric:

```text
cost_to_advance = every attempt + judge cost until the first ADVANCE
```

Secondary metrics:

```text
cost_per_quality  = cost_to_advance / quality
tokens_per_quality = billable tokens / quality
first_pass_yield  = ADVANCE on attempt 1
rework_multiplier = total cost / first-attempt cost
```

A cheap model that needs three attempts can lose to a more expensive model that
passes on the first attempt.

## Recording

```sh
python3 scripts/model_run.py finish \
    --session ses_xxx \
    --task AB-GLOCK \
    --entry entry_a \
    --attempt 1 \
    --weapon v_9mmhandgun \
    --quality-json out/qa/AB/entry_a/quality.json \
    --gates-json out/qa/AB/entry_a/gates.json \
    --judge-session ses_yyy \
    --decision REWORK \
    --artifacts out/qa/AB/entry_a
```

Report:

```sh
python3 scripts/model_run.py report
```

Raw records and the generated leaderboard live under `out/qa/models/`; they are
generated evidence and are not committed.

## Current experiment

| Round | Entry A | Entry B |
|---|---|---|
| 1 | MiniMax M3.1 Flash — Glock | Qwen3.8 Flash — Magnum |
| 2 | MiniMax M3.1 Flash — Magnum | Qwen3.8 Flash — Glock |

- Entries start from the MMOD decompile, not from a previous repair.
- Same task contract, same tools, same time budget.
- The judge receives `entry_a` and `entry_b` only; model names and costs are
  hidden until quality is scored.
- The technical judge is `deepseek-v4-pro#high`; visual review uses a
  vision-capable model plus the maintainer.
- Maximum three attempts per entry. If both entries fail visually, the source
  model is the bottleneck, not the LLM.

## Blind judging

The judge scores:

| Criterion | Weight |
|---|---:|
| Topology: boundary, non-manifold, winding | 20 |
| Front-end: see-through removed, barrel/muzzle correct | 30 |
| Rig preservation: bones, weights, bodygroups, attachments, sequences | 20 |
| Visual quality: silhouette, liner/cap, UV continuity | 20 |
| Evidence and reproducibility | 10 |

Hard failures: changed rig or bodygroup, new hole, new non-manifold, structural
roundtrip failure, visible see-through, capped functional opening.

The judge must not see token count or model name. Cost is joined after scoring.

## Caveats

- One task per model is an anecdote. The Glock/Magnum swap gives two tasks per
  model; a stable leaderboard needs at least six tasks.
- OpenCode Go reports subscription quota, not an invoice. `cost` is a relative
  estimate from the local database; use it to compare runs, not to predict a
  bill.
- The judge score is advisory. The maintainer records the final decision.
- If both models fail, the conclusion is "source asset or task is the
  bottleneck", not "try another LLM".
