import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useResource } from "../hooks/useResource";
import { Alert, Field, Form, Loading, Modal, Select } from "../components/UI";
import { usePlanningContext } from "./usePlanningContext";
import { LiveStatus, LoadFailure, useAnnouncer } from "./PlanningWidgets";
import { duration, plural } from "./format";
import { weekdays } from "./types";
import type { Availability, Slot } from "./types";
import {
  changes,
  minutesOf,
  usePlanningForm,
  validateSlot,
} from "./validation";
import "./planning.css";
const MAX_SLOTS = 21;
type Dialog = { kind: "slot"; slot?: Slot } | { kind: "delete"; slot: Slot };
const slotLabel = (slot: Slot) =>
  `${weekdays[slot.weekday] || slot.weekday_label} de ${slot.start_time} à ${slot.end_time}`;
export default function AvailabilityPage() {
  const { apiBase, base } = usePlanningContext();
  const { data, error, loading, reload } = useResource<Availability>(
    apiBase + "availability/",
  );
  const [dialog, setDialog] = useState<Dialog | null>(null);
  const { message, announce } = useAnnouncer();
  const add = useRef<HTMLButtonElement>(null),
    total = useRef<HTMLHeadingElement>(null),
    focusAfterClose = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (!dialog && focusAfterClose.current) {
      focusAfterClose.current.focus();
      focusAfterClose.current = null;
    }
  }, [dialog]);
  const slots = data?.results || [];
  const full = slots.length >= MAX_SLOTS;
  function saved(text: string, focus?: HTMLElement | null) {
    focusAfterClose.current = focus || null;
    setDialog(null);
    announce(text);
    reload();
  }
  return (
    <div className="planning-module">
      <div className="page-heading">
        <div>
          <p className="eyebrow">PLANIFICATION ET COACHING</p>
          <h1>Mes disponibilités</h1>
          <p>
            Indiquez vos créneaux de révision habituels : les plannings ne
            proposent des tâches que pendant ces créneaux (heure de Tunis).
          </p>
        </div>
        <Link className="text-button" to={base}>
          Mon planning de révision ↗
        </Link>
      </div>
      <LiveStatus message={message} />
      {loading && !data ? (
        <Loading />
      ) : !data ? (
        <LoadFailure error={error} onRetry={reload} />
      ) : (
        <>
          <Alert error={error} />
          <section
            className="panel planning-week-summary"
            aria-labelledby="planning-week-total"
          >
            <div>
              <h2 id="planning-week-total" ref={total} tabIndex={-1}>
                Total de la semaine : {duration(data.weekly_minutes)}
              </h2>
              <p className="planning-muted">
                {plural(slots.length, "créneau", "créneaux")} sur {MAX_SLOTS}{" "}
                possibles · par quarts d’heure, de 30 min à 6 h, sans
                chevauchement.
              </p>
            </div>
            {full ? (
              <p className="notice">
                Vous avez atteint la limite de {MAX_SLOTS} créneaux. Supprimez
                ou modifiez un créneau existant.
              </p>
            ) : (
              <button
                ref={add}
                className="btn_one"
                onClick={() => setDialog({ kind: "slot" })}
              >
                Ajouter un créneau +
              </button>
            )}
          </section>
          <div className="planning-week">
            {weekdays.map((weekday, index) => {
              const daySlots = slots
                .filter((slot) => slot.weekday === index)
                .sort(
                  (a, b) => minutesOf(a.start_time) - minutesOf(b.start_time),
                );
              return (
                <section
                  className="planning-weekday"
                  key={weekday}
                  aria-labelledby={"planning-weekday-" + index}
                >
                  <h2 id={"planning-weekday-" + index}>{weekday}</h2>
                  {daySlots.length ? (
                    <ul className="planning-slots">
                      {daySlots.map((slot) => (
                        <li key={slot.id}>
                          <span>
                            <strong>
                              {slot.start_time} – {slot.end_time}
                            </strong>
                            <small>{duration(slot.minutes)}</small>
                          </span>
                          <span className="planning-row-actions">
                            <button
                              className="text-button"
                              onClick={() => setDialog({ kind: "slot", slot })}
                            >
                              Modifier
                              <span className="visually-hidden">
                                {" "}
                                le créneau du {slotLabel(slot).toLowerCase()}
                              </span>
                            </button>
                            <button
                              className="text-button"
                              onClick={() =>
                                setDialog({ kind: "delete", slot })
                              }
                            >
                              Supprimer
                              <span className="visually-hidden">
                                {" "}
                                le créneau du {slotLabel(slot).toLowerCase()}
                              </span>
                            </button>
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="planning-muted">Aucun créneau.</p>
                  )}
                </section>
              );
            })}
          </div>
        </>
      )}
      {dialog?.kind === "slot" && (
        <Modal
          title={dialog.slot ? "Modifier le créneau" : "Ajouter un créneau"}
          onClose={() => setDialog(null)}
        >
          <SlotForm
            slot={dialog.slot}
            others={slots.filter((slot) => slot.id !== dialog.slot?.id)}
            onSaved={(label) =>
              saved(
                dialog.slot
                  ? `Créneau du ${label} enregistré.`
                  : `Créneau du ${label} ajouté.`,
              )
            }
          />
        </Modal>
      )}
      {dialog?.kind === "delete" && (
        <Modal title="Supprimer ce créneau ?" onClose={() => setDialog(null)}>
          <p className="intro">
            Le créneau du {slotLabel(dialog.slot).toLowerCase()} ne sera plus
            proposé dans vos prochains plannings. Les plannings existants ne
            changent pas.
          </p>
          <Form
            label="Confirmer la suppression"
            onSubmit={() =>
              api(apiBase + "availability/" + dialog.slot.id + "/", "DELETE")
            }
            onSuccess={() =>
              saved(
                `Créneau du ${slotLabel(dialog.slot).toLowerCase()} supprimé.`,
                add.current || total.current,
              )
            }
          />
        </Modal>
      )}
    </div>
  );
}
function SlotForm({
  slot,
  others,
  onSaved,
}: {
  slot?: Slot;
  others: Slot[];
  onSaved: (label: string) => void;
}) {
  const { apiBase } = usePlanningContext();
  const form = usePlanningForm({
    weekday: String(slot?.weekday ?? 0),
    start_time: slot?.start_time || "18:00",
    end_time: slot?.end_time || "20:00",
  });
  const { values, errors, change } = form;
  const body = (v: typeof values) => ({
    weekday: Number(v.weekday),
    start_time: v.start_time.slice(0, 5),
    end_time: v.end_time.slice(0, 5),
  });
  return (
    <Form
      formRef={form.formRef}
      noValidate
      clearErrorOnChange
      label={slot ? "Enregistrer le créneau" : "Ajouter le créneau"}
      onSubmit={() =>
        form.submit(validateSlot(values, others), async () => {
          if (!slot)
            return api(apiBase + "availability/", "POST", body(values));
          const changed = changes(body(values), body(form.initial));
          if (Object.keys(changed).length)
            return api(
              apiBase + "availability/" + slot.id + "/",
              "PATCH",
              changed,
            );
        })
      }
      onSuccess={() =>
        onSaved(
          `${weekdays[Number(values.weekday)].toLowerCase()} de ${values.start_time.slice(0, 5)} à ${values.end_time.slice(0, 5)}`,
        )
      }
    >
      <Select
        label="Jour"
        name="weekday"
        value={values.weekday}
        onChange={change("weekday")}
        required
        error={errors.weekday}
      >
        {weekdays.map((weekday, index) => (
          <option key={weekday} value={index}>
            {weekday}
          </option>
        ))}
      </Select>
      <div className="form-grid">
        <Field
          label="Début"
          name="start_time"
          type="time"
          step={900}
          value={values.start_time}
          onChange={change("start_time")}
          required
          error={errors.start_time}
        />
        <Field
          label="Fin"
          name="end_time"
          type="time"
          step={900}
          value={values.end_time}
          onChange={change("end_time")}
          required
          error={errors.end_time}
        />
      </div>
      <p className="field-help">
        Par quarts d’heure (00, 15, 30 ou 45), de 30 min à 6 h, sans chevaucher
        un autre créneau du même jour.
      </p>
    </Form>
  );
}
