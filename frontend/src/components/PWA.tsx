import { useEffect, useState, useRef } from "react";
export function PWAStatus() {
  const updateRequested = useRef(false);
  const [online, setOnline] = useState(navigator.onLine);
  const [waiting, setWaiting] = useState<ServiceWorker | null>(null);
  useEffect(() => {
    const check = () => setOnline(navigator.onLine);
    window.addEventListener("online", check);
    window.addEventListener("offline", check);
    let registration: ServiceWorkerRegistration | null = null;
    if (
      "serviceWorker" in navigator &&
      window.isSecureContext &&
      import.meta.env.PROD
    ) {
      void navigator.serviceWorker
        .register("/sw.js")
        .then((r) => {
          registration = r;
          if (r.waiting) setWaiting(r.waiting);
          r.addEventListener("updatefound", () => {
            const worker = r.installing;
            worker?.addEventListener("statechange", () => {
              if (
                worker.state === "installed" &&
                navigator.serviceWorker.controller
              )
                setWaiting(worker);
            });
          });
        })
        .catch(() => {});
    }
    const changed = () => {
      if (updateRequested.current) location.reload();
    };
    navigator.serviceWorker?.addEventListener("controllerchange", changed);
    return () => {
      window.removeEventListener("online", check);
      window.removeEventListener("offline", check);
      navigator.serviceWorker?.removeEventListener("controllerchange", changed);
      registration = null;
    };
  }, []);
  return (
    <>
      {!online && (
        <div className="offline-banner" role="status">
          设备当前离线。页面内容可能是旧数据；请恢复与 Ubuntu
          服务的连接后再保存。
        </div>
      )}
      {waiting && (
        <div className="pwa-update">
          新版本已就绪，请先保存表单。
          <button
            className="text-button"
            onClick={() => {
              updateRequested.current = true;
              waiting.postMessage("SKIP_WAITING");
            }}
          >
            更新并重新打开
          </button>
        </div>
      )}
    </>
  );
}
