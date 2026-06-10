# Iteration 24 - Chapter Consistency + Neo4j Mixed Graph Read

## Completed in this iteration
- Verified backend imports after the latest chapter consistency additions.
- Verified frontend production build after the latest chapter workbench updates.
- Confirmed the chapter consistency flow is wired through backend route and frontend action.
- Extended Neo4j graph client with mixed graph read capability for:
  - `Character`
  - `PlotLine`
  - `StoryEvent`
  - `Chapter`
  - `ChapterPlan`
- Updated graph service to prefer Neo4j for non-character graph reads when graph data exists.
- Kept SQLite fallback as the resilience path when Neo4j is unavailable or sparse.

## Key code changes
- `backend/app/graph/client.py`
  - Added `get_mixed_graph(...)`
  - Added `_get_mixed_graph_tx(...)`
  - Added node mapping for multiple entity labels
  - Added edge normalization for:
    - `RELATED_TO`
    - `PARTICIPATES_IN`
    - `CONTAINS_EVENT`
    - `INCLUDES_EVENT`
    - `HAS_PLAN`
    - `GUIDES_PLAN`
- `backend/app/services/graph_service.py`
  - `get_project_graph(...)` now attempts Neo4j mixed reads for:
    - `mixed`
    - `plot`
    - `event`
    - `chapter`
  - Character-only path still uses the focused character graph query when applicable.

## Validation results
- Backend import check: passed
  - `import app.main`
  - `execute_chapter_consistency_task`
  - `get_project_graph`
- Frontend build: passed
  - `npm run build`

## Issues encountered
- One validation command failed initially because the import name used in the shell check was wrong.
- This was not an application bug. The actual exported symbol is:
  - `execute_chapter_consistency_task`

## Analysis
- Before this iteration, graph writes had started to reach Neo4j for more entities, but read behavior still favored SQLite fallback for most graph views.
- That meant the frontend graph studio could not fully benefit from Neo4j once richer entities were synchronized.
- The new mixed read path closes that gap and makes the architecture more coherent:
  - structured entities are written to relational storage
  - graph relationships are mirrored to Neo4j
  - graph visualization can now read from Neo4j first

## Current stage
- Project stage is now:
  - real backend/frontend foundation complete
  - search-driven topic exploration complete
  - OpenRouter-first generation complete
  - taskified chapter design/draft flows complete
  - chapter consistency self-check started
  - Neo4j mixed visualization path partially operational

## Remaining gaps
- Neo4j synchronization is still not fully comprehensive for every possible novel entity.
- Worldbook graph sync is still not represented in Neo4j.
- There is not yet a revision loop that consumes consistency reports and rewrites chapter drafts automatically.
- Task center and chapter workbench are related, but chapter-quality task traceability can still be made clearer in the UI.
- End-to-end docker runtime with all dependent services still needs final operational verification while your Docker stack is coming up.

## Recommended next priorities
1. Add chapter revision/version chain:
   - consistency report -> rewrite task -> new version
2. Add worldbook graph sync and mixed graph read support.
3. Add project workflow orchestration endpoints:
   - trend explore -> asset map -> plan -> chapter design -> draft -> consistency -> revise
4. Add richer task center linkage on frontend:
   - filter by chapter
   - filter by module
   - inspect step runtime inline
5. Run docker-compose level verification with backend, frontend, redis, neo4j and database together.

## Reusable details for next AI
- Use OpenRouter as the primary LLM path and continue runtime free-model discovery instead of fixed model IDs.
- Keep secrets in env only; do not read or print private values.
- Keep updating `cache-memory` after each meaningful milestone.
- Prefer taskified workflows over one-shot endpoints for any non-trivial creative pipeline.
