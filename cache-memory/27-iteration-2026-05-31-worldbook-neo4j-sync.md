# Iteration 27 - Worldbook Neo4j Sync + Mixed Graph Support

## Completed in this iteration
- Added `WorldbookEntry` synchronization into Neo4j.
- Extended Neo4j mixed graph read path to include worldbook nodes.
- Added `worldbook` graph type option in frontend graph studio.
- Expanded frontend graph node meta typing to support multiple entity families.

## Backend changes
- `backend/app/graph/client.py`
  - added `upsert_worldbook_entry(...)`
  - added `_upsert_worldbook_entry_tx(...)`
  - extended mixed graph read query to include `WorldbookEntry`
  - added node mapping for `WorldbookEntry`
- `backend/app/services/graph_service.py`
  - added `sync_worldbook_entry_to_neo4j(...)`
  - added SQLite fallback node rendering for worldbook entries
  - included `worldbook` in graph type support
- `backend/app/services/worldbook_service.py`
  - now syncs entries to Neo4j after relational persistence

## Frontend changes
- `frontend/src/components/GraphStudioView.tsx`
  - added `worldbook` graph type selector
  - graph detail view now displays `category` when `status` is absent
- `frontend/src/types.ts`
  - extended `GraphNode.meta` with multi-entity fields:
    - `category`
    - `source_type`
    - `source_ref`
    - `plot_type`
    - `priority`
    - `event_type`
    - `impact_level`
    - `chapter_no`
    - `selected_model`

## Validation results
- Backend import check: passed
- Frontend build: passed

## Product impact
- Worldbuilding assets are no longer isolated in relational lists only.
- Graph Studio can now present worldbook knowledge as part of the broader project knowledge graph.
- This improves the long-term architecture for:
  - world rule consistency
  - lore inspection
  - future constraint-aware writing agents

## Remaining limitations
- Worldbook entries are currently represented as standalone graph nodes.
- They are not yet linked to:
  - chapters
  - events
  - plot lines
  - characters
- There is not yet a worldbook-specific authoring or linking workflow.

## Recommended next priorities
1. Add orchestration endpoint for one-click workflow execution:
   - trend exploration
   - asset mapping
   - chapter design
   - draft generation
   - consistency check
   - revision
2. Add explicit graph edges from worldbook entries to relevant entities.
3. Add restore-from-version action for chapter history.
4. Add richer filters in task center.
