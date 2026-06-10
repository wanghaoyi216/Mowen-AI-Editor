# Iteration 26 - Task Browser + Chapter Version Compare

## Completed in this iteration
- Upgraded task center from manual task ID lookup to a browsable task list workflow.
- Added backend task detail query support.
- Added chapter-scoped task browsing in frontend.
- Added chapter version compare view in chapter workbench.
- Linked chapter workbench to task runtime panel for chapter-local task inspection.

## Backend changes
- `backend/app/services/task_service.py`
  - added `get_task(...)`
- `backend/app/api/routes/tasks.py`
  - added `GET /api/v1/projects/{project_id}/tasks/{task_id}`

## Frontend changes
- `frontend/src/lib/api.ts`
  - added:
    - `fetchTasks(...)`
    - `fetchTask(...)`
    - `fetchTaskSteps(...)`
- `frontend/src/types.ts`
  - added:
    - `AITask`
    - `TaskStep`
- `frontend/src/components/TaskRuntimePanel.tsx`
  - now supports:
    - project filter
    - chapter filter
    - task selection dropdown
    - task detail rendering
    - step list rendering
    - runtime + persisted step detail fusion
- `frontend/src/components/ChapterWorkbench.tsx`
  - now supports:
    - selecting a historical chapter version
    - viewing current draft and historical version side by side
    - basic diff preview based on paragraph-level changes
    - embedded task runtime panel scoped to current chapter
- `frontend/src/App.tsx`
  - simplified task page header section and delegated real task browsing to `TaskRuntimePanel`
- `frontend/src/styles.css`
  - added:
    - comparison grid
    - selectable cards
    - diff row styles

## Validation results
- Backend import check: passed
- Frontend build: passed

## Product impact
- Writers/operators can now inspect actual task execution traces without manually guessing task IDs.
- Chapter revision history is no longer opaque:
  - current draft can be compared with a stored historical version
  - revision chain is more auditable
- This is a practical step toward:
  - draft QA
  - regression analysis
  - future rollback / restore capabilities

## Remaining limitations
- Diff preview is currently lightweight paragraph comparison, not a full structured text diff.
- There is no explicit restore-version action yet.
- Task center still lacks richer grouping by:
  - module type
  - task type
  - status
- Chapter plan history is not versioned yet, only chapter draft outputs are versioned.

## Recommended next priorities
1. Add `WorldbookEntry` sync into Neo4j and expose it in mixed graph reads.
2. Add restore-from-version action for chapters.
3. Add task filtering by status/module/task type in the task center.
4. Add richer diff presentation for revised chapters.
