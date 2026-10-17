CREATE TABLE subjects (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE);
INSERT INTO subjects(name) VALUES ('数学'),('英语'),('政治'),('专业课'),('C/C++'),('Linux');
INSERT OR IGNORE INTO subjects(name) SELECT subject FROM tasks UNION SELECT subject FROM mistakes UNION SELECT subject FROM study_sessions;
CREATE TABLE goals (
 id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, subject TEXT NOT NULL,
 target_date TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '', completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN(0,1)),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
ALTER TABLE tasks ADD COLUMN priority INTEGER NOT NULL DEFAULT 2 CHECK(priority BETWEEN 1 AND 3);
ALTER TABLE tasks ADD COLUMN goal_id INTEGER REFERENCES goals(id) ON DELETE SET NULL;
ALTER TABLE tasks ADD COLUMN status TEXT NOT NULL DEFAULT 'todo' CHECK(status IN('todo','doing','done'));
UPDATE tasks SET status='done' WHERE completed=1;
ALTER TABLE knowledge_points ADD COLUMN subject TEXT NOT NULL DEFAULT '数学';
ALTER TABLE knowledge_points ADD COLUMN parent_id INTEGER REFERENCES knowledge_points(id) ON DELETE RESTRICT;
ALTER TABLE knowledge_points ADD COLUMN mastery INTEGER NOT NULL DEFAULT 0 CHECK(mastery BETWEEN 0 AND 5);
ALTER TABLE knowledge_points ADD COLUMN last_studied_at TEXT;
ALTER TABLE knowledge_points ADD COLUMN last_reviewed_at TEXT;
ALTER TABLE knowledge_points ADD COLUMN exam_scopes TEXT NOT NULL DEFAULT '[]';
ALTER TABLE knowledge_points ADD COLUMN syllabus_source TEXT NOT NULL DEFAULT '';
ALTER TABLE knowledge_points ADD COLUMN syllabus_year INTEGER;
UPDATE knowledge_points SET mastery=CASE status WHEN 'mastered' THEN 5 WHEN 'consolidating' THEN 3 WHEN 'learning' THEN 1 ELSE 0 END;
ALTER TABLE study_sessions ADD COLUMN mode TEXT NOT NULL DEFAULT 'forward' CHECK(mode IN('forward','pomodoro','manual'));
ALTER TABLE study_sessions ADD COLUMN target_seconds INTEGER NOT NULL DEFAULT 1500;
ALTER TABLE study_sessions ADD COLUMN break_seconds INTEGER NOT NULL DEFAULT 300;
ALTER TABLE study_sessions ADD COLUMN request_id TEXT;
CREATE UNIQUE INDEX session_requests ON study_sessions(request_id) WHERE request_id IS NOT NULL;
ALTER TABLE mistakes ADD COLUMN wrong_answer TEXT NOT NULL DEFAULT '';
ALTER TABLE mistakes ADD COLUMN category TEXT NOT NULL DEFAULT '未分类';
ALTER TABLE mistakes ADD COLUMN mastery TEXT NOT NULL DEFAULT 'unmastered' CHECK(mastery IN('unmastered','reviewing','mastered'));
UPDATE mistakes SET mastery=CASE WHEN id IN(SELECT mistake_id FROM review_schedules WHERE stage=5) THEN 'mastered' ELSE 'unmastered' END;
ALTER TABLE review_events RENAME TO review_events_v1;
CREATE TABLE review_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, mistake_id INTEGER NOT NULL REFERENCES mistakes(id) ON DELETE CASCADE,
 outcome TEXT NOT NULL CHECK(outcome IN('remembered','forgotten','assisted')), reviewed_at TEXT NOT NULL,
 previous_stage INTEGER NOT NULL, next_stage INTEGER NOT NULL, next_due_date TEXT, notes TEXT NOT NULL DEFAULT '', due_date TEXT
);
INSERT INTO review_events(id,mistake_id,outcome,reviewed_at,previous_stage,next_stage,next_due_date,notes)
 SELECT id,mistake_id,outcome,reviewed_at,previous_stage,next_stage,next_due_date,notes FROM review_events_v1;
DROP TABLE review_events_v1;
CREATE TABLE knowledge_reviews (
 knowledge_id INTEGER PRIMARY KEY REFERENCES knowledge_points(id) ON DELETE CASCADE,
 stage INTEGER NOT NULL DEFAULT 0 CHECK(stage BETWEEN 0 AND 5), due_date TEXT, last_reviewed_at TEXT,
 CHECK((stage=5)=(due_date IS NULL))
);
CREATE TABLE knowledge_review_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, knowledge_id INTEGER NOT NULL REFERENCES knowledge_points(id) ON DELETE CASCADE,
 outcome TEXT NOT NULL CHECK(outcome IN('remembered','forgotten','assisted')), reviewed_at TEXT NOT NULL,
 previous_stage INTEGER NOT NULL, next_stage INTEGER NOT NULL, next_due_date TEXT, notes TEXT NOT NULL DEFAULT '', due_date TEXT
);
CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE activity_events (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, entity_id INTEGER NOT NULL, value INTEGER NOT NULL DEFAULT 0, happened_at TEXT NOT NULL);
CREATE INDEX activity_time ON activity_events(happened_at);
CREATE TABLE files (id TEXT PRIMARY KEY, name TEXT NOT NULL, mime TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN('image','material')), size INTEGER NOT NULL, sha256 TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE mistake_files (mistake_id INTEGER NOT NULL REFERENCES mistakes(id) ON DELETE CASCADE, file_id TEXT NOT NULL REFERENCES files(id) ON DELETE RESTRICT, PRIMARY KEY(mistake_id,file_id));
CREATE TABLE materials (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, category TEXT NOT NULL DEFAULT '未分类', notes TEXT NOT NULL DEFAULT '', knowledge_id INTEGER REFERENCES knowledge_points(id) ON DELETE RESTRICT, file_id TEXT REFERENCES files(id) ON DELETE RESTRICT, extracted_text TEXT NOT NULL DEFAULT '', extraction_status TEXT NOT NULL DEFAULT 'none', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE ai_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL, purpose TEXT NOT NULL, prompt TEXT NOT NULL, answer TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL, context_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX ai_conversation ON ai_runs(conversation_id,id);
ALTER TABLE tasks ADD COLUMN revision INTEGER NOT NULL DEFAULT 1;
ALTER TABLE knowledge_points ADD COLUMN revision INTEGER NOT NULL DEFAULT 1;
ALTER TABLE mistakes ADD COLUMN revision INTEGER NOT NULL DEFAULT 1;
