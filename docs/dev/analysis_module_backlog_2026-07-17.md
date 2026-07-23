Type: PRODUCT
Authority: self

# Analysis module backlog (ranked) — 2026-07-17

> Ranked product backlog for **new or deepened** analysis modules, libraries, and approaches.  
> Companion to [`stocktake_2026-07-17.md`](stocktake_2026-07-17.md) and the prior coverage discussion.  
> Related research: [`competitive_inspiration_2026-07-22.md`](competitive_inspiration_2026-07-22.md) (five OSS tools vs TranscriptX — features, S/W, learnings for B10/P2/B18).  
> Organized against web UI groups in `src/transcriptx/web/module_ui_groups.py`.

**Non-goals:** release hygiene, Top-3 eng refactors, transcription engine integration, plugin marketplace, realtime analysis.

**Default stance:** Prefer deepen-in-place over new module IDs when overlap is high. Prefer local-first libs and Ollama-structured extract over remote SaaS APIs.

**Capacity rule:** No more than **two new module IDs per delivery wave**. All other work must deepen, revive, or replace existing modules unless a written overlap assessment demonstrates a distinct user-facing object.

---

## 1. How to read this

| Field | Meaning |
|-------|---------|
| **Rank** | Global priority within the **analysis backlog** (1 = do first when product capacity opens). Platform workstreams are tracked separately (§2). |
| **Mode** | `new` = new module id; `deepen` = extend existing; `revive` = re-wire archived/optional path |
| **UI group** | Target `MODULE_UI_GROUPS` bucket (or new bucket if noted) |
| **Effort** | S / M / L (rough; contracts + tests assumed) |
| **Depends** | Eng or product prerequisites |

**Gate before any item:** Wave 0 eng gate (release hygiene A1–A10 + Config ownership through 1.8) is **closed** in-tree (stocktake §1 / §4). Wave 1 product capacity is unlocked for eng work. A **public version tag** still requires [`release_governance.md`](release_governance.md) evidence (clean tree, green CI on exact commit, evidence bundle) — that process gate does not block starting Wave 1 implementation. Items marked **Revive** may still land earlier if they are mostly rewire + deps, not new algorithms.

**Do not treat platform work as a single “shipped analysis.”** Multilingual routing (P1) and shared evidence/provenance (P2) are infrastructure with downstream adoption milestones; “done” must name which consumers adopted them.

---

## 2. Platform workstreams (not ranked as analysis modules)

These are shared capabilities. Track adoption per consumer; avoid presenting them as one shippable analysis feature.

| ID | Workstream | Affects | Intent | Adoption milestones (examples) |
|----|------------|---------|--------|--------------------------------|
| **P1** | **Multilingual model routing** (spaCy / embeddings / emotion / NER / understandability / keyphrases; potentially sentiment) from `language` metadata | Language & Meaning (+ Foundations) | Shared model-resolution; download / air-gap policy in `docs/runtime/models.md` | Per-consumer: supported-language declaration, unsupported-language behaviour, offline discovery |
| **P2** | **Evidence / provenance infrastructure** for inferred results | Summary & Synthesis consumers | One shared contract for spans, source module refs, confidence, abstention | Required before/alongside B10, B11, B18 — not reinvented three times |

P1 may start in Wave 1 as infrastructure while individual language switches land later. Avoid ranking “multilingual routing” next to BERTopic or hedging as if they were the same kind of deliverable.

---

## 3. Ranked backlog (global) — first product-capacity window

Order after the engineering gate. B2 (old ID for multilingual routing) is **P1** above, not a ranked analysis item.

| Rank | ID | Item | Mode | UI group | Effort | Depends |
|------|----|------|------|----------|--------|---------|
| 1 | B1 | **BERTopic rewire** as topic path | revive (**shipped**; default install for now) | Language & Meaning | M | base deps + registry + agg + charts; public release → install profiles |
| 2 | B3 | **ASR / transcript quality** diagnostics — shipped as Foundations module `transcript_quality` (**ASR confidence** evidence/review; no quality scorecard; filler deferred) | new (**shipped** Phase 1+2; 0.6.3+) | Foundations | M | WhisperX word scores + provenance-aware group agg |
| 3 | B9 | **Agenda / topic-shift segmentation** (embedding change-points) | new (**shipped** — module `topic_shift`; dual stores; Chapters tab; group cohort agg + overlays; Stage 5 acceptance; finalize: language status / lexical embed / offline+deadline / enrichment envelope). Residual: group-synthesis shared ACTIVE migration **waived** | Dynamics & Flow | M | reuse semantic embeddings |
| 4 | B12 | **Turn-taking equity pack** (floor entropy, interruption asymmetry, response latency fairness) | deepen (**shipped** 0.4.8; semantics v2 + group charts) | Speakers & Interaction | S–M | mostly from `interactions` + `stats` |
| 5 | B6 | **Hedging / certainty / epistemic markers** | new (**shipped** as `epistemic_markers`) | Language & Meaning | S–M | lexicon + optional classifier; group charts |
| 6 | — | *(P1 routing infrastructure continues; not a ranked module)* | platform | — | M | see §2 |
| 7 | B10 | **Structured decisions / commitments** — extraction-family deepen (`llm_action_items` v2 meeting extracts) | deepen (**shipped** v2 contract: typed records + sectioned render + group schema 2; residual: broader P2 platform) | Summary & Synthesis | M | Ollama; taxonomy vs `llm_action_items` (see §3.1); P2 provenance |
| 8 | B7 | **Politeness / formality / power** (lexicon-first) | new (**shipped** as `politeness`; power = lexical directiveness; B12 equity for interactional power) | Speakers & Interaction | M | lexicon path first; ConvoKit optional later |
| 9 | B14 | **Cross-session concept drift / recurring motifs** | deepen | Language & Meaning (+ Groups) | M | `semantic_similarity_v2` + group finalize |
| 10 | B13 | **Speaker interaction graphs** (NetworkX artifacts + gallery) | deepen (**shipped**: GraphML/JSON + upgraded `interactions.network_graph.global`) | Speakers & Interaction / Visualisations | M | Phase 3 network mention; B12 primitives help |

### Later / lower in the same global list

| Rank | ID | Item | Mode | UI group | Effort | Depends |
|------|----|------|------|----------|--------|---------|
| 11 | B5 | **Longitudinal speaker tracking v1** + Speakers UI charts | deepen / new surfaces (**Phase 1.5 + 1.6 + R2 voice + Locations pack shipped**: file store, Speakers UX, over-time charts, accents, analytics pack, avatars, voice match/accept/enrol, NER locations map; **file-backed voice residuals shipped** — accept query-evidence co-journal, eval harness, chunked merge transfer, Stage 9 file index; remainder: **DB analytics views**, **group gallery keyed by `profile_id`**) | Speakers & Interaction (+ Groups) | L | Phase 3 remainder; group cross-session allowlists |
| 12 | B18 | **Insight narratives grounded in module evidence** | deepen | Summary & Synthesis | M | `insights` + LLM; **P2** provenance contracts |
| — | — | **Group LLM synthesis** (cross-session rollup of member `llm_summary` / `llm_speaker_summary`) | deepen (finalize; no new module ID) | Summary & Synthesis (+ Groups) | M | Shipped contract: [`group_llm_synthesis_contract.md`](../groups/group_llm_synthesis_contract.md) |
| 13 | B4 | **ConvoKit accommodation / coordination** — implementation option, not product objective | revive (optional) | Speakers & Interaction | L | define desired outputs first; resolve numpy/spaCy/thinc only if still needed |
| 14 | B8 | **Dialogue-act model upgrade** (re-enable transformer `acts` path) | deepen | Speakers & Interaction | M | model size / core-mode story; keep rules fallback; may move earlier if genuinely small rewire |
| 15 | B11 | **Claim–evidence / argument mining** (exploratory) | new | Summary & Synthesis or Language & Meaning | L | genres + schema + eval fixtures + UI + abstention before delivery (see §3.2); P2 |
| 16 | B15 | **Emotion × prosody fusion** (“said vs sounded”) | deepen | Voice & Audio (+ Dynamics) | M | `emotion` + `voice_*` join keys |
| 17 | B16 | **Keyphrase ranking** (KeyBERT / YAKE / noun-chunks) | new or deepen wordclouds | Visualisations / Language & Meaning | S | optional dep; group pooled phrases; P1 for language |
| 18 | B17 | **Toxicity / hostility** (optional, labeled) | new | Language & Meaning | S–M | Detoxify or similar; clear ethics/docs |
| 19 | B19 | **Diarization / speaker-map consistency diagnostics** (per run + group) | new | Foundations / Speakers | M | voice fingerprint + speaker-map sidecars |
| 19 | B19 | **Multilingual-aware NER / entity paths** | deepen | Language & Meaning | M | after P1 |
| 20 | B20 | **Pooled wordcloud deferred variant matrix** | deepen | Visualisations | S | eng backlog already listed in ROADMAP |
| — | B21 | **Custom questions at analysis time** (`llm_custom_qa`) — Settings library + Run/Batch picker → Insights citation cards (not viewer chat) | new (**shipped**) | Summary & Synthesis | M | Ollama; frozen envelope/row contract; empty-Q gate |

### 3.1 B10 — decisions vs action items (required taxonomy)

B10 is worthwhile only with a strict semantic boundary. Prefer deepening the existing structured extraction pipeline with multiple record types rather than a separate module ID unless overlap assessment says otherwise.

| Type | Meaning |
|------|---------|
| **Decision** | A conclusion or selected course of action |
| **Commitment** | A speaker or group undertaking |
| **Action item** | An executable task, optionally with owner and deadline |
| **Proposal** | Considered but not accepted |
| **Open question** | Unresolved matter |

Without this taxonomy, B10 mostly duplicates `llm_action_items`, summaries, and highlights.

### 3.2 B4 — ConvoKit as option, not objective

B4 ranks low relative to dependency surface (NumPy/spaCy/thinc), overlap with B7/B12, optional packaging burden, and uncertain end-user value until outputs are specified.

1. Define desired **accommodation** and **coordination** outputs.  
2. Implement them directly **or** revive only the necessary ConvoKit components.  
3. Do not treat “ConvoKit re-enabled” as the product goal.

### 3.3 B11 — argument mining stays exploratory

Most research-heavy, least contractually obvious. “Claim”, “evidence”, and “argument” vary across meetings, interviews, debates, and informal talk.

Keep below decision tracking and evidence-grounded insights until there are: target transcript genres; stable output schema; evaluation fixtures; clear UI; confidence and abstention behaviour. Do **not** anchor Wave 3 delivery on B11.

### 3.4 B9 and B12 — why promoted

**B9 (topic-shift segmentation):** Improves navigation, summaries, moments, chapter-like exports, topic modelling, action-item/decision context, and group comparisons; highly visible; reuses embeddings.

**B12 (interaction equity):** Strong low-cost deepen-in-place; **shipped in 0.4.8** (floor entropy, interruption asymmetry, response latency fairness + semantics v2 + group charts). Reusable interaction primitives ahead of heavier social-linguistic work (B4, B7).

---

## 4. By UI group (add vs deepen)

### Summary & Synthesis
*Existing:* `llm_summary`, `narrative_summary`, `llm_speaker_summary`, `llm_action_items`, `chart_descriptions`, `summary`, `highlights`, `insights` (+ group LLM synthesis finalize path)

| Prefer | Items |
|--------|-------|
| **Deepen** | B18 evidence-grounded insight narratives; B10 structured decisions/commitments as extraction-family types; richer action-item ↔ moment linkage |
| **Add** | B11 claim–evidence only after §3.3 gates (exploratory) |

Avoid: another free-form summarizer that overlaps `llm_summary` / `narrative_summary`.

### Foundations
*Existing:* `stats`, `transcript_output`, `simplified_transcript`, `tics`, `transcript_quality`, `pauses`, `temporal_dynamics`, `insight_eligibility`

| Prefer | Items |
|--------|-------|
| **Deepen** | `tics` ← filler/disfluency metrics if needed later; further `transcript_quality` review surfaces |
| **Add** | ~~B3 ASR/transcript quality~~ **shipped** as `transcript_quality` (ASR confidence); B19 speaker-map consistency |

### Language & Meaning
*Existing:* `sentiment`, `emotion`, `contextual_emotion`, `fine_grained_emotion`, `ner`, `entity_sentiment`, `topic_modeling`, `bertopic` (default install for now), semantic similarity family, `understandability`, `lexical_diversity`

| Prefer | Items |
|--------|-------|
| **Deepen** | ~~B1 BERTopic~~ shipped; B14 concept drift; P1 multilingual routing adoption; emotion-family Phase 5 calibration; model upgrades per `docs/runtime/models.md` |
| **Add** | ~~B6 hedging/certainty~~ **shipped** as `epistemic_markers`; B16 keyphrases; B17 toxicity (optional) |

Avoid: third sentiment backend as a product feature (keep as config only). Emotion family is intentional separate module IDs (see §6 override).

### Speakers & Interaction
*Existing:* `acts`, `interactions` (incl. **equity pack**), `conversation_loops`, `qa_analysis`, `echoes`, `contagion`

| Prefer | Items |
|--------|-------|
| **Deepen** | ~~B12 equity~~ shipped; B8 acts ML path; B5 longitudinal speakers (file-backed + locations **shipped**; DB/group `profile_id` remainder); ~~B13 graphs~~ shipped |
| **Add** | ~~B7 politeness/formality~~ **shipped** as `politeness` |
| **Optional revive** | B4 ConvoKit only after desired outputs are specified (§3.2) |

### Dynamics & Flow
*Existing:* `momentum`, `moments`, `affect_tension`

| Prefer | Items |
|--------|-------|
| **Deepen** | `moments` / `affect_tension` consumers of B15 fusion scores |
| **Add** | ~~B9 agenda / topic-shift segmentation~~ **shipped** as `topic_shift` |

### Voice & Audio
*Existing:* `voice_features`, `voice_mismatch`, `voice_tension`, `voice_fingerprint`, charts/contours/prosody

| Prefer | Items |
|--------|-------|
| **Deepen** | B15 emotion×prosody fusion; fingerprint → B5 / B19 |
| **Add** | none required near-term |

### Visualisations
*Existing:* `wordclouds`

| Prefer | Items |
|--------|-------|
| **Deepen** | B20 pooled variant matrix; optional B16 keyphrase charts |
| **Add** | none required near-term (~~B13 graph viz~~ shipped under Speakers & Interaction / `interactions`) |

---

## 5. Suggested delivery waves

```mermaid
flowchart LR
  W0[Wave 0: Eng gate] --> W1[Wave 1: Topic structure and trust]
  W1 --> W2[Wave 2: Interaction depth]
  W2 --> W3[Wave 3: Cross-session and synthesis]
  W3 --> W4[Wave 4: Experimental and heavy deps]
```

| Wave | When | Items | Intent |
|------|------|-------|--------|
| **0** | **Closed** (2026-07-22) | Top-3 config through 1.8; release hygiene A1–A10 | Capacity, not features — eng criteria green; tagging still via governance |
| **1** | **Shipped core** (2026-07-23) | ~~B1~~, ~~B3~~, ~~B9~~ shipped; **initial P1** routing infrastructure not started | Topic structure and trust; visible navigation/quality |
| **2** | **Shipped** (2026-07-23) | ~~B12~~; ~~B6~~ `epistemic_markers`; ~~B7~~ `politeness`; ~~B13~~ interaction graphs (+ profile avatars) | Interaction depth from existing data + light linguistics |
| **3** | Phase 3 product (in progress via 0.7.x Speakers) | B5 remainder (**DB views** / group `profile_id` charts; file-backed Speakers/voice/locations **closed**), B14, B18 (+ **P2** provenance) | Cross-session and structured synthesis — **not** B11 |
| **4** | Opportunistic / experimental | B4, B8, B11, B15, B16, B17, B19, B20 | Dependency-heavy and research paths |

**Next product capacity (ranked open):** Wave 3 items (B5 DB/group `profile_id` remainder, B14, B18 / P2); P1 infrastructure in parallel when eng capacity allows. **Also shipped adjacent to Wave 3:** configurable analysis presets (`analysis.ui_presets`, 0.7.5); Speakers Locations pack (0.7.5).

**Wave constraints:** ≤2 new module IDs per wave (capacity rule). B8 may move earlier if the transformer path is a small rewire, but it should not outrank user-visible improvements (B9, remaining Wave 2 linguistics).

P1 may begin alongside remaining Wave 3 work as infrastructure; do not call “multilingual routing” shipped until named consumers adopt it.

---

## 6. Explicit non-adds (near-term)

| Temptation | Why skip |
|------------|----------|
| Another *sentiment* module / third valence backend as a product feature | Keep as config/backends on `sentiment` only |
| ~~Another sentiment/emotion module~~ | **Product override (2026-07-18):** `contextual_emotion` and `fine_grained_emotion` are intentional new module IDs alongside lexical `emotion`. See [`emotion_family_contracts_2026-07-18.md`](emotion_family_contracts_2026-07-18.md). Do not reintroduce “converge emotion via config only.” |
| Chat-over-transcript product | Analysis-first north star; not beta scope |
| Remote OpenAI-backed modules | Deferred post-beta (Ollama only) |
| Plugin marketplace | 6-month out of scope |
| Realtime / streaming analysis | Out of scope |
| Heavy model training in-tree | Out of scope |
| “ConvoKit enabled” as the goal | Outputs first; library is optional (§3.2) |
| Argument mining as Wave 3 anchor | Exploratory until genres/schema/eval/UI/abstention exist (§3.3) |

---

## 7. Acceptance criteria (per new / revive / deepen ship)

Minimum bar before claiming “shipped.” Registration alone is not enough.

### Contract and behaviour
1. Explicit **output schema** and **schema-version / no-version** decision documented  
2. **Evidence / provenance** requirements for every inferred result (prefer shared **P2** where applicable)  
3. **Confidence, abstention, and partial-failure** semantics  
4. **Deterministic fallback** or explicit **optional-only** behaviour  
5. **Aggregation semantics:** pool, compare, recompute, or unsupported — documented in `docs/groups/group_analysis_module_outputs.md`  
6. **Deletion or deprecation** decision for any output made redundant  

### Engineering and packaging
7. `AnalysisModule` + registry entry + UI group placement (where a module exists)  
8. Aggregation entry and chart class decision (when group-relevant)  
9. Config knobs under owned subtree (no new ownership sprawl)  
10. Core-mode / optional-extra story clear (`TRANSCRIPTX_CORE`, extras)  
11. **Packaging tests** for every optional extra on supported Python versions  
12. **Performance budgets** for transcript and group execution  
13. **Offline / air-gapped** behaviour: model discovery, downloads, failure modes  

### Language, privacy, UI, evaluation
14. **Supported-language declaration** and unsupported-language behaviour (esp. P1 consumers)  
15. **Privacy statement** where audio embeddings, speaker identity, or sensitive labels are involved  
16. Docs: runtime note + model/license if HF/spaCy/third-party  
17. **UI empty / error / partial states**, not only analysis empty paths  
18. **Representative evaluation fixtures**, not merely happy-path goldens  

---

## 8. Source index

| Topic | Path |
|-------|------|
| Current module order | `src/transcriptx/core/pipeline/module_specs/__init__.py` |
| UI groups | `src/transcriptx/web/module_ui_groups.py` |
| ConvoKit / BERTopic deferrals | `docs/ROADMAP.md` |
| Model upgrade matrix | `docs/runtime/models.md` |
| Group output classes | `docs/groups/group_analysis_module_outputs.md` |
| Stocktake sequencing | `docs/dev/stocktake_2026-07-17.md` |
| Competitive inspiration (5 OSS tools vs TX) | [`competitive_inspiration_2026-07-22.md`](competitive_inspiration_2026-07-22.md) |
| Wave 2 lexicon linguistics (B6/B7) | [`wave2_lexicon_linguistics_2026-07-23.md`](wave2_lexicon_linguistics_2026-07-23.md) |
| Wave B13 interaction graphs | [`wave_b13_interaction_graphs_2026-07-23.md`](wave_b13_interaction_graphs_2026-07-23.md) |
| Speaker profiles v1 | [`../contracts/speaker_profiles_v1.md`](../contracts/speaker_profiles_v1.md) |
| Speaker profiles voice | [`../contracts/speaker_profiles_voice_v1.md`](../contracts/speaker_profiles_voice_v1.md) |
| Analysis presets (runtime) | [`../runtime/installation.md`](../runtime/installation.md) (Analysis presets) |
