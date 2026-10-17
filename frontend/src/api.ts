export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

function headers(): Record<string, string> {
  const token = sessionStorage.getItem("yantu-access-token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function check(response: Response) {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = Array.isArray(body.detail)
      ? "输入内容不符合要求，请检查必填项、日期与长度。"
      : body.detail;
    throw new ApiError(
      detail || `请求失败（${response.status}）`,
      response.status,
    );
  }
  return response;
}

export async function api<T>(
  path: string,
  method = "GET",
  data?: unknown,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      signal: AbortSignal.timeout(path === "/ai/chat" ? 130000 : 30000),
      headers: {
        ...headers(),
        ...(data !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      body: data !== undefined ? JSON.stringify(data) : undefined,
    });
  } catch {
    throw new Error("无法连接研途服务，请确认服务正在运行，然后重试。");
  }
  await check(response);
  if (method !== "GET" && !["/ai/preview", "/ai/verify-math"].includes(path))
    window.dispatchEvent(new Event("yantu-data-changed"));
  return response.status === 204 ? (undefined as T) : response.json();
}

export async function download(kind: "export" | "backup") {
  const response = await check(
    await fetch(`/api/data/${kind}`, { headers: headers() }),
  );
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `yantu-${new Date().toISOString().slice(0, 10)}.${kind === "export" ? "json" : "sqlite3"}`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function uploadFile(path: string, file: File) {
  const body = new FormData();
  body.append("file", file);
  const response = await check(
    await fetch(`/api${path}`, { method: "POST", headers: headers(), body }),
  );
  return response.json();
}
export async function downloadPath(path: string, filename: string) {
  const response = await check(
    await fetch(`/api${path}`, { headers: headers() }),
  );
  const url = URL.createObjectURL(await response.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export async function fileBlob(id: string) {
  return (
    await check(
      await fetch(`/api/files/${id}?inline=true`, { headers: headers() }),
    )
  ).blob();
}
