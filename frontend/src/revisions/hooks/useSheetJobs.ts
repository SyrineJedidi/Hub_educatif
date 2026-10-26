import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../api/client";
import type { AIJob } from "../types";
const POLL_MS = 1500;
export const isActive = (job: AIJob) =>
  job.status === "QUEUED" || job.status === "RUNNING";
// Follows the background AI jobs of a sheet: polls the active ones and reports
// each job once when it reaches a final status.
export function useSheetJobs(
  sheetId: string | undefined,
  enabled: boolean,
  onFinished: (job: AIJob) => void,
) {
  const [jobs, setJobs] = useState<AIJob[]>([]);
  const finished = useRef(onFinished);
  finished.current = onFinished;
  useEffect(() => {
    if (!sheetId || !enabled) return;
    let alive = true;
    api<{ results: AIJob[] }>("sheets/" + sheetId + "/jobs/")
      .then((r) => alive && setJobs(r.results))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [sheetId, enabled]);
  const activeIds = jobs
    .filter(isActive)
    .map((j) => j.id)
    .join(",");
  useEffect(() => {
    if (!activeIds) return;
    let alive = true;
    const timer = window.setInterval(async () => {
      for (const id of activeIds.split(",")) {
        try {
          const job = await api<AIJob>("ai/jobs/" + id + "/");
          if (!alive) return;
          setJobs((list) => list.map((j) => (j.id === id ? job : j)));
          if (!isActive(job)) finished.current(job);
        } catch {
          // A transient network error: the next tick retries.
        }
      }
    }, POLL_MS);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [activeIds]);
  const track = useCallback((job: AIJob) => {
    setJobs((list) => [job, ...list.filter((j) => j.id !== job.id)]);
    if (!isActive(job)) finished.current(job);
  }, []);
  const replace = useCallback(
    (job: AIJob) =>
      setJobs((list) => list.map((j) => (j.id === job.id ? job : j))),
    [],
  );
  return { jobs, track, replace, running: jobs.filter(isActive) };
}
