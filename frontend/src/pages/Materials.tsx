import { useState } from "react";
import { api, downloadPath, uploadFile } from "../api";
import type { Knowledge } from "../types";
import { Modal } from "../components/core";
import { Feedback, Section, useAction, useResource } from "../components/hooks";

type Material = {
  id: number;
  title: string;
  category: string;
  notes: string;
  knowledge_id: number | null;
  file_id: string | null;
  extracted_text: string;
  extraction_status: string;
  filename: string | null;
};
export function MaterialsPage() {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const items = useResource<Material[]>("/materials");
  const knowledge = useResource<Knowledge[]>("/knowledge");
  const action = useAction(items.reload);
  const [edit, setEdit] = useState<Partial<Material> | null>(null);
  const [detail, setDetail] = useState<Material | null>(null);
  const extraction: Record<string, string> = {
    text: "已提取文本",
    partial_50_pages: "仅提取前 50 页",
    no_text_layer: "未检测到文本层；未启用 OCR",
    unavailable: "提取不可用或文件加密，原文件仍可下载",
    none: "个人笔记",
  };
  return (
    <>
      <h1>学习资料与笔记</h1>
      <p className="muted">
        文件保存在本机。支持 Markdown、TXT、PDF；扫描件需要自行识别后补充笔记。
      </p>
      <Feedback error={items.error || action.error} message={action.message} />
      <div className="filter-bar">
        <label>
          搜索资料
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="名称或笔记"
          />
        </label>
        <label>
          资料分类
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="">全部</option>
            {[...new Set(items.data?.map((m) => m.category))].map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <button
          className="button"
          onClick={() =>
            setEdit({
              title: "",
              category: "未分类",
              notes: "",
              knowledge_id: null,
              file_id: null,
            })
          }
        >
          添加资料或笔记
        </button>
      </div>
      {!items.data?.length && (
        <Section title="建立自己的资料库">
          <p className="muted">上传常用资料，或直接写下一篇学习笔记。</p>
        </Section>
      )}
      {items.data
        ?.filter(
          (m) =>
            (!category || m.category === category) &&
            (m.title + m.notes).includes(search),
        )
        .map((m) => (
          <Section title={m.title} key={m.id}>
            <p>
              {m.category} · {extraction[m.extraction_status]} ·{" "}
              {m.filename || "无附件"}
            </p>
            <p className="pre-wrap">{m.notes.slice(0, 300)}</p>
            <div className="settings-actions">
              <button className="text-button" onClick={() => setDetail(m)}>
                查看资料
              </button>
              <button className="text-button" onClick={() => setEdit(m)}>
                编辑资料
              </button>
              <button
                className="text-button"
                onClick={() =>
                  void action.run(
                    () =>
                      downloadPath(
                        `/materials/${m.id}/export`,
                        `material-${m.id}.md`,
                      ),
                    "笔记已导出",
                  )
                }
              >
                导出笔记
              </button>
              {m.file_id && (
                <button
                  className="text-button"
                  onClick={() =>
                    void action.run(
                      () =>
                        downloadPath(
                          `/files/${m.file_id}`,
                          m.filename || "material",
                        ),
                      "文件已下载",
                    )
                  }
                >
                  下载原文件
                </button>
              )}
              <button
                className="text-button danger"
                disabled={action.busy}
                onClick={() => {
                  if (
                    confirm(
                      "删除此资料记录和笔记？附件仍保留，可在设置中清理。",
                    )
                  )
                    void action.run(() => api(`/materials/${m.id}`, "DELETE"));
                }}
              >
                删除资料
              </button>
            </div>
          </Section>
        ))}
      {edit && (
        <Modal
          title="学习资料"
          close={() => setEdit(null)}
          error={action.error}
        >
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              const body = {
                title: edit.title,
                category: edit.category,
                notes: edit.notes,
                knowledge_id: edit.knowledge_id,
                file_id: edit.file_id,
              };
              if (
                await action.run(() =>
                  api(
                    edit.id ? `/materials/${edit.id}` : "/materials",
                    edit.id ? "PUT" : "POST",
                    body,
                  ),
                )
              )
                setEdit(null);
            }}
          >
            <label>
              资料名称
              <input
                required
                maxLength={200}
                value={edit.title}
                onChange={(e) => setEdit({ ...edit, title: e.target.value })}
              />
            </label>
            <label>
              分类
              <input
                required
                maxLength={40}
                value={edit.category}
                onChange={(e) => setEdit({ ...edit, category: e.target.value })}
              />
            </label>
            <label>
              上传资料文件
              <input
                type="file"
                accept=".md,.txt,.pdf"
                disabled={action.busy}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f)
                    void action.run(async () => {
                      const r = await uploadFile("/files?kind=material", f);
                      setEdit({
                        ...edit,
                        file_id: r.id,
                        filename: r.name,
                        title: edit.title || r.name,
                      });
                    }, "附件已上传，保存资料后完成关联");
                }}
              />
            </label>
            {edit.file_id && (
              <p>
                {edit.filename}
                <button
                  type="button"
                  className="text-button"
                  onClick={() =>
                    setEdit({ ...edit, file_id: null, filename: null })
                  }
                >
                  解除附件关联
                </button>
              </p>
            )}
            <label>
              关联知识点
              <select
                value={edit.knowledge_id || ""}
                onChange={(e) =>
                  setEdit({
                    ...edit,
                    knowledge_id: e.target.value
                      ? Number(e.target.value)
                      : null,
                  })
                }
              >
                <option value="">暂不关联</option>
                {knowledge.data?.map((k) => (
                  <option key={k.id} value={k.id}>
                    {k.title}
                  </option>
                ))}
              </select>
            </label>
            <label>
              个人笔记
              <textarea
                rows={6}
                maxLength={20000}
                value={edit.notes}
                onChange={(e) => setEdit({ ...edit, notes: e.target.value })}
              />
            </label>
            <button className="button" disabled={action.busy}>
              保存资料
            </button>
          </form>
        </Modal>
      )}
      {detail && (
        <Modal title={detail.title} close={() => setDetail(null)}>
          <p className="pre-wrap">{detail.notes}</p>
          <h3>提取文本 · {extraction[detail.extraction_status]}</h3>
          <pre className="pre-wrap">
            {detail.extracted_text || "暂无可提取文本。"}
          </pre>
        </Modal>
      )}
    </>
  );
}
