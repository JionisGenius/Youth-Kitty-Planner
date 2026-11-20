CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY NOT NULL,
    token_hash TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    last_used_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_runs (
    id TEXT PRIMARY KEY NOT NULL,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    thread_id TEXT NOT NULL,
    intent TEXT CHECK (intent IN ('CREATE_PLAN','UPDATE_CONSTRAINT','FACT_QUERY','EXPLAIN_PLAN','GENERAL')),
    status TEXT NOT NULL CHECK (status IN ('RUNNING','SUCCEEDED','PARTIAL','NEEDS_INPUT','FAILED','EXHAUSTED')),
    replan_count INTEGER NOT NULL DEFAULT 0 CHECK (replan_count >= 0),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    safe_error_code TEXT
);
CREATE TABLE IF NOT EXISTS plans (
    id TEXT PRIMARY KEY NOT NULL,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 160),
    category TEXT NOT NULL CHECK (category = 'FIRST_JOB_INDEPENDENCE'),
    planning_start_date TEXT NOT NULL,
    planning_end_date TEXT NOT NULL CHECK (planning_end_date >= planning_start_date),
    work_location_label TEXT,
    constraints_json TEXT NOT NULL CHECK (json_valid(constraints_json)),
    generated_by_run_id TEXT REFERENCES agent_runs(id) ON DELETE SET NULL,
    revision_number INTEGER NOT NULL DEFAULT 1 CHECK (revision_number >= 1),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS plan_tasks (
    id TEXT PRIMARY KEY NOT NULL,
    plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 160),
    description TEXT,
    task_date TEXT NOT NULL,
    scheduled_start_at TEXT,
    scheduled_end_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('TODO','IN_PROGRESS','DONE','SKIPPED')),
    estimated_cost_krw INTEGER CHECK (estimated_cost_krw >= 0),
    actual_cost_krw INTEGER CHECK (actual_cost_krw >= 0),
    estimated_duration_minutes INTEGER CHECK (estimated_duration_minutes > 0),
    actual_duration_minutes INTEGER CHECK (actual_duration_minutes > 0),
    source_kind TEXT NOT NULL CHECK (source_kind IN ('RULE','AI_DRAFT','USER_EDIT','FORK_IMPORT')),
    sort_order INTEGER NOT NULL CHECK (sort_order >= 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK ((scheduled_start_at IS NULL AND scheduled_end_at IS NULL)
        OR (scheduled_start_at IS NOT NULL AND scheduled_end_at IS NOT NULL
            AND scheduled_end_at > scheduled_start_at))
);
CREATE TABLE IF NOT EXISTS run_events (
    id TEXT PRIMARY KEY NOT NULL,
    run_id TEXT NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL CHECK (sequence > 0),
    event_type TEXT NOT NULL CHECK (event_type IN ('RUN_STARTED','NODE_STARTED','NODE_FINISHED',
        'INTENT_DECIDED','WORKFLOW_CREATED','TOOL_REQUESTED','TOOL_SUCCEEDED','TOOL_FAILED',
        'CONSTRAINT_EVALUATED','REPLAN_STARTED','REPLAN_EXHAUSTED','RUN_FINISHED','RUN_FAILED')),
    node_name TEXT,
    occurred_at TEXT NOT NULL,
    duration_ms INTEGER CHECK (duration_ms >= 0),
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    UNIQUE (run_id, sequence)
);
CREATE TRIGGER IF NOT EXISTS run_events_append_only
BEFORE UPDATE ON run_events BEGIN
    SELECT RAISE(ABORT, 'run_events is append-only');
END;
CREATE TABLE IF NOT EXISTS plan_sources (
    id TEXT PRIMARY KEY NOT NULL,
    plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    task_id TEXT REFERENCES plan_tasks(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL CHECK (source_type IN ('OFFICIAL_API','USER_INPUT','USER_EXPERIENCE','AI_ESTIMATE','EVIDENCE_VERIFIED')),
    provider TEXT,
    source_ref TEXT,
    source_url TEXT,
    fetched_at TEXT,
    observed_at TEXT,
    verification_status TEXT NOT NULL CHECK (verification_status IN ('UNVERIFIED','SOURCE_CONFIRMED','EVIDENCE_CHECKED')),
    caveat TEXT
);
CREATE TABLE IF NOT EXISTS plan_evaluations (
    id TEXT PRIMARY KEY NOT NULL,
    plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    candidate_id TEXT,
    rule_code TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PASS','FAIL','UNKNOWN')),
    expected_json TEXT CHECK (json_valid(expected_json)),
    observed_json TEXT CHECK (json_valid(observed_json)),
    reason_code TEXT NOT NULL,
    source_id TEXT REFERENCES plan_sources(id) ON DELETE SET NULL,
    checked_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS plans_session_updated ON plans(session_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS tasks_plan_date ON plan_tasks(plan_id, task_date);
CREATE INDEX IF NOT EXISTS runs_session_started ON agent_runs(session_id, started_at DESC);
CREATE INDEX IF NOT EXISTS evaluations_plan_rule ON plan_evaluations(plan_id, rule_code);
CREATE INDEX IF NOT EXISTS sources_plan ON plan_sources(plan_id);

