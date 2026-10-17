import { useState } from "react";
import { api } from "../api";
import type { Knowledge, Session, Task } from "../types";
import { duration, localDay, Modal, SubjectField } from "../components/core";
import { Feedback, Section, useAction, useResource } from "../components/hooks";

type Goal = {
  id: number;
  title: string;
  subject: string;
  target_date: string;
  notes: string;
  completed: boolean | number;
  task_count: number;
  completed_tasks: number;
};
const shift = (day: string, n: number) => {
  const d = new Date(day + "T12:00:00Z");
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
};
export function PlanPage({
  edit,
  create,
}: {
  edit: (task: Task) => void;
  create: () => void;
}) {
  const tasks = useResource<Task[]>("/tasks");
  const goals = useResource<Goal[]>("/goals");
  const action = useAction(async () => {
    await tasks.reload();
    await goals.reload();
  });
  const [start, setStart] = useState(localDay());
  const [view, setView] = useState("week");
  const [subject, setSubject] = useState("");
  const [goal, setGoal] = useState<Partial<Goal> | null>(null);
  const filtered = (tasks.data || [])
    .filter(
      (t) =>
        (!subject || t.subject === subject) &&
        (view === "all" ||
          (view === "unfinished" && !t.completed) ||
          (view === "week" &&
            t.scheduled_date >= start &&
            t.scheduled_date <= shift(start, 6))),
    )
    .sort(
      (a, b) =>
        a.scheduled_date.localeCompare(b.scheduled_date) ||
        a.priority - b.priority,
    );
  return (
    <>
      <h1>周计划与学习目标</h1>
      <Feedback
        error={tasks.error || goals.error || action.error}
        message={action.message}
        loading={tasks.loading}
      />
      <Section title="安排你的学习">
        <div className="filter-bar">
          <label>
            查看范围
            <select value={view} onChange={(e) => setView(e.target.value)}>
              <option value="week">七日计划</option>
              <option value="unfinished">全部未完成</option>
              <option value="all">历史全部</option>
            </select>
          </label>
          <label>
            起始日期
            <input
              type="date"
              value={start}
              onChange={(e) => setStart(e.target.value)}
            />
          </label>
          <label>
            科目
            <select
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
            >
              <option value="">全部</option>
              {[...new Set(tasks.data?.map((t) => t.subject))].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <button className="button" onClick={create}>
            创建学习任务
          </button>
          <button className="text-button" onClick={() => void tasks.reload()}>
            刷新计划
          </button>
        </div>
        {!filtered.length && <p className="muted">当前范围没有任务。</p>}
        {filtered.map((t) => (
          <div className="v2-row" key={t.id}>
            <div>
              <strong>{t.title}</strong>
              <p>
                {t.scheduled_date} · {t.subject} ·{" "}
                {["", "高", "中", "低"][t.priority]}优先级 ·{" "}
                {t.completed
                  ? "已完成"
                  : t.status === "doing"
                    ? "进行中"
                    : "未开始"}
              </p>
            </div>
            <button className="button secondary" onClick={() => edit(t)}>
              编辑
            </button>
          </div>
        ))}
      </Section>
      <Section title="阶段目标">
        <button
          className="button"
          onClick={() =>
            setGoal({
              subject: "数学",
              target_date: localDay(),
              title: "",
              notes: "",
              completed: false,
            })
          }
        >
          新建目标
        </button>
        {!goals.data?.length && (
          <p className="muted">
            写下可检验的能力目标，例如独立完成一章基础题。
          </p>
        )}
        {goals.data?.map((g) => (
          <div className="v2-row" key={g.id}>
            <div>
              <strong>{g.title}</strong>
              <p>
                {g.subject} · 截止 {g.target_date} · 任务 {g.completed_tasks}/
                {g.task_count} · {g.completed ? "目标已完成" : "进行中"}
              </p>
              {g.notes && <p>{g.notes}</p>}
            </div>
            <div className="row-actions">
              <button className="text-button" onClick={() => setGoal(g)}>
                编辑目标
              </button>
              <button
                className="text-button danger"
                disabled={action.busy}
                onClick={() => {
                  if (confirm("删除此目标？关联任务会保留。"))
                    void action.run(() => api(`/goals/${g.id}`, "DELETE"));
                }}
              >
                删除目标
              </button>
            </div>
          </div>
        ))}
      </Section>
      {goal && (
        <Modal
          title={goal.id ? "编辑目标" : "新建目标"}
          close={() => setGoal(null)}
          error={action.error}
        >
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              const { id, task_count, completed_tasks, ...body } = goal;
              if (
                await action.run(() =>
                  api(id ? `/goals/${id}` : "/goals", id ? "PUT" : "POST", {
                    ...body,
                    completed: !!body.completed,
                  }),
                )
              )
                setGoal(null);
            }}
          >
            <label>
              目标名称
              <input
                required
                maxLength={200}
                value={goal.title}
                onChange={(e) => setGoal({ ...goal, title: e.target.value })}
              />
            </label>
            <SubjectField
              value={goal.subject || "数学"}
              onChange={(subject) => setGoal({ ...goal, subject })}
            />
            <label>
              目标截止日期
              <input
                type="date"
                required
                value={goal.target_date}
                onChange={(e) =>
                  setGoal({ ...goal, target_date: e.target.value })
                }
              />
            </label>
            <label>
              验收说明
              <textarea
                value={goal.notes}
                onChange={(e) => setGoal({ ...goal, notes: e.target.value })}
              />
            </label>
            <label className="check-option">
              <input
                type="checkbox"
                checked={!!goal.completed}
                onChange={(e) =>
                  setGoal({ ...goal, completed: e.target.checked })
                }
              />
              目标已完成
            </label>
            <button className="button" disabled={action.busy}>
              保存目标
            </button>
          </form>
        </Modal>
      )}
    </>
  );
}

export function ManualRecords({
  sessions,
  refresh,
}: {
  sessions: Session[];
  refresh: () => Promise<unknown>;
}) {
  const action = useAction(refresh);
  const [form, setForm] = useState<{
    id?: number;
    subject: string;
    topic: string;
    notes: string;
    started_at: string;
    minutes: number;
  } | null>(null);
  const [breakUntil, setBreakUntil] = useState<number | null>(
    () => Number(localStorage.getItem("yantu-break-until")) || null,
  );
  const last = sessions.find((s) => s.mode === "pomodoro");
  return (
    <Section title="补录与更正">
      <Feedback {...action} />
      <div className="settings-actions">
        <button
          className="button secondary"
          onClick={() =>
            setForm({
              subject: "数学",
              topic: "",
              notes: "",
              started_at: localDay() + "T08:00",
              minutes: 30,
            })
          }
        >
          补录学习记录
        </button>
        {last && (
          <button
            className="button secondary"
            onClick={() => {
              const until = Date.now() + last.break_seconds * 1000;
              localStorage.setItem("yantu-break-until", String(until));
              setBreakUntil(until);
            }}
          >
            开始休息 {last.break_seconds / 60} 分钟
          </button>
        )}
      </div>
      {breakUntil && (
        <p>
          休息至 {new Date(breakUntil).toLocaleTimeString("zh-CN")}
          ，休息不计入学习时长。
          <button
            className="text-button"
            onClick={() => {
              localStorage.removeItem("yantu-break-until");
              setBreakUntil(null);
            }}
          >
            结束休息
          </button>
        </p>
      )}
      <details>
        <summary>更正或删除已结束的记录</summary>
        {sessions.map((s) => (
          <div className="v2-row" key={s.id}>
            <span>
              {s.topic || s.subject} · {duration(s.elapsed_seconds)}
            </span>
            <div className="row-actions">
              <button
                className="text-button"
                onClick={() =>
                  setForm({
                    id: s.id,
                    subject: s.subject,
                    topic: s.topic,
                    notes: s.notes,
                    started_at: new Date(
                      new Date(s.started_at).getTime() + 8 * 3600000,
                    )
                      .toISOString()
                      .slice(0, 16),
                    minutes: Math.max(1, Math.round(s.elapsed_seconds / 60)),
                  })
                }
              >
                更正
              </button>
              <button
                className="text-button danger"
                disabled={action.busy}
                onClick={() => {
                  if (confirm("删除此学习记录？统计将同步更新。"))
                    void action.run(() => api(`/records/${s.id}`, "DELETE"));
                }}
              >
                删除记录
              </button>
            </div>
          </div>
        ))}
      </details>
      {form && (
        <Modal
          title="学习记录"
          close={() => setForm(null)}
          error={action.error}
        >
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              const { id, ...body } = form;
              if (
                await action.run(() =>
                  api(
                    id ? `/records/${id}` : "/records/manual",
                    id ? "PUT" : "POST",
                    { ...body, started_at: body.started_at + ":00+08:00" },
                  ),
                )
              )
                setForm(null);
            }}
          >
            <SubjectField
              value={form.subject}
              onChange={(subject) => setForm({ ...form, subject })}
            />
            <label>
              记录内容
              <input
                value={form.topic}
                onChange={(e) => setForm({ ...form, topic: e.target.value })}
              />
            </label>
            <label>
              开始时间（北京时间）
              <input
                required
                type="datetime-local"
                value={form.started_at}
                onChange={(e) =>
                  setForm({ ...form, started_at: e.target.value })
                }
              />
            </label>
            <label>
              学习分钟数
              <input
                required
                type="number"
                min={1}
                max={1440}
                value={form.minutes}
                onChange={(e) =>
                  setForm({ ...form, minutes: Number(e.target.value) })
                }
              />
            </label>
            <label>
              记录备注
              <textarea
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
              />
            </label>
            <p className="form-hint">
              更正会把原计时片段替换为连续时段；不允许未来时间或与现有记录重叠。
            </p>
            <button className="button" disabled={action.busy}>
              保存学习记录
            </button>
          </form>
        </Modal>
      )}
    </Section>
  );
}

type KnowledgeReview = Knowledge & { due_date: string; stage: number };
export function KnowledgeReviews({
  refresh,
}: {
  refresh: () => Promise<unknown>;
}) {
  const data = useResource<KnowledgeReview[]>("/knowledge-reviews");
  const action = useAction(async () => {
    await data.reload();
    await refresh();
  });
  const [selected, setSelected] = useState<KnowledgeReview | null>(null);
  const [note, setNote] = useState("");
  const [all, setAll] = useState(false);
  const [schedule, setSchedule] = useState("");
  const history = useResource<
    { id: number; outcome: string; reviewed_at: string; notes: string }[]
  >(selected ? `/knowledge/${selected.id}/reviews` : "/knowledge/0/reviews");
  return (
    <Section title="知识点复习">
      <Feedback error={data.error || action.error} message={action.message} />
      <div className="settings-actions">
        <button
          className="button secondary"
          disabled={action.busy}
          onClick={() =>
            void action.run(() => api("/knowledge-reviews/generate", "POST"))
          }
        >
          根据掌握情况生成安排
        </button>
        <button className="text-button" onClick={() => setAll(!all)}>
          {all ? "只看今日到期" : "查看全部知识点安排"}
        </button>
      </div>
      <p className="form-hint">
        低掌握程度和较多关联错题会缩短首次间隔。已有日期不会被生成操作推迟。
      </p>
      {!(data.data || []).filter((k) => all || k.due_date <= localDay())
        .length && <p className="muted">当前没有待处理的知识点复习。</p>}
      {data.data
        ?.filter((k) => all || k.due_date <= localDay())
        .map((k) => (
          <div className="v2-row" key={k.id}>
            <div>
              <strong>{k.title}</strong>
              <p>
                {k.due_date < localDay() ? "已逾期 · " : ""}
                {k.due_date} · 掌握 {k.mastery}/5
              </p>
            </div>
            <button
              className="button secondary"
              onClick={() => {
                setSelected(k);
                setNote("");
                setSchedule(k.due_date);
              }}
            >
              回顾知识点
            </button>
          </div>
        ))}
      {selected && (
        <Modal
          title={selected.title}
          close={() => setSelected(null)}
          error={action.error}
        >
          <p className="pre-wrap">
            {selected.notes || "先独立回忆定义、条件与典型例题，再记录结果。"}
          </p>
          <label>
            复习笔记
            <textarea value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
          <div className="settings-actions">
            {[
              ["remembered", "独立完成"],
              ["assisted", "提示后完成"],
              ["forgotten", "尚未掌握"],
            ].map(([outcome, label]) => (
              <button
                key={outcome}
                className="button secondary"
                disabled={action.busy || selected.due_date > localDay()}
                onClick={async () => {
                  if (
                    await action.run(() =>
                      api(`/knowledge/${selected.id}/review`, "POST", {
                        outcome,
                        notes: note,
                      }),
                    )
                  )
                    setSelected(null);
                }}
              >
                {label}
              </button>
            ))}
          </div>
          <p className="form-hint">
            独立完成掌握程度 +1，未掌握
            −1，提示后保持不变；这是规则记录，不是考试能力评分。
          </p>
          <label>
            调整复习日期
            <input
              type="date"
              value={schedule}
              onChange={(e) => setSchedule(e.target.value)}
            />
          </label>
          <button
            className="button secondary"
            disabled={action.busy}
            onClick={async () => {
              if (
                await action.run(() =>
                  api(`/review-schedule/knowledge/${selected.id}`, "PUT", {
                    due_date: schedule,
                  }),
                )
              )
                setSelected(null);
            }}
          >
            保存复习日期
          </button>
          <h3>复习历史</h3>
          {history.data?.map((r) => (
            <p key={r.id}>
              {r.reviewed_at.slice(0, 10)} ·{" "}
              {
                {
                  remembered: "独立完成",
                  assisted: "提示后完成",
                  forgotten: "未掌握",
                }[r.outcome]
              }{" "}
              · {r.notes}
            </p>
          ))}
        </Modal>
      )}
    </Section>
  );
}

type Analytics = {
  seconds: number;
  daily: {
    date: string;
    seconds: number;
    new_mistakes: number;
    removed_mistakes: number;
    mistake_total: number;
  }[];
  subjects: { subject: string; seconds: number }[];
  tasks: { total: number; completed: number };
  reviews: {
    completed: number;
    pending: number;
    attempts: number;
    independent: number;
    failed: number;
  };
  knowledge: { mastery: number; count: number }[];
  mistakes: { category: string; mastery: string; count: number }[];
  notes: string;
  mastery_history: {
    id: number;
    title: string;
    value: number;
    happened_at: string;
  }[];
};
export function StatisticsPage() {
  const [start, setStart] = useState(localDay().slice(0, 8) + "01");
  const [end, setEnd] = useState(localDay());
  const resource = useResource<Analytics>(
    `/analytics?start=${start}&end=${end}`,
  );
  const d = resource.data;
  const max = Math.max(3600, ...(d?.daily.map((x) => x.seconds) || []));
  return (
    <>
      <h1>学习数据统计</h1>
      <div className="filter-bar">
        <label>
          开始日期
          <input
            type="date"
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
        </label>
        <label>
          结束日期
          <input
            type="date"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
          />
        </label>
        {[
          ["今日", 0],
          ["近七天", 6],
          ["近三十天", 29],
        ].map(([label, n]) => (
          <button
            className="button secondary"
            key={label}
            onClick={() => {
              setStart(shift(localDay(), -Number(n)));
              setEnd(localDay());
            }}
          >
            {label}
          </button>
        ))}
      </div>
      <Feedback {...resource} />
      {d && (
        <>
          <div className="v2-metrics">
            <Section title="学习时长">
              <strong>{duration(d.seconds)}</strong>
            </Section>
            <Section title="任务完成">
              <strong>
                {d.tasks.completed}/{d.tasks.total}
              </strong>
            </Section>
            <Section title="复习完成">
              <strong>
                {d.reviews.completed}/{d.reviews.completed + d.reviews.pending}
              </strong>
            </Section>
            <Section title="独立完成复习">
              <strong>
                {d.reviews.independent}/{d.reviews.attempts}
              </strong>
            </Section>
          </div>
          <Section title="学习趋势与日历">
            <div className="calendar-grid">
              {d.daily.map((x) => (
                <div
                  key={x.date}
                  title={`${x.date}：${duration(x.seconds)}`}
                  className={x.seconds ? "studied" : ""}
                >
                  <small>{x.date.slice(5)}</small>
                  <div
                    className="calendar-bar"
                    style={{ height: Math.max(2, (x.seconds / max) * 60) }}
                  />
                  <span>{Math.floor(x.seconds / 60)} 分</span>
                  <small>新增错题 {x.new_mistakes}</small>
                </div>
              ))}
            </div>
          </Section>
          <Section title="错题数量变化">
            <svg
              viewBox="0 0 720 180"
              role="img"
              aria-label="选定日期范围内可追溯的错题总数"
              style={{ width: "100%", height: "auto" }}
            >
              <line x1="20" y1="145" x2="700" y2="145" stroke="#d4ddd6" />
              <polyline
                fill="none"
                stroke="#2f7157"
                strokeWidth="3"
                points={d.daily
                  .map(
                    (x, i) =>
                      `${20 + (i * 680) / Math.max(1, d.daily.length - 1)},${145 - (x.mistake_total * 115) / Math.max(1, ...d.daily.map((v) => v.mistake_total))}`,
                  )
                  .join(" ")}
              />
              <text x="20" y="173" fontSize="12" fill="#627166">
                {start}
              </text>
              <text x="620" y="173" fontSize="12" fill="#627166">
                {end}
              </text>
            </svg>
            <p className="form-hint">
              按实际创建与删除事件计算；迁移前已经删除的历史记录无法重建。
            </p>
            <details>
              <summary>查看每日数量</summary>
              {d.daily.map((x) => (
                <p key={x.date}>
                  {x.date}：总数 {x.mistake_total}，新增 {x.new_mistakes}，移除{" "}
                  {x.removed_mistakes}
                </p>
              ))}
            </details>
          </Section>
          <Section title="掌握记录变化">
            {!d.mastery_history?.length && (
              <p className="muted">
                此范围内尚无掌握记录；不会推测过去的分数。
              </p>
            )}
            {d.mastery_history?.slice(-12).map((r) => (
              <p key={r.id}>
                {r.title} · {r.value}/5 · {r.happened_at.slice(0, 10)}
              </p>
            ))}
          </Section>
          <Section title="各科目投入">
            {!d.subjects.length && (
              <p className="muted">此范围尚无学习记录。</p>
            )}
            {d.subjects.map((s) => (
              <div className="subject-breakdown" key={s.subject}>
                <div className="subject-line">
                  <span>{s.subject}</span>
                  <strong>{duration(s.seconds)}</strong>
                </div>
                <div className="subject-track">
                  <div style={{ width: `${(s.seconds / d.seconds) * 100}%` }} />
                </div>
              </div>
            ))}
          </Section>
          <div className="v2-metrics">
            <Section title="当前知识掌握分布">
              {d.knowledge.map((k) => (
                <p key={k.mastery}>
                  {k.mastery}/5：{k.count} 个知识点
                </p>
              ))}
            </Section>
            <Section title="当前错题分布">
              {!d.mistakes.length && <p className="muted">尚无错题。</p>}
              {d.mistakes.map((m) => (
                <p key={m.category + m.mastery}>
                  {m.category} ·{" "}
                  {
                    {
                      unmastered: "未掌握",
                      reviewing: "复习中",
                      mastered: "已掌握",
                    }[m.mastery]
                  }
                  ：{m.count} 道
                </p>
              ))}
            </Section>
          </div>
          <p className="form-hint">{d.notes}</p>
        </>
      )}
      <Recommendations />
    </>
  );
}

type Report = {
  label: string;
  daily: string[];
  weekly: string[];
  weak_points: {
    id: number;
    title: string;
    mastery: number;
    mistake_count: number;
  }[];
  explanation: string;
  summary: {
    days_with_study: number;
    streak_days: number;
    recent_week_seconds: number;
    previous_week_seconds: number;
    new_mistakes_28_days: number;
    tasks: { completed: number; total: number };
  };
};
export function Recommendations() {
  const r = useResource<Report>("/recommendations");
  return (
    <Section title="学习建议">
      <Feedback {...r} />
      {r.data && (
        <>
          <span className="badge">{r.data.label}</span>
          <h3>今日建议</h3>
          <ul>
            {r.data.daily.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
          <h3>每周建议</h3>
          <ul>
            {r.data.weekly.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
          <h3>近 28 天回顾</h3>
          <p>
            有学习记录 {r.data.summary.days_with_study} 天 · 连续{" "}
            {r.data.summary.streak_days} 天 · 新增错题{" "}
            {r.data.summary.new_mistakes_28_days} 道
          </p>
          <p>
            近七天 {duration(r.data.summary.recent_week_seconds)}，前七天{" "}
            {duration(r.data.summary.previous_week_seconds)}；计划任务完成{" "}
            {r.data.summary.tasks.completed}/{r.data.summary.tasks.total}。
          </p>
          {r.data.weak_points.map((k) => (
            <p key={k.id}>
              {k.title} · 掌握 {k.mastery}/5 · 关联错题 {k.mistake_count}
            </p>
          ))}
          <p className="form-hint">{r.data.explanation}</p>
        </>
      )}
    </Section>
  );
}
