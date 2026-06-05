import { Link } from "react-router-dom";
import {
  ArrowRight,
  BadgeCheck,
  BookOpen,
  CheckCircle2,
  CreditCard,
  GalleryHorizontalEnd,
  Globe2,
  ImagePlus,
  Library,
  MessageCircle,
  Newspaper,
  ShieldCheck,
  Sparkles,
  UserRound,
  UsersRound,
  type LucideIcon,
} from "lucide-react";

const CREATION_MODES = [
  {
    title: "Art to Story",
    description:
      "Children upload a drawing and turn it into a narrated picture-book adventure.",
    icon: ImagePlus,
    tone: "border-primary/20 bg-primary/5 text-primary",
  },
  {
    title: "Interactive Tales",
    description:
      "Kids choose what happens next, so every story can branch into a new path.",
    icon: BookOpen,
    tone: "border-secondary/25 bg-secondary/10 text-teal-700",
  },
  {
    title: "Kids Daily",
    description:
      "Real-world topics become warm, age-aware listening moments for curious kids.",
    icon: Newspaper,
    tone: "border-accent/40 bg-accent/15 text-yellow-700",
  },
];

const ECOSYSTEM_FEATURES = [
  {
    title: "My Agent Buddy",
    description:
      "A personal creative buddy helps children start ideas and remembers what inspires them.",
    icon: MessageCircle,
  },
  {
    title: "Content Hub",
    description:
      "Families and groups can share finished creations with kid-safe attribution.",
    icon: Globe2,
  },
  {
    title: "My Library",
    description:
      "Stories, interactive sessions, and Kids Daily episodes stay organized for return visits.",
    icon: Library,
  },
];

const PROFILE_POINTS = [
  "Parent profiles manage account details, child profiles, memory controls, rewards, and membership.",
  "Child profiles use a nickname, age group, interests, and active-child selection to personalize stories.",
  "Memory and recommendations stay scoped to the active child profile, so siblings can have different creative worlds.",
];

const PARENT_FLOW = [
  "Sign up as a parent or guardian.",
  "Create the first child profile with nickname, age group, and interests.",
  "Meet My Agent Buddy during onboarding.",
  "Manage children, memory, rewards, and account details from Profile.",
];

const CHILD_FLOW = [
  "Choose the child account path during sign up.",
  "Enter a parent or guardian email address.",
  "Wait for parent approval before protected features are enabled.",
  "Return to sign in after approval is complete.",
];

function AboutUsPage() {
  return (
    <div className="mx-auto max-w-7xl space-y-8">
      <section className="overflow-hidden rounded-lg border border-gray-200 bg-white/90 shadow-sm">
        <div className="grid gap-0 lg:grid-cols-[0.95fr_1.05fr]">
          <div className="border-b border-gray-200 bg-gray-50/80 p-6 sm:p-8 lg:border-b-0 lg:border-r">
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/15 bg-white px-3 py-1.5 text-xs font-bold text-primary">
              <Sparkles className="h-4 w-4" aria-hidden="true" />
              About Creative Workshop
            </div>
            <h1 className="mt-4 text-3xl font-extrabold leading-tight text-gray-900 sm:text-4xl">
              A safe agentic creative workspace where children can let
              imagination fly.
            </h1>
            <p className="mt-4 text-base leading-relaxed text-gray-600">
              Creative Workshop helps kids turn drawings, choices, curiosity,
              and daily topics into stories they can read, hear, continue, save,
              and share with parent-friendly controls.
            </p>
            <div className="mt-6 flex flex-col gap-3 sm:flex-row">
              <Link
                to="/login"
                className="btn-primary inline-flex min-h-[48px] items-center justify-center gap-2 px-5"
              >
                Start Creating
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
              <Link
                to="/"
                className="btn-secondary inline-flex min-h-[48px] items-center justify-center gap-2 px-5"
              >
                View Home
              </Link>
            </div>
          </div>

          <div className="grid gap-3 p-6 sm:p-8">
            {CREATION_MODES.map((mode) => {
              const Icon = mode.icon;
              return (
                <article
                  key={mode.title}
                  className={`rounded-lg border p-4 ${mode.tone}`}
                >
                  <Icon className="mb-3 h-6 w-6" aria-hidden="true" />
                  <h2 className="text-base font-bold text-gray-900">
                    {mode.title}
                  </h2>
                  <p className="mt-1 text-sm leading-relaxed text-gray-600">
                    {mode.description}
                  </p>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        {ECOSYSTEM_FEATURES.map((feature) => {
          const Icon = feature.icon;
          return (
            <article
              key={feature.title}
              className="rounded-lg border border-gray-200 bg-white/90 p-5 shadow-sm"
            >
              <Icon className="mb-4 h-6 w-6 text-primary" aria-hidden="true" />
              <h2 className="text-lg font-bold text-gray-900">
                {feature.title}
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-gray-600">
                {feature.description}
              </p>
            </article>
          );
        })}
      </section>

      <section className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="rounded-lg border border-gray-200 bg-white/90 p-6 shadow-sm">
          <div className="mb-4 flex items-center gap-3">
            <div className="rounded-lg bg-primary/10 p-2 text-primary">
              <UsersRound className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-wide text-gray-500">
                Profiles
              </p>
              <h2 className="text-xl font-bold text-gray-900">
                One family account can support multiple children.
              </h2>
            </div>
          </div>
          <div className="space-y-3">
            {PROFILE_POINTS.map((point) => (
              <div key={point} className="flex gap-3">
                <CheckCircle2
                  className="mt-0.5 h-4 w-4 flex-none text-primary"
                  aria-hidden="true"
                />
                <p className="text-sm leading-relaxed text-gray-600">{point}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <FlowCard
            title="Parent setup"
            description="Best for families who want a parent or guardian to create the first child profile."
            icon={UserRound}
            steps={PARENT_FLOW}
          />
          <FlowCard
            title="Child sign up"
            description="Best when a child starts first and needs a parent or guardian to approve access."
            icon={ShieldCheck}
            steps={CHILD_FLOW}
          />
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <article className="rounded-lg border border-gray-200 bg-white/90 p-5 shadow-sm">
          <GalleryHorizontalEnd
            className="mb-4 h-6 w-6 text-primary"
            aria-hidden="true"
          />
          <h2 className="text-lg font-bold text-gray-900">Profile dashboard</h2>
          <p className="mt-2 text-sm leading-relaxed text-gray-600">
            Profile brings together overview stats, child management, memory,
            rewards, account details, and referral or membership status.
          </p>
        </article>
        <article className="rounded-lg border border-gray-200 bg-white/90 p-5 shadow-sm">
          <CreditCard className="mb-4 h-6 w-6 text-primary" aria-hidden="true" />
          <h2 className="text-lg font-bold text-gray-900">Pricing</h2>
          <p className="mt-2 text-sm leading-relaxed text-gray-600">
            Families can start free, then upgrade when they need richer
            creation history, daily routines, and more room to explore.
          </p>
        </article>
        <article className="rounded-lg border border-gray-200 bg-white/90 p-5 shadow-sm">
          <BadgeCheck
            className="mb-4 h-6 w-6 text-primary"
            aria-hidden="true"
          />
          <h2 className="text-lg font-bold text-gray-900">Membership</h2>
          <p className="mt-2 text-sm leading-relaxed text-gray-600">
            Membership is designed around family controls, safe sharing, saved
            projects, parent visibility, and creative routines for children.
          </p>
        </article>
      </section>
    </div>
  );
}

function FlowCard({
  title,
  description,
  icon: Icon,
  steps,
}: {
  title: string;
  description: string;
  icon: LucideIcon;
  steps: string[];
}) {
  return (
    <article className="rounded-lg border border-gray-200 bg-white/90 p-5 shadow-sm">
      <Icon className="mb-4 h-6 w-6 text-primary" aria-hidden="true" />
      <h2 className="text-lg font-bold text-gray-900">{title}</h2>
      <p className="mt-2 text-sm leading-relaxed text-gray-600">
        {description}
      </p>
      <ol className="mt-4 space-y-3">
        {steps.map((step, index) => (
          <li key={step} className="flex gap-3 text-sm text-gray-600">
            <span className="flex h-6 w-6 flex-none items-center justify-center rounded-lg bg-primary/10 text-xs font-bold text-primary">
              {index + 1}
            </span>
            <span className="leading-relaxed">{step}</span>
          </li>
        ))}
      </ol>
    </article>
  );
}

export default AboutUsPage;
