---
name: my-research-claw
description: >
  Research assistant for finding top conference papers by topic. Core skill: conference-scout.
  Trigger words: 搜论文, find papers, conference papers, 顶会论文, paper search, scout papers.
metadata:
  version: "0.1.0"
  author: meng
---

# MyResearchClaw — Conference Paper Scout

A focused research assistant for finding **top-venue papers** by topic across AI, IoT, networking, and systems conferences.

## Skills

| # | Skill | Directory | What it does |
|---|---|---|---|
| 1 | **Conference Scout** 📡 | `skills/conference-scout/` | Search top-conference papers by topic + time range |

## Quick Reference

| Say this | Skill triggered |
|---|---|
| `搜论文 [topic] [years] [conference type]` | Conference Scout |
| `find papers on [topic] in [NeurIPS/MobiCom/...] since [year]` | Conference Scout |
| `[topic]领域近[N]年的[AI/IoT]顶会论文` | Conference Scout |

## Conference Groups

```yaml
conference_groups:
  ai_ml:
    - NeurIPS        # Neural Information Processing Systems
    - ICLR           # International Conference on Learning Representations
    - ICML           # International Conference on Machine Learning
    - AAAI           # AAAI Conference on Artificial Intelligence
    - CVPR           # Computer Vision and Pattern Recognition
    - ICCV           # International Conference on Computer Vision
    - ACL            # Association for Computational Linguistics
    - EMNLP          # Empirical Methods in NLP
  iot_systems:
    - MobiCom        # ACM International Conference on Mobile Computing
    - MobiSys        # ACM International Conference on Mobile Systems
    - SenSys         # ACM Conference on Embedded Networked Sensor Systems
    - UbiComp        # ACM International Joint Conference on Pervasive and Ubiquitous Computing
    - IPSN           # ACM/IEEE Conference on Information Processing in Sensor Networks
  networking:
    - SIGCOMM        # ACM Special Interest Group on Data Communication
    - NSDI           # USENIX Symposium on Networked Systems Design and Implementation
    - INFOCOM        # IEEE International Conference on Computer Communications
  systems:
    - OSDI           # USENIX Symposium on Operating Systems Design and Implementation
    - SOSP           # ACM Symposium on Operating Systems Principles
    - ATC            # USENIX Annual Technical Conference
    - EuroSys        # European Conference on Computer Systems
```

## Shared Config

- **Output:** chat text (no HTML in v0.1)
