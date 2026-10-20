# AILT9019 Midterm Check — Team Status Sheet (One Page)

> Companion to the proposal. Keep to one page. Update the bracketed `[...]` items.
> Date: 2026-10-20 · Week 9

## 1. Working now
- [x] Repository scaffold (README, license, .gitignore, sample data, test).
- [x] Core path reference implementation: document ingestion → extraction →
      prioritization → weekly brief (`src/pipeline.py`, dependency-free).
- [x] Reproducibility test (`tests/test_pipeline.py`) passing on sample inputs.
- [ ] Browser / richer UI (should-have, not required for the check).
- [ ] PDF / .docx ingestion (should-have).

## 2. Test evidence
- `python tests/test_pipeline.py` → `TEST PASSED` with task counts.
- Sample inputs in `data/sample_inputs/` (synthetic syllabus + announcement).
- Generated brief in `data/sample_output/brief.json`; illustrative expected
  structure in `data/sample_output/expected_brief.json`.
- Known limitation demonstrated: a missing/ambiguous deadline is **flagged**,
  not invented (see `note` field on undated tasks).

## 3. Limitations
- Rule-based extraction (keyword + date matching), not an LLM.
- Priority = function of days-until-deadline only; importance not yet weighted.
- Conflict detection only when two dated tasks fall within 2 days.
- PDF / .docx not yet parsed (text inputs supported).

## 4. Blockers & owners
| Blocker | Owner | Next step |
|---------|-------|-----------|
| [ ] PDF/.docx ingestion not implemented | [name] | Add pdfplumber/python-docx reader behind `extract.py` |
| [ ] UI for non-coders | [name] | Wrap pipeline in minimal web form |
| [ ] Realistic test set size | [name] | Expand `sample_inputs` with edge cases |

## 5. Next two weeks (three dated milestones)
| # | Milestone | Owner | Due | Completion check |
|---|-----------|-------|-----|------------------|
| 1 | Finalize + record 1-min demo of core path | [name] | 2026-10-23 | mp4 plays end-to-end, <60s |
| 2 | Expand test set + edge cases; lock evaluation metrics | [name] | 2026-10-28 | `test_pipeline.py` covers conflicts + missing dates |
| 3 | Write final README + dry-run staff reproduction | [name] | 2026-11-02 | A fresh clone reproduces the brief unaided |

## 6. Contribution & scope (one entry per member)
| Member | Genuine contribution (incl. non-coding) |
|--------|------------------------------------------|
| [name / UID] | [e.g. built extract.py, wrote sample data, recorded demo] |
| [name / UID] | [e.g. designed prioritization, authored STATUS_SHEET] |
| [name / UID] | [e.g. set up repo + README, ran tests] |

**Scope decision (keep / cut):** Keeping core workflow + testing for the check.
Cutting (for now): full UI, multi-format ingestion, MCP/agent integration —
tracked as should-haves for the final project stage.
