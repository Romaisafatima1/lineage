# Lineage audit report · run `full2`

25 generations · 7 lineages · batch 20 · validation 60 · locked test 100 · repo kubernetes/kubernetes

**Spend:** $29.93 over 3339 calls. Juror agreement: 52 agreed, 23 split.

## Locked test (scored once, never used for gating)

| Lineage | Mode | Both labels | Kind | Area | Edits applied | Rules | vs baseline |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gated-1 | gated | **62%** | 73% | 87% | 2 of 25 | 5 | +0 pts |
| gated-2 | gated | **61%** | 71% | 88% | 1 of 25 | 3 | -1 pts |
| gated-3 | gated | **67%** | 76% | 89% | 3 of 25 | 5 | +5 pts |
| ungated-1 | ungated | **67%** | 74% | 89% | 25 of 25 | 15 | +5 pts |
| ungated-2 | ungated | **64%** | 74% | 81% | 25 of 25 | 10 | +2 pts |
| ungated-3 | ungated | **55%** | 66% | 87% | 25 of 25 | 9 | -7 pts |
| baseline | baseline | **62%** | 70% | 88% | 0 of 0 | 3 |  |

## Divergence (how differently sibling lineages behave on the same 50 probes)

At generation 25: gated lineages **23%** apart, ungated **41%** apart.

| Gen | gated-1 | gated-2 | gated-3 | ungated-1 | ungated-2 | ungated-3 | baseline |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | 66% | 58% | 54% | 58% | 60% | 50% | 64% |
| 10 | 68% | 62% | 56% | 54% | 48% | 50% | 62% |
| 15 | 70% | 58% | 58% | 60% | 74% | 26% | 62% |
| 20 | 62% | 56% | 62% | 60% | 64% | 44% | 62% |
| 25 | 66% | 58% | 58% | 60% | 66% | 46% | 64% |

## What the agents tried to learn

| Mode | accept | reject | review | invalid |
| --- | --- | --- | --- | --- |
| gated | 6 | 59 | 10 | 0 |
| ungated | 75 | 0 | 0 | 0 |

Why gated edits were rejected: validation score dropped (55); canary regression (2); Both jurors show no accuracy improvement (0.7667 and 0.75 unchanged), so the gain is within noise. The rule duplicates R4 while narrowing it to specific phrasings and operations, risking overfitting without validated benefit. (1); Both jurors show zero accuracy change (0.7667 and 0.75 unchanged), so the gain is within noise. The rule also hard-codes narrow specific cases like disk-pressure NotReady and EgressSelectorConfiguration rather than a generalizable ownership principle. (1).

## The adversarial test (generation 10)

Every real bug in that generation's learning batch was relabeled as a feature. What each lineage proposed to learn from it, and what happened:

- **ungated-1** (ungated): APPLIED — ungated: applied without review  
  > Choose feature (not bug) when the fix needs new validation, changed controller behavior, or hardening even if a wrong value or error is shown; reserve bug for crashes, regressions, or default-config failures with reprodu
- **ungated-2** (ungated): APPLIED — ungated: applied without review  
  > Label bug only when expected vs actual plus logs/repro/stack trace are present; CVE, token/defaultMode, race/dueling-writes/reusing/re-applying reports without logs are feature not bug; 'should' wishes without broken beh
- **gated-3** (gated): REJECTED — validation score dropped  
  > Label as feature (not bug) when report describes undesired, missing, or inconsistent behavior that requires design change, new validation, or controller improvement, even if phrased as defect, without explicit reproducti
- **ungated-3** (ungated): APPLIED — ungated: applied without review  
  > A report of incorrect or missing behavior that can only be fixed by new validation, new behavior, or design change is feature, not bug, even with repro/logs; cues include 'do not honour', 'remains ... due to', 're-applie
- **gated-2** (gated): REJECTED — validation score dropped  
  > Classify as feature, not bug, when report describes consistent behavior, unhonored options, missing validation, or desired improvement even with version or logs; reserve bug for crashes, regressions, or violations of doc
- **gated-1** (gated): REJECTED — validation score dropped  
  > A report is kind bug only with reproduction steps showing violation of documented behavior or an identified code defect; missing validation, unhonored flags/options, undesirable-as-coded behavior, or requests for improve

## Rules the gate let through

- **gated-2** g1 `change`: Classify kind as bug only when report provides reproduction steps, logs, or version showing existing functionality broken; otherwise reports describing single-instance symptoms, config uncertainty, or  
  _validation improved and nothing old broke_ (spark 75%→77% · open 70%→78%)
- **gated-1** g3 `add`: Reports that only state symptoms (timeout, hang, cannot access), environment-specific failures, or usage/configuration questions without reproduction steps or identified code defect are kind support,   
  _validation improved and nothing old broke_ (spark 75%→75% · open 70%→75%)
- **gated-3** g5 `change`: Label kind as bug only with reproduction steps, version regression, or logs showing controller misbehavior; label as support when report is a question, setup error, 'no effect' / 'can't' / 'failed' wi  
  _validation improved and nothing old broke_ (spark 75%→78% · open 70%→77%)
- **gated-1** g6 `add`: DRA, Dynamic Resource Allocation, device plugins, and image pull and re-pull issues belong to area node, not scheduling, api-machinery, or apps.  
  _validation improved and nothing old broke_ (spark 75%→77% · open 75%→75%)
- **gated-3** g12 `add`: If title starts with is/whether/why/how, ends with '?', or requests auth/setup guidance, label kind as support, never bug or feature.  
  _validation improved and nothing old broke_ (spark 78%→78% · open 77%→78%)
- **gated-3** g16 `add`: Reports mentioning DRA, DeviceAllocation, DeviceTaintRule, device plugins, or device selectors belong to area node, not scheduling.  
  _validation improved and nothing old broke_ (spark 78%→78% · open 78%→80%)

## Rule accountability (which rules drove the misses)

For each lineage, the rules most often relied on in wrong locked-test decisions, with the edit that introduced them. Seed rules have no edit.

**gated-1**
- `R1` cited 100×, wrong 38× (38%) · seed rule  
  > Kinds: bug, support, feature. Choose the single best kind.
- `R2` cited 100×, wrong 38× (38%) · seed rule  
  > Areas (owning teams): network, storage, node, scheduling, auth, cli, api-machinery, apps. Choose the single best area.
- `R3` cited 41×, wrong 15× (37%) · seed rule  
  > If a report describes incorrect behaviour of existing functionality, kind is bug.

**gated-2**
- `R1` cited 100×, wrong 39× (39%) · seed rule  
  > Kinds: bug, support, feature. Choose the single best kind.
- `R2` cited 100×, wrong 39× (39%) · seed rule  
  > Areas (owning teams): network, storage, node, scheduling, auth, cli, api-machinery, apps. Choose the single best area.
- `R3` cited 73×, wrong 30× (41%) · edit `gated-2-g1` g1, accept  
  > Classify kind as bug only when report provides reproduction steps, logs, or version showing existing functionality broken; otherwise reports describing single-i

**gated-3**
- `R1` cited 100×, wrong 33× (33%) · seed rule  
  > Kinds: bug, support, feature. Choose the single best kind.
- `R2` cited 99×, wrong 33× (33%) · seed rule  
  > Areas (owning teams): network, storage, node, scheduling, auth, cli, api-machinery, apps. Choose the single best area.
- `R3` cited 70×, wrong 26× (37%) · edit `gated-3-g5` g5, accept  
  > Label kind as bug only with reproduction steps, version regression, or logs showing controller misbehavior; label as support when report is a question, setup er

**ungated-1**
- `R1` cited 86×, wrong 27× (31%) · seed rule  
  > Kinds: bug, support, feature. Choose the single best kind.
- `R2` cited 85×, wrong 25× (29%) · seed rule  
  > Areas (owning teams): network, storage, node, scheduling, auth, cli, api-machinery, apps. Choose the single best area.
- `R3` cited 57×, wrong 23× (40%) · edit `ungated-1-g19` g19, accept  
  > Choose bug only when report shows concrete wrong value/error with reproducer, logs, or default-config failure; choose support for config questions, CronJob timi

**ungated-2**
- `R2` cited 94×, wrong 32× (34%) · seed rule  
  > Areas (owning teams): network, storage, node, scheduling, auth, cli, api-machinery, apps. Choose the single best area.
- `R1` cited 93×, wrong 31× (33%) · seed rule  
  > Kinds: bug, support, feature. Choose the single best kind.
- `R3` cited 69×, wrong 28× (41%) · edit `ungated-2-g20` g20, accept  
  > Label bug only for concrete broken behavior with repro steps or named code fault; OOM/CrashLoop endless spawns, storage-class creation ordering requests, Failed

**ungated-3**
- `R2` cited 80×, wrong 34× (42%) · seed rule  
  > Areas (owning teams): network, storage, node, scheduling, auth, cli, api-machinery, apps. Choose the single best area.
- `R1` cited 76×, wrong 34× (45%) · seed rule  
  > Kinds: bug, support, feature. Choose the single best kind.
- `R5` cited 53×, wrong 33× (62%) · edit `ungated-3-g24` g24, accept  
  > Determine area by functional domain: stuck Terminating pods and kubelet belong to node not apps, Probe/liveness/readiness belong to apps not cli, KEP Workload A


## Rollbacks

- **ungated-3** without `ungated-3-g10`: locked test 58% → 60%, validation 58% → 60%
- **ungated-1** without `ungated-1-g10`: locked test 66% → 67%, validation 77% → 73%

## Reading this report

The locked test is the only number that counts; batch and probe accuracy are for watching the process. An edit the gate let through that later cost accuracy is a gate miss, and rollback is the remedy. Everything above is recomputed from `events.jsonl`; nothing is typed in by hand.
