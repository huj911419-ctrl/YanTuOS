import { useEffect, useState } from "react";
import { api, download, downloadPath, uploadFile } from "../api";
import { Feedback, Section, useAction, useResource } from "../components/hooks";

type Preferences = {
  exam_scope: string;
  review_intervals: number[];
  pomodoro_minutes: number;
  break_minutes: number;
  ai_base_url: string;
  ai_model: string;
  ai_timeout: number;
};
type Stage = {
  stage_id: string;
  warning: string;
  counts: Record<string, number>;
};
export function SettingsPage() {
  const prefs = useResource<Preferences>("/settings");
  const [form, setForm] = useState<Preferences | null>(null);
  const subjects = useResource<{ id: number; name: string }[]>("/subjects");
  const files =
    useResource<{ id: string; name: string; reference_count: number }[]>(
      "/files",
    );
  const ai = useResource<{
    available: boolean;
    key_configured: boolean;
    message: string;
  }>("/ai/status");
  const action = useAction(async () => {
    await prefs.reload();
    await subjects.reload();
    await files.reload();
    await ai.reload();
  });
  const [newSubject, setNewSubject] = useState("");
  const [stage, setStage] = useState<Stage | null>(null);
  const [confirmText, setConfirmText] = useState("");
  const [integrity, setIntegrity] = useState("");
  useEffect(() => {
    if (prefs.data) setForm(prefs.data);
  }, [prefs.data]);
  return (
    <>
      <h1>数据与设置</h1>
      <Feedback error={prefs.error || action.error} message={action.message} />
      <Section title="学习偏好">
        {form && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void action.run(() => api("/settings", "PUT", form));
            }}
          >
            <div className="settings-grid">
              <label>
                考研数学类别
                <select
                  value={form.exam_scope}
                  onChange={(e) =>
                    setForm({ ...form, exam_scope: e.target.value })
                  }
                >
                  <option value="unset">尚未确定</option>
                  <option value="math1">数学一</option>
                  <option value="math2">数学二</option>
                  <option value="math3">数学三</option>
                </select>
              </label>
              <label>
                番茄钟默认分钟
                <input
                  type="number"
                  min={1}
                  max={180}
                  value={form.pomodoro_minutes}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      pomodoro_minutes: Number(e.target.value),
                    })
                  }
                />
              </label>
              <label>
                默认休息分钟
                <input
                  type="number"
                  min={1}
                  max={60}
                  value={form.break_minutes}
                  onChange={(e) =>
                    setForm({ ...form, break_minutes: Number(e.target.value) })
                  }
                />
              </label>
            </div>
            <fieldset>
              <legend>五次复习的间隔天数（严格递增）</legend>
              <div className="interval-inputs">
                {form.review_intervals.map((n, i) => (
                  <label key={i}>
                    阶段 {i + 1}
                    <input
                      required
                      type="number"
                      min={1}
                      max={365}
                      value={n}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          review_intervals: form.review_intervals.map((v, j) =>
                            i === j ? Number(e.target.value) : v,
                          ),
                        })
                      }
                    />
                  </label>
                ))}
              </div>
            </fieldset>
            <p className="form-hint">
              修改间隔影响后续复习结果生成的日期，已有安排不自动改写。知识点的考试范围由你维护，系统不伪造官方大纲。
            </p>
            <h3>AI 兼容服务</h3>
            <p>{ai.data?.message}</p>
            <label>
              服务 Base URL
              <input
                type="url"
                value={form.ai_base_url}
                onChange={(e) =>
                  setForm({ ...form, ai_base_url: e.target.value })
                }
                placeholder="https://服务地址/v1"
              />
            </label>
            <label>
              模型名称
              <input
                maxLength={200}
                value={form.ai_model}
                onChange={(e) => setForm({ ...form, ai_model: e.target.value })}
                placeholder="由服务商提供的模型标识"
              />
            </label>
            <label>
              请求超时（秒）
              <input
                type="number"
                min={5}
                max={120}
                value={form.ai_timeout}
                onChange={(e) =>
                  setForm({ ...form, ai_timeout: Number(e.target.value) })
                }
              />
            </label>
            <p className="form-hint">
              API Key {ai.data?.key_configured ? "已在服务端配置" : "尚未配置"}
              。在本机 .env 中设置 YANTU_AI_API_KEY
              后重启服务；密钥不在此页面填写，也不包含在数据导出中。环境变量中的地址和模型优先于页面设置。本地无认证模型可将密钥设为
              local。
            </p>
            <button className="button" disabled={action.busy}>
              保存设置
            </button>
          </form>
        )}
      </Section>
      <Section title="科目管理">
        <form
          className="filter-bar"
          onSubmit={(e) => {
            e.preventDefault();
            void action.run(async () => {
              await api("/subjects", "POST", { name: newSubject });
              setNewSubject("");
            });
          }}
        >
          <label>
            新科目
            <input
              required
              maxLength={40}
              value={newSubject}
              onChange={(e) => setNewSubject(e.target.value)}
            />
          </label>
          <button className="button secondary" disabled={action.busy}>
            添加科目
          </button>
        </form>
        <div className="file-chips">
          {subjects.data?.map((s) => (
            <span className="badge" key={s.id}>
              {s.name}
              <button
                className="text-button danger"
                aria-label={`删除科目：${s.name}`}
                disabled={action.busy}
                onClick={() => {
                  if (confirm("删除此科目？已有记录的科目会拒绝删除。"))
                    void action.run(() => api(`/subjects/${s.id}`, "DELETE"));
                }}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      </Section>
      <Section title="导出与备份">
        <p>
          完整 ZIP 包含数据库、题目图片、资料和校验清单。JSON 便于阅读；SQLite
          快照与 JSON 都不包含附件内容。
        </p>
        <div className="settings-actions">
          <button
            className="button"
            disabled={action.busy}
            onClick={() =>
              void action.run(
                () => downloadPath("/data/archive", "yantu-full-backup.zip"),
                "完整备份已下载",
              )
            }
          >
            下载完整备份
          </button>
          <button
            className="button secondary"
            disabled={action.busy}
            onClick={() =>
              void action.run(() => download("export"), "JSON 已下载")
            }
          >
            导出 JSON
          </button>
          <button
            className="button secondary"
            disabled={action.busy}
            onClick={() =>
              void action.run(() => download("backup"), "数据库快照已下载")
            }
          >
            下载数据库快照
          </button>
          <button
            className="button secondary"
            disabled={action.busy}
            onClick={() =>
              void action.run(async () => {
                const result = await api<{
                  integrity: string;
                  attachments: string;
                }>("/data/integrity");
                setIntegrity(
                  `数据库 ${result.integrity}，附件 ${result.attachments}`,
                );
              }, "校验完成")
            }
          >
            检查数据完整性
          </button>
        </div>
        <p>{integrity}</p>
      </Section>
      <Section title="导入与恢复">
        <p>
          先在隔离目录校验并预览数量，确认后才替换当前数据。恢复前会自动保存完整备份。含附件的数据请使用
          ZIP；不合并或静默覆盖现有记录。
        </p>
        <label>
          选择备份或 JSON
          <input
            type="file"
            accept=".zip,.json,.sqlite3"
            disabled={action.busy}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) {
                setStage(null);
                setConfirmText("");
                void action.run(
                  async () =>
                    setStage(await uploadFile("/data/restore/preview", file)),
                  "隔离校验通过，请核对数据量",
                );
              }
              e.target.value = "";
            }}
          />
        </label>
        {stage && (
          <>
            <p className="connection-note">{stage.warning}</p>
            <p>
              任务 {stage.counts.tasks} · 学习记录 {stage.counts.study_sessions}{" "}
              · 知识点 {stage.counts.knowledge_points} · 错题{" "}
              {stage.counts.mistakes} · 附件 {stage.counts.files}
            </p>
            <label>
              确认文字
              <input
                value={confirmText}
                onChange={(e) => setConfirmText(e.target.value)}
                placeholder="覆盖当前学习数据"
              />
            </label>
            <button
              className="button"
              disabled={action.busy || confirmText !== "覆盖当前学习数据"}
              onClick={() =>
                void action.run(async () => {
                  const result = await api<{ rollback_backup: string }>(
                    "/data/restore/confirm",
                    "POST",
                    { stage_id: stage.stage_id, confirmation: confirmText },
                  );
                  setStage(null);
                  setConfirmText("");
                  setIntegrity("恢复完成。回滚备份：" + result.rollback_backup);
                }, "数据已恢复，请重新打开其他页面")
              }
            >
              确认恢复数据
            </button>
          </>
        )}
      </Section>
      <Section title="附件维护">
        <p className="form-hint">
          取消上传表单或删除资料后，附件仍保留。这里只允许删除未关联文件；此操作需要单独确认。
        </p>
        {!files.data?.some((f) => f.reference_count === 0) && (
          <p className="muted">没有未关联附件。</p>
        )}
        {files.data
          ?.filter((f) => f.reference_count === 0)
          .map((f) => (
            <div className="v2-row" key={f.id}>
              <span>{f.name}</span>
              <button
                className="text-button danger"
                disabled={action.busy}
                onClick={() => {
                  if (confirm(`永久删除未关联附件「${f.name}」？`))
                    void action.run(() => api(`/files/${f.id}`, "DELETE"));
                }}
              >
                删除未关联附件
              </button>
            </div>
          ))}
      </Section>
      <Section title="手机、离线与访问安全">
        <p>
          Ubuntu 本机默认地址为
          http://127.0.0.1:8000。手机局域网使用需要显式配置访问令牌和受信任的
          HTTPS；详见项目 README。
        </p>
        <p>
          iPhone：Safari 分享菜单 →
          添加到主屏幕。离线只提供说明页面；服务不可达时不能写入学习数据。没有模型
          API 不影响本地基础功能。
        </p>
        <p>
          北京时间 · 周一开始每周 · 2027 年 12 月考试目标，具体日期待官方公布。
        </p>
        <button
          className="button secondary"
          onClick={() =>
            void action.run(async () => {
              await api("/auth/logout", "POST");
              sessionStorage.removeItem("yantu-access-token");
              location.reload();
            }, "已退出")
          }
        >
          退出访问会话
        </button>
      </Section>
    </>
  );
}
