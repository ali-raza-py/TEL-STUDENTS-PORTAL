"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, ArrowRight, Mail, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { TelWordmark } from "@/components/layout/wordmark";
import { ApiError } from "@/lib/api-client";
import { endpoints } from "@/lib/endpoints";
import { PageTransitionWrapper } from "@/components/education/education-components";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    setIsSubmitting(true);
    try {
      const response = await endpoints.auth.forgotPassword({ email: email.trim() });
      setMessage(response.detail);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "We could not submit that request. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main id="main" className="relative min-h-dvh bg-hero-gradient px-5 py-10 sm:px-10">
      <div className="relative z-10 mx-auto flex min-h-[calc(100dvh-5rem)] w-full max-w-5xl flex-col">
        <TelWordmark size="md" />
        <div className="grid flex-1 items-center gap-12 py-12 lg:grid-cols-[0.85fr_1.15fr] lg:gap-24">
          <div className="hidden lg:block">
            <PageTransitionWrapper delay={0.2}>
              <p className="text-label font-bold uppercase text-brand">Account recovery</p>
              <h1 className="mt-4 max-w-md font-display text-display text-ink">A fresh start is one email away.</h1>
              <p className="mt-5 max-w-sm text-body-lg text-ink-muted">
                Enter your institutional email and we will help you securely regain access.
              </p>
            </PageTransitionWrapper>
          </div>

          <section className="w-full max-w-[28rem]">
            <div className="mb-8 lg:hidden">
              <p className="text-label font-bold uppercase text-brand">Account recovery</p>
              <h1 className="mt-3 font-display text-h1 text-ink">Reset your password</h1>
            </div>
            <div className="rounded-card border border-line bg-surface p-7 shadow-raised sm:p-9">
              <div className="flex h-11 w-11 items-center justify-center rounded-control bg-brand-tint text-brand">
                <Mail className="h-5 w-5" aria-hidden />
              </div>
              <h2 className="mt-6 font-display text-h1 text-ink">Reset your password</h2>
              <p className="mt-2 text-body text-ink-muted">
                We will send reset instructions if an account exists for that address.
              </p>

              <form onSubmit={handleSubmit} className="mt-7 space-y-5">
                {error ? <p role="alert" className="rounded-control bg-danger-soft px-3 py-2 text-small text-danger">{error}</p> : null}
                {message ? <p role="status" className="rounded-control bg-success-soft px-3 py-2 text-small text-success">{message}</p> : null}
                <Field label="Institutional email" htmlFor="email" required>
                  <Input
                    id="email"
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="you@tel.edu.pk"
                    required
                    disabled={isSubmitting}
                    leading={<Mail className="h-4 w-4" aria-hidden />}
                    className="h-12 pl-10"
                  />
                </Field>
                <Button type="submit" block loading={isSubmitting} size="lg" className="h-12 shadow-raised" icon={<ArrowRight className="h-4 w-4" />}>
                  Send reset instructions
                </Button>
              </form>

              <div className="mt-7 flex items-center gap-2 text-small text-ink-muted">
                <ShieldCheck className="h-4 w-4 text-brand" aria-hidden />
                Your account details stay private.
              </div>
            </div>
            <Link href="/login" className="mt-6 inline-flex items-center gap-2 text-small font-medium text-brand hover:text-brand-deep">
              <ArrowLeft className="h-4 w-4" aria-hidden />
              Back to sign in
            </Link>
          </section>
        </div>
      </div>
    </main>
  );
}