# Iteration 28 - Auto Workflow Orchestration

## Completed in this iteration
- Added a one-click end-to-end automatic novel workflow.
- Implemented orchestration as a formal task-domain workflow instead of ad hoc frontend chaining.
- Added frontend trigger entry for automatic execution from the trend workbench.
- Added failure-state reporting for orchestration runtime steps.

## Backend changes
- Added schema:
  - `backend/app/schemas/workflow_orchestration.py`
  - `AutoNovelWorkflowRequest`
- Added orchestration service:
  - `backend/app/services/workflow_orchestration_service.py`
- Added task route:
  - `POST /api/v1/projects/{project_id}/tasks/execute-auto-novel-workflow`

## Workflow coverage
- The orchestration now executes:
  1. trend exploration
  2. trend asset mapping
  3. chapter load or auto-create
  4. chapter design
  5. chapter draft generation
  6. chapter consistency check
  7. chapter revision

## Runtime behavior
- Workflow is represented as a parent orchestration task in the task center.
- Step runtime state is updated during execution.
- When an exception occurs:
  - current step runtime is marked `failed`
  - parent task runtime is marked `failed`
  - error text is surfaced into runtime message

## Frontend changes
- `frontend/src/components/TrendWorkbench.tsx`
  - added one-click execution button:
    - `一键自动创作流程`
  - added chapter title / design guidance / style hint / revision focus inputs
  - added automatic workflow result rendering
- `frontend/src/lib/api.ts`
  - added `executeAutoNovelWorkflow(...)`
- `frontend/src/types.ts`
  - added `AutoNovelWorkflowResult`

## Validation results
- Backend import check: passed
- Frontend build: passed

## Real smoke-test finding
- A real orchestration smoke test was attempted.
- The workflow failed at the external Tavily request layer due to a network connection reset:
  - connection aborted / remote host closed connection
- This does not contradict the orchestration code being wired correctly.
- It does show the next production-hardening need very clearly:
  - retry
  - graceful degradation
  - optional cached or fallback trend path

## Current project stage
- The project now has:
  - search
  - asset generation
  - graph sync
  - task center
  - chapter design/draft/check/revise
  - version history
  - one-click orchestration

## Remaining important gaps
- Auto workflow currently depends on external search availability at runtime.
- No retry/backoff strategy exists yet for Tavily / Firecrawl transient failures.
- No workflow dashboard summary exists yet for success/failure rate and last run status.
- Docker full-stack validation is still pending once all services are up and connected.

## Recommended next priorities
1. Add resilient retry/fallback logic for external search/scrape calls.
2. Add workflow run summary UI in dashboard/task center.
3. Add restore-from-version action for chapters.
4. Add Docker full-stack verification with backend, frontend, redis, neo4j and DB together.
