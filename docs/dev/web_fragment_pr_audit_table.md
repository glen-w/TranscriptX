Type: PRODUCT
Authority: self

# Web fragment / rerun audit (PR review aid)

Copy this table into the PR description and update **Status** as work lands.

| Page | Candidate widgets | Fragment boundary | Kept full-rerun actions | Notes / risks |
|------|-------------------|-------------------|-------------------------|---------------|
| Batch Ops | Transcript + module multiselects, mode select | Selection + captions inside fragment; Run button outside | After batch run (none unless added); button uses `session_state` | Commit: Run Batch Analysis reads widget keys on full rerun |
| Run Analysis | Target + transcript/group pick (parent); mode, profile, defaults checkbox, module multiselect | Config stack in fragment; target + launch + progress outside | Launch, post-run nav, progress panel | `default_modules` passed from parent on full run only |
| Charts | Filters + gallery + export + overview | Single fragment: reset through gallery; shell/artifact list outside | Fullscreen card `st.rerun` (commit-style UI) | Parent precomputes `all_charts`, filter option lists, overview config |
| Groups | Create-group transcript multiselect | Create expander body in fragment | After successful **Create group** | Name/description stay outside fragment (low churn) |
| Corrections Studio | (deferred this PR) | Full-page rerun retained | — | Risky auto-edit reverted; follow-up: fragment from filters through export with tests |
| Audio Prep | (deferred this PR) | — | — | Needs parent/fragment split for section B/C coupling |
| Audio Merge | Multiselect + order + merge run | `@st.fragment` on `_render_section_1` (includes merge through section 2) | Upload in parent | Move arrows use `st.rerun(scope="fragment")` |

**Rerun classification:** navigation | commit-apply | stale-data invalidation | accidental preview — remove accidental.

**Rollback:** Revert any page that needs fragile parent/fragment sync or extra rerun gymnastics.
