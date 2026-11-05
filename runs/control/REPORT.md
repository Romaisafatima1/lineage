# Lineage audit report · run `control`

12 generations · 5 lineages · batch 20 · validation 60 · locked test 100 · repo kubernetes/kubernetes · convention `platform`

**Spend:** $9.70 over 1160 calls. Juror agreement: 13 agreed, 11 split.

## Locked test (scored once, never used for gating)

| Lineage | Mode | Both labels | Kind | Area | Edits applied | Rules | vs baseline |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gated-1 | gated | **59%** | 69% | 88% | 3 of 12 | 6 | +0 pts |
| gated-2 | gated | **60%** | 70% | 87% | 5 of 12 | 5 | +1 pts |
| ungated-1 | ungated | **59%** | 72% | 83% | 12 of 12 | 6 | +0 pts |
| ungated-2 | ungated | **61%** | 74% | 84% | 12 of 12 | 6 | +2 pts |
| baseline | baseline | **59%** | 70% | 82% | 0 of 0 | 3 |  |

## Divergence (how differently sibling lineages behave on the same 50 probes)

At generation 12: gated lineages **30%** apart, ungated **20%** apart.

| Gen | gated-1 | gated-2 | ungated-1 | ungated-2 | baseline |
| --- | --- | --- | --- | --- | --- |
| 5 | 68% | 64% | 50% | 54% | 60% |
| 10 | 68% | 64% | 62% | 64% | 68% |
| 12 | 72% | 62% | 56% | 58% | 60% |

## What the agents tried to learn

| Mode | accept | reject | review | invalid |
| --- | --- | --- | --- | --- |
| gated | 8 | 9 | 7 | 0 |
| ungated | 24 | 0 | 0 | 0 |

Why gated edits were rejected: validation score dropped (9).

## Rules the gate let through

- **gated-2** g1 `change`: If a report describes incorrect behaviour, kind is bug only when it includes concrete reproduction steps, logs, or version details showing a code defect; otherwise vague, environment-specific, or info  
  _validation improved and nothing old broke_ (spark 65%→67% · open 70%→70%)
- **gated-1** g2 `add`: Reports involving DRA, ResourceSlice, or SELinux belong to area node.  
  _validation improved and nothing old broke_ (spark 65%→70% · open 70%→70%)
- **gated-2** g3 `change`: Incorrect, misleading or unexpected system behavior, including confusing events and documentation errors, is bug even when phrased as a question or without full reproduction; support is only for help   
  _validation improved and nothing old broke_ (spark 67%→75% · open 70%→73%)
- **gated-1** g4 `add`: Reports phrased as Why/How questions, requests for help, or single error-log/OOM observations without clear reproduction belong to kind support, not bug.  
  _validation improved and nothing old broke_ (spark 70%→75% · open 70%→75%)
- **gated-2** g7 `change`: Incorrect, misleading or unexpected system behavior, including confusing events and documentation errors, is bug when clear defect indicated even if phrased as question; support is for help requests,   
  _validation improved and nothing old broke_ (spark 75%→75% · open 73%→78%)
- **gated-2** g10 `add`: Choose area by underlying subsystem, not surface tool: port-forward/connectivity to network, CSR/certificates/auth to platform, kubectl flag/parsing behavior to cli, even if kubelet or kubectl is ment  
  _validation improved and nothing old broke_ (spark 75%→77% · open 78%→80%)
- **gated-2** g11 `add`: Pod spec, init containers, container restartPolicy, and manifest validation belong to area node, not apps; apps is only for workload controllers like Deployment, DaemonSet, Job, CronJob.  
  _validation improved and nothing old broke_ (spark 77%→78% · open 80%→80%)
- **gated-1** g11 `add`: Reports involving RBAC, ClusterRole, authentication, impersonation, mTLS, or exec auth belong to area platform, even if they mention kubectl, IngressClass, or other resources.  
  _validation improved and nothing old broke_ (spark 75%→78% · open 75%→77%)

## Rule accountability (which rules drove the misses)

For each lineage, the rules most often relied on in wrong locked-test decisions, with the edit that introduced them. Seed rules have no edit.

**gated-1**
- `R1` cited 100×, wrong 41× (41%) · seed rule  
  > Kinds: bug, support, feature. Choose the single best kind.
- `R2` cited 99×, wrong 40× (40%) · seed rule  
  > Areas (owning teams): apps, cli, network, node, platform, scheduling, storage. Choose the single best area.
- `R3` cited 47×, wrong 21× (45%) · seed rule  
  > If a report describes incorrect behaviour of existing functionality, kind is bug.

**gated-2**
- `R1` cited 96×, wrong 38× (40%) · seed rule  
  > Kinds: bug, support, feature. Choose the single best kind.
- `R2` cited 88×, wrong 34× (39%) · seed rule  
  > Areas (owning teams): apps, cli, network, node, platform, scheduling, storage. Choose the single best area.
- `R3` cited 70×, wrong 30× (43%) · edit `gated-2-g7` g7, accept  
  > Incorrect, misleading or unexpected system behavior, including confusing events and documentation errors, is bug when clear defect indicated even if phrased as 

**ungated-1**
- `R1` cited 98×, wrong 40× (41%) · seed rule  
  > Kinds: bug, support, feature. Choose the single best kind.
- `R2` cited 96×, wrong 38× (40%) · seed rule  
  > Areas (owning teams): apps, cli, network, node, platform, scheduling, storage. Choose the single best area.
- `R3` cited 72×, wrong 31× (43%) · edit `ungated-1-g10` g10, accept  
  > Concrete wrong-behavior reports naming a component/API and observed incorrect effect are bugs even without full repro steps or crash logs if version is hinted; 

**ungated-2**
- `R1` cited 99×, wrong 38× (38%) · seed rule  
  > Kinds: bug, support, feature. Choose the single best kind.
- `R2` cited 96×, wrong 37× (39%) · seed rule  
  > Areas (owning teams): apps, cli, network, node, platform, scheduling, storage. Choose the single best area.
- `R5` cited 19×, wrong 10× (53%) · edit `ungated-2-g8` g8, accept  
  > In-tree kubelet image pull, pod lifecycle/ready state, and container/coredump logs belong to area node; DRA RBAC, emptyDir eviction, and third-party drivers lik


## Reading this report

The locked test is the only number that counts; batch and probe accuracy are for watching the process. An edit the gate let through that later cost accuracy is a gate miss, and rollback is the remedy. Everything above is recomputed from `events.jsonl`; nothing is typed in by hand.
