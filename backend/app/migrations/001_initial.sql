CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    subject TEXT NOT NULL,
    scheduled_date TEXT NOT NULL,
    estimated_minutes INTEGER NOT NULL DEFAULT 30 CHECK(estimated_minutes BETWEEN 1 AND 1440),
    notes TEXT NOT NULL DEFAULT '',
    completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN (0,1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX tasks_date ON tasks(scheduled_date);
CREATE TABLE knowledge_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    domain TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'unstarted' CHECK(status IN ('unstarted','learning','consolidating','mastered')),
    notes TEXT NOT NULL DEFAULT '',
    is_reference INTEGER NOT NULL DEFAULT 0 CHECK(is_reference IN (0,1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(domain,title)
);
CREATE TABLE study_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    topic TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL,
    ended_at TEXT,
    status TEXT NOT NULL CHECK(status IN ('running','paused','finished')),
    CHECK((status = 'finished') = (ended_at IS NOT NULL))
);
CREATE UNIQUE INDEX one_active_session ON study_sessions((1)) WHERE status != 'finished';
CREATE TABLE study_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES study_sessions(id) ON DELETE CASCADE,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    CHECK(ended_at IS NULL OR ended_at >= started_at)
);
CREATE UNIQUE INDEX one_open_segment ON study_segments(session_id) WHERE ended_at IS NULL;
CREATE TABLE mistakes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    subject TEXT NOT NULL DEFAULT '数学',
    question TEXT NOT NULL,
    answer TEXT NOT NULL DEFAULT '',
    error_reason TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE mistake_knowledge (
    mistake_id INTEGER NOT NULL REFERENCES mistakes(id) ON DELETE CASCADE,
    knowledge_id INTEGER NOT NULL REFERENCES knowledge_points(id) ON DELETE RESTRICT,
    PRIMARY KEY(mistake_id,knowledge_id)
);
CREATE TABLE review_schedules (
    mistake_id INTEGER PRIMARY KEY REFERENCES mistakes(id) ON DELETE CASCADE,
    stage INTEGER NOT NULL DEFAULT 0 CHECK(stage BETWEEN 0 AND 5),
    due_date TEXT,
    last_reviewed_at TEXT,
    CHECK((stage = 5) = (due_date IS NULL))
);
CREATE INDEX reviews_due ON review_schedules(due_date);
CREATE TABLE review_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mistake_id INTEGER NOT NULL REFERENCES mistakes(id) ON DELETE CASCADE,
    outcome TEXT NOT NULL CHECK(outcome IN ('remembered','forgotten')),
    reviewed_at TEXT NOT NULL,
    previous_stage INTEGER NOT NULL,
    next_stage INTEGER NOT NULL,
    next_due_date TEXT,
    notes TEXT NOT NULL DEFAULT ''
);
