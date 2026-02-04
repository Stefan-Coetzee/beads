# Maji Ndogo Part 1 - JSON Build Plan

## Overview

We're converting the LaTeX document `project_data/DA/MN_Part1/md_part1.tex` into structured JSON for LLM tutor ingestion.

### Source Material
- **LaTeX file**: Contains chat-style messages from Chidi Kunto (mentor) guiding learners through SQL exploration
- **Setting**: Maji Ndogo country, analyzing water source survey data
- **Characters**:
  - Aziza Naledi (President) - sets the mission
  - Chidi Kunto (Mentor/Tutor) - guides the learning
- **Database**: `md_water_services` with 60,000 records

### Schema Reference
See `docs/SCHEMA-FOR-LLM-INGESTION.md` for field definitions.

---

## File Structure

```
src/ltt/tempdocs/
├── BUILD_PLAN.md           # This file
├── 00_project_overview.json # Project-level metadata
├── 01_epic_introduction.json
├── 02_epic_get_to_know_data.json
├── 03_epic_dive_into_sources.json
├── 04_epic_unpack_visits.json
├── 05_epic_water_quality.json
├── 06_epic_pollution_issues.json
└── aggregate.py            # Combines fragments into final JSON
```

---

## Epic Breakdown (from LaTeX)

### Epic 0: Introduction
- Naledi's opening message (narrative context)
- Chidi's self-introduction
- Task overview (5 tasks listed)

### Epic 1: Get to Know Our Data
- SHOW TABLES
- Explore location table (SELECT * LIMIT 5)
- Explore visits table
- Explore water_source table
- Data dictionary mention

### Epic 2: Dive into Water Sources
- SELECT DISTINCT type_of_water_source
- Water source type explanations:
  - River (worst, open water)
  - Well (underground, can be contaminated)
  - Shared tap (public, serves ~2700 people)
  - Tap in home (best, serves ~6 people)
  - Broken tap in home (infrastructure failure)
- Note on aggregated home tap records (160 homes × 6 people ≈ 956)

### Epic 3: Unpack the Visits
- WHERE time_in_queue > 500
- Human impact discussion (8+ hours for water)
- Use IN() to check multiple source_ids
- Discover which source types have queues (shared_tap)

### Epic 4: Water Source Quality
- Explore water_quality table
- Find records: subjective_quality_score = 10 AND visit_count = 2
- Identify data anomalies (218 suspicious records)
- Answer rationale: shared_taps shouldn't have score 10

### Epic 5: Pollution Issues
- Explore well_pollution table
- Find contradictions: results='Clean' AND biological > 0.01
- LIKE pattern matching: description LIKE 'Clean_%'
- CREATE TABLE copy for safe testing
- UPDATE statements (3 cases):
  - Case 1a: Fix 'Clean Bacteria: E. coli' → 'Bacteria: E. coli'
  - Case 1b: Fix 'Clean Bacteria: Giardia Lamblia' → 'Bacteria: Giardia Lamblia'
  - Case 2: Set results='Contaminated: Biological' where biological > 0.01
- DROP TABLE cleanup

---

## Key SQL Answers (from LaTeX memo sections)

| Task | Expected SQL |
|------|-------------|
| SHOW TABLES | `SHOW TABLES` |
| Explore location | `SELECT * FROM location LIMIT 5` |
| Explore visits | `SELECT * FROM visits LIMIT 5` |
| Explore water_source | `SELECT * FROM water_source LIMIT 5` |
| Unique source types | `SELECT DISTINCT type_of_water_source FROM water_source` |
| Long queues | `SELECT * FROM visits WHERE time_in_queue > 500` |
| Check source IDs | `SELECT * FROM water_source WHERE source_id IN('AkRu05234224', ...)` |
| Quality anomalies | `SELECT * FROM water_quality WHERE visit_count = 2 AND subjective_quality_score = 10` |
| Explore pollution | `SELECT * FROM well_pollution` |
| Find contradictions | `SELECT * FROM well_pollution WHERE results = 'Clean' AND biological > 0.01` |
| LIKE pattern | `SELECT * FROM well_pollution WHERE description LIKE 'Clean_%'` |
| Create copy | `CREATE TABLE well_pollution_copy AS (SELECT * FROM well_pollution)` |
| Update E. coli | `UPDATE well_pollution SET description = 'Bacteria: E. coli' WHERE description = 'Clean Bacteria: E. coli'` |
| Update Giardia | `UPDATE well_pollution SET description = 'Bacteria: Giardia Lamblia' WHERE description = 'Clean Bacteria: Giardia Lamblia'` |
| Update results | `UPDATE well_pollution SET results = 'Contaminated: Biological' WHERE biological > 0.01 AND results = 'Clean'` |
| Drop copy | `DROP TABLE well_pollution_copy` |

---

## Design Decisions

1. **Chidi's voice**: His actual messages become `content` fields
2. **Conversational subtasks**: Precede technical exercises (e.g., "Consider the human impact" before "Write WHERE clause")
3. **Linear dependencies**: Maintain the original document's flow
4. **Answer rationales**: Extracted from orange memo boxes for `tutor_guidance.answer_rationale`
5. **Acceptance criteria**: Focus on SQL query submission (interface validates result sets)

---

## Aggregation

Run `python aggregate.py` to combine all fragments into `water_analysis_project.json`
