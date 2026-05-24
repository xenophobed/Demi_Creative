import { useEffect, useMemo, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import {
  Archive,
  CheckCircle2,
  Pencil,
  Plus,
  Star,
  UserRound,
} from "lucide-react";
import Button from "@/components/common/Button";
import Card from "@/components/common/Card";
import useChildStore, { DEFAULT_INTERESTS } from "@/store/useChildStore";
import type { AgeGroup, ChildProfile } from "@/types/api";

const AGE_OPTIONS: AgeGroup[] = ["3-5", "6-8", "9-12"];

type FormState = {
  name: string;
  age_group: AgeGroup;
  interestsText: string;
  avatar: string;
};

const EMPTY_FORM: FormState = {
  name: "",
  age_group: "6-8",
  interestsText: "",
  avatar: "",
};

interface ChildrenTabProps {
  isParent: boolean;
}

function ChildrenTab({ isParent }: ChildrenTabProps) {
  const {
    childProfiles,
    currentChild,
    activeChildId,
    isLoading,
    error,
    loadChildProfiles,
    createChildProfile,
    saveChildProfile,
    archiveChildProfile,
    setDefaultChildProfile,
    switchActiveChild,
  } = useChildStore();
  const [isAdding, setIsAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [savingAction, setSavingAction] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (!isParent) return;
    loadChildProfiles().catch((err) => {
      console.error("Failed to load child profiles:", err);
    });
  }, [isParent, loadChildProfiles]);

  const activeProfiles = useMemo(
    () => childProfiles.filter((child) => !child.archived_at),
    [childProfiles],
  );

  const activeId = activeChildId ?? currentChild?.child_id ?? null;

  if (!isParent) {
    return (
      <Card className="p-6">
        <div className="flex items-start gap-3">
          <div className="rounded-lg bg-gray-100 p-2 text-gray-500">
            <UserRound className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-gray-800">
              Child Profiles
            </h2>
            <p className="mt-1 text-sm text-gray-500">
              Parent controls are hidden for child accounts.
            </p>
          </div>
        </div>
      </Card>
    );
  }

  const openAddForm = () => {
    setIsAdding(true);
    setEditingId(null);
    setForm(EMPTY_FORM);
    setFormError(null);
  };

  const openEditForm = (child: ChildProfile) => {
    setIsAdding(false);
    setEditingId(child.child_id);
    setForm({
      name: child.name,
      age_group: child.age_group,
      interestsText: child.interests.join(", "),
      avatar: child.avatar ?? "",
    });
    setFormError(null);
  };

  const closeForm = () => {
    setIsAdding(false);
    setEditingId(null);
    setForm(EMPTY_FORM);
    setFormError(null);
  };

  const parseInterests = () =>
    form.interestsText
      .split(",")
      .map((interest) => interest.trim())
      .filter(Boolean)
      .slice(0, 8);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const name = form.name.trim();
    if (!name) {
      setFormError("Add a nickname for this child profile.");
      return;
    }

    const payload = {
      name,
      age_group: form.age_group,
      interests: parseInterests(),
      avatar: form.avatar.trim() || null,
    };

    setSavingAction(editingId ? `edit:${editingId}` : "create");
    setFormError(null);
    try {
      if (editingId) {
        await saveChildProfile(editingId, payload);
      } else {
        await createChildProfile(payload);
      }
      closeForm();
    } catch (err) {
      console.error("Failed to save child profile:", err);
      setFormError("We could not save this profile. Please try again.");
    } finally {
      setSavingAction(null);
    }
  };

  const handleArchive = async (child: ChildProfile) => {
    const confirmed = window.confirm(`Archive ${child.name}'s profile?`);
    if (!confirmed) return;

    setSavingAction(`archive:${child.child_id}`);
    try {
      await archiveChildProfile(child.child_id);
    } catch (err) {
      console.error("Failed to archive child profile:", err);
    } finally {
      setSavingAction(null);
    }
  };

  const handleSetDefault = async (childId: string) => {
    setSavingAction(`default:${childId}`);
    try {
      await setDefaultChildProfile(childId);
    } catch (err) {
      console.error("Failed to set default child profile:", err);
    } finally {
      setSavingAction(null);
    }
  };

  return (
    <div className="space-y-5">
      <Card className="p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-lg font-bold text-gray-800">
              Child Profiles
            </h2>
            <p className="mt-1 max-w-2xl text-sm text-gray-500">
              Create a nickname-based profile for each child so stories,
              memory, rewards, and recommendations fit their age and interests.
            </p>
          </div>
          <Button
            size="sm"
            className="w-full sm:w-auto"
            leftIcon={<Plus className="h-4 w-4" aria-hidden="true" />}
            onClick={openAddForm}
          >
            Add Child
          </Button>
        </div>

        {activeProfiles.length > 1 && (
          <div className="mt-5 border-t border-gray-100 pt-4">
            <p className="mb-2 text-xs font-bold uppercase tracking-wide text-gray-500">
              Active child
            </p>
            <div className="flex flex-wrap gap-2">
              {activeProfiles.map((child) => {
                const isActive = child.child_id === activeId;
                return (
                  <button
                    key={child.child_id}
                    type="button"
                    className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-bold transition-colors ${
                      isActive
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-gray-200 bg-white text-gray-600 hover:border-primary/50"
                    }`}
                    onClick={() => switchActiveChild(child.child_id)}
                  >
                    {avatarLabel(child)}
                    <span>{child.name}</span>
                    {isActive && (
                      <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </Card>

      {(isAdding || editingId) && (
        <Card className="p-6" variant="outlined">
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="flex flex-col gap-1">
              <h3 className="text-base font-bold text-gray-800">
                {editingId ? "Edit Child Profile" : "Add Child Profile"}
              </h3>
              <p className="text-sm text-gray-500">
                Use a nickname, favorite initials, or family name. No child
                email or username is needed.
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-gray-600">
                  Nickname
                </span>
                <input
                  type="text"
                  value={form.name}
                  onChange={(event) =>
                    setForm({ ...form, name: event.target.value })
                  }
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                  placeholder="Little Artist"
                />
              </label>

              <label className="block">
                <span className="mb-1 block text-sm font-medium text-gray-600">
                  Age group
                </span>
                <select
                  value={form.age_group}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      age_group: event.target.value as AgeGroup,
                    })
                  }
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                >
                  {AGE_OPTIONS.map((age) => (
                    <option key={age} value={age}>
                      {age}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <label className="block">
              <span className="mb-1 block text-sm font-medium text-gray-600">
                Interests
              </span>
              <input
                type="text"
                value={form.interestsText}
                onChange={(event) =>
                  setForm({ ...form, interestsText: event.target.value })
                }
                className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                placeholder="Space, Animals, Music"
              />
              <span className="mt-1 block text-xs text-gray-400">
                Separate interests with commas.
              </span>
            </label>

            <div>
              <span className="mb-2 block text-sm font-medium text-gray-600">
                Quick interest ideas
              </span>
              <div className="flex flex-wrap gap-2">
                {DEFAULT_INTERESTS.slice(0, 8).map((interest) => (
                  <button
                    key={interest}
                    type="button"
                    className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-bold text-gray-600 hover:border-primary/50 hover:text-primary"
                    onClick={() => {
                      const current = parseInterests();
                      if (current.includes(interest)) return;
                      setForm({
                        ...form,
                        interestsText: [...current, interest].join(", "),
                      });
                    }}
                  >
                    {interest}
                  </button>
                ))}
              </div>
            </div>

            {formError && (
              <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">
                {formError}
              </p>
            )}

            <div className="flex flex-wrap gap-2">
              <Button
                type="submit"
                size="sm"
                isLoading={savingAction === (editingId ? `edit:${editingId}` : "create")}
              >
                Save Profile
              </Button>
              <Button type="button" size="sm" variant="ghost" onClick={closeForm}>
                Cancel
              </Button>
            </div>
          </form>
        </Card>
      )}

      {error && (
        <Card className="border border-amber-200 bg-amber-50 p-4">
          <p className="text-sm text-amber-800">
            We could not load child profiles right now.
          </p>
        </Card>
      )}

      {isLoading ? (
        <Card className="p-6 text-center text-sm text-gray-500">
          Loading child profiles...
        </Card>
      ) : activeProfiles.length === 0 ? (
        <Card className="p-6 text-center">
          <UserRound
            className="mx-auto mb-3 h-8 w-8 text-gray-300"
            aria-hidden="true"
          />
          <h3 className="text-base font-bold text-gray-800">
            No child profiles yet
          </h3>
          <p className="mx-auto mt-1 max-w-md text-sm text-gray-500">
            Add a nickname-based child profile to personalize creative sessions.
          </p>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {activeProfiles.map((child) => {
            const isActive = child.child_id === activeId;
            const isDefault = Boolean(child.is_default);
            return (
              <Card
                key={child.child_id}
                className={`p-5 ${isActive ? "ring-2 ring-primary/40" : ""}`}
                variant="outlined"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-2xl">{avatarLabel(child)}</span>
                      <h3 className="truncate text-lg font-bold text-gray-800">
                        {child.name}
                      </h3>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <StatusPill>{child.age_group}</StatusPill>
                      {isDefault && (
                        <StatusPill icon={<Star className="h-3 w-3" />}>
                          Default
                        </StatusPill>
                      )}
                      {isActive && (
                        <StatusPill icon={<CheckCircle2 className="h-3 w-3" />}>
                          Active
                        </StatusPill>
                      )}
                    </div>
                  </div>
                </div>

                <div className="mt-4">
                  <p className="mb-2 text-xs font-bold uppercase tracking-wide text-gray-500">
                    Interests
                  </p>
                  {child.interests.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {child.interests.map((interest) => (
                        <span
                          key={interest}
                          className="rounded-lg bg-gray-100 px-2.5 py-1 text-xs font-semibold text-gray-600"
                        >
                          {interest}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-gray-400">
                      No interests added yet.
                    </p>
                  )}
                </div>

                <div className="mt-5 flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant={isActive ? "ghost" : "outline"}
                    disabled={isActive}
                    leftIcon={<CheckCircle2 className="h-4 w-4" />}
                    onClick={() => switchActiveChild(child.child_id)}
                  >
                    {isActive ? "Active" : "Switch"}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    leftIcon={<Pencil className="h-4 w-4" />}
                    onClick={() => openEditForm(child)}
                  >
                    Edit
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={isDefault}
                    isLoading={savingAction === `default:${child.child_id}`}
                    leftIcon={<Star className="h-4 w-4" />}
                    onClick={() => handleSetDefault(child.child_id)}
                  >
                    Default
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-red-600 hover:bg-red-50"
                    isLoading={savingAction === `archive:${child.child_id}`}
                    leftIcon={<Archive className="h-4 w-4" />}
                    onClick={() => handleArchive(child)}
                  >
                    Archive
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

function StatusPill({
  children,
  icon,
}: {
  children: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <span className="inline-flex items-center gap-1 rounded-lg bg-gray-100 px-2.5 py-1 text-xs font-bold text-gray-600">
      {icon}
      {children}
    </span>
  );
}

function avatarLabel(child: ChildProfile): string {
  if (child.avatar?.startsWith("emoji:")) {
    return child.avatar.replace("emoji:", "");
  }
  return "🎨";
}

export default ChildrenTab;
