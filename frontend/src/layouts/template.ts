import { useLayoutEffect } from "react";
export type Template = "front" | "back";
declare global {
  interface Window {
    __templates: Record<Template, string[]>;
  }
}
/**
 * The public site (Eduleb) and the back-office (Soft UI Dashboard) are two separate
 * templates: each layout enables its own stylesheets — downloaded the first time the
 * area is visited — and disables the other ones.
 */
export function useTemplate(area: Template) {
  useLayoutEffect(() => {
    document.documentElement.dataset.template = area;
    for (const href of window.__templates?.[area] || []) {
      if (!document.querySelector(`link[data-template][href="${href}"]`)) {
        const link = document.createElement("link");
        link.rel = "stylesheet";
        link.href = href;
        link.dataset.template = area;
        // Templates stay before the application styles, which refine them.
        const templates = document.querySelectorAll("link[data-template]");
        const anchor = templates[templates.length - 1] || document.head.querySelector("script");
        if (anchor) anchor.after(link);
        else document.head.prepend(link);
      }
    }
    document
      .querySelectorAll<HTMLLinkElement>("link[data-template]")
      .forEach((link) => {
        link.disabled = link.dataset.template !== area;
      });
  }, [area]);
}
