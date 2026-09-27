"use client";

import { useState } from "react";
import { Save } from "lucide-react";

import { PageHeader, PageStack, SectionHeading } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Field, Input, Textarea } from "@/components/ui/input";
import { Skeleton, SkeletonText } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/states";
import { useResource, useMutation } from "@/lib/hooks/use-resource";
import { useAuth, useRequiredUser } from "@/components/providers/auth-provider";
import { endpoints } from "@/lib/endpoints";
import type { CurrentUser } from "@/lib/types";
import { ApiError } from "@/lib/api-client";

export default function ProfilePage() {
  const { user, status, error: authError, refresh } = useAuth();
  const requiredUser = useRequiredUser();

  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<ApiError | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const [phone, setPhone] = useState(user?.phone ?? "");

  const updateMutation = useMutation(
    (body: Record<string, unknown>) => endpoints.auth.updateProfile(body),
  );
  const changePasswordMutation = useMutation(
    (body: { current_password: string; new_password: string }) =>
      endpoints.auth.changePassword(body),
  );

  if (status === "loading") return <ProfileSkeleton />;
  if (authError) return <ErrorState error={authError} />;
  if (!user) return null;

  const profile = user.profile;

  async function handleSave() {
    setIsSaving(true);
    setSaveError(null);
    setSaveSuccess(false);
    const result = await updateMutation.run({ phone });
    if (result !== null) {
      setSaveSuccess(true);
      void refresh();
      setTimeout(() => setSaveSuccess(false), 3000);
    } else {
      setSaveError(updateMutation.error ?? new ApiError(0, "unknown", "Failed to save profile."));
    }
    setIsSaving(false);
  }

  return (
    <PageStack>
      <PageHeader
        title="Profile"
        description={user.fullName}
        actions={
          isEditing ? (
            <Button variant="secondary" size="sm" icon={<Save className="h-4 w-4" />} onClick={handleSave} loading={isSaving}>
              Save changes
            </Button>
          ) : (
            <Button size="sm" onClick={() => setIsEditing(true)}>
              Edit profile
            </Button>
          )
        }
      />

      {saveError && <ErrorState error={saveError} compact />}

      {/* Contact information */}
      <SectionHeading title="Contact information" />
      <Card>
        <CardContent className="pt-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Full name" htmlFor="full_name">
              <Input id="full_name" value={user.fullName} readOnly={!isEditing} />
            </Field>
            <Field label="Email" htmlFor="email">
              <Input id="email" type="email" value={user.email} readOnly />
            </Field>
            <Field label="Phone" htmlFor="phone">
              <Input
                id="phone"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                readOnly={!isEditing}
                disabled={!isEditing}
              />
            </Field>
            <Field label="Role" htmlFor="role">
              <Input id="role" value={user.role} readOnly />
            </Field>
          </div>
          {saveSuccess && (
            <p className="mt-3 text-small text-success">
              Profile updated successfully.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Student profile details */}
      {profile && (
        <>
          <SectionHeading title="Student details" />
          <Card>
            <CardContent className="pt-5">
              <div className="grid gap-4 sm:grid-cols-2">
                <DetailRow label="Student code" value={profile.student_code} />
                <DetailRow label="Roll number" value={profile.roll_number} />
                <DetailRow label="Class" value={profile.class_display} />
                <DetailRow label="Section" value={profile.section?.name ?? "—"} />
                <DetailRow label="Campus" value={profile.campus?.name ?? "—"} />
                <DetailRow label="Program" value={profile.program?.name ?? "—"} />
                <DetailRow label="Academic year" value={profile.academic_year?.label ?? "—"} />
                <DetailRow label="Admission date" value={profile.admission_date ?? "—"} />
              </div>
            </CardContent>
          </Card>
        </>
      )}

      {/* Change password */}
      <SectionHeading title="Change password" />
      <ChangePasswordForm
        mutation={changePasswordMutation}
        onDone={() => {
          changePasswordMutation.reset();
        }}
      />
    </PageStack>
  );
}

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="text-caption text-ink-faint">{label}</p>
      <p className="text-small font-medium text-ink">{value}</p>
    </div>
  );
}

function ChangePasswordForm({
  mutation,
  onDone,
}: {
  mutation: {
    run: (body: { current_password: string; new_password: string }) => Promise<unknown>;
    isPending: boolean;
    error: ApiError | null;
    reset: () => void;
  };
  onDone: () => void;
}) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  function passwordsMatch(): boolean {
    return newPassword.length >= 8 && newPassword === confirmPassword;
  }

  async function handleSubmit() {
    if (!passwordsMatch()) return;
    const result = await mutation.run({
      current_password: currentPassword,
      new_password: newPassword,
    });
    if (result !== null) {
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      onDone();
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Reset your password</CardTitle>
        <CardDescription>
          Choose a strong password you haven't used before.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 pt-0">
        <Field label="Current password" htmlFor="current_password" required>
          <Input
            id="current_password"
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            required
            disabled={mutation.isPending}
          />
        </Field>

        <Field label="New password" htmlFor="new_password" required hint="At least 8 characters.">
          <Input
            id="new_password"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            disabled={mutation.isPending}
          />
        </Field>

        <Field label="Confirm new password" htmlFor="confirm_password" required>
          <Input
            id="confirm_password"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            disabled={mutation.isPending}
            invalid={confirmPassword.length > 0 && newPassword !== confirmPassword}
          />
        </Field>

        {mutation.error && (
          <p role="alert" className="text-caption text-danger">{mutation.error.message}</p>
        )}
      </CardContent>
      <CardFooter className="border-t border-line-soft">
        <Button
          variant="primary"
          onClick={handleSubmit}
          loading={mutation.isPending}
          disabled={!currentPassword || !passwordsMatch()}
        >
          Change password
        </Button>
      </CardFooter>
    </Card>
  );
}

function ProfileSkeleton() {
  return (
    <PageStack>
      <PageHeader title="Profile" description="Loading…" />
      <Card className="p-5">
        <SkeletonText lines={8} />
      </Card>
    </PageStack>
  );
}
