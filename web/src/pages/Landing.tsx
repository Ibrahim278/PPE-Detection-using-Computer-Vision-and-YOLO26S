import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight, BarChart3, Bell, Camera, Cpu, Crosshair, ExternalLink, FileVideo, HardHat, LineChart, ScanSearch,
  ShieldAlert, Timer, Users, type LucideIcon,
} from "lucide-react";
import { Link } from "react-router";

import { ImageWithOverlay } from "../components/MediaOverlay";
import hero from "../landing-hero.json";
import { api, type Box, type Worker } from "../lib/api";

const REPO = "https://github.com/Ibrahim278/PPE-Detection-using-Computer-Vision-and-YOLO26S";

// Test-set results (502 images, helmet + head), shown if the API can't be reached.
const FALLBACK = {
  v3: { mAP50: 0.963, "mAP50-95": 0.639, precision: 0.932, recall: 0.926 },
  v2: { mAP50: 0.963, "mAP50-95": 0.635, precision: 0.942, recall: 0.918 },
};

export default function Landing() {
  return (
    <div className="min-h-full">
      <TopBar />
      <main>
        <Hero />
        <Intro />
        <HowItWorks />
        <Features />
        <Results />
        <BuiltWith />
        <Notes />
        <CallToAction />
      </main>
      <Footer />
    </div>
  );
}

function TopBar() {
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-bg/85 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3 md:px-6">
        <Link to="/" className="flex items-center gap-2">
          <span className="grid size-8 place-items-center rounded-lg bg-brand text-brand-ink"><HardHat size={18} aria-hidden /></span>
          <span className="font-semibold">SiteGuard</span>
        </Link>
        <nav className="ml-auto hidden items-center gap-6 text-sm text-muted md:flex" aria-label="Sections">
          <a href="#how" className="hover:text-ink">How it works</a>
          <a href="#features" className="hover:text-ink">Features</a>
          <a href="#results" className="hover:text-ink">Results</a>
        </nav>
        <Link to="/analyze" className="btn-primary ml-auto md:ml-0">Open app <ArrowRight size={16} aria-hidden /></Link>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <section className="mx-auto grid max-w-6xl items-center gap-10 px-4 pt-14 pb-16 md:px-6 lg:grid-cols-[1fr_1.15fr] lg:pt-20">
      <div>
        <span className="inline-flex items-center gap-2 rounded-full border border-line bg-panel px-3 py-1 text-xs text-muted">
          <span className="size-1.5 rounded-full bg-brand" aria-hidden /> Computer vision for construction safety
        </span>
        <h1 className="mt-5 text-4xl font-semibold tracking-tight md:text-5xl">
          Spot missing hard hats <span className="text-brand">automatically.</span>
        </h1>
        <p className="mt-5 max-w-xl text-lg text-muted">
          SiteGuard watches camera feeds and site videos, tracks every worker, and raises an alert, with a snapshot,
          when someone stays on site without a hard hat.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link to="/analyze" className="btn-primary px-5 py-2.5 text-base">Analyze a video <ArrowRight size={18} aria-hidden /></Link>
          <Link to="/live" className="btn-ghost px-5 py-2.5 text-base"><Camera size={18} aria-hidden /> Live Monitor</Link>
        </div>
        <p className="mt-4 text-xs text-muted">Free to try. No sign-up. Works with MP4, MOV, AVI, YouTube and Vimeo links.</p>
      </div>

      <figure>
        <div className="relative">
          <div className="rounded-2xl border border-line bg-panel p-2 shadow-2xl shadow-black/40">
            <ImageWithOverlay src="/landing/hero.jpg" width={hero.width} height={hero.height}
              workers={hero.workers as Worker[]} unverified={hero.unverified as Box[]} />
          </div>
          <div className="absolute -bottom-5 left-4 flex flex-wrap gap-2 sm:left-6">
            <Chip tone="ok" label={`${hero.summary.compliant} with hard hats`} />
            <Chip tone="bad" label={`${hero.summary.violations} without`} />
          </div>
        </div>
        <figcaption className="mt-9 text-xs text-muted">
          Real output from the model: workers with hard hats in green; the man in the cap is flagged in red.
        </figcaption>
      </figure>
    </section>
  );
}

function Chip({ tone, label }: { tone: "ok" | "bad"; label: string }) {
  const Icon = tone === "ok" ? HardHat : ShieldAlert;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border bg-panel px-3 py-1.5 text-sm font-medium shadow-lg
      ${tone === "ok" ? "border-ok/40 text-ok" : "border-bad/40 text-bad"}`}>
      <Icon size={15} aria-hidden /> {label}
    </span>
  );
}

function Section({ id, eyebrow, title, intro, children }: {
  id?: string; eyebrow: string; title: string; intro?: string; children: React.ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-20 border-t border-line">
      <div className="mx-auto max-w-6xl px-4 py-16 md:px-6 md:py-20">
        <div className="max-w-2xl">
          <div className="text-xs font-semibold uppercase tracking-wider text-brand">{eyebrow}</div>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight">{title}</h2>
          {intro && <p className="mt-4 text-muted">{intro}</p>}
        </div>
        <div className="mt-10">{children}</div>
      </div>
    </section>
  );
}

function Intro() {
  return (
    <Section eyebrow="The problem" title="Hard hats save lives, but checking every worker doesn't scale"
      intro="Head protection is required on active construction sites, yet compliance is usually checked by people walking the site. That's slow, easy to miss, and impossible to do continuously across many cameras.">
      <div className="grid gap-4 md:grid-cols-3">
        <Card icon={Users} title="Busy, changing scenes">
          Workers move, turn away, and overlap. A tool has to follow each person, not just count hats in one picture.
        </Card>
        <Card icon={Bell} title="Alerts people can trust">
          Flagging every flicker creates noise. SiteGuard waits until a bare head persists before raising an alert.
        </Card>
        <Card icon={LineChart} title="Evidence, not just alarms">
          Each incident keeps a snapshot, a timestamp and a duration, so supervisors can review and spot patterns.
        </Card>
      </div>
    </Section>
  );
}

const STEPS: { icon: LucideIcon; title: string; text: string }[] = [
  { icon: ScanSearch, title: "Detect", text: "A YOLO26s model, fine-tuned on 5,000 site images, finds every head and whether it has a hard hat." },
  { icon: Crosshair, title: "Track", text: "Each worker gets a stable ID across frames, so the system follows people, not single detections." },
  { icon: Timer, title: "Confirm", text: "An alert opens only after about 1.5 s without a hard hat, which filters out brief misdetections." },
  { icon: Bell, title: "Alert & log", text: "The incident is saved with a snapshot and duration, and shows up live and on the dashboard." },
];

function HowItWorks() {
  return (
    <Section id="how" eyebrow="How it works" title="From video to verified alert in four steps">
      <ol className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {STEPS.map(({ icon: Icon, title, text }, i) => (
          <li key={title} className="card relative p-5">
            <div className="flex items-center gap-3">
              <span className="grid size-9 place-items-center rounded-lg bg-brand/15 text-brand"><Icon size={18} aria-hidden /></span>
              <span className="tabular text-sm text-muted">Step {i + 1}</span>
            </div>
            <h3 className="mt-4 font-semibold">{title}</h3>
            <p className="mt-2 text-sm text-muted">{text}</p>
          </li>
        ))}
      </ol>
    </Section>
  );
}

const FEATURES: { icon: LucideIcon; title: string; text: string; to: string; cta: string }[] = [
  { icon: Camera, title: "Live Monitor", to: "/live", cta: "Start monitoring",
    text: "Use a webcam, or play a recording as if it were a camera. See boxes, a live compliance count and a violation feed." },
  { icon: FileVideo, title: "Video & link analysis", to: "/analyze", cta: "Analyze a video",
    text: "Upload a video or paste a YouTube, Vimeo or direct link. Get an annotated MP4, a timeline and every incident." },
  { icon: BarChart3, title: "Violations dashboard", to: "/violations", cta: "View dashboard",
    text: "Every incident in one place, with snapshots, filters, CSV export and a heatmap of when violations happen." },
  { icon: Cpu, title: "Open model", to: "/model", cta: "See the model",
    text: "Accuracy on a held-out test set, per-class results, tuned thresholds, and exactly how alerts are decided." },
];

function Features() {
  return (
    <Section id="features" eyebrow="Features" title="Everything you need to check a site">
      <div className="grid gap-4 md:grid-cols-2">
        {FEATURES.map(({ icon: Icon, title, text, to, cta }) => (
          <Link key={title} to={to} className="card group flex flex-col p-6 transition hover:border-muted">
            <span className="grid size-10 place-items-center rounded-lg bg-panel-2 text-brand"><Icon size={20} aria-hidden /></span>
            <h3 className="mt-4 text-lg font-semibold">{title}</h3>
            <p className="mt-2 flex-1 text-sm text-muted">{text}</p>
            <span className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-brand">
              {cta} <ArrowRight size={15} className="transition group-hover:translate-x-0.5" aria-hidden />
            </span>
          </Link>
        ))}
      </div>
    </Section>
  );
}

const METRICS = [["mAP50", "mAP@50"], ["mAP50-95", "mAP@50-95"], ["precision", "Precision"], ["recall", "Recall"]] as const;

function Results() {
  const q = useQuery({ queryKey: ["model"], queryFn: api.model, staleTime: Infinity, retry: 0 });
  const v3 = q.data?.test_metrics ?? FALLBACK.v3;
  const v2 = q.data?.baseline_v2 ?? FALLBACK.v2;
  return (
    <Section id="results" eyebrow="Results" title="Measured on 502 images the model never saw"
      intro="Scores for detecting hard hats and bare heads on a held-out test set, compared with the original course version (v2). Accuracy is on par; v3 adds tracking, confirmed alerts and a cleaner two-class design.">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {METRICS.map(([k, label]) => {
          const delta = (v3[k] - v2[k]) * 100;
          return (
            <div key={k} className="card p-5">
              <div className="text-xs font-medium uppercase tracking-wide text-muted">{label}</div>
              <div className="tabular mt-2 text-3xl font-semibold">{v3[k].toFixed(3)}</div>
              <div className="mt-1 text-xs text-muted">
                v2 {v2[k].toFixed(3)} · {delta >= 0 ? "+" : ""}{delta.toFixed(1)} pts
              </div>
            </div>
          );
        })}
      </div>
      <p className="mt-4 text-xs text-muted">
        mAP@50: how often boxes are found and placed correctly. mAP@50-95: the same, with stricter box overlap.{" "}
        <Link to="/model" className="text-brand hover:underline">Full model details</Link>
      </p>
    </Section>
  );
}

const STACK = [
  ["YOLO26s", "Ultralytics detection model"], ["ByteTrack", "multi-object tracking"], ["PyTorch", "training & inference"],
  ["FastAPI", "API, jobs, WebSocket"], ["React + Tailwind", "this web app"], ["Docker", "Render & Vercel hosting"],
];

function BuiltWith() {
  return (
    <Section eyebrow="Built with" title="Open, end to end">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        {STACK.map(([name, what]) => (
          <div key={name} className="card px-4 py-3">
            <div className="font-medium">{name}</div>
            <div className="mt-0.5 text-xs text-muted">{what}</div>
          </div>
        ))}
      </div>
    </Section>
  );
}

function Notes() {
  return (
    <Section eyebrow="Good to know" title="Limits of this demo">
      <ul className="grid gap-4 md:grid-cols-3">
        <li className="card p-5 text-sm text-muted">
          <h3 className="mb-2 font-semibold text-ink">Runs on a single CPU</h3>
          This hosted demo has no GPU. Images take about a second and a 10-second video a few minutes. Live monitoring
          needs a GPU or a local install for smooth real-time tracking.
        </li>
        <li className="card p-5 text-sm text-muted">
          <h3 className="mb-2 font-semibold text-ink">Hard hats only</h3>
          The model knows hard hats and bare heads. Caps count as violations; improvised head coverings can fool it.
          Other PPE (vests, glasses) isn't checked yet.
        </li>
        <li className="card p-5 text-sm text-muted">
          <h3 className="mb-2 font-semibold text-ink">A demo, not a safety system</h3>
          Results are for illustration and review. Don't rely on SiteGuard as the only safety control, and check
          privacy rules before recording real people.
        </li>
      </ul>
    </Section>
  );
}

function CallToAction() {
  return (
    <section className="border-t border-line">
      <div className="mx-auto max-w-6xl px-4 py-16 md:px-6">
        <div className="card flex flex-col items-start gap-6 bg-gradient-to-br from-panel to-panel-2 p-8 md:flex-row md:items-center md:justify-between md:p-10">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight">Try it with your own footage</h2>
            <p className="mt-2 text-muted">Upload a short site video and see every worker tracked and checked.</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link to="/analyze" className="btn-primary px-5 py-2.5">Analyze a video <ArrowRight size={18} aria-hidden /></Link>
            <Link to="/live" className="btn-ghost px-5 py-2.5"><Camera size={18} aria-hidden /> Live Monitor</Link>
          </div>
        </div>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-8 text-sm text-muted md:flex-row md:items-center md:justify-between md:px-6">
        <div className="flex items-center gap-2">
          <HardHat size={16} className="text-brand" aria-hidden /> SiteGuard · PPE compliance with computer vision
        </div>
        <div className="flex flex-wrap gap-x-5 gap-y-2">
          <a href={REPO} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 hover:text-ink">
            Source on GitHub <ExternalLink size={13} aria-hidden />
          </a>
          <a href="https://www.kaggle.com/datasets/andrewmvd/hard-hat-detection" target="_blank" rel="noreferrer" className="hover:text-ink">
            Training data: Kaggle
          </a>
          <a href="https://www.pexels.com" target="_blank" rel="noreferrer" className="hover:text-ink">Demo footage: Pexels</a>
        </div>
      </div>
    </footer>
  );
}

function Card({ icon: Icon, title, children }: { icon: LucideIcon; title: string; children: React.ReactNode }) {
  return (
    <div className="card p-5">
      <span className="grid size-9 place-items-center rounded-lg bg-panel-2 text-brand"><Icon size={18} aria-hidden /></span>
      <h3 className="mt-4 font-semibold">{title}</h3>
      <p className="mt-2 text-sm text-muted">{children}</p>
    </div>
  );
}
