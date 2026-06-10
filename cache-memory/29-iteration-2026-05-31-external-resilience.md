# Iteration 29 - External Dependency Resilience

## Completed in this iteration
- Added a shared retry utility for unstable external dependencies.
- Added retry/timeout handling to Tavily, Firecrawl and OpenRouter integrations.
- Improved trend exploration failure semantics.
- Improved OpenRouter error reporting so model discovery, selection and completion failures are easier to diagnose.

## Backend changes
- Added:
  - `backend/app/core/resilience.py`
  - `with_retries(...)`
- Extended settings:
  - `external_request_retries`
  - `external_request_timeout_seconds`
  - `llm_request_timeout_seconds`
- Updated integrations:
  - `backend/app/integrations/tavily_client.py`
  - `backend/app/integrations/firecrawl_client.py`
  - `backend/app/integrations/openrouter_client.py`
- Updated services:
  - `backend/app/services/trend_service.py`
  - `backend/app/services/openrouter_service.py`

## Functional impact
- Tavily searches now retry instead of failing immediately on transient transport errors.
- Firecrawl scrapes now retry with shared timeout policy.
- OpenRouter model listing and chat completion now retry with shared timeout policy.
- Trend exploration now raises clearer business-layer errors when the Tavily stage fails.
- When search returns no results, trend extraction still produces a usable fallback direction message.

## Validation results
- Backend import check: passed
- Frontend build: passed

## Engineering impact
- The automatic novel workflow is now more resilient to transient network failures.
- Resilience settings are centralized instead of hardcoded across integrations.
- The next step can focus on runtime UX and infrastructure validation instead of basic external-call brittleness.

## Remaining gaps
- No circuit breaker or provider health cache exists yet.
- No fallback search provider beyond Tavily is implemented.
- Orchestration still depends on live external search for the trend stage.
- Docker full-stack runtime validation is still pending.

## Recommended next priorities
1. Add workflow run summary/dashboard status visibility.
2. Add Docker full-stack verification with backend, frontend, redis, neo4j and SQLite/DB services together.
3. Add optional cached/fallback trend mode when external search is unavailable.
4. Add restore-from-version capability for chapter history.
