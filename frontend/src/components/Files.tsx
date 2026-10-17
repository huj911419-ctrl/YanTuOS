import { useEffect, useState } from "react";
import { downloadPath, fileBlob, uploadFile } from "../api";
import { Feedback, useAction } from "./hooks";

export function FileImages({ ids }: { ids: string[] }) {
  const [urls, setUrls] = useState<string[]>([]);
  const [error, setError] = useState("");
  const key = ids.join(",");
  useEffect(() => {
    let gone = false;
    const made: string[] = [];
    setError("");
    Promise.all(
      ids.map(async (id) => {
        const u = URL.createObjectURL(await fileBlob(id));
        made.push(u);
        return u;
      }),
    )
      .then((values) => {
        if (!gone) setUrls(values);
        else values.forEach(URL.revokeObjectURL);
      })
      .catch(() => {
        if (!gone) setError("图片读取失败，请检查附件完整性。");
      });
    return () => {
      gone = true;
      made.forEach(URL.revokeObjectURL);
    };
  }, [key]);
  return (
    <>
      <Feedback error={error} />
      <div className="file-chips">
        {urls.map((u, i) => (
          <a key={u} href={u} target="_blank" rel="noreferrer">
            <img src={u} alt={`题目图片 ${i + 1}`} />
          </a>
        ))}
      </div>
    </>
  );
}
export function ImagePicker({
  ids,
  onChange,
  onBusy,
}: {
  ids: string[];
  onChange: (ids: string[]) => void;
  onBusy: (busy: boolean) => void;
}) {
  const a = useAction();
  useEffect(() => onBusy(a.busy), [a.busy, onBusy]);
  return (
    <fieldset>
      <legend>题目图片（PNG / JPEG / WebP）</legend>
      <input
        aria-label="上传题目图片"
        type="file"
        accept="image/png,image/jpeg,image/webp"
        disabled={a.busy || ids.length >= 10}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f)
            void a.run(async () => {
              const v = await uploadFile("/files?kind=image", f);
              onChange([...ids, v.id]);
            }, "图片已上传，保存错题后完成关联");
          e.target.value = "";
        }}
      />
      <Feedback {...a} />
      <FileImages ids={ids} />
      {ids.map((id, i) => (
        <button
          type="button"
          className="text-button"
          key={id}
          onClick={() => onChange(ids.filter((x) => x !== id))}
        >
          移除图片 {i + 1}
        </button>
      ))}
      <p className="form-hint">
        本地保存，不自动发送给 AI。取消表单后的未关联附件可在设置中清理。
      </p>
    </fieldset>
  );
}
