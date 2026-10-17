import { useCallback, useEffect, useRef, useState } from "react";
import type { CSSProperties, FormEvent, ReactNode } from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  BookOpen,
  CalendarDays,
  ChartNoAxesCombined,
  Check,
  CheckCheck,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Clock3,
  Database,
  FileWarning,
  Flame,
  LayoutDashboard,
  Leaf,
  ListTodo,
  LoaderCircle,
  Map,
  Pause,
  Pencil,
  Play,
  Plus,
  RotateCcw,
  Search,
  Settings2,
  ShieldCheck,
  Square,
  Target,
  Trash2,
  X,
} from "lucide-react";
import { api, ApiError, download } from "../api";
import type {
  AIStatus,
  Knowledge,
  KnowledgeStatus,
  Mistake,
  Page,
  ReviewEvent,
  Session,
  Stats,
  Task,
} from "../types";

import { useResource } from "./hooks";
import { ImagePicker } from "./Files";

export const statuses: Record<KnowledgeStatus, string> = {
  unstarted: "未开始",
  learning: "学习中",
  consolidating: "待巩固",
  mastered: "已掌握",
};
export const subjects = ["数学", "英语", "政治", "专业课", "C/C++", "Linux"];
export const reviewLabels = {
  new: "待初次复习",
  reviewing: "复习中",
  mastered: "本轮已掌握",
};
export const localDay = () =>
  new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
export const dateLabel = (value: string, full = false) =>
  new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "long",
    day: "numeric",
    ...(full ? { weekday: "long" as const } : {}),
  }).format(new Date(`${value}T12:00:00+08:00`));
export const dateTime = (value: string) =>
  new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
export const duration = (value: number) =>
  value < 60
    ? `${Math.floor(value)} 秒`
    : value < 3600
      ? `${Math.floor(value / 60)} 分`
      : `${Math.floor(value / 3600)} 小时 ${Math.floor((value % 3600) / 60)} 分`;
export const timerText = (value: number) =>
  [
    Math.floor(value / 3600),
    Math.floor((value % 3600) / 60),
    Math.floor(value % 60),
  ]
    .map((v) => String(v).padStart(2, "0"))
    .join(":");
export const percent = (done: number, total: number) =>
  total ? Math.round((done / total) * 100) : 0;

export function Empty({
  icon = BookOpen,
  title,
  children,
  action,
}: {
  icon?: typeof BookOpen;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  const Icon = icon;
  return (
    <div className="empty">
      <div className="empty-icon">
        <Icon size={27} strokeWidth={1.5} />
      </div>
      <strong>{title}</strong>
      {children && <p>{children}</p>}
      {action}
    </div>
  );
}

export function Modal({
  title,
  children,
  close,
  error,
}: {
  title: string;
  children: ReactNode;
  close: () => void;
  error?: string;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const el = dialog.current!;
    el.showModal();
    return () => el.close();
  }, []);
  return (
    <dialog
      ref={dialog}
      className="modal"
      onCancel={(e) => {
        e.preventDefault();
        close();
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div className="modal-heading">
        <h2>{title}</h2>
        <button className="icon-button" aria-label="关闭弹窗" onClick={close}>
          <X size={21} />
        </button>
      </div>
      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}
      {children}
    </dialog>
  );
}

export function SubjectField({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label>
      学习科目
      <input
        required
        maxLength={40}
        list="subject-options"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="选择或输入科目"
      />
    </label>
  );
}

export function TaskForm({
  task,
  day,
  busy,
  save,
  close,
}: {
  task?: Task;
  day: string;
  busy: boolean;
  save: (data: unknown) => void;
  close: () => void;
}) {
  const [title, setTitle] = useState(task?.title || "");
  const [priority, setPriority] = useState(task?.priority || 2);
  const [goalId, setGoalId] = useState(task?.goal_id || null);
  const [state, setState] = useState(task?.status || "todo");
  const goals = useResource<{ id: number; title: string }[]>("/goals");
  const [subject, setSubject] = useState(task?.subject || "数学");
  const [scheduled, setScheduled] = useState(task?.scheduled_date || day);
  const [minutes, setMinutes] = useState(task?.estimated_minutes || 30);
  const [notes, setNotes] = useState(task?.notes || "");
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        save({
          title,
          subject,
          scheduled_date: scheduled,
          estimated_minutes: minutes,
          notes,
          priority,
          goal_id: goalId,
          status: state,
          completed: state === "done",
          expected_revision: task?.revision,
        });
      }}
    >
      <label>
        任务名称
        <input
          autoFocus
          required
          maxLength={200}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="例如：学习导数定义，独立完成 5 道基础题"
        />
      </label>
      <div className="form-row">
        <SubjectField value={subject} onChange={setSubject} />
        <label>
          计划日期
          <input
            type="date"
            required
            value={scheduled}
            onChange={(e) => setScheduled(e.target.value)}
          />
        </label>
      </div>
      <label>
        预计用时（分钟）
        <input
          type="number"
          required
          min={1}
          max={1440}
          value={minutes}
          onChange={(e) => setMinutes(Number(e.target.value))}
        />
      </label>
      <div className="form-row">
        <label>
          任务优先级
          <select
            value={priority}
            onChange={(e) => setPriority(Number(e.target.value))}
          >
            <option value={1}>高</option>
            <option value={2}>中</option>
            <option value={3}>低</option>
          </select>
        </label>
        <label>
          任务状态
          <select
            value={state}
            onChange={(e) => setState(e.target.value as Task["status"])}
          >
            <option value="todo">未开始</option>
            <option value="doing">进行中</option>
            <option value="done">已完成</option>
          </select>
        </label>
      </div>
      <label>
        关联阶段目标
        <select
          value={goalId || ""}
          onChange={(e) =>
            setGoalId(e.target.value ? Number(e.target.value) : null)
          }
        >
          <option value="">暂不关联</option>
          {goals.data?.map((g) => (
            <option key={g.id} value={g.id}>
              {g.title}
            </option>
          ))}
        </select>
      </label>
      <label>
        学习目标或备注
        <textarea
          maxLength={20000}
          rows={3}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="写下可以验收的小目标"
        />
      </label>
      <div className="form-actions">
        <button
          type="button"
          className="button secondary"
          onClick={close}
          disabled={busy}
        >
          取消
        </button>
        <button className="button" disabled={busy}>
          {busy ? "保存中…" : "保存任务"}
        </button>
      </div>
    </form>
  );
}

export function KnowledgeForm({
  point,
  knowledge,
  busy,
  save,
  close,
}: {
  knowledge: Knowledge[];
  point?: Knowledge;
  busy: boolean;
  save: (data: unknown) => void;
  close: () => void;
}) {
  const [title, setTitle] = useState(point?.title || "");
  const [subject, setSubject] = useState(point?.subject || "数学");
  const [parentId, setParentId] = useState(point?.parent_id || null);
  const [mastery, setMastery] = useState(point?.mastery || 0);
  const [scopes, setScopes] = useState<string[]>(
    JSON.parse(point?.exam_scopes || "[]"),
  );
  const [source, setSource] = useState(point?.syllabus_source || "");
  const [year, setYear] = useState(point?.syllabus_year || null);
  const [domain, setDomain] = useState(point?.domain || "高等数学");
  const [status, setStatus] = useState<KnowledgeStatus>(
    point?.status || "unstarted",
  );
  const [notes, setNotes] = useState(point?.notes || "");
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        save({
          title,
          domain,
          status,
          notes,
          subject,
          parent_id: parentId,
          mastery,
          exam_scopes: scopes,
          syllabus_source: source,
          syllabus_year: year,
          expected_revision: point?.revision,
        });
      }}
    >
      <SubjectField value={subject} onChange={setSubject} />
      <label>
        知识点名称
        <input
          autoFocus
          required
          maxLength={200}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
      </label>
      <div className="form-row">
        <label>
          知识分类
          <input
            required
            maxLength={40}
            list="domain-options"
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
          />
        </label>
        <label>
          学习状态
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as KnowledgeStatus)}
          >
            {Object.entries(statuses).map(([v, label]) => (
              <option key={v} value={v}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="form-row">
        <label>
          父知识点
          <select
            value={parentId || ""}
            onChange={(e) =>
              setParentId(e.target.value ? Number(e.target.value) : null)
            }
          >
            <option value="">章节下的知识点</option>
            {knowledge
              .filter(
                (k) =>
                  k.id !== point?.id &&
                  k.subject === subject &&
                  k.domain === domain,
              )
              .map((k) => (
                <option key={k.id} value={k.id}>
                  {k.title}
                </option>
              ))}
          </select>
        </label>
        <label>
          掌握程度（0–5）
          <input
            type="number"
            min={0}
            max={5}
            value={mastery}
            onChange={(e) => setMastery(Number(e.target.value))}
          />
        </label>
      </div>
      <fieldset>
        <legend>适用范围（个人标注，不代表官方大纲）</legend>
        {[
          ["math1", "数学一"],
          ["math2", "数学二"],
          ["math3", "数学三"],
        ].map(([id, label]) => (
          <label className="check-option" key={id}>
            <input
              type="checkbox"
              checked={scopes.includes(id)}
              onChange={(e) =>
                setScopes(
                  e.target.checked
                    ? [...scopes, id]
                    : scopes.filter((x) => x !== id),
                )
              }
            />
            {label}
          </label>
        ))}
      </fieldset>
      <div className="form-row">
        <label>
          资料来源
          <input
            maxLength={500}
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder="书名、资料链接或个人整理"
          />
        </label>
        <label>
          适用年份
          <input
            type="number"
            min={2000}
            max={2100}
            value={year || ""}
            onChange={(e) =>
              setYear(e.target.value ? Number(e.target.value) : null)
            }
          />
        </label>
      </div>
      <label>
        学习笔记
        <textarea
          rows={5}
          maxLength={20000}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="记录定义、前置知识、还不理解的地方"
        />
      </label>
      <div className="form-actions">
        <button
          type="button"
          className="button secondary"
          disabled={busy}
          onClick={close}
        >
          取消
        </button>
        <button className="button" disabled={busy}>
          保存知识点
        </button>
      </div>
    </form>
  );
}

export function MistakeForm({
  mistake,
  knowledge,
  busy,
  save,
  close,
}: {
  mistake?: Mistake;
  knowledge: Knowledge[];
  busy: boolean;
  save: (data: unknown) => void;
  close: () => void;
}) {
  const [title, setTitle] = useState(mistake?.title || "");
  const [uploading, setUploading] = useState(false);
  const [fileIds, setFileIds] = useState<string[]>(mistake?.file_ids || []);
  const [subject, setSubject] = useState(mistake?.subject || "数学");
  const [question, setQuestion] = useState(mistake?.question || "");
  const [answer, setAnswer] = useState(mistake?.answer || "");
  const [wrongAnswer, setWrongAnswer] = useState(mistake?.wrong_answer || "");
  const [category, setCategory] = useState(mistake?.category || "未分类");
  const [mastery, setMastery] = useState(mistake?.mastery || "unmastered");
  const [reason, setReason] = useState(mistake?.error_reason || "");
  const [source, setSource] = useState(mistake?.source || "");
  const [ids, setIds] = useState<number[]>(mistake?.knowledge_ids || []);
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        save({
          title,
          subject,
          question,
          answer,
          error_reason: reason,
          source,
          knowledge_ids: ids,
          wrong_answer: wrongAnswer,
          category,
          mastery,
          file_ids: fileIds,
          expected_revision: mistake?.revision,
        });
      }}
    >
      <label>
        错题标题
        <input
          autoFocus
          required
          maxLength={200}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="用一句话概括这道题"
        />
      </label>
      <div className="form-row">
        <SubjectField value={subject} onChange={setSubject} />
        <label>
          题目来源
          <input
            maxLength={500}
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder="教材 / 页码 / 题号"
          />
        </label>
      </div>
      <ImagePicker ids={fileIds} onChange={setFileIds} onBusy={setUploading} />
      <label>
        题目内容
        <textarea
          required
          maxLength={20000}
          rows={4}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="手动输入题目，可用纯文本记录公式"
        />
      </label>
      <div className="form-row">
        <label>
          错题分类
          <input
            maxLength={40}
            required
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          />
        </label>
        <label>
          错题掌握状态
          <select value={mastery} onChange={(e) => setMastery(e.target.value)}>
            <option value="unmastered">未掌握</option>
            <option value="reviewing">复习中</option>
            <option value="mastered">已掌握</option>
          </select>
        </label>
      </div>
      <label>
        我的错误答案
        <textarea
          maxLength={20000}
          rows={3}
          value={wrongAnswer}
          onChange={(e) => setWrongAnswer(e.target.value)}
        />
      </label>
      <label>
        正确答案与解题过程
        <textarea
          maxLength={20000}
          rows={4}
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
        />
      </label>
      <label>
        错误原因
        <textarea
          maxLength={20000}
          rows={3}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="例如：混淆定义 / 运算错误 / 不知道如何开始"
        />
      </label>
      <fieldset>
        <legend>关联知识点（可多选）</legend>
        <div className="knowledge-picker">
          {knowledge.map((k) => (
            <label key={k.id} className="check-option">
              <input
                type="checkbox"
                checked={ids.includes(k.id)}
                onChange={(e) =>
                  setIds(
                    e.target.checked
                      ? [...ids, k.id]
                      : ids.filter((id) => id !== k.id),
                  )
                }
              />
              <span>
                {k.title}
                <small>{k.domain}</small>
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      <p className="form-hint">
        {mistake
          ? "编辑题目保留已有复习进度。"
          : "保存后自动安排明天的第一次复习。"}
      </p>
      <div className="form-actions">
        <button
          type="button"
          className="button secondary"
          disabled={busy}
          onClick={close}
        >
          取消
        </button>
        <button className="button" disabled={busy || uploading}>
          保存错题
        </button>
      </div>
    </form>
  );
}

export function TaskList({
  tasks,
  busy,
  toggle,
  edit,
  remove,
  focus,
}: {
  tasks: Task[];
  busy: boolean;
  toggle: (task: Task) => void;
  edit: (task: Task) => void;
  remove: (task: Task) => void;
  focus: (task: Task) => void;
}) {
  return (
    <div className="task-list">
      {tasks.map((task) => (
        <div
          key={task.id}
          className={`task-row ${task.completed ? "done" : ""}`}
        >
          <button
            className="task-check"
            aria-label={`${task.completed ? "取消完成" : "完成任务"}：${task.title}`}
            aria-pressed={!!task.completed}
            onClick={() => toggle(task)}
            disabled={busy}
          >
            {!!task.completed && <Check size={15} />}
          </button>
          <div className="task-content">
            <strong>{task.title}</strong>
            <div className="task-meta">
              <span className="subject-tag">{task.subject}</span>
              <span>{["", "高", "中", "低"][task.priority]}优先级</span>
              <span>
                <Clock3 size={12} />
                预计 {task.estimated_minutes} 分钟
              </span>
            </div>
            {task.notes && <p>{task.notes}</p>}
          </div>
          <div className="row-actions">
            <button
              className="icon-button"
              aria-label={`开始学习：${task.title}`}
              title="开始学习"
              onClick={() => focus(task)}
              disabled={busy}
            >
              <Play size={16} />
            </button>
            <button
              className="icon-button"
              aria-label={`编辑任务：${task.title}`}
              onClick={() => edit(task)}
              disabled={busy}
            >
              <Pencil size={16} />
            </button>
            <button
              className="icon-button danger"
              aria-label={`删除任务：${task.title}`}
              onClick={() => remove(task)}
              disabled={busy}
            >
              <Trash2 size={16} />
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

export function SessionHistory({ sessions }: { sessions: Session[] }) {
  const [filter, setFilter] = useState("");
  const filtered = sessions.filter(
    (s) =>
      !filter ||
      new Intl.DateTimeFormat("en-CA", {
        timeZone: "Asia/Shanghai",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      }).format(new Date(s.started_at)) === filter,
  );
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>
          学习记录 <span className="count">{filtered.length}</span>
        </h2>
        <label className="sr-only" htmlFor="history-date">
          筛选学习记录日期
        </label>
        <input
          id="history-date"
          type="date"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <button className="text-button" onClick={() => setFilter("")}>
          全部
        </button>
      </div>
      {filtered.length ? (
        <div className="session-list">
          {filtered.map((s) => (
            <div className="session-row" key={s.id}>
              <div className="session-icon">
                <BookOpen size={19} />
              </div>
              <div className="session-content">
                <strong>{s.topic || `${s.subject}学习`}</strong>
                <p>
                  {s.subject} · {dateTime(s.started_at)} —{" "}
                  {s.ended_at ? dateTime(s.ended_at) : ""}
                </p>
                {s.notes && <p className="session-notes">{s.notes}</p>}
              </div>
              <strong className="session-duration">
                {duration(s.elapsed_seconds)}
              </strong>
            </div>
          ))}
        </div>
      ) : (
        <Empty icon={Clock3} title="还没有学习记录">
          结束一次专注后，记录会出现在这里。
        </Empty>
      )}
    </section>
  );
}
