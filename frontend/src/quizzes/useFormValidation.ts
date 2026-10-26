import { t } from "./i18n";
import { useEffect, useRef, useState } from "react";
import type { FocusEvent } from "react";
import { ApiError } from "../api/client";
import type { FieldErrors } from "./validation";

export function useFormValidation(
  validate: () => FieldErrors,
  inputs: Record<string, unknown>,
) {
  const [errors, setErrors] = useState<FieldErrors>({});
  const formRef = useRef<HTMLFormElement>(null);
  const checked = useRef(new Set<string>());
  const server = useRef<FieldErrors>({});
  const previousInputs = useRef(inputs);
  function currentErrors() {
    return {
      ...Object.fromEntries(
        Object.entries(validate()).filter(([key]) => checked.current.has(key)),
      ),
      ...server.current,
    };
  }
  useEffect(() => {
    for (const key of Object.keys(server.current)) {
      if (previousInputs.current[key] !== inputs[key])
        delete server.current[key];
    }
    previousInputs.current = inputs;
    const next = currentErrors();
    if (
      Object.keys(next).length !== Object.keys(errors).length ||
      Object.entries(next).some(([key, value]) => errors[key] !== value)
    )
      setErrors(next);
  });
  function focusError() {
    requestAnimationFrame(() =>
      formRef.current
        ?.querySelector<HTMLElement>('[aria-invalid="true"]')
        ?.focus(),
    );
  }
  function onBlur(event: FocusEvent<HTMLFormElement>) {
    // Valider au submit évite de déplacer le bouton entre l’appui et le clic.
    if (
      event.relatedTarget instanceof HTMLElement &&
      event.relatedTarget.closest("button, a")
    )
      return;
    const field = event.target.getAttribute("name");
    if (!field) return;
    checked.current.add(field);
    setErrors(currentErrors());
  }
  function check() {
    checked.current = new Set(Object.keys(inputs));
    server.current = {};
    const issues = validate();
    setErrors(issues);
    if (Object.keys(issues).length) {
      focusError();
      throw new ApiError(
        400,
        t("Veuillez corriger les champs indiqués."),
        issues,
      );
    }
  }
  function serverErrors(error: unknown) {
    if (!(error instanceof ApiError)) return;
    server.current = Object.fromEntries(
      Object.entries(error.fields).map(([field, value]) => [
        field,
        Array.isArray(value) ? value.join(" ") : value,
      ]),
    );
    setErrors(currentErrors());
    focusError();
  }
  return {
    errors,
    check,
    serverErrors,
    formProps: { formRef, noValidate: true, onBlur, clearErrorOnChange: true },
  };
}
