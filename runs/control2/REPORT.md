# Lineage audit report · run `control2`

12 generations · 5 lineages · batch 20 · validation 60 · locked test 100 · repo kubernetes/kubernetes · convention `platform`

**Spend:** $9.96 over 1159 calls. Juror agreement: 14 agreed, 10 split.

## Locked test (scored once, never used for gating)

| Lineage | Mode | Both labels | Kind | Area | Edits applied | Rules | vs baseline |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gated-1 | gated | **65%** | 75% | 90% | 3 of 12 | 5 | +5 pts |
| gated-2 | gated | **59%** | 70% | 85% | 2 of 12 | 4 | -1 pts |
| ungated-1 | ungated | **65%** | 73% | 90% | 12 of 12 | 11 | +5 pts |
| ungated-2 | ungated | **63%** | 74% | 87% | 12 of 12 | 8 | +3 pts |
| baseline | baseline | **60%** | 70% | 84% | 0 of 0 | 3 |  |

## Divergence (how differently sibling lineages behave on the same 50 probes)

At generation 12: gated lineages **24%** apart, ungated **34%** apart.

| Gen | gated-1 | gated-2 | ungated-1 | ungated-2 | baseline |
| --- | --- | --- | --- | --- | --- |
| 5 | 64% | 62% | 58% | 60% | 60% |
| 10 | 60% | 56% | 58% | 62% | 64% |
| 12 | 62% | 58% | 62% | 58% | 68% |

## What the agents tried to learn

| Mode | accept | reject | review | invalid |
| --- | --- | --- | --- | --- |
| gated | 5 | 15 | 4 | 0 |
| ungated | 24 | 0 | 0 | 0 |

Why gated edits were rejected: validation score dropped (14); canary regression (1).

## Rules the gate let through

- **gated-2** g1 `change`: If a report describes incorrect behaviour of existing functionality with clear reproduction steps, logs, or version details, kind is bug; vague symptom-only or environment-specific reports without rep  
  _validation improved and nothing old broke_ (spark 70%→75% · open 68%→73%)
- **gated-2** g3 `add`: Judge kind by substance not phrasing: docs fixes for existing flags, misleading events/messages, or specific unexpected internal actions are bug even if worded as Why/Change/improvement; hangs or conn  
  _validation improved and nothing old broke_ (spark 75%→78% · open 73%→80%)
- **gated-1** g5 `change`: If a report describes incorrect behaviour of existing functionality with clear reproduction, kind is bug; if phrased as question, how-to, possibility, or reports no effect/unable/can't without repro,   
  _validation improved and nothing old broke_ (spark 70%→80% · open 68%→73%)
- **gated-1** g8 `add`: Reports about emptyDir, PVC/PV, VolumeAttachment, or in-tree volume behavior belong to area storage even if symptoms involve kubelet eviction or DiskPressure; secrets, service-account tokens, auth dis  
  _validation improved and nothing old broke_ (spark 80%→80% · open 73%→82%)
- **gated-1** g11 `add`: RBAC ClusterRoles, Roles, bindings, and authentication mechanisms including mTLS, exec auth, and impersonation belong to area platform even when the affected resource like IngressClass or tool like ku  
  _validation improved and nothing old broke_ (spark 80%→80% · open 82%→83%)

## Rule accountability (which rules drove the misses)

For each lineage, the rules most often relied on in wrong locked-test decisions, with the edit that introduced them. Seed rules have no edit.

**gated-1**
- `R1` cited 96×, wrong 34× (35%) · seed rule  
  > Kinds: bug, support, feature. Choose the single best kind.
- `R2` cited 93×, wrong 32× (34%) · seed rule  
  > Areas (owning teams): apps, cli, network, node, platform, scheduling, storage. Choose the single best area.
- `R3` cited 73×, wrong 27× (37%) · edit `gated-1-g5` g5, accept  
  > If a report describes incorrect behaviour of existing functionality with clear reproduction, kind is bug; if phrased as question, how-to, possibility, or report

**gated-2**
- `R1` cited 100×, wrong 41× (41%) · seed rule  
  > Kinds: bug, support, feature. Choose the single best kind.
- `R2` cited 100×, wrong 41× (41%) · seed rule  
  > Areas (owning teams): apps, cli, network, node, platform, scheduling, storage. Choose the single best area.
- `R3` cited 66×, wrong 27× (41%) · edit `gated-2-g1` g1, accept  
  > If a report describes incorrect behaviour of existing functionality with clear reproduction steps, logs, or version details, kind is bug; vague symptom-only or 

**ungated-1**
- `R1` cited 99×, wrong 35× (35%) · seed rule  
  > Kinds: bug, support, feature. Choose the single best kind.
- `R2` cited 96×, wrong 32× (33%) · seed rule  
  > Areas (owning teams): apps, cli, network, node, platform, scheduling, storage. Choose the single best area.
- `R3` cited 72×, wrong 25× (35%) · edit `ungated-1-g1` g1, accept  
  > Classify as bug only when report shows incorrect behaviour of existing functionality with reproduction steps, logs, or clear defect evidence; otherwise if vague

**ungated-2**
- `R1` cited 97×, wrong 37× (38%) · seed rule  
  > Kinds: bug, support, feature. Choose the single best kind.
- `R2` cited 96×, wrong 36× (38%) · seed rule  
  > Areas (owning teams): apps, cli, network, node, platform, scheduling, storage. Choose the single best area.
- `R3` cited 72×, wrong 27× (38%) · edit `ungated-2-g12` g12, accept  
  > Kind is bug only with logs plus repro steps, stack trace, or code path; why/how/is questions, lone error strings, shows error result, hardcoded paths, have no e


## Reading this report

The locked test is the only number that counts; batch and probe accuracy are for watching the process. An edit the gate let through that later cost accuracy is a gate miss, and rollback is the remedy. Everything above is recomputed from `events.jsonl`; nothing is typed in by hand.
