-- Rebuild with foreign keys temporarily disabled by the migration runner.
-- All IDs and references are retained and checked before the transaction commits.
CREATE TABLE knowledge_points_new (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 title TEXT NOT NULL, domain TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'unstarted' CHECK(status IN('unstarted','learning','consolidating','mastered')),
 notes TEXT NOT NULL DEFAULT '', is_reference INTEGER NOT NULL DEFAULT 0 CHECK(is_reference IN(0,1)),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 subject TEXT NOT NULL DEFAULT '数学', parent_id INTEGER REFERENCES knowledge_points(id) ON DELETE RESTRICT,
 mastery INTEGER NOT NULL DEFAULT 0 CHECK(mastery BETWEEN 0 AND 5), last_studied_at TEXT, last_reviewed_at TEXT,
 exam_scopes TEXT NOT NULL DEFAULT '[]', syllabus_source TEXT NOT NULL DEFAULT '', syllabus_year INTEGER,
 revision INTEGER NOT NULL DEFAULT 1
);
INSERT INTO knowledge_points_new SELECT * FROM knowledge_points;
DROP TABLE knowledge_points;
ALTER TABLE knowledge_points_new RENAME TO knowledge_points;
CREATE UNIQUE INDEX knowledge_location_title ON knowledge_points(subject,domain,COALESCE(parent_id,0),title);
CREATE INDEX knowledge_parent ON knowledge_points(parent_id);

INSERT INTO activity_events(kind,entity_id,value,happened_at) SELECT 'mistake_created',id,0,created_at FROM mistakes WHERE NOT EXISTS(SELECT 1 FROM activity_events e WHERE e.kind='mistake_created' AND e.entity_id=mistakes.id);
