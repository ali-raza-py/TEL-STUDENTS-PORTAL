"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Timer, Save, Send, PauseCircle, PlayCircle } from "lucide-react";

import { PageHeader, PageStack } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { RadioCard, Checkbox, Textarea, Field } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Skeleton, SkeletonText } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/states";
import { Dialog, DialogContent, DialogTrigger, DialogTriggerButton, DialogClose } from "@/components/ui/dialog";
import { useResource, useMutation } from "@/lib/hooks/use-resource";
import { ApiError } from "@/lib/api-client";
import { endpoints } from "@/lib/endpoints";
import type { PracticeSession, PracticeQuestion, SavedAnswer } from "@/lib/types";
import { formatDuration } from "@/lib/utils";

export default function PracticeRunnerPage({ params }: { params: { id: string } }) {
  const paperId = Number(params.id);
  const router = useRouter();
  const [timeLeft, setTimeLeft] = useState<number | null>(null);
  const [isPaused, setIsPaused] = useState(false);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const [answers, setAnswers] = useState<Record<number, SavedAnswer>>({});
  const [showSubmitDialog, setShowSubmitDialog] = useState(false);

  const { data: session, error, isLoading, refetch: refetchSession } = useResource(
    (signal) => endpoints.papers.startPractice(paperId),
    { deps: [paperId] },
  );

  const saveMutation = useMutation(
    (attemptId: number, answerList: unknown[]) =>
      endpoints.papers.save(attemptId, answerList),
  );
  const submitMutation = useMutation(
    (attemptId: number, answerList: unknown[]) =>
      endpoints.papers.submit(attemptId, answerList),
  );

  useEffect(() => {
    if (session?.time_remaining_seconds !== null && session?.time_remaining_seconds !== undefined && !isPaused) {
      setTimeLeft(session.time_remaining_seconds);
    }
  }, [session, isPaused]);

  useEffect(() => {
    if (timeLeft === null || isPaused) return;
    if (timeLeft <= 0) {
      handleSubmit();
      return;
    }
    timerRef.current = setInterval(() => {
      setTimeLeft((prev) => (prev !== null ? prev - 1 : null));
    }, 1000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [timeLeft, isPaused]);

  function handleSelect(questionId: number, optionIndex: number) {
    setAnswers((prev) => ({
      ...prev,
      [questionId]: {
        question_id: questionId,
        selected_option: optionIndex,
        text_answer: prev[questionId]?.text_answer ?? "",
      },
    }));
  }

  function handleTextAnswer(questionId: number, text: string) {
    setAnswers((prev) => ({
      ...prev,
      [questionId]: {
        question_id: questionId,
        selected_option: prev[questionId]?.selected_option ?? null,
        text_answer: text,
      },
    }));
  }

  function handleCheckbox(questionId: number) {
    setAnswers((prev) => {
      const existing = prev[questionId]?.selected_option ?? -1;
      const next = existing === 1 ? -1 : 1;
      return {
        ...prev,
        [questionId]: {
          question_id: questionId,
          selected_option: next,
          text_answer: prev[questionId]?.text_answer ?? "",
        },
      };
    });
  }

  function getAnswerList(): SavedAnswer[] {
    return Object.values(answers);
  }

  async function handleSave() {
    if (!session) return;
    const result = await saveMutation.run(session.attempt_id, getAnswerList());
    if (result === null) return;
    void refetchSession();
  }

  async function handleSubmit() {
    if (!session) return;
    const result = await submitMutation.run(session.attempt_id, getAnswerList());
    if (result !== null) {
      router.push(`/practice/review/${result.attempt_id}`);
    }
  }

  if (isLoading) return <PracticeSkeleton />;
  if (error) return <ErrorState error={error} onRetry={refetchSession} />;
  if (!session) return null;

  const answeredCount = Object.keys(answers).filter(
    (key) => {
      const ans = answers[Number(key)];
      return ans.selected_option !== null && ans.selected_option !== -1 && ans.selected_option !== undefined;
    },
  ).length;

  return (
    <PageStack>
      <PageHeader
        title={session.paper.title}
        description={
          <>
            <span className="text-caption text-ink-faint">
              {session.paper.subject_name} · {session.questions.length} questions ·{" "}
              {session.paper.total_marks} marks
            </span>
          </>
        }
        actions={
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="sm"
              icon={isPaused ? <PlayCircle className="h-4 w-4" /> : <PauseCircle className="h-4 w-4" />}
              onClick={() => setIsPaused(!isPaused)}
            >
              {isPaused ? "Resume" : "Pause"}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              icon={<Save className="h-4 w-4" />}
              onClick={handleSave}
              loading={saveMutation.isPending}
            >
              Save
            </Button>
            <Button
              variant="primary"
              size="sm"
              icon={<Send className="h-4 w-4" />}
              onClick={() => setShowSubmitDialog(true)}
              loading={submitMutation.isPending}
            >
              Submit
            </Button>
          </div>
        }
      />

      {/* Timer bar */}
      {session.time_remaining_seconds !== null && (
        <div className="flex items-center gap-3">
          <Timer className="h-4 w-4 text-ink-faint" />
          <span className="font-mono text-body font-medium text-ink">
            {formatDuration(timeLeft ?? session.time_remaining_seconds)}
          </span>
          <Progress
            value={timeLeft !== null ? (timeLeft / (session.time_remaining_seconds || 1)) * 100 : null}
            size="sm"
            tone={timeLeft !== null && timeLeft < 60 ? "danger" : "brand"}
          />
        </div>
      )}

      <p className="text-small text-ink-muted">
        Answered {answeredCount}/{session.questions.length} questions
      </p>

      {/* Questions */}
      <div className="space-y-6">
        {session.questions.map((question: PracticeQuestion) => {
          const saved = answers[question.id];
          return (
            <Card key={question.id} className="p-5">
              <CardHeader>
                <CardTitle>
                  <div className="flex items-start gap-3">
                    <Badge tone="neutral" size="sm">
                      {question.order}
                    </Badge>
                    <span>{question.text}</span>
                  </div>
                </CardTitle>
                {question.chapter && (
                  <CardDescription>Chapter: {question.chapter}</CardDescription>
                )}
              </CardHeader>
              <CardContent>
                {renderQuestion(question, saved, (val) =>
                  question.question_type === "MCQ"
                    ? handleSelect(question.id, val as number)
                    : question.question_type === "TRUE_FALSE"
                    ? handleSelect(question.id, val as number)
                    : handleTextAnswer(question.id, val as string),
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Submit dialog */}
      <Dialog open={showSubmitDialog} onOpenChange={setShowSubmitDialog}>
        <DialogContent
          title="Submit practice"
          description="Are you sure you want to submit? Your answers will be finalised and you won't be able to edit them."
        >
          <p className="text-small text-ink-muted">
            Answered {answeredCount}/{session.questions.length} questions.
          </p>
          <DialogClose asChild>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setShowSubmitDialog(false)}>
                Cancel
              </Button>
              <Button
                variant="danger"
                onClick={handleSubmit}
                loading={submitMutation.isPending}
              >
                Submit anyway
              </Button>
            </div>
          </DialogClose>
        </DialogContent>
      </Dialog>
    </PageStack>
  );
}

function renderQuestion(
  question: PracticeQuestion,
  saved: SavedAnswer | undefined,
  onSelect: (value: number | string) => void,
) {
  const value = saved?.selected_option ?? null;
  const textValue = saved?.text_answer ?? "";

  switch (question.question_type) {
    case "MCQ":
      return (
        <div className="space-y-2">
          {question.options.map((option, index) => (
            <RadioCard
              key={index}
              checked={value === index}
              onChange={() => onSelect(index)}
            >
              {option}
            </RadioCard>
          ))}
        </div>
      );

    case "TRUE_FALSE":
      return (
        <div className="flex gap-3">
          <RadioCard checked={value === 1} onChange={() => onSelect(1)}>
            True
          </RadioCard>
          <RadioCard checked={value === 0} onChange={() => onSelect(0)}>
            False
          </RadioCard>
        </div>
      );

    case "SHORT":
    case "SUBJECTIVE":
      return (
        <Field label="Your answer" htmlFor={`answer-${question.id}`}>
          <Textarea
            id={`answer-${question.id}`}
            value={textValue}
            onChange={(e) => onSelect(e.target.value)}
            rows={4}
            placeholder="Type your answer here…"
          />
        </Field>
      );

    default:
      return null;
  }
}

function PracticeSkeleton() {
  return (
    <PageStack>
      <PageHeader title="Practice" description="Loading your practice session…" />
      <Skeleton className="h-8 w-48" />
      {Array.from({ length: 5 }).map((_, i) => (
        <Card key={i} className="p-5">
          <SkeletonText lines={3} />
        </Card>
      ))}
    </PageStack>
  );
}
