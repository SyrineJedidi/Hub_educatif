import { t } from "./i18n";
import { useEffect } from "react";
import { flushSync } from "react-dom";
import { useBlocker } from "react-router-dom";
import { Modal } from "../components/UI";
export default function UnsavedChanges({
  dirty,
  ignore,
}: {
  dirty: boolean;
  ignore?: { current: boolean };
}) {
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      dirty &&
      !ignore?.current &&
      (currentLocation.pathname !== nextLocation.pathname ||
        currentLocation.search !== nextLocation.search),
  );
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (dirty && !ignore?.current) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty, ignore]);
  function stay() {
    if (blocker.state === "blocked") {
      const reset = blocker.reset;
      flushSync(() => reset());
    }
  }
  return blocker.state === "blocked" ? (
    <Modal title={t("Quitter sans enregistrer ?")} onClose={stay}>
      <p className="intro">
        {t(
          "Vos modifications n’ont pas encore été enregistrées. Voulez-vous les abandonner ? ",
        )}
      </p>
      <div className="actions">
        <button className="btn_one" onClick={stay}>
          {t("Continuer la saisie ")}
        </button>
        <button className="text-button" onClick={() => blocker.proceed()}>
          {t("Abandonner les modifications ")}
        </button>
      </div>
    </Modal>
  ) : null;
}
