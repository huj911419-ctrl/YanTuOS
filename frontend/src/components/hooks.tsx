import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { api } from "../api";

export function useResource<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const seq = useRef(0);
  const reload = useCallback(async () => {
    const n = ++seq.current;
    setLoading(true);
    setError("");
    try {
      const value = await api<T>(path);
      if (n === seq.current) setData(value);
    } catch (e) {
      if (n === seq.current)
        setError(String(e instanceof Error ? e.message : e));
    } finally {
      if (n === seq.current) setLoading(false);
    }
  }, [path]);
  useEffect(() => {
    void reload();
    const changed = () => {
      void reload();
    };
    window.addEventListener("yantu-data-changed", changed);
    return () => {
      seq.current++;
      window.removeEventListener("yantu-data-changed", changed);
    };
  }, [reload]);
  return { data, error, loading, reload };
}
export function useAction(after?: () => Promise<unknown> | void) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const locked = useRef(false);
  async function run(fn: () => Promise<unknown>, success = "已保存") {
    if (locked.current) return false;
    locked.current = true;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await fn();
      await after?.();
      setMessage(success);
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return false;
    } finally {
      locked.current = false;
      setBusy(false);
    }
  }
  return { error, busy, message, run };
}
export function Feedback({
  error,
  message,
  loading,
}: {
  error?: string;
  message?: string;
  loading?: boolean;
}) {
  return (
    <>
      {error && (
        <p role="alert" className="error-banner">
          {error}
        </p>
      )}
      {message && (
        <p role="status" className="success-banner">
          {message}
        </p>
      )}
      {loading && <p className="muted">正在读取…</p>}
    </>
  );
}
export function Section({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="panel v2-panel">
      <h2>{title}</h2>
      {children}
    </section>
  );
}
