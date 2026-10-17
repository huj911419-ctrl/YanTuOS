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
import { api, ApiError, download, downloadPath } from "./api";
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
} from "./types";

import {
  statuses,
  subjects,
  reviewLabels,
  localDay,
  dateLabel,
  dateTime,
  duration,
  timerText,
  percent,
  Empty,
  Modal,
  SubjectField,
  TaskForm,
  KnowledgeForm,
  MistakeForm,
  TaskList,
  SessionHistory,
} from "./components/core";
import {
  PlanPage,
  StatisticsPage,
  KnowledgeReviews,
  ManualRecords,
  Recommendations,
} from "./pages/Learning";
import "./v2.css";
import { AIPage } from "./pages/AI";
import { MaterialsPage } from "./pages/Materials";
import { SettingsPage } from "./pages/Settings";
import { FileImages } from "./components/Files";
import { useResource } from "./components/hooks";
import { PWAStatus } from "./components/PWA";

const nav = [
  { id: "overview", label: "学习总览", icon: LayoutDashboard },
  { id: "tasks", label: "每日计划", icon: ListTodo },
  { id: "plans", label: "周计划与目标", icon: Target },
  { id: "analytics", label: "学习统计", icon: ChartNoAxesCombined },
  { id: "focus", label: "专注计时", icon: Clock3 },
  { id: "knowledge", label: "知识地图", icon: Map },
  { id: "mistakes", label: "我的错题", icon: BookOpen },
  { id: "reviews", label: "复习日程", icon: RotateCcw },
  { id: "ai", label: "AI 学习助手", icon: Flame },
  { id: "materials", label: "学习资料", icon: BookOpen },
  { id: "settings", label: "数据与设置", icon: Settings2 },
] as const;
export default function App() {
  const subjectList = useResource<{ id: number; name: string }[]>("/subjects");
  const preferences = useResource<{
    pomodoro_minutes: number;
    break_minutes: number;
    review_intervals: number[];
  }>("/settings");
  const [page, setPage] = useState<Page>(() =>
    nav.some((n) => n.id === location.hash.slice(1))
      ? (location.hash.slice(1) as Page)
      : "overview",
  );
  const [day, setDay] = useState(localDay());
  const [tasks, setTasks] = useState<Task[]>([]);
  const [knowledge, setKnowledge] = useState<Knowledge[]>([]);
  const [mistakes, setMistakes] = useState<Mistake[]>([]);
  const [reviews, setReviews] = useState<Mistake[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [current, setCurrent] = useState<Session | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [ai, setAI] = useState<AIStatus | null>(null);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [needsToken, setNeedsToken] = useState(false);
  const [tokenInput, setTokenInput] = useState("");
  const [taskModal, setTaskModal] = useState<Task | "new" | null>(null);
  const [knowledgeModal, setKnowledgeModal] = useState<
    Knowledge | "new" | null
  >(null);
  const [mistakeModal, setMistakeModal] = useState<Mistake | "new" | null>(
    null,
  );
  const [reviewModal, setReviewModal] = useState<Mistake | null>(null);
  const [reviewHistory, setReviewHistory] = useState<ReviewEvent[]>([]);
  const [answerVisible, setAnswerVisible] = useState(false);
  const [reviewNote, setReviewNote] = useState("");
  const [reviewDate, setReviewDate] = useState("");
  const [reviewFilter, setReviewFilter] = useState("due");
  const [knowledgeSearch, setKnowledgeSearch] = useState("");
  const [domainFilter, setDomainFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [mistakeSearch, setMistakeSearch] = useState("");
  const [mistakeKnowledge, setMistakeKnowledge] = useState("");
  const [mistakeCategory, setMistakeCategory] = useState("");
  const [mistakeMastery, setMistakeMastery] = useState("");
  const [focusSubject, setFocusSubject] = useState("数学");
  const [focusTopic, setFocusTopic] = useState("");
  const [focusMode, setFocusMode] = useState("forward");
  const [focusMinutes, setFocusMinutes] = useState(25);
  const [breakMinutes, setBreakMinutes] = useState(5);
  const [knowledgeSubject, setKnowledgeSubject] = useState("");
  const [examScope, setExamScope] = useState("");
  const [finishModal, setFinishModal] = useState(false);
  const [finishNote, setFinishNote] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const timerSnapshot = useRef({ value: 0, at: performance.now() });
  const loadSequence = useRef(0);
  const busyRef = useRef(false);

  const load = useCallback(async () => {
    const seq = ++loadSequence.current;
    const results = await Promise.allSettled([
      api<Task[]>("/tasks"),
      api<Knowledge[]>("/knowledge"),
      api<Mistake[]>("/mistakes"),
      api<Mistake[]>("/reviews"),
      api<Session[]>("/sessions"),
      api<Session | null>("/sessions/current"),
      api<Stats>("/stats"),
      api<AIStatus>("/ai/status"),
    ]);
    if (seq !== loadSequence.current) return;
    const setters = [
      setTasks,
      setKnowledge,
      setMistakes,
      setReviews,
      setSessions,
      setCurrent,
      setStats,
      setAI,
    ];
    results.forEach((result, i) => {
      if (result.status === "fulfilled") {
        (setters[i] as (v: unknown) => void)(result.value);
      }
    });
    const active = results[5];
    if (active.status === "fulfilled") {
      const value = active.value as Session | null;
      timerSnapshot.current = {
        value: value?.elapsed_seconds || 0,
        at: performance.now(),
      };
      setElapsed(value?.elapsed_seconds || 0);
    }
    const failure = results.find((r) => r.status === "rejected");
    if (failure?.status === "rejected") {
      if (failure.reason instanceof ApiError && failure.reason.status === 401)
        throw failure.reason;
      setError(
        failure.reason instanceof Error
          ? failure.reason.message
          : "部分数据读取失败，请重试",
      );
    }
    setReady(results.some((r) => r.status === "fulfilled"));
    setNeedsToken(false);
  }, []);

  const report = useCallback((e: unknown) => {
    setError(e instanceof Error ? e.message : "操作失败，请重试。");
    if (e instanceof ApiError && e.status === 401) setNeedsToken(true);
  }, []);

  const reload = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      await load();
    } catch (e) {
      report(e);
    } finally {
      setLoading(false);
    }
  }, [load, report]);
  useEffect(() => {
    void reload();
  }, [reload]);
  useEffect(() => {
    if (preferences.data) {
      setFocusMinutes(preferences.data.pomodoro_minutes);
      setBreakMinutes(preferences.data.break_minutes);
    }
  }, [preferences.data]);
  useEffect(() => {
    const fn = () => {
      const hash = location.hash.slice(1);
      if (nav.some((n) => n.id === hash)) setPage(hash as Page);
    };
    window.addEventListener("hashchange", fn);
    return () => window.removeEventListener("hashchange", fn);
  }, []);
  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(""), 3500);
    return () => clearTimeout(id);
  }, [toast]);
  useEffect(() => {
    if (!current) return;
    const id = setInterval(
      () =>
        setElapsed(
          timerSnapshot.current.value +
            (current.status === "running"
              ? Math.floor(
                  (performance.now() - timerSnapshot.current.at) / 1000,
                )
              : 0),
        ),
      300,
    );
    return () => clearInterval(id);
  }, [current]);
  useEffect(() => {
    const refresh = () => {
      if (document.visibilityState === "visible" && !busyRef.current)
        void load().catch(report);
    };
    document.addEventListener("visibilitychange", refresh);
    window.addEventListener("yantu-data-changed", refresh);
    const id = setInterval(refresh, 30000);
    return () => {
      document.removeEventListener("visibilitychange", refresh);
      window.removeEventListener("yantu-data-changed", refresh);
      clearInterval(id);
    };
  }, [load, report]);

  useEffect(() => {
    if (
      current?.mode === "pomodoro" &&
      current.status === "running" &&
      elapsed >= current.target_seconds
    )
      void load().catch(report);
  }, [elapsed, current, load, report]);

  function go(next: Page) {
    location.hash = next;
    setPage(next);
    window.scrollTo({ top: 0 });
  }
  async function mutate(
    action: () => Promise<unknown>,
    message: string,
    after?: () => void,
  ) {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setError("");
    try {
      await action();
      after?.();
      setToast(message);
      await load();
    } catch (e) {
      report(e);
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }
  const today = stats?.date || localDay();
  const dailyTasks = tasks.filter((t) => t.scheduled_date === day);
  const todayTasks = tasks.filter((t) => t.scheduled_date === today);
  const dueReviews = reviews.filter((m) => m.review.due_date! <= today);
  const domainNames = [...new Set(knowledge.map((k) => k.domain))];
  const knowledgeNames = (ids: number[]) =>
    knowledge.filter((k) => ids.includes(k.id)).map((k) => k.title);

  function shiftDay(offset: number) {
    const d = new Date(`${day}T12:00:00+08:00`);
    d.setUTCDate(d.getUTCDate() + offset);
    setDay(
      new Intl.DateTimeFormat("en-CA", {
        timeZone: "Asia/Shanghai",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      }).format(d),
    );
  }
  function editTask(task: Task) {
    setTaskModal(task);
  }
  const taskActions = {
    busy,
    toggle: (task: Task) =>
      void mutate(
        () =>
          api(`/tasks/${task.id}/completion`, "PATCH", {
            completed: !task.completed,
          }),
        task.completed ? "任务已恢复" : "又完成了一个小目标",
      ),
    edit: editTask,
    remove: (task: Task) => {
      if (confirm(`确定删除任务“${task.title}”？`))
        void mutate(() => api(`/tasks/${task.id}`, "DELETE"), "任务已删除");
    },
    focus: (task: Task) => {
      if (current) {
        go("focus");
        setToast("请先结束当前学习，再开始下一个任务");
      } else {
        setFocusSubject(task.subject);
        setFocusTopic(task.title);
        go("focus");
      }
    },
  };

  async function openReview(mistake: Mistake) {
    setAnswerVisible(false);
    setReviewNote("");
    setReviewDate(mistake.review.due_date || localDay());
    setReviewHistory([]);
    setReviewModal(mistake);
    try {
      const history = await api<ReviewEvent[]>(
        `/mistakes/${mistake.id}/reviews`,
      );
      setReviewHistory(history);
    } catch (e) {
      report(e);
    }
  }

  const saveTask = (data: unknown) =>
    void mutate(
      () =>
        api(
          taskModal === "new" ? "/tasks" : `/tasks/${(taskModal as Task).id}`,
          taskModal === "new" ? "POST" : "PUT",
          data,
        ),
      "任务已保存",
      () => setTaskModal(null),
    );
  const saveKnowledge = (data: unknown) =>
    void mutate(
      () =>
        api(
          knowledgeModal === "new"
            ? "/knowledge"
            : `/knowledge/${(knowledgeModal as Knowledge).id}`,
          knowledgeModal === "new" ? "POST" : "PUT",
          data,
        ),
      "知识点已保存",
      () => setKnowledgeModal(null),
    );
  const saveMistake = (data: unknown) =>
    void mutate(
      () =>
        api(
          mistakeModal === "new"
            ? "/mistakes"
            : `/mistakes/${(mistakeModal as Mistake).id}`,
          mistakeModal === "new" ? "POST" : "PUT",
          data,
        ),
      "错题已保存",
      () => setMistakeModal(null),
    );

  return (
    <div className="app-shell">
      <PWAStatus />
      <aside className="sidebar">
        <a
          className="brand"
          href="#overview"
          onClick={() => go("overview")}
          aria-label="研途 OS 首页"
        >
          <span className="brand-mark">研</span>
          <span>
            研途 <em>OS</em>
            <small>YanTu · 每一步都算数</small>
          </span>
        </a>
        <div className="workspace-label">
          我的学习空间 <span>01</span>
        </div>
        <nav aria-label="主导航">
          {nav.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              aria-label={label}
              className={`nav-item ${page === id ? "active" : ""}`}
              onClick={() => go(id)}
              aria-current={page === id ? "page" : undefined}
            >
              <Icon size={20} strokeWidth={1.7} />
              <span>{label}</span>
              {id === "reviews" && !!dueReviews.length && (
                <b>{dueReviews.length}</b>
              )}
              {id === "overview" && <span className="nav-dot" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="local-status">
            <span />
            本地数据 · 由你掌控
          </div>
          <div className="profile">
            <span className="avatar">研</span>
            <div>
              <strong>我的研途</strong>
              <small>2027 年 12 月 · 考研目标</small>
            </div>
            <Leaf size={18} />
          </div>
        </div>
      </aside>
      <div className="main-wrap">
        <header className="topbar">
          <div className="breadcrumb">
            我的学习空间 <span>/</span>
            <strong>{nav.find((n) => n.id === page)?.label}</strong>
          </div>
          <div className="topbar-right">
            <span className="date-chip">
              <CalendarDays size={15} />
              {dateLabel(today, true)}
            </span>
            <span className="version">YanTu OS 0.2</span>
          </div>
        </header>
        <main>
          {error && (
            <div className="error-banner" role="alert">
              <FileWarning size={18} />
              <span>{error}</span>
              <button className="text-button" onClick={() => void reload()}>
                重试
              </button>
              <button
                className="icon-button"
                aria-label="关闭错误提示"
                onClick={() => setError("")}
              >
                <X size={16} />
              </button>
            </div>
          )}
          {needsToken ? (
            <section className="panel token-panel">
              <ShieldCheck size={32} />
              <h1>连接你的学习空间</h1>
              <p>
                此服务启用了访问令牌。登录后使用 24 小时有效的 HttpOnly
                会话；服务重启后需重新登录。
              </p>
              <form
                onSubmit={(e: FormEvent) => {
                  e.preventDefault();
                  void api("/auth/login", "POST", { token: tokenInput })
                    .then(() => {
                      setTokenInput("");
                      void reload();
                    })
                    .catch(report);
                }}
              >
                <label>
                  访问令牌
                  <input
                    type="password"
                    required
                    value={tokenInput}
                    onChange={(e) => setTokenInput(e.target.value)}
                    autoComplete="current-password"
                  />
                </label>
                <button className="button">连接</button>
              </form>
            </section>
          ) : !ready ? (
            <div className="loading-state">
              {loading ? (
                <>
                  <LoaderCircle className="spin" />
                  正在打开你的学习空间…
                </>
              ) : (
                <>
                  <Database size={30} />
                  <p>暂时无法读取学习数据</p>
                  <button className="button" onClick={() => void reload()}>
                    重新连接
                  </button>
                </>
              )}
            </div>
          ) : (
            <>
              {page === "overview" && stats && (
                <>
                  <div className="page-heading">
                    <div>
                      <span className="eyebrow">YOUR LEARNING, IN FOCUS</span>
                      <h1>
                        把今天，变成进步的一天
                        <span className="heading-dot">.</span>
                      </h1>
                      <p>从一个小目标开始，让每一次学习都有迹可循。</p>
                    </div>
                    <button
                      className="button"
                      onClick={() => {
                        setDay(today);
                        setTaskModal("new");
                      }}
                    >
                      <Plus size={18} />
                      新建学习任务
                    </button>
                  </div>
                  <section className="hero">
                    <div>
                      <span className="hero-kicker">
                        <span />向 2027 年 12 月，稳步前进
                      </span>
                      <h2>
                        不必一次走很远，
                        <br />
                        只要今天再向前一步。
                      </h2>
                      <p>计划、专注、回顾。慢慢建立属于你的知识体系。</p>
                      <button
                        className="hero-button"
                        onClick={() => go("focus")}
                      >
                        {current ? "回到进行中的学习" : "开始一次专注"}
                        <ArrowRight size={17} />
                      </button>
                    </div>
                    <div className="hero-art" aria-hidden="true">
                      <div className="orbit orbit-one" />
                      <div className="orbit orbit-two" />
                      <div className="art-line" />
                      <div className="art-step step-one" />
                      <div className="art-step step-two" />
                      <div className="art-step step-three" />
                      <div className="art-sun">
                        <Leaf size={33} />
                      </div>
                      <span className="art-caption">GROW AT YOUR OWN PACE</span>
                      <span className="art-coordinate">27° / 12′</span>
                    </div>
                  </section>
                  <div className="stats-grid">
                    <Stat
                      icon={Clock3}
                      label="今日学习"
                      value={duration(stats.today_seconds)}
                      note="不含暂停时间"
                    />
                    <Stat
                      icon={ChartNoAxesCombined}
                      label="本周投入"
                      value={duration(stats.week_seconds)}
                      note={`自 ${dateLabel(stats.week_start)} 起`}
                    />
                    <Stat
                      icon={CheckCheck}
                      label="今日任务"
                      value={`${stats.today_tasks.completed} / ${stats.today_tasks.total}`}
                      note={
                        stats.today_tasks.total
                          ? `${percent(stats.today_tasks.completed, stats.today_tasks.total)}% 已完成`
                          : "给今天安排一个小目标"
                      }
                    />
                    <Stat
                      icon={RotateCcw}
                      label="到期复习"
                      value={`${stats.due_review_count}`}
                      suffix="项"
                      note={`共 ${stats.pending_review_count} 项等待复习`}
                      accent
                    />
                  </div>
                  <div className="dashboard-grid">
                    <section className="panel today-panel">
                      <div className="panel-header">
                        <h2>
                          <span className="title-line" />
                          今日计划{" "}
                          <span className="count">{todayTasks.length}</span>
                        </h2>
                        <button
                          className="text-button"
                          onClick={() => {
                            setDay(today);
                            go("tasks");
                          }}
                        >
                          查看全部
                          <ArrowRight size={14} />
                        </button>
                      </div>
                      {todayTasks.length ? (
                        <TaskList
                          tasks={todayTasks.slice(0, 4)}
                          {...taskActions}
                        />
                      ) : (
                        <Empty
                          icon={ListTodo}
                          title="今天的进步，从这里开始"
                          action={
                            <button
                              className="button secondary small"
                              onClick={() => {
                                setDay(today);
                                setTaskModal("new");
                              }}
                            >
                              <Plus size={15} />
                              添加第一个任务
                            </button>
                          }
                        >
                          把大目标拆成今天可以完成的小事。
                        </Empty>
                      )}
                      <div className="panel-foot">
                        <Leaf size={14} />
                        完成计划之外，也给理解和思考留一点时间。
                      </div>
                    </section>
                    <section className="panel week-panel">
                      <div className="panel-header">
                        <h2>本周学习节奏</h2>
                        <span className="muted small-text">周一至周日</span>
                      </div>
                      <WeekChart stats={stats} />
                      <div className="week-summary">
                        <span>本周累计</span>
                        <strong>{duration(stats.week_seconds)}</strong>
                      </div>
                    </section>
                    <section className="panel">
                      <div className="panel-header">
                        <h2>知识积累</h2>
                        <button
                          className="text-button"
                          onClick={() => go("knowledge")}
                        >
                          知识地图
                          <ArrowRight size={14} />
                        </button>
                      </div>
                      <div className="knowledge-overview">
                        <div
                          className="progress-ring"
                          style={
                            {
                              "--progress": `${percent(stats.mastered_knowledge_count, stats.knowledge_count)}%`,
                            } as CSSProperties
                          }
                        >
                          <span>
                            <strong>{stats.mastered_knowledge_count}</strong>
                            <small>已掌握知识点</small>
                          </span>
                        </div>
                        <div>
                          <p>
                            累计整理 <strong>{stats.mistake_count}</strong>{" "}
                            道错题
                          </p>
                          <p className="muted">
                            学习状态由你确认。
                            <br />
                            参考知识点可持续调整。
                          </p>
                          <button
                            className="text-button"
                            onClick={() => go("mistakes")}
                          >
                            去整理一道错题
                            <ArrowRight size={14} />
                          </button>
                        </div>
                      </div>
                    </section>
                    <section className="panel review-preview">
                      <div className="panel-header">
                        <h2>温故，才能知新</h2>
                        <span className="badge warm">间隔复习</span>
                      </div>
                      {dueReviews.length ? (
                        <>
                          <p className="review-callout">
                            有 <strong>{dueReviews.length}</strong>{" "}
                            道错题，等你重新理解。
                          </p>
                          <button
                            className="button secondary"
                            onClick={() => go("reviews")}
                          >
                            开始今日复习
                            <ArrowRight size={16} />
                          </button>
                        </>
                      ) : (
                        <>
                          <p className="review-callout">
                            {reviews.length
                              ? "今天没有到期复习。"
                              : "把一次错误，变成下次的把握。"}
                          </p>
                          <p className="muted">
                            录入错题后，系统将按规则安排复习日期。
                          </p>
                          <button
                            className="text-button"
                            onClick={() =>
                              go(reviews.length ? "reviews" : "mistakes")
                            }
                          >
                            {reviews.length ? "查看后续安排" : "整理错题"}
                            <ArrowRight size={14} />
                          </button>
                        </>
                      )}
                    </section>
                  </div>
                  <section className="panel" style={{ marginTop: 20 }}>
                    <div className="panel-header">
                      <h2>本周各科目投入</h2>
                      <span className="muted small-text">实际学习时长</span>
                    </div>
                    {stats.subjects.length ? (
                      <div className="subject-breakdown">
                        {stats.subjects.map((s) => (
                          <div key={s.subject}>
                            <div className="subject-line">
                              <span>{s.subject}</span>
                              <strong>{duration(s.seconds)}</strong>
                            </div>
                            <div className="subject-track">
                              <div
                                style={{
                                  width: `${stats.week_seconds ? (s.seconds / stats.week_seconds) * 100 : 0}%`,
                                }}
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <Empty
                        icon={ChartNoAxesCombined}
                        title="还没有本周科目记录"
                      >
                        开始一次学习，投入就会在这里留下痕迹。
                      </Empty>
                    )}
                    <div className="all-task-summary">
                      全部任务：{stats.all_tasks.completed} /{" "}
                      {stats.all_tasks.total} 已完成 · 累计错题：
                      {stats.mistake_count} 道
                    </div>
                  </section>
                  <Recommendations />
                  <div className="footer-note">
                    <Database size={13} />
                    统计来自你的真实数据库 · 上海时间（UTC+8） · 每 30 秒刷新
                  </div>
                </>
              )}

              {page === "plans" && (
                <PlanPage edit={editTask} create={() => setTaskModal("new")} />
              )}
              {page === "analytics" && <StatisticsPage />}
              {page === "tasks" && (
                <>
                  <PageHeading
                    eyebrow="A LITTLE PROGRESS, EVERY DAY"
                    title="每日计划"
                    description="明确今天要做的事，也给自己留一点余地。"
                    action={
                      <button
                        className="button"
                        onClick={() => setTaskModal("new")}
                      >
                        <Plus size={18} />
                        新建任务
                      </button>
                    }
                  />
                  <div className="day-toolbar">
                    <div className="date-navigation">
                      <button
                        className="icon-button"
                        aria-label="前一天"
                        onClick={() => shiftDay(-1)}
                      >
                        <ChevronLeft size={20} />
                      </button>
                      <label>
                        <span className="sr-only">计划日期</span>
                        <input
                          type="date"
                          value={day}
                          required
                          onChange={(e) =>
                            e.target.value && setDay(e.target.value)
                          }
                        />
                      </label>
                      <button
                        className="icon-button"
                        aria-label="后一天"
                        onClick={() => shiftDay(1)}
                      >
                        <ChevronRight size={20} />
                      </button>
                      <button
                        className="text-button"
                        onClick={() => setDay(today)}
                      >
                        今天
                      </button>
                    </div>
                    <span className="muted">
                      {dailyTasks.filter((t) => !!t.completed).length} /{" "}
                      {dailyTasks.length} 项已完成 · 预计{" "}
                      {dailyTasks.reduce(
                        (sum, t) => sum + t.estimated_minutes,
                        0,
                      )}{" "}
                      分钟
                    </span>
                  </div>
                  <section className="panel">
                    <div className="panel-header">
                      <h2>
                        {dateLabel(day, true)}
                        {day === today && <span className="badge">今天</span>}
                      </h2>
                    </div>
                    {dailyTasks.length ? (
                      <TaskList tasks={dailyTasks} {...taskActions} />
                    ) : (
                      <Empty
                        icon={CalendarDays}
                        title="这一天还没有任务"
                        action={
                          <button
                            className="button secondary"
                            onClick={() => setTaskModal("new")}
                          >
                            <Plus size={16} />
                            安排一个小目标
                          </button>
                        }
                      >
                        建议从 30 分钟可以完成的学习内容开始。
                      </Empty>
                    )}
                  </section>
                </>
              )}

              {page === "focus" && (
                <>
                  <PageHeading
                    eyebrow="ONE THING AT A TIME"
                    title="专注于眼前这一件事"
                    description="计时由服务端保存。刷新页面、切换标签页后仍可继续。"
                  />
                  <section
                    className={`focus-panel panel ${current?.status === "running" ? "is-running" : ""}`}
                  >
                    <div className="focus-state">
                      <span
                        className={`status-dot ${current?.status === "running" ? "live" : ""}`}
                      />
                      {current
                        ? current.status === "running"
                          ? "正在专注"
                          : "已暂停 · 休息一下"
                        : "准备开始一次新的学习"}
                    </div>
                    <div className="timer" aria-label="已学习时长" role="timer">
                      {timerText(
                        current
                          ? current.mode === "pomodoro"
                            ? Math.max(0, current.target_seconds - elapsed)
                            : elapsed
                          : 0,
                      )}
                    </div>
                    {current ? (
                      <div className="current-topic">
                        <span className="subject-tag">{current.subject}</span>
                        <strong>{current.topic || "专注学习"}</strong>
                        <p>
                          开始于 {dateTime(current.started_at)} ·
                          只累计实际计时的时间
                        </p>
                      </div>
                    ) : (
                      <div className="focus-fields">
                        <SubjectField
                          value={focusSubject}
                          onChange={setFocusSubject}
                        />
                        <label>
                          本次学习内容
                          <input
                            maxLength={200}
                            value={focusTopic}
                            onChange={(e) => setFocusTopic(e.target.value)}
                            placeholder="例如：理解极限的定义"
                          />
                        </label>
                      </div>
                    )}
                    {!current && (
                      <div className="form-row timer-options">
                        <label>
                          计时模式
                          <select
                            value={focusMode}
                            onChange={(e) => setFocusMode(e.target.value)}
                          >
                            <option value="forward">正向计时</option>
                            <option value="pomodoro">番茄钟</option>
                          </select>
                        </label>
                        {focusMode === "pomodoro" && (
                          <>
                            <label>
                              专注分钟
                              <input
                                type="number"
                                min={1}
                                max={180}
                                value={focusMinutes}
                                onChange={(e) =>
                                  setFocusMinutes(Number(e.target.value))
                                }
                              />
                            </label>
                            <label>
                              休息分钟
                              <input
                                type="number"
                                min={1}
                                max={60}
                                value={breakMinutes}
                                onChange={(e) =>
                                  setBreakMinutes(Number(e.target.value))
                                }
                              />
                            </label>
                          </>
                        )}
                      </div>
                    )}
                    <div className="focus-actions">
                      {current ? (
                        <>
                          <button
                            className="button large"
                            disabled={busy}
                            onClick={() =>
                              void mutate(
                                () =>
                                  api(
                                    `/sessions/${current.id}/${current.status === "running" ? "pause" : "resume"}`,
                                    "POST",
                                  ),
                                current.status === "running"
                                  ? "已暂停计时"
                                  : "已继续计时",
                              )
                            }
                          >
                            {current.status === "running" ? (
                              <Pause size={18} />
                            ) : (
                              <Play size={18} />
                            )}
                            {current.status === "running"
                              ? "暂停学习"
                              : "继续学习"}
                          </button>
                          <button
                            className="button secondary large"
                            disabled={busy}
                            onClick={() => {
                              setFinishNote("");
                              setFinishModal(true);
                            }}
                          >
                            <Square size={16} />
                            结束并记录
                          </button>
                        </>
                      ) : (
                        <button
                          className="button large"
                          disabled={busy || !focusSubject.trim()}
                          onClick={() =>
                            void mutate(
                              () =>
                                api("/sessions", "POST", {
                                  subject: focusSubject,
                                  topic: focusTopic,
                                  mode: focusMode,
                                  target_minutes: focusMinutes,
                                  break_minutes: breakMinutes,
                                  request_id: crypto.randomUUID(),
                                }),
                              "计时已开始",
                            )
                          }
                        >
                          <Play size={19} />
                          开始学习
                        </button>
                      )}
                    </div>
                    <p className="focus-tip">
                      <CircleHelp size={14} />
                      离开学习前请暂停；关闭浏览器不会自动停止计时。
                    </p>
                  </section>
                  <ManualRecords sessions={sessions} refresh={load} />
                  <SessionHistory sessions={sessions} />
                </>
              )}

              {page === "knowledge" && (
                <>
                  <PageHeading
                    eyebrow="BUILD YOUR UNDERSTANDING"
                    title="一点点，连成知识地图"
                    description="先打牢基础，再逐步拓展。学习状态由你亲自确认。"
                    action={
                      <button
                        className="button"
                        onClick={() => setKnowledgeModal("new")}
                      >
                        <Plus size={18} />
                        添加知识点
                      </button>
                    }
                  />
                  <div className="notice">
                    <Map size={19} />
                    <span>
                      当前为可编辑的基础参考知识库，
                      <strong>不是某类考研数学的最终大纲</strong>
                      。待确定数学类别后再调整范围。
                    </span>
                  </div>
                  <div className="filter-bar">
                    <label className="search-input">
                      <Search size={17} />
                      <span className="sr-only">搜索知识点</span>
                      <input
                        value={knowledgeSearch}
                        onChange={(e) => setKnowledgeSearch(e.target.value)}
                        placeholder="搜索知识点或笔记…"
                      />
                    </label>
                    <label>
                      <span className="sr-only">筛选知识分类</span>
                      <select
                        value={domainFilter}
                        onChange={(e) => setDomainFilter(e.target.value)}
                      >
                        <option value="">全部分类</option>
                        {domainNames.map((name) => (
                          <option key={name}>{name}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      <span className="sr-only">筛选学习状态</span>
                      <select
                        value={statusFilter}
                        onChange={(e) => setStatusFilter(e.target.value)}
                      >
                        <option value="">全部状态</option>
                        {Object.entries(statuses).map(([v, label]) => (
                          <option key={v} value={v}>
                            {label}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <div className="filter-bar">
                    <label>
                      科目筛选
                      <select
                        value={knowledgeSubject}
                        onChange={(e) => setKnowledgeSubject(e.target.value)}
                      >
                        <option value="">全部科目</option>
                        {[...new Set(knowledge.map((k) => k.subject))].map(
                          (s) => (
                            <option key={s}>{s}</option>
                          ),
                        )}
                      </select>
                    </label>
                    <label>
                      数学范围
                      <select
                        value={examScope}
                        onChange={(e) => setExamScope(e.target.value)}
                      >
                        <option value="">全部（未确定考试类别）</option>
                        <option value="math1">数学一</option>
                        <option value="math2">数学二</option>
                        <option value="math3">数学三</option>
                      </select>
                    </label>
                  </div>
                  <div className="knowledge-groups">
                    {domainNames
                      .filter((d) => !domainFilter || domainFilter === d)
                      .map((domain) => {
                        const points = knowledge.filter(
                          (k) =>
                            k.domain === domain &&
                            (!knowledgeSubject ||
                              k.subject === knowledgeSubject) &&
                            (!examScope ||
                              JSON.parse(k.exam_scopes || "[]").includes(
                                examScope,
                              )) &&
                            (!statusFilter || k.status === statusFilter) &&
                            `${k.title}${k.notes}`.includes(knowledgeSearch),
                        );
                        if (!points.length) return null;
                        return (
                          <section
                            className="panel knowledge-group"
                            key={domain}
                          >
                            <div className="panel-header">
                              <h2>
                                <BookOpen size={19} />
                                {domain}
                                <span className="count">{points.length}</span>
                              </h2>
                              <span className="muted small-text">
                                {
                                  points.filter((k) => k.status === "mastered")
                                    .length
                                }{" "}
                                个已掌握
                              </span>
                            </div>
                            {points.map((k) => (
                              <div className="knowledge-row" key={k.id}>
                                <span className={`knowledge-dot ${k.status}`} />
                                <div className="knowledge-content">
                                  <strong>
                                    {k.parent_id
                                      ? `↳ ${knowledge.find((p) => p.id === k.parent_id)?.title} / `
                                      : ""}
                                    {k.title}
                                  </strong>
                                  <small className="muted">
                                    {" "}
                                    {k.subject} · 掌握 {k.mastery}/5 · 最近学习{" "}
                                    {k.last_studied_at
                                      ? dateTime(k.last_studied_at)
                                      : "尚无"}{" "}
                                    · 最近复习{" "}
                                    {k.last_reviewed_at
                                      ? dateTime(k.last_reviewed_at)
                                      : "尚无"}
                                  </small>
                                  {!!k.is_reference && (
                                    <span className="reference-tag">
                                      初始参考
                                    </span>
                                  )}
                                  {k.syllabus_source && (
                                    <p>
                                      资料来源：{k.syllabus_source}
                                      {k.syllabus_year
                                        ? ` · ${k.syllabus_year} 年`
                                        : " · 年份未注明"}
                                    </p>
                                  )}
                                  {k.notes && <p>{k.notes}</p>}
                                  {k.unresolved_count > 0 && (
                                    <button
                                      className="weakness-link"
                                      onClick={() => {
                                        setMistakeKnowledge(String(k.id));
                                        go("mistakes");
                                      }}
                                    >
                                      {k.unresolved_count} 道未掌握错题 · 查看
                                    </button>
                                  )}
                                </div>
                                <select
                                  aria-label={`${k.title}的学习状态`}
                                  className={`state-select ${k.status}`}
                                  value={k.status}
                                  disabled={busy}
                                  onChange={(e) =>
                                    void mutate(
                                      () =>
                                        api(
                                          `/knowledge/${k.id}/status`,
                                          "PATCH",
                                          { status: e.target.value },
                                        ),
                                      "学习状态已更新",
                                    )
                                  }
                                >
                                  {Object.entries(statuses).map(
                                    ([v, label]) => (
                                      <option key={v} value={v}>
                                        {label}
                                      </option>
                                    ),
                                  )}
                                </select>
                                <div className="row-actions">
                                  <button
                                    className="icon-button"
                                    aria-label={`编辑知识点：${k.title}`}
                                    onClick={() => setKnowledgeModal(k)}
                                  >
                                    <Pencil size={15} />
                                  </button>
                                  <button
                                    className="icon-button danger"
                                    disabled={busy}
                                    aria-label={`删除知识点：${k.title}`}
                                    onClick={() => {
                                      if (
                                        confirm(`确定删除知识点“${k.title}”？`)
                                      )
                                        void mutate(
                                          () =>
                                            api(`/knowledge/${k.id}`, "DELETE"),
                                          "知识点已删除",
                                        );
                                    }}
                                  >
                                    <Trash2 size={15} />
                                  </button>
                                </div>
                              </div>
                            ))}
                          </section>
                        );
                      })}
                  </div>
                  {!knowledge.some(
                    (k) =>
                      (!domainFilter || k.domain === domainFilter) &&
                      (!statusFilter || k.status === statusFilter) &&
                      `${k.title}${k.notes}`.includes(knowledgeSearch),
                  ) && (
                    <section className="panel">
                      <Empty icon={Search} title="没有匹配的知识点">
                        调整筛选条件，或添加自己的知识点。
                      </Empty>
                    </section>
                  )}
                </>
              )}

              {page === "mistakes" && (
                <>
                  <PageHeading
                    eyebrow="MISTAKES ARE PART OF LEARNING"
                    title="让错过的题，成为掌握的题"
                    description={`已整理 ${mistakes.length} 道错题。记下错误原因，比只记答案更有价值。`}
                    action={
                      <button
                        className="button"
                        onClick={() => setMistakeModal("new")}
                      >
                        <Plus size={18} />
                        录入错题
                      </button>
                    }
                  />
                  <div className="filter-bar">
                    <label className="search-input">
                      <Search size={17} />
                      <span className="sr-only">搜索错题</span>
                      <input
                        value={mistakeSearch}
                        onChange={(e) => setMistakeSearch(e.target.value)}
                        placeholder="搜索标题、题目或错误原因…"
                      />
                    </label>
                    <label>
                      <span className="sr-only">按知识点筛选错题</span>
                      <select
                        value={mistakeKnowledge}
                        onChange={(e) => setMistakeKnowledge(e.target.value)}
                      >
                        <option value="">全部知识点</option>
                        {knowledge.map((k) => (
                          <option key={k.id} value={k.id}>
                            {k.title}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <div className="filter-bar">
                    <label>
                      错题分类筛选
                      <select
                        value={mistakeCategory}
                        onChange={(e) => setMistakeCategory(e.target.value)}
                      >
                        <option value="">全部分类</option>
                        {[...new Set(mistakes.map((m) => m.category))].map(
                          (c) => (
                            <option key={c}>{c}</option>
                          ),
                        )}
                      </select>
                    </label>
                    <label>
                      掌握状态筛选
                      <select
                        value={mistakeMastery}
                        onChange={(e) => setMistakeMastery(e.target.value)}
                      >
                        <option value="">全部状态</option>
                        <option value="unmastered">未掌握</option>
                        <option value="reviewing">复习中</option>
                        <option value="mastered">已掌握</option>
                      </select>
                    </label>
                    <button
                      className="button secondary"
                      disabled={busy}
                      onClick={() =>
                        void mutate(
                          () =>
                            downloadPath(
                              `/mistakes-export?q=${encodeURIComponent(mistakeSearch)}${mistakeKnowledge ? `&knowledge_id=${mistakeKnowledge}` : ""}`,
                              "yantu-mistakes.md",
                            ),
                          "错题已导出",
                        )
                      }
                    >
                      导出错题文本
                    </button>
                  </div>
                  <div className="mistake-grid">
                    {mistakes
                      .filter(
                        (m) =>
                          (!mistakeCategory ||
                            m.category === mistakeCategory) &&
                          (!mistakeMastery || m.mastery === mistakeMastery) &&
                          (!mistakeKnowledge ||
                            m.knowledge_ids.includes(
                              Number(mistakeKnowledge),
                            )) &&
                          `${m.title}${m.question}${m.error_reason}`.includes(
                            mistakeSearch,
                          ),
                      )
                      .map((m) => (
                        <article className="panel mistake-card" key={m.id}>
                          <div className="mistake-top">
                            <span className="subject-tag">{m.subject}</span>
                            <span
                              className={`badge ${m.review_status === "mastered" ? "" : "warm"}`}
                            >
                              {reviewLabels[m.review_status]}
                            </span>
                          </div>
                          <h2>{m.title}</h2>
                          <p className="question-excerpt">{m.question}</p>
                          <div className="tag-list">
                            {knowledgeNames(m.knowledge_ids).map((name) => (
                              <span key={name}>{name}</span>
                            ))}
                          </div>
                          {m.error_reason && (
                            <div className="error-reason">
                              <span>错误原因</span>
                              <p>{m.error_reason}</p>
                            </div>
                          )}
                          <div className="mistake-bottom">
                            <span className="muted small-text">
                              {m.review.due_date
                                ? `下次复习 ${m.review.due_date}`
                                : "已完成本轮复习"}
                            </span>
                            <div className="row-actions">
                              <button
                                className="text-button"
                                onClick={() => void openReview(m)}
                              >
                                查看
                                <ArrowRight size={14} />
                              </button>
                              <button
                                className="icon-button"
                                aria-label={`编辑错题：${m.title}`}
                                onClick={() => setMistakeModal(m)}
                              >
                                <Pencil size={16} />
                              </button>
                              <button
                                className="icon-button danger"
                                disabled={busy}
                                aria-label={`删除错题：${m.title}`}
                                onClick={() => {
                                  if (
                                    confirm(
                                      `确定删除错题“${m.title}”及其复习记录？`,
                                    )
                                  )
                                    void mutate(
                                      () => api(`/mistakes/${m.id}`, "DELETE"),
                                      "错题已删除",
                                    );
                                }}
                              >
                                <Trash2 size={16} />
                              </button>
                            </div>
                          </div>
                        </article>
                      ))}
                  </div>
                  {!mistakes.filter(
                    (m) =>
                      (!mistakeCategory || m.category === mistakeCategory) &&
                      (!mistakeMastery || m.mastery === mistakeMastery) &&
                      (!mistakeKnowledge ||
                        m.knowledge_ids.includes(Number(mistakeKnowledge))) &&
                      `${m.title}${m.question}${m.error_reason}`.includes(
                        mistakeSearch,
                      ),
                  ).length && (
                    <section className="panel">
                      <Empty
                        title={
                          mistakes.length
                            ? "没有匹配的错题"
                            : "每一道错题，都是进步的线索"
                        }
                        action={
                          !mistakes.length && (
                            <button
                              className="button secondary"
                              onClick={() => setMistakeModal("new")}
                            >
                              <Plus size={16} />
                              录入第一道错题
                            </button>
                          )
                        }
                      >
                        {mistakes.length
                          ? "试试其他关键词或知识点。"
                          : "先记录题目，再慢慢补充解题过程与错误原因。"}
                      </Empty>
                    </section>
                  )}
                </>
              )}

              {page === "reviews" && (
                <>
                  <PageHeading
                    eyebrow="REMEMBER THROUGH RETRIEVAL"
                    title="在遗忘之前，再理解一次"
                    description="先独立回忆，再查看答案，最后如实记录本次掌握情况。"
                  />
                  <KnowledgeReviews refresh={load} />
                  <div className="review-rule">
                    <RotateCcw size={24} />
                    <div>
                      <strong>清楚、可解释的间隔复习</strong>
                      <p>
                        当前间隔：
                        {(
                          preferences.data?.review_intervals || [
                            1, 3, 7, 14, 30,
                          ]
                        ).join("、")}{" "}
                        天。独立完成推进阶段，提示后完成次日巩固，未掌握重置；连续通过
                        5 次结束本轮。
                      </p>
                    </div>
                    <span className="badge">规则驱动</span>
                  </div>
                  <div className="tab-bar">
                    <button
                      className={reviewFilter === "due" ? "active" : ""}
                      onClick={() => setReviewFilter("due")}
                    >
                      今日到期<span>{dueReviews.length}</span>
                    </button>
                    <button
                      className={reviewFilter === "all" ? "active" : ""}
                      onClick={() => setReviewFilter("all")}
                    >
                      全部待复习<span>{reviews.length}</span>
                    </button>
                  </div>
                  <section className="panel">
                    {(reviewFilter === "due" ? dueReviews : reviews).length ? (
                      <div className="review-list">
                        {(reviewFilter === "due" ? dueReviews : reviews).map(
                          (m) => (
                            <div className="review-row" key={m.id}>
                              <span
                                className={`review-calendar ${m.review.due_date! <= today ? "due" : ""}`}
                              >
                                <small>
                                  {new Date(
                                    `${m.review.due_date}T12:00:00+08:00`,
                                  ).getMonth() + 1}{" "}
                                  月
                                </small>
                                <strong>
                                  {Number(m.review.due_date!.slice(-2))}
                                </strong>
                              </span>
                              <div className="review-content">
                                <strong>{m.title}</strong>
                                <p>
                                  {m.subject} ·{" "}
                                  {knowledgeNames(m.knowledge_ids).join("、") ||
                                    "未关联知识点"}
                                </p>
                                <div
                                  className="review-dots"
                                  aria-label={`已连续记住 ${m.review.stage} 次`}
                                >
                                  {Array.from({ length: 5 }, (_, i) => (
                                    <span
                                      key={i}
                                      className={
                                        i < m.review.stage ? "filled" : ""
                                      }
                                    />
                                  ))}
                                  <small>
                                    已连续记住 {m.review.stage} / 5 次
                                  </small>
                                </div>
                              </div>
                              <button
                                className="button secondary small"
                                onClick={() => void openReview(m)}
                              >
                                {m.review.due_date! <= today
                                  ? "开始复习"
                                  : "查看题目"}
                                <ArrowRight size={15} />
                              </button>
                            </div>
                          ),
                        )}
                      </div>
                    ) : (
                      <Empty
                        icon={CheckCheck}
                        title={
                          reviewFilter === "due"
                            ? "今天没有到期的复习"
                            : "还没有待复习的错题"
                        }
                      >
                        {reviews.length
                          ? "按自己的节奏继续学习，别忘了按时回来。"
                          : "录入一道错题，系统会自动生成复习安排。"}
                      </Empty>
                    )}
                  </section>
                </>
              )}

              {page === "settings" && <SettingsPage />}
              {page === "ai" && <AIPage />}
              {page === "materials" && <MaterialsPage />}
            </>
          )}
        </main>
        <footer className="app-footer">
          <span>研途 OS</span> 少一点焦虑，多一点踏实。
          <span className="footer-right">为持续学习而设计</span>
        </footer>
      </div>
      {current && page !== "focus" && (
        <button className="floating-timer" onClick={() => go("focus")}>
          <span
            className={`status-dot ${current.status === "running" ? "live" : ""}`}
          />
          <span>
            {current.subject} ·{" "}
            {current.status === "paused" ? "已暂停" : "专注中"}
          </span>
          <strong>{timerText(elapsed)}</strong>
          <ArrowRight size={15} />
        </button>
      )}
      {toast && (
        <div className="toast" role="status">
          <Check size={17} />
          {toast}
        </div>
      )}
      {taskModal && (
        <Modal
          error={error}
          title={taskModal === "new" ? "新建学习任务" : "编辑学习任务"}
          close={() => !busy && setTaskModal(null)}
        >
          <TaskForm
            task={taskModal === "new" ? undefined : taskModal}
            day={day}
            busy={busy}
            save={saveTask}
            close={() => setTaskModal(null)}
          />
        </Modal>
      )}
      {knowledgeModal && (
        <Modal
          error={error}
          title={knowledgeModal === "new" ? "添加知识点" : "编辑知识点"}
          close={() => !busy && setKnowledgeModal(null)}
        >
          <KnowledgeForm
            knowledge={knowledge}
            point={knowledgeModal === "new" ? undefined : knowledgeModal}
            busy={busy}
            save={saveKnowledge}
            close={() => setKnowledgeModal(null)}
          />
        </Modal>
      )}
      {mistakeModal && (
        <Modal
          error={error}
          title={mistakeModal === "new" ? "录入一道错题" : "编辑错题"}
          close={() => !busy && setMistakeModal(null)}
        >
          <MistakeForm
            mistake={mistakeModal === "new" ? undefined : mistakeModal}
            knowledge={knowledge}
            busy={busy}
            save={saveMistake}
            close={() => setMistakeModal(null)}
          />
        </Modal>
      )}
      {finishModal && current && (
        <Modal
          error={error}
          title="记录这一次进步"
          close={() => !busy && setFinishModal(false)}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void mutate(
                () =>
                  api(`/sessions/${current.id}/finish`, "POST", {
                    notes: finishNote,
                  }),
                "学习已记录，辛苦了",
                () => setFinishModal(false),
              );
            }}
          >
            <p className="finish-summary">
              {current.subject} · 已专注 <strong>{duration(elapsed)}</strong>
            </p>
            <label>
              学习小结（选填）
              <textarea
                autoFocus
                rows={4}
                maxLength={20000}
                value={finishNote}
                onChange={(e) => setFinishNote(e.target.value)}
                placeholder="今天理解了什么？还有哪里需要再想一想？"
              />
            </label>
            <p className="form-hint">确认结束前仍按当前状态计时。</p>
            <div className="form-actions">
              <button
                type="button"
                className="button secondary"
                disabled={busy}
                onClick={() => setFinishModal(false)}
              >
                继续学习
              </button>
              <button className="button" disabled={busy}>
                确认结束并保存
              </button>
            </div>
          </form>
        </Modal>
      )}
      {reviewModal && (
        <Modal
          error={error}
          title="回顾这道错题"
          close={() => !busy && setReviewModal(null)}
        >
          <article className="review-detail">
            <div className="mistake-top">
              <span className="subject-tag">{reviewModal.subject}</span>
              <span className="badge warm">
                {reviewLabels[reviewModal.review_status]}
              </span>
            </div>
            <h3>{reviewModal.title}</h3>
            {reviewModal.source && (
              <p className="muted">来源：{reviewModal.source}</p>
            )}
            <div className="tag-list">
              {knowledgeNames(reviewModal.knowledge_ids).map((n) => (
                <span key={n}>{n}</span>
              ))}
            </div>
            <div className="detail-block">
              <h4>题目</h4>
              <p>{reviewModal.question}</p>
              <FileImages ids={reviewModal.file_ids} />
            </div>
            {!answerVisible ? (
              <div className="recall-box">
                <BookOpen size={25} />
                <p>先独立回忆或在纸上重做，再查看答案。</p>
                <button
                  className="button secondary"
                  onClick={() => setAnswerVisible(true)}
                >
                  查看答案与错因
                </button>
              </div>
            ) : (
              <>
                <div className="detail-block answer-block">
                  <h4>答案与解题过程</h4>
                  <p>
                    {reviewModal.answer || "尚未录入答案，可在错题编辑中补充。"}
                  </p>
                </div>
                <div className="detail-block">
                  <h4>我的错误答案</h4>
                  <p>{reviewModal.wrong_answer || "尚未记录"}</p>
                  <h4>当时的错误原因</h4>
                  <p>{reviewModal.error_reason || "尚未记录。"}</p>
                </div>
              </>
            )}
            {reviewModal.review.due_date &&
              reviewModal.review.due_date <= today && (
                <>
                  <label>
                    本次复习笔记（选填）
                    <textarea
                      rows={2}
                      maxLength={20000}
                      value={reviewNote}
                      onChange={(e) => setReviewNote(e.target.value)}
                    />
                  </label>
                  <div className="review-outcomes">
                    <button
                      className="button secondary"
                      disabled={busy || !answerVisible}
                      onClick={() =>
                        void mutate(
                          () =>
                            api(`/mistakes/${reviewModal.id}/review`, "POST", {
                              outcome: "assisted",
                              notes: reviewNote,
                            }),
                          "已安排次日巩固",
                          () => setReviewModal(null),
                        )
                      }
                    >
                      提示后完成
                    </button>
                    <button
                      className="button secondary"
                      disabled={busy || !answerVisible}
                      onClick={() =>
                        void mutate(
                          () =>
                            api(`/mistakes/${reviewModal.id}/review`, "POST", {
                              outcome: "forgotten",
                              notes: reviewNote,
                            }),
                          "已安排明天再复习",
                          () => setReviewModal(null),
                        )
                      }
                    >
                      <RotateCcw size={17} />
                      还没掌握
                    </button>
                    <button
                      className="button"
                      disabled={busy || !answerVisible}
                      onClick={() =>
                        void mutate(
                          () =>
                            api(`/mistakes/${reviewModal.id}/review`, "POST", {
                              outcome: "remembered",
                              notes: reviewNote,
                            }),
                          "复习结果已记录",
                          () => setReviewModal(null),
                        )
                      }
                    >
                      <Check size={17} />
                      本次已记住
                    </button>
                  </div>
                  {!answerVisible && (
                    <p className="form-hint">查看答案后再确认复习结果。</p>
                  )}
                </>
              )}
            {reviewModal.review.due_date &&
              reviewModal.review.due_date > today && (
                <p className="notice small-text">
                  安排于 {reviewModal.review.due_date} 复习；到期后可记录结果。
                </p>
              )}
            {!reviewModal.review.due_date && (
              <button
                className="button secondary"
                disabled={busy}
                onClick={() =>
                  void mutate(
                    () =>
                      api(`/mistakes/${reviewModal.id}/restart-review`, "POST"),
                    "已重新加入复习，明天开始",
                    () => setReviewModal(null),
                  )
                }
              >
                <RotateCcw size={16} />
                重新加入复习
              </button>
            )}
            <label>
              手动调整复习日期
              <input
                type="date"
                value={reviewDate}
                onChange={(e) => setReviewDate(e.target.value)}
              />
            </label>
            <button
              className="button secondary"
              disabled={busy || !reviewDate}
              onClick={() =>
                void mutate(
                  () =>
                    api(`/review-schedule/mistake/${reviewModal.id}`, "PUT", {
                      due_date: reviewDate,
                    }),
                  "复习日期已调整",
                  () => setReviewModal(null),
                )
              }
            >
              保存错题复习日期
            </button>
            <div className="review-history">
              <h4>复习记录 · {reviewHistory.length} 次</h4>
              {reviewHistory.length ? (
                reviewHistory.map((event) => (
                  <div key={event.id}>
                    <span
                      className={`badge ${event.outcome === "remembered" ? "" : "warm"}`}
                    >
                      {event.outcome === "remembered"
                        ? "已记住"
                        : event.outcome === "assisted"
                          ? "提示后完成"
                          : "未掌握"}
                    </span>
                    <span>{dateTime(event.reviewed_at)}</span>
                    <small>
                      {event.next_due_date
                        ? `下次 ${event.next_due_date}`
                        : "本轮完成"}
                    </small>
                    {event.notes && <p>{event.notes}</p>}
                  </div>
                ))
              ) : (
                <p className="muted">尚无复习记录。</p>
              )}
            </div>
          </article>
        </Modal>
      )}
      <datalist id="subject-options">
        {(subjectList.data?.map((s) => s.name) || subjects).map((subject) => (
          <option key={subject} value={subject} />
        ))}
      </datalist>
      <datalist id="domain-options">
        {["基础工具", "高等数学", "线性代数", "概率统计", "自定义"].map((d) => (
          <option key={d} value={d} />
        ))}
      </datalist>
    </div>
  );
}

function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>
          {title}
          <span className="heading-dot">.</span>
        </h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}

function Stat({
  icon: Icon,
  label,
  value,
  note,
  suffix,
  accent,
}: {
  icon: typeof Clock3;
  label: string;
  value: string;
  note: string;
  suffix?: string;
  accent?: boolean;
}) {
  return (
    <section className={`stat-card ${accent ? "accent" : ""}`}>
      <div className="stat-label">
        {label}
        <Icon size={18} strokeWidth={1.6} />
      </div>
      <div className="stat-value">
        {value}
        {suffix && <small>{suffix}</small>}
      </div>
      <div className="stat-note">{note}</div>
    </section>
  );
}

function WeekChart({ stats }: { stats: Stats }) {
  const max = Math.max(3600, ...stats.daily.map((d) => d.seconds));
  return (
    <div
      className="week-chart"
      role="img"
      aria-label={`本周每日学习时长：${stats.daily.map((d) => `${d.date} ${duration(d.seconds)}`).join("，")}`}
    >
      <div className="chart-grid">
        <span>小时</span>
        <span>{Math.ceil(max / 3600)}</span>
        <span>0</span>
      </div>
      <div className="chart-bars">
        {stats.daily.map((d, i) => (
          <div
            key={d.date}
            className={`chart-day ${d.date === stats.date ? "today" : ""}`}
          >
            <div className="bar-track">
              <div
                className="bar"
                style={{
                  height: `${Math.max(d.seconds ? 3 : 0, (d.seconds / max) * 100)}%`,
                }}
                title={`${d.date} · ${duration(d.seconds)}`}
              />
            </div>
            <span>{["一", "二", "三", "四", "五", "六", "日"][i]}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
