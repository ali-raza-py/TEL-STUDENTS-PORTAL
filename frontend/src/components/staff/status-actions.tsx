"use client";

import * as React from "react";
import { ArrowRight, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogClose, DialogTrigger } from "@/components/ui/dialog";
import { Field, Textarea } from "@/components/ui/input";
import { cn } from "@/lib/utils";

/**
 * Lifecycle controls for a staff register.
 *
 * Only the moves the server considers legal from the current state are offered,
 * so a user is never handed a change that will bounce. This is a convenience
 * layer only: the server re-checks the transition and rejects anything invalid.
 *
 * Pass `noteLabel` for records whose workflow wants an explanation recorded
 * alongside the state change, and list irreversible states in `confirmTargets`.
 */
export function TransitionActions<TStatus extends string>({
  current,
  transitions,
  labels,
  onTransition,
  busy = false,
  entityLabel,
  noteLabel,
  noteRequired = false,
  confirmTargets = [],
  emptyHint = "No further changes available",
}: {
  current: TStatus;
  transitions: Record<TStatus, TStatus[]>;
  labels: Record<TStatus, string>;
  onTransition: (target: TStatus, note: string) => void;
  busy?: boolean;
  entityLabel: string;
  noteLabel?: string;
  noteRequired?: boolean;
  confirmTargets?: TStatus[];
  emptyHint?: string;
}) {
  const targets = transitions[current] ?? [];

  if (targets.length === 0) {
    return <span className="text-caption text-ink-faint">{emptyHint}</span>;
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {targets.map((target) => (
        <TransitionButton
          key={target}
          target={target}
          label={labels[target] ?? target}
          entityLabel={entityLabel}
          noteLabel={noteLabel}
          noteRequired={noteRequired}
          confirm={confirmTargets.includes(target)}
          onConfirm={onTransition}
          disabled={busy}
        />
      ))}
    </div>
  );
}

function TransitionButton<TStatus extends string>({
  target,
  label,
  entityLabel,
  noteLabel,
  noteRequired,
  confirm,
  onConfirm,
  disabled,
}: {
  target: TStatus;
  label: string;
  entityLabel: string;
  noteLabel?: string;
  noteRequired: boolean;
  confirm: boolean;
  onConfirm: (target: TStatus, note: string) => void;
  disabled: boolean;
}) {
  const [note, setNote] = React.useState("");

  const fire = () => {
    onConfirm(target, note);
    setNote("");
  };

  // A plain move needs no ceremony; a noted or irreversible one is confirmed.
  if (!noteLabel && !confirm) {
    return (
      <Button size="sm" variant="secondary" type="button" disabled={disabled} onClick={() => onConfirm(target, "")}>
        <ArrowRight className="h-3.5 w-3.5" aria-hidden />
        {label}
      </Button>
    );
  }

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button size="sm" variant="secondary" type="button" disabled={disabled}>
          <ArrowRight className="h-3.5 w-3.5" aria-hidden />
          {label}
        </Button>
      </DialogTrigger>
      <DialogContent
        title={`${label} — ${entityLabel}`}
        description={
          confirm
            ? "This change is visible to everyone immediately. Confirm to continue."
            : "Add a note so the history explains this change, then continue."
        }
        footer={
          <>
            <DialogClose asChild>
              <Button variant="ghost" type="button">
                Cancel
              </Button>
            </DialogClose>
            <DialogClose asChild>
              <Button
                type="button"
                disabled={noteRequired && note.trim().length === 0}
                onClick={fire}
              >
                {label}
              </Button>
            </DialogClose>
          </>
        }
      >
        {noteLabel ? (
          <Field label={noteLabel} htmlFor={`note-${target}`} required={noteRequired}>
            <Textarea
              id={`note-${target}`}
              value={note}
              onChange={(event) => setNote(event.target.value)}
              rows={4}
              placeholder="Add context for this change…"
            />
          </Field>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

/** Compact inline spinner used while a register mutation is in flight. */
export function PendingChip({ label = "Saving…" }: { label?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-caption text-ink-muted")}>
      <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
      {label}
    </span>
  );
}
