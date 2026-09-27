"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Eye, EyeOff, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input, Field } from "@/components/ui/input";
import { ErrorState } from "@/components/ui/states";
import { TelWordmark } from "@/components/layout/wordmark";
import { useAuth } from "@/components/providers/auth-provider";
import { ApiError } from "@/lib/api-client";
import { FloatingOrbs, PageTransitionWrapper } from "@/components/education/education-components";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [formError, setFormError] = useState<ApiError | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setIsSubmitting(true);
    try {
      await login(email.trim(), password);
      router.replace("/dashboard");
      router.refresh();
    } catch (cause) {
      const apiError =
        cause instanceof ApiError
          ? cause
          : new ApiError(0, "unknown", "Sign-in failed. Please try again.");
      setFormError(apiError);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main id="main" className="relative min-h-dvh lg:grid lg:grid-cols-[minmax(22rem,0.85fr)_minmax(30rem,1.15fr)] bg-hero-gradient overflow-hidden">
      <FloatingOrbs opacity={0.06} color="brand" count={6} />

      <section className="relative hidden overflow-hidden bg-[#102a43] px-12 py-12 text-white lg:flex lg:flex-col lg:justify-between xl:px-20">
        <div className="absolute -right-24 -top-24 h-80 w-80 rounded-full border-[3rem] border-[#1e5268] opacity-60" />
        <div className="absolute -bottom-28 -left-24 h-96 w-96 rounded-full border-[4rem] border-[#0b3d58] opacity-80" />
        <div className="relative">
          <PageTransitionWrapper delay={0.3}>
            <TelWordmark size="md" showSubtitle={false} className="[&_span]:text-white [&>span:first-child]:bg-brand" />
            <div className="mt-24 max-w-md">
              <p className="text-caption font-semibold uppercase tracking-[0.16em] text-[#8bd5d7]">Student access</p>
              <h1 className="mt-5 font-display text-[clamp(2.5rem,4vw,4.4rem)] font-semibold leading-[0.98] tracking-[-0.04em] text-white">
                Your learning, in one clear view.
              </h1>
              <p className="mt-7 max-w-sm text-body-lg leading-relaxed text-[#c5d8e1]">
                A focused home for your timetable, attendance, assessments, and academic progress.
              </p>
            </div>
          </PageTransitionWrapper>
        </div>
        <div className="relative flex items-center gap-3 text-small text-[#c5d8e1]">
          <ShieldCheck className="h-5 w-5 text-[#8bd5d7]" aria-hidden />
          Secure access for the TEL Education Link community
        </div>
      </section>

      <section className="flex min-h-dvh items-center justify-center px-5 py-10 sm:px-10">
        <div className="w-full max-w-[28rem]">
          <div className="mb-10 lg:hidden">
            <TelWordmark size="md" />
          </div>

          <PageTransitionWrapper>
            <p className="text-caption font-semibold uppercase tracking-[0.16em] text-brand">Student portal</p>
            <h2 className="mt-3 font-display text-display text-ink">Welcome back</h2>
            <p className="mt-3 max-w-md text-body text-ink-muted">
              Sign in with your institutional account to continue to your dashboard.
            </p>

            <form onSubmit={handleSubmit} className="mt-6 space-y-4">
              {formError && <ErrorState error={formError} compact />}

              <Field label="Email address" htmlFor="email" required>
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@tel.edu.pk"
                  disabled={isSubmitting}
                  className="h-12 rounded-control bg-surface"
                />
              </Field>

              <Field label="Password" htmlFor="password" required>
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  disabled={isSubmitting}
                  trailing={
                    <button
                      type="button"
                      tabIndex={-1}
                      onClick={() => setShowPassword(!showPassword)}
                      className="rounded p-1 text-ink-faint hover:text-ink"
                      aria-label={showPassword ? "Hide password" : "Show password"}
                    >
                      {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  }
                  className="h-12 rounded-control bg-surface pr-12"
                />
              </Field>

              <Button type="submit" block loading={isSubmitting} size="lg" className="mt-3 h-12 shadow-raised" icon={<ArrowRight className="h-4 w-4" />}>
                Sign in
              </Button>
            </form>

            <div className="mt-6 text-center">
              <Link
                href="/forgot-password"
                className="text-small font-medium text-brand underline underline-offset-2 hover:text-brand-deep"
              >
                Forgot your password?
              </Link>
            </div>
          </PageTransitionWrapper>
          <p className="mt-10 text-small leading-relaxed text-ink-muted">
            By signing in, you agree to the TEL Education Link student portal terms.
          </p>
          <div className="mt-6 border-t border-line pt-5 text-caption text-ink-faint">
            Need help accessing your account? Contact your institution administrator.
          </div>
        </div>
      </section>
    </main>
  );
}
