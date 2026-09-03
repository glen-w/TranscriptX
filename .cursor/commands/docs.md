Documentation Maintenance (# docs)

Refactor and update project documentation so it matches the current codebase and the documentation architecture.

Run from the workspace root.

Do not modify code during this step unless explicitly requested. After completion, summarize what documentation was updated, which authority boundaries were established, and any remaining documentation gaps or ambiguities.

⸻

Documentation model (must enforce)

TranscriptX docs are structured into explicit layers:
	•	CONTRACT — owns invariants, schemas, support policy, and rule definitions.
	•	GUIDE — owns user/developer flows and examples; may summarize contracts briefly, but may not define rules.
	•	ARCHITECTURE — owns system shape, boundaries, and extension points; defers to contracts for invariants.
	•	PRODUCT — owns roadmap, vision, and planning/status material.

Hard rules
	•	Every major concept must have one authoritative home.
	•	Guides must not define rules.
	•	Architecture docs must not define rules.
	•	Runtime docs (`docs/runtime/*`) must not define invariants or support policy; they may only describe runtime behavior and operations and then link to contracts.
	•	If a guide, architecture doc, or runtime doc contains normative language for storage, run truth, output layout, or support policy, move or delete it and replace it with a short summary plus a link to the authoritative contract.
	•	Do not create new contract docs lightly; prefer extending an existing authoritative contract when possible.

Lint rules (must fail #docs)
	•	Concept uniqueness:
		•	Fail if the same core concept (storage layout, run truth semantics, outputs/layout, public surfaces/support) is normatively defined in more than one CONTRACT doc.
	•	GUIDEs:
		•	Fail if any GUIDE contains “must”, “required”, or “invariant” language that defines behavior or rules instead of summarizing a CONTRACT doc.
	•	ARCHITECTURE:
		•	Fail if `docs/ARCHITECTURE.md` defines behavior or invariants instead of describing structure and boundaries.
	•	Runtime docs:
		•	Fail if runtime docs (`docs/runtime/*`) define storage structure, sidecar/metadata schemas, run-truth semantics, or support policy instead of linking to the appropriate CONTRACT doc.
	•	TERMS:
		•	Fail if `docs/TERMS.md` introduces new meanings or rule text instead of acting as a non-authoritative index that points to CONTRACT sections.

⸻

1. Classify docs without page headers

Do **not** add `Type:` / `Authority:` rows. They render on hosted Sphinx pages. Classification is by location and index, not a file header:

	•	CONTRACT — `docs/contracts/`, `docs/runtime/STORAGE.md`, `docs/run_outcome_contract.md`, `docs/public_surfaces.md`, listed in `docs/CONTRACT_INDEX.md`
	•	GUIDE — `docs/workflows/`, runtime how-tos, `docs/USER_INDEX.md`, README
	•	ARCHITECTURE — `docs/ARCHITECTURE.md`, ADRs, composition/config architecture notes
	•	PRODUCT — `docs/PRODUCT.md`, `docs/ROADMAP.md`, programme docs under `docs/dev/`

Authority lives in CONTRACT_INDEX and the contract files themselves. Do not restore classification headers on any Markdown page, including archive.

⸻

2. Enforce authority boundaries

Storage authority

Treat docs/STORAGE.md as the only authoritative source for:
	•	path layout
	•	metadata and metadata subtree rules
	•	sidecar rules
	•	imports/ semantics
	•	rename rules
	•	“where things live” invariants

Run outcome authority

Treat docs/run_outcome_contract.md as the only authoritative source for:
	•	run_results.json semantics
	•	allowed run/module statuses
	•	precedence rules
	•	“file presence is not truth”

Public surfaces authority

Treat docs/public_surfaces.md as the only authoritative source for:
	•	supported user-facing and programmatic surfaces
	•	unsupported or deprecated interfaces
	•	support policy boundaries

Terminology authority

Treat docs/TERMS.md as the terminology index, aggregating canonical terms from contract docs.

De-duplication pass

In all GUIDE and ARCHITECTURE docs:
	•	remove duplicated rule text
	•	replace with short summaries and direct links to the relevant contract
	•	delete conflicting statements
	•	if a guide still contains detailed storage rules, run-status definitions, or support-policy rules after the pass, treat that as a failed documentation pass and fix it

⸻

3. README (user-guide entry)

Keep README.md as the public first-run page. Do not put Type:/Authority: headers on any Markdown page.

Keep:
	•	short product explanation (BYO transcripts; link comparison)
	•	screenshot (Overview after Balanced)
	•	what you can do (about five outcomes)
	•	3–4 step first analysis (GUI labels)
	•	about five common workflows, linking the full set
	•	installation (Docker compose up first; native helper second)
	•	privacy / local AI
	•	advanced/developer links (Python API, public surfaces, architecture)

Remove from the first screen:
	•	managed-import / public-surfaces / schema-epoch / install-marker jargon
	•	Python API snippets (those live in docs/generated/cli.md)
	•	release-history paragraphs (ROADMAP / pre_release_roadmap)
	•	detailed storage rules, run semantics, and architecture

Validate that README claims match supported surfaces.  ￼

⸻

4. Storage, installation, transcription, and Docker docs

docs/STORAGE.md

Ensure it is the clear canonical home for storage invariants. Expand or clarify only if current code behavior requires it.

docs/transcription.md

Keep it as an ingestion guide only:
	•	what TranscriptX expects
	•	how to generate/load transcripts
	•	how to import through the managed path
	•	examples that match current APIs

Do not let it define storage rules; link to docs/STORAGE.md instead. Current ingestion docs already mix workflow with storage/validation concepts, so tighten that boundary where needed.  ￼

docs/installation.md

Keep it focused on installation, environment variables, optional dependencies, and troubleshooting.
If it mentions storage behavior, use canonical contract language or link to docs/STORAGE.md.

docs/docker.md

Keep it focused on Docker runtime behavior, compose usage, mounts, permissions, and container-specific pitfalls.
Cross-check all Docker claims against docker-compose.yml, especially volumes, read/write expectations, imports mounts, environment variables, and service names. The current compose file contains specific mount and environment behavior that can easily drift from prose docs.

⸻

5. Run outcome contract

Ensure docs/run_outcome_contract.md exists and is complete.

It must define:
	•	run_results.json as the single source of truth for run/module outcomes
	•	allowed statuses and their meanings
	•	precedence rules when artifacts and statuses disagree
	•	contract-violation states
	•	relationship to manifest.json, report.json, report.md, and any optional outputs

Then remove inline run-truth semantics from README and other docs, replacing them with a short summary and link.

⸻

6. Output conventions

Review docs/output_conventions.md and decide explicitly whether it is:
	•	the authoritative output contract, or
	•	a short reference/pointer to a more formal output contract doc

Make that explicit in its Type and Authority header.
Do not leave this ambiguous.

⸻

7. Terminology normalization

Ensure docs/TERMS.md exists and is used consistently.

Normalize docs to the canonical vocabulary, including:
	•	canonical transcript
	•	managed transcript
	•	library-valid transcript
	•	sidecar
	•	metadata subtree
	•	staging vs canonical
	•	public surface / supported surface

Remove ad hoc synonyms where they create ambiguity.

⸻

8. Public surfaces

Ensure docs/public_surfaces.md exists and clearly defines:
	•	supported interfaces
	•	unsupported interfaces
	•	deprecated interfaces if any

At minimum, verify whether the following are supported and document them accurately:
	•	GUI / Streamlit app
	•	Python API workflows and request models
	•	managed import workflow
	•	Docker usage as an operational surface
	•	whether any CLI beyond the launcher is supported

Remove stale references to removed CLI analysis commands. The current contributing checklist already warns against reintroducing old CLI surfaces; keep docs aligned with that rule.  ￼

⸻

9. Examples and API validation

Validate all examples against the codebase:
	•	import paths must exist
	•	names and signatures must match
	•	environment variables and defaults must match implementation
	•	Docker commands must match the current compose/image behavior
	•	documented file/layout examples must match current contracts

Do not validate examples against historical CLI behavior; validate against the actual current supported surfaces.

⸻

10. Drift checklist and maintenance docs

Update docs/CONTRIBUTING.md (or the dedicated docs-maintenance doc if one exists) to include a “Doc Drift Checklist” aligned with the new documentation architecture.

At minimum include checks for:
	•	entrypoints changed
	•	storage invariants changed
	•	run-outcome semantics changed
	•	support policy changed
	•	duplicated contract text in a guide
	•	deprecated or removed surfaces reappearing in docs

The current contributing guidance already includes a lightweight sync checklist; extend it so it enforces the new authority model rather than only example correctness.  ￼

⸻

11. Final consistency review

Perform a final pass across core docs and check:
	•	each major concept has one authoritative home
	•	no guide defines storage rules
	•	no guide defines run-truth semantics
	•	no architecture doc defines contract invariants
	•	supported surfaces are described consistently across README, Docker docs, and public-surfaces docs
	•	storage wording is consistent across README, transcription, installation, Docker, and STORAGE
	•	run outcome wording is consistent across README, output docs, and run outcome contract
	•	terminology is normalized

Also sanity-check the contributor journey:
	•	README → installation → transcription → analysis
should be usable without conflicting instructions.

⸻

Execution rules
	•	Documentation-only pass unless explicitly instructed otherwise.
	•	Prefer deleting duplicated rule text over trying to harmonize it in multiple places.
	•	Prefer links to authoritative contract docs over repeated prose.
	•	Do not document speculative or future features.
	•	Do not document unsupported or internal-only surfaces as if they are public APIs.
	•	Keep examples minimal, runnable, and aligned with the current supported interfaces.

⸻

Required completion summary

After completion, summarize:
	•	files updated
	•	headers added or corrected
	•	new contract docs created or expanded
	•	duplicated rule sections removed
	•	supported surfaces confirmed
	•	unresolved ambiguities or docs/code mismatches found