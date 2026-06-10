# Iteration 25 - Chapter Revision Chain + Migration Alignment

## Completed in this iteration
- Added a real chapter revision workflow after consistency checking.
- Added persistent chapter version history storage.
- Added frontend revision action and version history display.
- Aligned local SQLite development database with Alembic migration state.

## Backend changes
- Added `ChapterVersion` model:
  - stores version number
  - operation type
  - revision instruction
  - consistency report
  - generated content
  - selected model
- Added schema:
  - `ChapterVersionRead`
  - `ChapterRevisionRequest`
- Added chapter version listing service.
- Added revision pipeline in `chapter_ai_service.py`:
  - consistency review
  - rewrite generation
  - chapter status update
  - version increment
  - chapter version persistence
- Added taskified chapter revision flow in `chapter_task_service.py`.
- Added routes:
  - `GET /api/v1/projects/{project_id}/chapters/{chapter_id}/versions`
  - `POST /api/v1/projects/{project_id}/chapters/{chapter_id}/revise-task`

## Frontend changes
- `ChapterWorkbench` now supports:
  - revision focus input
  - consistency-driven revision action
  - version history list
  - display of consistency model and rewrite model
- API client now supports:
  - fetch chapter versions
  - execute revision task

## Migration and DB status
- Added Alembic migration:
  - `20260531_0002_chapter_versions.py`
- Found a real local DB alignment issue:
  - existing SQLite database had been partially created outside Alembic history
  - direct `alembic upgrade head` failed because base tables already existed
- Recovery path executed:
  - inspected current tables
  - ensured metadata tables existed
  - stamped Alembic to `20260531_0002`
- Current Alembic version in local DB:
  - `20260531_0002`

## Validation results
- Backend import check: passed
- Frontend build: passed
- Alembic version check: passed

## Important engineering note
- Local development database history was not purely migration-driven.
- For continued development, prefer:
  - schema changes via Alembic first
  - avoid relying on `create_all()` as the authoritative path for existing environments

## Current project stage
- The project is now at:
  - trend exploration and asset extraction complete
  - taskified chapter design complete
  - taskified chapter drafting complete
  - consistency checking complete
  - consistency-guided revision chain started
  - revision history persistence complete
  - Neo4j mixed graph read path partially operational

## Next priority recommendations
1. Add revision diff view on frontend:
   - compare current draft with previous versions
2. Add worldbook to Neo4j sync + visualization
3. Add one-click end-to-end workflow orchestration:
   - trend -> assets -> plan -> design -> draft -> check -> revise
4. Add Docker full-stack verification once all containers are running:
   - frontend
   - backend
   - redis
   - neo4j
   - database
5. Add chapter quality score extraction from consistency reports for project-wide monitoring
