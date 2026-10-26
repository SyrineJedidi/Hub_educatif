import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { taskStatuses } from "./types";
import type { Task, TaskStatus } from "./types";

// Shows a status change at once, then keeps the server's copy or rolls back.
export function useTaskStatus(source: unknown, onSaved: (task: Task) => void) {
  const [copies, setCopies] = useState<Record<string, Task>>({}),
    [saving, setSaving] = useState<Record<string, boolean>>({}),
    [error, setError] = useState<unknown>();
  const pending = useRef(new Set<string>());
  useEffect(() => {
    // Freshly loaded data already contains every confirmed change.
    setCopies((current) =>
      Object.fromEntries(
        Object.entries(current).filter(([id]) => pending.current.has(id)),
      ),
    );
  }, [source]);
  const view = (task: Task) => copies[task.id] || task;
  async function change(task: Task, status: TaskStatus) {
    const current = view(task);
    if (pending.current.has(task.id) || current.status === status) return;
    pending.current.add(task.id);
    const previous = copies[task.id];
    setCopies((all) => ({
      ...all,
      [task.id]: { ...current, status, status_label: taskStatuses[status] },
    }));
    setSaving((all) => ({ ...all, [task.id]: true }));
    setError(undefined);
    try {
      const saved = await api<Task>(
        `student/planning/tasks/${task.id}/`,
        "PATCH",
        { status },
      );
      setCopies((all) => ({ ...all, [task.id]: saved }));
      pending.current.delete(task.id);
      onSaved(saved);
    } catch (e) {
      setCopies((all) => {
        const next = { ...all };
        if (previous) next[task.id] = previous;
        else delete next[task.id];
        return next;
      });
      setError(e);
    } finally {
      pending.current.delete(task.id);
      setSaving((all) => {
        const next = { ...all };
        delete next[task.id];
        return next;
      });
    }
  }
  return { view, change, saving, error };
}
