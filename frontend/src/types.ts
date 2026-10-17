export type Page =
  | "overview"
  | "tasks"
  | "focus"
  | "knowledge"
  | "mistakes"
  | "reviews"
  | "settings"
  | "plans"
  | "analytics"
  | "ai"
  | "materials";
export interface Task {
  id: number;
  title: string;
  subject: string;
  scheduled_date: string;
  priority: number;
  goal_id: number | null;
  status: "todo" | "doing" | "done";
  revision: number;
  estimated_minutes: number;
  notes: string;
  completed: boolean | number;
}
export type KnowledgeStatus =
  "unstarted" | "learning" | "consolidating" | "mastered";
export interface Knowledge {
  id: number;
  title: string;
  domain: string;
  status: KnowledgeStatus;
  notes: string;
  subject: string;
  parent_id: number | null;
  mastery: number;
  exam_scopes: string;
  syllabus_source: string;
  syllabus_year: number | null;
  last_studied_at: string | null;
  last_reviewed_at: string | null;
  revision: number;
  is_reference: number;
  mistake_count: number;
  unresolved_count: number;
}
export interface Session {
  id: number;
  subject: string;
  topic: string;
  notes: string;
  started_at: string;
  mode: string;
  target_seconds: number;
  break_seconds: number;
  ended_at: string | null;
  status: "running" | "paused" | "finished";
  elapsed_seconds: number;
  server_now: string;
}
export interface Mistake {
  id: number;
  title: string;
  subject: string;
  question: string;
  answer: string;
  error_reason: string;
  wrong_answer: string;
  category: string;
  mastery: string;
  file_ids: string[];
  revision: number;
  source: string;
  knowledge_ids: number[];
  review_status: "new" | "reviewing" | "mastered";
  review: {
    stage: number;
    due_date: string | null;
    last_reviewed_at: string | null;
  };
}
export interface ReviewEvent {
  id: number;
  outcome: "remembered" | "forgotten" | "assisted";
  reviewed_at: string;
  next_stage: number;
  next_due_date: string | null;
  notes: string;
}
export interface Stats {
  date: string;
  timezone: string;
  week_start: string;
  today_seconds: number;
  week_seconds: number;
  subjects: { subject: string; seconds: number }[];
  daily: { date: string; seconds: number }[];
  today_tasks: { total: number; completed: number };
  all_tasks: { total: number; completed: number };
  mistake_count: number;
  due_review_count: number;
  pending_review_count: number;
  knowledge_count: number;
  mastered_knowledge_count: number;
  data_source: "database";
}
export interface AIStatus {
  available: boolean;
  message: string;
}
