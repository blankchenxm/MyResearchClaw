# Conference Scout: More modality in wearable system
Phase 1 | 2026-06-26 07:32 | 16.5 min | $3.222 | 86 turns

## [pre-start]  14 turns

  → Read(/Users/xiaomeng/research/MyResearchClaw/skills/conference-scout/SKILL.md)
Now let me read the venue registry and API cookbook.
  → Read(/Users/xiaomeng/research/MyResearchClaw/references/venue-registry.md)
  → Read(/Users/xiaomeng/research/MyResearchClaw/references/api-cookbook.md)
  → Bash(ls /Users/xiaomeng/research/MyResearchClaw/references/ 2>/dev/null && ls /Users/xiaomeng/research/MyResearchClaw/skills/)
  → Bash(ls /Users/xiaomeng/research/MyResearchClaw/skills/conference-scout/references/ 2>/dev/null)
  → Read(/Users/xiaomeng/research/MyResearchClaw/skills/conference-scout/references/venue-registry.md)
Now I have all the context. Let me load the WebFetch and WebSearch tools and begin the rounds.
  → ToolSearch({'query': 'select:WebFetch,WebSearch', 'max_results': 2})

## [Round 0]  49 turns

---

## Round 0 — Query Expansion *(LLM only)*

**Topic:** More modality in wearable system (earphones/glasses + extra sensors)
**Focus:** (1) vision/camera added to earphones; (2) ExG physiological sensing in earphones or glasses

**Expanded queries:**

| # | Query | Rationale |
|---|-------|-----------|
| Q1 | `multimodal wearable earphone sensor camera` | Camera-equipped earables |
| Q2 | `in-ear EEG electroencephalography earbuds wearable` | EEG inside earphones |
| Q3 | `smart glasses EEG EMG physiological sensing wearable` | ExG in eyewear |
| Q4 | `earable sensing multimodal physiological` | Broad earable multimodal |
| Q5 | `wearable camera glasses vision sensing` | Vision-added head-worn |

**Synonym expansions:**
- earphone ↔ earbuds ↔ in-ear ↔ earable ↔ hearable
- ExG ↔ EEG ↔ EM…
  → WebFetch(https://api.semanticscholar.org/graph/v1/paper/search?query=multimodal+wearable+earphone+camera+sensor&fields=title,authors,year,abstract,citationCount,influentialCitationCount,externalIds,openAccessPdf,venue,publicationTypes&limit=10)
  → WebFetch(https://api.semanticscholar.org/graph/v1/paper/search?query=in-ear+EEG+electroencephalography+earbuds+wearable&fields=title,authors,year,abstract,citationCount,influentialCitationCount,externalIds,openAccessPdf,venue,publicationTypes&limit=10)
S2 is rate-limiting (429). Per SKILL.md: switch to DBLP immediately. Let me use DBLP search + WebSearch.
  → WebFetch(https://dblp.org/search/publ/api?q=multimodal+wearable+earphone+sensor&format=json&h=20)
  → WebSearch(wearable earphone earbuds multimodal sensor modality camera vision EEG physiological CHI UIST IMWUT 2021 2022 2023 2024 2025)
  → WebSearch(in-ear EEG wearable earbuds CHI UIST UbiComp IMWUT 2021 2022 2023 2024)
  → WebSearch(earable multimodal sensing camera vision earphone wearable ACM CHI IMWUT SenSys 2021 2022 2023 2024 2025)
Good leads found. Let me search more specifically now.
  → WebSearch("earable" EEG EMG physiological signal sensing wearable CHI IMWUT SenSys MobiSys 2021 2022 2023 2024)
  → WebSearch(smart glasses camera vision sensing physiological EEG EOG EMG wearable CHI UIST IMWUT 2021 2022 2023 2024)
Excellent finds! Let me fetch the arXiv earable survey and VueBuds paper, and search for more.
  → WebFetch(https://arxiv.org/abs/2506.05720)
  → WebFetch(https://arxiv.org/abs/2603.29095)
VueBuds (CHI 2026) is a perfect match. Let me search for more papers.
  → WebSearch(JINSense EOG smart glasses gesture sensing CHI 2021)
  → WebSearch(earphone earbuds EEG brain sensing wearable system CHI UIST IMWUT SenSys MobiSys 2021 2022 2023 2024 2025)
  → WebSearch("camera" "earbuds" OR "earphone" OR "in-ear" wearable sensing ACM 2022 2023 2024 2025 2026)
  → WebSearch(EEG sensing earbuds earphone "MobiSys" OR "SenSys" OR "IMWUT" OR "UbiComp" 2021 2022 2023 2024 2025)
Let me now fetch key papers to get their details and discover more from their references.
  → WebFetch(https://dl.acm.org/doi/10.1145/3712069)
  → WebSearch(site:dl.acm.org EEG OR EMG OR EOG earbuds earphone wearable sensing 2021 2022 2023 2024 2025)
  → WebSearch(wearable glasses EEG EOG EMG ExG physiological sensing CHI UIST IMWUT 2021 2022 2023 2024 2025 site:dl.acm.org)
  → WebSearch("earbuds" OR "earphone" "camera" OR "visual" wearable sensing system 2022 2023 2024 2025 CHI IMWUT SenSys MobiSys)
Let me now look at the earable survey to find more papers, and search for specific missing leads.
  → WebFetch(https://arxiv.org/html/2506.05720v3)
  → WebSearch("EarEEG" OR "ear EEG" wearable sensing CHI UIST IMWUT MobiSys SenSys 2021 2022 2023 2024 2025)
  → WebSearch("EarSleeve" ECG earphone sensing SenSys 2026)
  → WebSearch(smart glasses EEG EOG camera sensing physiological CHI UIST IMWUT SenSys 2021 2022 2023 2024 2025 site:dl.acm.org OR site:arxiv.org)
  → WebFetch(https://arxiv.org/abs/2511.11811)
  → WebSearch(earphone glasses wearable camera visual sensing CHI UIST IMWUT SenSys MobiSys MobiCom 2021 2022 2023 2024 2025 2026)
  → WebSearch(OpenEarable "IMWUT" OR "UbiComp" earbuds physiological sensing open platform 2023 2024 2025)
  → WebSearch("EyeEcho" OR "FingerPing" OR "EarSAT" OR "EarCommand" earphone glasses wearable sensor modality 2021 2022 2023 2024 CHI UIST IMWUT)
  → WebSearch(wearable earphone earbuds physiological EEG ECG PPG EMG sensing system platform 2021 2022 2023 2024 SenSys MobiCom MobiSys IPSN IMWUT CHI)
  → WebSearch("smart glasses" OR "AR glasses" physiological sensing EEG EMG EOG vision camera modality 2021 2022 2023 2024 2025 CHI UIST IMWUT SenSys)

## [Round 1]  73 turns

Good coverage from Round 1. Now moving to anchor extraction.

---

## Round 2 — Anchor Extraction *(LLM only)*

```json
{
  "system_names": [
    "VueBuds", "OpenEarable", "OpenEarable ExG", "ID.EARS",
    "EarEOG", "EarSleeve", "EarSD", "EyeEcho", "JINSense",
    "GAPses", "ElectraSight", "EarIO", "EarHealth"
  ],
  "author_names": [
    "Shyamnath Gollakota", "Tobias Röddiger", "Yang Liu",
    "Nirupam Roy", "Junxi Xia"
  ],
  "key_phrases": [
    "earable multimodal sensing",
    "in-ear EEG wearable",
    "earphone physiological sensing",
    "camera-equipped earbuds",
    "smart glasses ExG",
    "ear-worn EEG EMG EOG",
    "wearable biopotential sensing earphone",
    "earphone ECG cardiac sensing"
  ],
  "venue_year_pairs": [
    "CHI 2024", "CHI 2025", "CHI 2026",
    "IMWUT 2024",…
  → WebFetch(https://dblp.org/db/conf/chi/chi2025.html)
  → WebFetch(https://dblp.org/db/conf/chi/chi2024.html)
CHI pages too large. Switching to DBLP search API.
  → WebFetch(https://dblp.org/search/publ/api?q=earable+earphone+sensing+venue%3ACHI&format=json&h=30)
  → WebFetch(https://dblp.org/search/publ/api?q=wearable+glasses+EEG+EOG+sensing+venue%3ACHI&format=json&h=20)
  → WebFetch(https://dblp.org/search/publ/api?q=earable+earphone+wearable+sensing+CHI&format=json&h=30)
  → WebFetch(https://dblp.org/search/publ/api?q=earphone+EEG+EMG+EOG+wearable&format=json&h=30)
  → WebFetch(https://dblp.org/search/publ/api?q=earable+sensing&format=json&h=30)
  → WebFetch(https://dblp.org/search/publ/api?q=in-ear+EEG+wearable&format=json&h=20)
Good DBLP results. Now doing author sweep and precision searches.
  → WebFetch(https://dblp.org/search/publ/api?q=earphone+earbuds+physiological+sensing&format=json&h=20)
  → WebSearch(Shyamnath Gollakota wearable earbuds sensing CHI UIST IMWUT SenSys MobiSys 2021 2022 2023 2024 2025)
  → WebFetch(https://dblp.org/search/publ/api?q=EEG+earphone+wearable&format=json&h=20)
  → WebSearch("OpenEarable ExG" OR "OmniBuds" earphone biopotential sensing IMWUT CHI UbiComp 2024 2025)
  → WebFetch(https://dblp.org/search/publ/api?q=smart+glasses+sensing+physiological&format=json&h=20)
  → WebSearch("ID.EARS" OR "EarEOG" OR "Advancing Wearable BCI" EEG earphone headphone CHI IMWUT 2024 2025)
  → WebSearch(smart glasses wearable EEG EMG sensing physiological 2022 2023 2024 IMWUT CHI UIST site:dl.acm.org)
  → WebSearch("EyeEcho" glasses acoustic sensing CHI 2024 facial expression tracking wearable)
  → WebSearch("ActSonic" earbuds glasses acoustic inaudible everyday activity sensing IMWUT 2024)
  → WebSearch(wearable hearable earphone heart rate PPG ECG sensing CHI IMWUT UbiComp SenSys MobiSys 2021 2022 2023 2024 2025)
Let me do the mandatory DBLP venue scan for IMWUT (top relevant venue for this topic).
  → WebFetch(https://dblp.org/db/journals/imwut/imwut9.html)
  → WebFetch(https://dblp.org/db/journals/imwut/imwut8.html)
  → WebFetch(https://dblp.org/search/publ/api?q=earphone+glasses+sensing+physiological+EEG+wearable&format=json&h=30)
  → WebSearch(EchoSpeech silent speech recognition glasses acoustic sensing CHI 2023)
  → WebSearch(Tobias Röddiger earphone earable EEG ExG biopotential sensing IMWUT CHI UbiComp 2022 2023 2024 2025)
  → WebSearch(wearable glasses EEG EOG camera physiological sensor modality CHI 2021 2022 2023 2024 2025 UIST SenSys IMWUT)
Now trying Semantic Scholar for citation counts (may have cleared rate limit).
  → WebFetch(https://api.semanticscholar.org/graph/v1/paper/DOI:10.1145/3772318.3791322?fields=title,authors,year,citationCount,influentialCitationCount,externalIds,openAccessPdf,venue)
  → WebFetch(https://api.semanticscholar.org/graph/v1/paper/DOI:10.1145/3706598.3714185?fields=title,authors,year,citationCount,influentialCitationCount,externalIds,openAccessPdf,venue)
  → WebFetch(https://api.semanticscholar.org/graph/v1/paper/DOI:10.1145/3712283?fields=title,authors,year,citationCount,influentialCitationCount,externalIds,openAccessPdf,venue)
  → WebFetch(https://api.semanticscholar.org/graph/v1/paper/DOI:10.1145/3613904.3642613?fields=title,authors,year,citationCount,influentialCitationCount,externalIds,openAccessPdf,venue)
  → WebFetch(https://api.semanticscholar.org/graph/v1/paper/DOI:10.1145/3712069?fields=title,authors,year,citationCount,influentialCitationCount,externalIds,openAccessPdf,venue)
  → WebFetch(https://api.semanticscholar.org/graph/v1/paper/DOI:10.1145/3699752?fields=title,authors,year,citationCount,influentialCitationCount,externalIds,openAccessPdf,venue)
  → WebFetch(https://api.semanticscholar.org/graph/v1/paper/DOI:10.1145/3544548.3580801?fields=title,authors,year,citationCount,influentialCitationCount,externalIds,openAccessPdf,venue)
  → WebFetch(https://api.semanticscholar.org/graph/v1/paper/DOI:10.1145/3534621?fields=title,authors,year,citationCount,influentialCitationCount,externalIds,openAccessPdf,venue)
  → WebFetch(https://api.semanticscholar.org/graph/v1/paper/DOI:10.1145/3774906.3802785?fields=title,authors,year,citationCount,influentialCitationCount,externalIds,openAccessPdf,venue)
  → WebFetch(https://api.semanticscholar.org/graph/v1/paper/ARXIV:2506.05720?fields=title,authors,year,citationCount,influentialCitationCount,externalIds,openAccessPdf,venue)
  → WebFetch(https://api.semanticscholar.org/graph/v1/paper/DOI:10.1145/3544793.3563415?fields=title,authors,year,citationCount,influentialCitationCount,externalIds,openAccessPdf,venue)
  → WebFetch(https://sensys.acm.org/2026/accepted_papers.html)
  → WebFetch(https://api.semanticscholar.org/graph/v1/paper/DOI:10.1145/3550289?fields=title,authors,year,citationCount,influentialCitationCount,externalIds,openAccessPdf,venue)
  → WebSearch("Sensing with Earables" systematic literature review taxonomy phenomena IMWUT 2022 Röddiger Clarke)
  → WebFetch(https://api.semanticscholar.org/graph/v1/paper/DOI:10.1145/3550314?fields=title,authors,year,citationCount,influentialCitationCount,externalIds,openAccessPdf,venue)
  → WebFetch(https://api.semanticscholar.org/graph/v1/paper/DOI:10.1145/3411763.3451741?fields=title,authors,year,citationCount,influentialCitationCount,externalIds,openAccessPdf,venue)
  → WebSearch("GazeTrak" OR "AirSpeech" OR "EarGest" OR "EarBuddy" earphone glasses camera vision additional modality wearable CHI UIST IMWUT 2021 2022 2023 2024)
  → WebFetch(https://api.semanticscholar.org/graph/v1/paper/ARXIV:2511.11811?fields=title,authors,year,citationCount,influentialCitationCount,externalIds,openAccessPdf,venue)
  → WebFetch(https://api.semanticscholar.org/graph/v1/paper/DOI:10.1145/3636534.3649376?fields=title,authors,year,citationCount,influentialCitationCount,externalIds,openAccessPdf,venue)
  → WebSearch("BrainRead" OR "OmniBuds" earable physiological multimodal sensing wearable 2024 2025 IMWUT CHI SenSys)
I now have enough data for Rounds 4 and the checkpoint. Let me save everything.
  → WebFetch(https://api.semanticscholar.org/graph/v1/paper/DOI:10.1145/3478080?fields=title,authors,year,citationCount,influentialCitationCount,externalIds,openAccessPdf,venue)
  → WebFetch(https://dblp.org/rec/journals/imwut/VermaBSSP21.html)
  → WebFetch(https://api.semanticscholar.org/graph/v1/paper/DOI:10.1145/3478085?fields=title,authors,year,citationCount,influentialCitationCount,externalIds,openAccessPdf,venue)

## [Round 4]  3 turns

Now I have all data for the checkpoint and candidates. Let me create the output directory and files.

---

## Round 4 — Relevance Gate *(LLM only)*

Applying the three-criteria gate against `subfield_boundary`: "Papers must be about earphones/earbuds/smart-glasses form-factor wearables that add at least one extra sensor modality beyond the device's primary function."

| # | Paper | Criterion 1: Specific subproblem? | Criterion 2: Form factor match? | Decision |
|---|-------|------|------|------|
| 1 | VueBuds | Camera added to earbuds | Earbuds ✓ | **PASS** |
| 2 | ID.EARS | EEG from single earphone | Earphone ✓ | **PASS** |
| 3 | Headphone EEG (Knierim) | EEG in headphone form factor | Headphone ✓ | **PASS** |
| 4 | OpenEarable 2.0 | PPG+IMU+temp platform for earphone | Earphone ✓ | **PAS…
  → Bash(mkdir -p /Users/xiaomeng/research/MyResearchClaw/output/tmp/scout_more-modality-in-wearable-system)
  → Write(/Users/xiaomeng/research/MyResearchClaw/output/tmp/scout_more-modality-in-wearable-system/scout_checkpoint_r3.json)

## [Round 4.5]  3 turns

Now writing the Round 4.5 candidates JSON:
  → Write(/Users/xiaomeng/research/MyResearchClaw/output/tmp/scout_more-modality-in-wearable-system/candidates_r4.json)
---

## Round 4.5 — Candidate Confirmation *(PAUSE)*

共 **13 篇**通过 Round 4 相关性门控。

按类别分组：

**📷 视觉/相机 (Vision/Camera)**

| # | 标题 | Venue | 年份 | 引用 | influential | PDF |
|---|------|-------|------|------|-------------|-----|
| 1 | VueBuds: Visual Intelligence with Wireless Earbuds | CHI | 2026 | 0 | 0 | ✓ arXiv |
| 2 | Lessons Learned from Developing a Privacy-Preserving Multimodal Wearable for Local Voice-and-Vision Inference | arXiv | 2025 | 0 | 0 | ✓ arXiv |

**🧠 EEG / ECG / ExG 生理信号 (Physiological ExG)**

| # | 标题 | Venue | 年份 | 引用 | influential | PDF |
|---|------|-------|------|------|-------------|-----|
| 3 | ID.EARS: One-Ear EEG Device with Biosignal Noise for Real-Time Gesture Recognition | CHI | 2025 | 2 | 0 | ✗ |
| 4 | Advancing Wearable BCI: Headphone EEG for Cognitive Load Det…
