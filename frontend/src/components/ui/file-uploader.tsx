"use client";

import { FileUp, Paperclip, Trash2 } from "lucide-react";
import * as React from "react";

import { ApiError } from "@/lib/api-client";
import { cn, formatFileSize } from "@/lib/utils";
import { Button } from "./button";

/**
 * File uploader.
 *
 * The browser performs the same cheap checks the server enforces, so a user is
 * told immediately — but the server remains the authority: extension, declared
 * MIME type, byte signature and size are all validated again on arrival.
 */

const ACCEPT = ".pdf,.png,.jpg,.jpeg,.webp,.doc,.docx,.txt,.csv,.xls,.xlsx";
const MAX_BYTES = 15 * 1024 * 1024;

export function FileUploader({
  value,
  onChange,
  accept = ACCEPT,
  maxBytes = MAX_BYTES,
  label = "Attachment",
  hint = "PDF, image or document up to 15 MB.",
  invalid,
  className,
  existingName,
  existingUrl,
}: {
  value: File | null;
  onChange: (file: File | null) => void;
  accept?: string;
  maxBytes?: number;
  label?: string;
  hint?: string;
  invalid?: boolean;
  className?: string;
  existingName?: string;
  existingUrl?: string | null;
}) {
  const inputId = React.useId();
  const [dragging, setDragging] = React.useState(false);
  const [localError, setLocalError] = React.useState<string | null>(null);

  function validate(file: File): string | null {
    const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
    if (!accept.split(",").some((token) => token.trim() === `.${extension}`)) {
      return `Files of type '.${extension}' are not accepted.`;
    }
    if (file.size > maxBytes) {
      return `Files must be ${formatFileSize(maxBytes)} or smaller.`;
    }
    if (file.size === 0) return "That file is empty.";
    return null;
  }

  function handleFile(file: File | undefined) {
    if (!file) return;
    const problem = validate(file);
    setLocalError(problem);
    if (!problem) onChange(file);
  }

  const shown = value ?? (existingName ? { name: existingName } as File : null);

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <label htmlFor={inputId} className="text-small font-medium text-ink-soft">
        {label}
      </label>
      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          handleFile(event.dataTransfer.files?.[0]);
        }}
        className={cn(
          "flex flex-col items-center gap-2 rounded-control border border-dashed px-4 py-6 text-center transition-colors duration-200",
          dragging ? "border-brand bg-brand-tint" : "border-line-strong bg-surface-muted/50",
          invalid && "border-danger",
        )}
      >
        <input
          id={inputId}
          type="file"
          accept={ACCEPT}
          className="sr-only"
           onChange={(event) => handleFile(event.target.files?.[0])}
        />
        <span className="flex h-9 w-9 items-center justify-center rounded-pill bg-surface text-brand">
          <FileUp className="h-4 w-4" aria-hidden />
        </span>
        {shown ? (
          <div className="flex items-center gap-2 text-small text-ink">
            <Paperclip className="h-3.5 w-3.5 text-ink-faint" aria-hidden />
            <span className="max-w-[16rem] truncate font-medium">{shown.name}</span>
            {value ? (
              <span className="text-ink-faint">{formatFileSize(value.size)}</span>
            ) : null}
          </div>
        ) : (
          <p className="text-small text-ink-soft">
            Drop a file here, or{" "}
            <label htmlFor={inputId} className="cursor-pointer font-medium text-brand underline underline-offset-4">
              browse
            </label>
          </p>
        )}
        <p className="text-caption text-ink-faint">{hint}</p>
      </div>

      {localError ? (
        <p role="alert" className="text-caption font-medium text-danger">
          {localError}
        </p>
      ) : null}

      {value ? (
        <div className="flex justify-end">
          <Button
            variant="quiet"
            size="sm"
            icon={<Trash2 className="h-3.5 w-3.5" />}
            onClick={() => {
              onChange(null);
              setLocalError(null);
            }}
          >
            Remove file
          </Button>
        </div>
      ) : existingUrl ? (
        <a
          href={existingUrl}
          target="_blank"
          rel="noreferrer"
          className="text-caption font-medium text-brand underline underline-offset-4"
        >
          Open the file you already submitted
        </a>
      ) : null}
    </div>
  );
}

export function useFileUploadError(error: ApiError | null, field: string): string | undefined {
  if (!error) return undefined;
  const messages = error.fieldErrors[field];
  return messages?.join(" ");
}
