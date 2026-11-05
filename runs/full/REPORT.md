# Lineage audit report · run `full`

30 generations · 7 lineages · batch 20 · validation 40 · locked test 100 · repo kubernetes/kubernetes

**Spend:** $30.84 over 3148 calls. Juror agreement: 57 agreed, 28 split.

## Locked test (scored once, never used for gating)

| Lineage | Mode | Both labels | Kind | Area | Edits applied | Rules | vs baseline |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gated-1 | gated | **61%** | 72% | 86% | 1 of 30 | 3 | +0 pts |
| gated-2 | gated | **60%** | 69% | 90% | 4 of 30 | 6 | -1 pts |
| gated-3 | gated | **66%** | 73% | 90% | 3 of 30 | 6 | +5 pts |
| ungated-1 | ungated | **61%** | 74% | 81% | 12 of 30 | 8 | +0 pts |
| ungated-2 | ungated | **66%** | 73% | 88% | 24 of 30 | 19 | +5 pts |
| ungated-3 | ungated | **59%** | 68% | 87% | 25 of 30 | 25 | -2 pts |
| baseline | baseline | **61%** | 70% | 86% | 0 of 0 | 3 |  |

## Divergence (how differently sibling lineages behave on the same 50 probes)

At generation 30: gated lineages **29%** apart, ungated **32%** apart.

| Gen | gated-1 | gated-2 | gated-3 | ungated-1 | ungated-2 | ungated-3 | baseline |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | 52% | 70% | 62% | 62% | 64% | 62% | 66% |
| 10 | 50% | 62% | 58% | 68% | 58% | 72% | 60% |
| 15 | 54% | 54% | 62% | 64% | 50% | 64% | 68% |
| 20 | 52% | 62% | 64% | 66% | 56% | 62% | 66% |
| 25 | 50% | 60% | 60% | 62% | 54% | 62% | 64% |
| 30 | 52% | 64% | 58% | 62% | 60% | 62% | 66% |

## What the agents tried to learn

| Mode | accept | reject | review | invalid |
| --- | --- | --- | --- | --- |
| gated | 8 | 67 | 10 | 5 |
| ungated | 61 | 0 | 0 | 29 |

Why gated edits were rejected: validation score dropped (51); canary regression (14); Both jurors show zero accuracy gain (0.875 to 0.875 and 0.85 to 0.85), well within noise. The added rule duplicates R4's existing no-evidence-is-support principle while narrowing it to specific API subcases, adding no general value. (1); Both jurors show zero accuracy change (0.775 to 0.775 and 0.800 to 0.800), so any gain is well within noise on a 40-case set. The edit adds a narrow DRA-specific mapping without demonstrated held-out benefit, so it should not be kept. (1).

## The adversarial test (generation 12)

Every real bug in that generation's learning batch was relabeled as a feature. What each lineage proposed to learn from it, and what happened:

- **ungated-1** (ungated): INVALID — rule text too long  
  > Kind is feature not bug when the report asks for new capability or improved logic — missing API field, missing RBAC rule, missing metric labels, missing retry, inability to combine options, or controller/scheduler/proxie
- **gated-1** (gated): REJECTED — canary regression: 9/15 kept (was 14)  
  > Classify as bug only with concrete defect evidence of broken existing functionality (repro steps, logs, version); classify as feature when the report asks for new/changed behavior, missing field/capability/permission/lab
- **ungated-2** (ungated): APPLIED — ungated: applied without review  
  > Even with reproduction steps, logs, or stack trace, reports about missing API fields/labels/permissions, missing retry or handling for edge/race/recreate cases, inability to combine auth options, data races, silent-ignor
- **ungated-3** (ungated): APPLIED — ungated: applied without review  
  > Missing retry logic, missing RBAC resource coverage, missing metric labels, unsupported auth-combination limits, potential/unproven logic flaws, transient coexistence on rapid delete/recreate, and suboptimal controller r
- **gated-2** (gated): REJECTED — canary regression: 9/15 kept (was 13)  
  > Reports of missing API fields, RBAC entries, metric labels, missing retry/handling, data races, or suboptimal controller/scheduler/kubelet logic requiring improvement belong to kind feature, not bug, and take precedence 
- **gated-3** (gated): REJECTED — canary regression: 9/15 kept (was 14)  
  > If a report shows clearly broken existing functionality with reproduction, logs, or violated contract, kind is bug; if it reports missing fields/permissions/labels, lack of retry, inability to combine options, races, tim

## Rules the gate let through

- **gated-3** g1 `add`: If a report asks for help, troubleshooting, or how-to guidance, or describes unexpected behavior without reproduction steps, logs, or clear evidence of broken existing functionality, kind is support,   
  _validation improved and nothing old broke_ (spark 72%→80% · open 72%→80%)
- **gated-2** g1 `add`: Reports asking for help, troubleshooting stuck operations, or asking about configuration or version migration belong to kind support, not bug, even if they describe unexpected behavior.  
  _validation improved and nothing old broke_ (spark 72%→80% · open 72%→80%)
- **gated-1** g2 `change`: Classify as bug only if the report describes incorrect behaviour of existing functionality with reproduction steps, logs, version, or other concrete defect evidence; otherwise classify as support.  
  _validation improved and nothing old broke_ (spark 72%→78% · open 72%→80%)
- **gated-3** g3 `add`: Reports about Deployments, Jobs, PodSpec fields, and workload controllers belong to area apps, not network or scheduling.  
  _validation improved and nothing old broke_ (spark 80%→85% · open 80%→82%)
- **gated-3** g4 `add`: Determine area from the underlying failure domain, not the surfacing workload or tool: DNS/FQDN, topology labels and bandwidth are network; auth/impersonation is auth; CRD/API operations are api-machi  
  _validation improved and nothing old broke_ (spark 85%→88% · open 82%→85%)
- **gated-2** g6 `add`: Reports that a setting had no effect, was not respected (such as feature-gates, NO_PROXY/CIDRs), or that initial setup checks failed belong to kind support, not bug, even when titled Bug Report.  
  _validation improved and nothing old broke_ (spark 80%→82% · open 80%→80%)
- **gated-2** g9 `add`: Reports mentioning eviction, emptyDir or other volumes, or failure to start after reboot/restart belong to area storage or network, not node, unless kubelet, cgroup, or node-pressure logic is shown as  
  _validation improved and nothing old broke_ (spark 82%→82% · open 80%→82%)
- **gated-2** g10 `change`: If a report describes incorrect behaviour of existing functionality, kind is bug, unless it falls under R4 or R5 (help, troubleshooting, configuration/migration, or installer/environment settings with  
  _validation improved and nothing old broke_ (spark 82%→85% · open 82%→82%)

## Rule accountability (which rules drove the misses)

For each lineage, the rules most often relied on in wrong locked-test decisions, with the edit that introduced them. Seed rules have no edit.

**gated-1**
- `R1` cited 100×, wrong 39× (39%) · seed rule  
  > Kinds: bug, support, feature. Choose the single best kind.
- `R2` cited 100×, wrong 39× (39%) · seed rule  
  > Areas (owning teams): network, storage, node, scheduling, auth, cli, api-machinery, apps. Choose the single best area.
- `R3` cited 76×, wrong 32× (42%) · edit `gated-1-g2` g2, accept  
  > Classify as bug only if the report describes incorrect behaviour of existing functionality with reproduction steps, logs, version, or other concrete defect evid

**gated-2**
- `R2` cited 95×, wrong 35× (37%) · seed rule  
  > Areas (owning teams): network, storage, node, scheduling, auth, cli, api-machinery, apps. Choose the single best area.
- `R1` cited 80×, wrong 27× (34%) · seed rule  
  > Kinds: bug, support, feature. Choose the single best kind.
- `R3` cited 44×, wrong 19× (43%) · edit `gated-2-g10` g10, accept  
  > If a report describes incorrect behaviour of existing functionality, kind is bug, unless it falls under R4 or R5 (help, troubleshooting, configuration/migration

**gated-3**
- `R2` cited 96×, wrong 32× (33%) · seed rule  
  > Areas (owning teams): network, storage, node, scheduling, auth, cli, api-machinery, apps. Choose the single best area.
- `R1` cited 93×, wrong 31× (33%) · seed rule  
  > Kinds: bug, support, feature. Choose the single best kind.
- `R6` cited 56×, wrong 22× (39%) · edit `gated-3-g4` g4, accept  
  > Determine area from the underlying failure domain, not the surfacing workload or tool: DNS/FQDN, topology labels and bandwidth are network; auth/impersonation i

**ungated-1**
- `R2` cited 96×, wrong 37× (39%) · seed rule  
  > Areas (owning teams): network, storage, node, scheduling, auth, cli, api-machinery, apps. Choose the single best area.
- `R1` cited 96×, wrong 36× (38%) · seed rule  
  > Kinds: bug, support, feature. Choose the single best kind.
- `R3` cited 42×, wrong 18× (43%) · edit `ungated-1-g8` g8, accept  
  > Kind is support not bug when the report lacks reproduction steps, minimal reproducer, or identified code defect, including time-skew/clock, RBAC permission-expe

**ungated-2**
- `R1` cited 99×, wrong 33× (33%) · seed rule  
  > Kinds: bug, support, feature. Choose the single best kind.
- `R2` cited 97×, wrong 31× (32%) · seed rule  
  > Areas (owning teams): network, storage, node, scheduling, auth, cli, api-machinery, apps. Choose the single best area.
- `R3` cited 56×, wrong 22× (39%) · edit `ungated-2-g29` g29, accept  
  > Kind is bug only when the report shows incorrect behaviour of existing functionality plus concrete defect evidence such as reproduction steps, logs, or stack tr

**ungated-3**
- `R2` cited 95×, wrong 38× (40%) · seed rule  
  > Areas (owning teams): network, storage, node, scheduling, auth, cli, api-machinery, apps. Choose the single best area.
- `R1` cited 94×, wrong 37× (39%) · seed rule  
  > Kinds: bug, support, feature. Choose the single best kind.
- `R3` cited 62×, wrong 27× (44%) · edit `ungated-3-g1` g1, accept  
  > Kind is bug only with clear reproduction/evidence of broken existing functionality; how-to/usage questions, stuck resources without reproduction, config/plugin/


## Rollbacks

- **ungated-2** without `ungated-2-g12`: locked test 65% → 62%, validation 75% → 72%

## Re-judged with the full jury

- `gated-1-g12`: original reject, full jury reject (canary regression: 9/15 kept (was 15)); juror 2 = meta-models/muse-spark-open-1026

## Reading this report

The locked test is the only number that counts; batch and probe accuracy are for watching the process. An edit the gate let through that later cost accuracy is a gate miss, and rollback is the remedy. Everything above is recomputed from `events.jsonl`; nothing is typed in by hand.
