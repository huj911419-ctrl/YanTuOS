import { useState } from "react";
import { api } from "../api";
import type { Knowledge, Mistake } from "../types";
import { Feedback, Section, useAction, useResource } from "../components/hooks";

type Status = {
  available: boolean;
  message: string;
  base_url: string;
  model: string;
  key_configured: boolean;
};
type Run = {
  id: number;
  conversation_id: string;
  purpose: string;
  prompt: string;
  answer: string;
  created_at: string;
};
type Preview = {
  digest: string;
  target: string;
  model: string;
  messages: { role: string; content: string }[];
  note: string;
};
export function AIPage() {
  const status = useResource<Status>("/ai/status");
  const knowledge = useResource<Knowledge[]>("/knowledge");
  const mistakes = useResource<Mistake[]>("/mistakes");
  const history = useResource<Run[]>("/ai/history");
  const action = useAction(history.reload);
  const [prompt, setPrompt] = useState("");
  const [purpose, setPurpose] = useState("chat");
  const [kids, setKids] = useState<number[]>([]);
  const [mids, setMids] = useState<number[]>([]);
  const [summary, setSummary] = useState(false);
  const [cid, setCid] = useState<string | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [math, setMath] = useState("");
  const [mathResult, setMathResult] = useState("");
  const body = {
    prompt,
    purpose,
    knowledge_ids: kids,
    mistake_ids: mids,
    include_summary: summary,
    conversation_id: cid,
  };
  const invalidate = () => {
    setPreview(null);
    setConfirmed(false);
  };
  return (
    <>
      <h1>AI 学习助手</h1>
      <Feedback error={status.error || action.error} message={action.message} />
      <p className={status.data?.available ? "notice" : "connection-note"}>
        {status.data?.message || "正在检查配置…"}
      </p>
      <Section title="提出一个具体的问题">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void action.run(async () => {
              setPreview(await api<Preview>("/ai/preview", "POST", body));
              setConfirmed(false);
            }, "已生成发送预览，尚未调用模型");
          }}
        >
          <label>
            助手任务
            <select
              value={purpose}
              onChange={(e) => {
                setPurpose(e.target.value);
                invalidate();
              }}
            >
              {Object.entries({
                chat: "对话答疑",
                concept: "数学与知识概念讲解",
                solution: "题目步骤解析",
                mistake: "错题原因与知识关联建议",
                practice: "生成类似练习",
                daily: "今日学习建议",
                weekly: "每周计划建议",
                summary: "阶段总结",
              }).map(([id, label]) => (
                <option key={id} value={id}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            你的问题
            <textarea
              required
              rows={5}
              maxLength={12000}
              value={prompt}
              onChange={(e) => {
                setPrompt(e.target.value);
                invalidate();
              }}
              placeholder="描述题目、你尝试的步骤，以及具体卡在哪里"
            />
          </label>
          <details>
            <summary>选择本次授权的学习数据（默认不附带）</summary>
            <fieldset>
              <legend>知识点</legend>
              <div className="knowledge-picker">
                {knowledge.data?.map((k) => (
                  <label className="check-option" key={k.id}>
                    <input
                      type="checkbox"
                      checked={kids.includes(k.id)}
                      onChange={(e) => {
                        setKids(
                          e.target.checked
                            ? [...kids, k.id]
                            : kids.filter((x) => x !== k.id),
                        );
                        invalidate();
                      }}
                    />
                    {k.title}
                  </label>
                ))}
              </div>
            </fieldset>
            <fieldset>
              <legend>错题文本</legend>
              <div className="knowledge-picker">
                {mistakes.data?.map((m) => (
                  <label className="check-option" key={m.id}>
                    <input
                      type="checkbox"
                      checked={mids.includes(m.id)}
                      onChange={(e) => {
                        setMids(
                          e.target.checked
                            ? [...mids, m.id]
                            : mids.filter((x) => x !== m.id),
                        );
                        invalidate();
                      }}
                    />
                    {m.title}
                  </label>
                ))}
              </div>
            </fieldset>
            <label className="check-option">
              <input
                type="checkbox"
                checked={summary}
                onChange={(e) => {
                  setSummary(e.target.checked);
                  invalidate();
                }}
              />
              附带近 28 天统计和薄弱点摘要
            </label>
          </details>
          <p className="form-hint">
            最多选择 10 个知识点和 10 道错题；继续对话会附带该对话最近 6
            轮文本。题目图片与资料文件不会自动发送。
          </p>
          <button
            className="button"
            disabled={action.busy || !status.data?.available}
          >
            预览发送内容
          </button>
          {cid && (
            <button
              type="button"
              className="button secondary"
              onClick={() => {
                setCid(null);
                invalidate();
              }}
            >
              开始新对话
            </button>
          )}
        </form>
        {preview && (
          <>
            <h3>确认本次发送</h3>
            <p>
              服务：{preview.target} · 模型：{preview.model}
            </p>
            <p>{preview.note}</p>
            <div className="scope-preview">
              {preview.messages.map((m, i) => (
                <div key={i}>
                  <strong>{m.role}</strong>
                  <pre className="pre-wrap">{m.content}</pre>
                </div>
              ))}
            </div>
            <label className="check-option">
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(e) => setConfirmed(e.target.checked)}
              />
              我授权将以上消息发送到该服务，并了解可能产生费用
            </label>
            <button
              className="button"
              disabled={action.busy || !confirmed}
              onClick={() =>
                void action.run(async () => {
                  const r = await api<{ conversation_id: string }>(
                    "/ai/chat",
                    "POST",
                    { ...body, consent: true, approved_digest: preview.digest },
                  );
                  setCid(r.conversation_id);
                  setPrompt("");
                  invalidate();
                }, "模型回复已保存")
              }
            >
              {action.busy ? "正在请求模型…" : "确认发送给模型"}
            </button>
          </>
        )}
      </Section>
      <Section title="本地数值核对">
        <p className="form-hint">
          支持数字、括号和 + - * / **，例如
          (2+3)*4=20。不执行模型代码，不证明一般数学结论。
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void action.run(async () => {
              const r = await api<{
                value: number;
                equal: boolean | null;
                note: string;
              }>("/ai/verify-math", "POST", { expression: math });
              setMathResult(
                `计算值 ${r.value}；${r.equal === null ? "未比较等式" : r.equal ? "两侧数值一致" : "两侧数值不一致"}。${r.note}`,
              );
            }, "本地核对完成");
          }}
        >
          <label>
            待核对算式
            <input
              required
              value={math}
              maxLength={200}
              onChange={(e) => setMath(e.target.value)}
            />
          </label>
          <button className="button secondary" disabled={action.busy}>
            核对算式
          </button>
        </form>
        <p>{mathResult}</p>
      </Section>
      <Section title="对话与分析记录">
        <Feedback error={history.error} />
        {!history.data?.length && (
          <p className="muted">
            尚无模型分析记录。配置真实服务后，成功的回复会保存在本地。
          </p>
        )}
        {history.data
          ?.filter((r) => !cid || r.conversation_id === cid)
          .slice()
          .reverse()
          .map((r) => (
            <article className="chat-turn" key={r.id}>
              <strong>{r.prompt}</strong>
              <p className="chat-answer">{r.answer}</p>
              <p className="form-hint">
                真实模型回复 · 数学结论尚未自动证明 · {r.created_at}
              </p>
              <button
                className="text-button"
                onClick={() => {
                  setCid(r.conversation_id);
                  invalidate();
                }}
              >
                继续此对话
              </button>
              <button
                className="text-button danger"
                disabled={action.busy}
                onClick={() => {
                  if (confirm("删除此对话的全部本地记录？"))
                    void action.run(async () => {
                      await api(`/ai/history/${r.conversation_id}`, "DELETE");
                      setCid(null);
                      invalidate();
                    });
                }}
              >
                删除对话
              </button>
            </article>
          ))}
      </Section>
    </>
  );
}
