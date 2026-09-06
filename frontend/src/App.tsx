import { useEffect, useRef, useState } from "react";
import { makeBlankBudget } from "./data/blankBudget";
import { EXAMPLES, type Example } from "./data/examples";
import { ErrorBoundary } from "./ErrorBoundary";
import { ApiError, parseBudgetPdf } from "./lib/api";
import { useHeroGlow } from "./lib/heroGlow";
import { ManualForm } from "./screens/ManualForm";
import { Results } from "./screens/Results";
import type { BudgetVector, ParsedBudget } from "./types";

type Screen = "splash" | "home" | "form" | "results";
interface NavState {
  screen: Screen;
  budget: BudgetVector | null;
}

type UploadState =
  | { status: "idle" }
  | { status: "parsing"; fileName: string }
  | { status: "error"; fileName: string; message: string };

/**
 * BUILD_BRIEF.md section 8 build order: examples path first ("a judge
 * opening the live URL has no budget file"), then manual form, then results
 * screen — all wired end to end against the real backend, and Results
 * itself runs the real Layer 1 pipeline (Parallel search + Gemini
 * extraction) live for every jurisdiction, not canned data. The upload path
 * (step 7, last) reads a budget PDF with Gemini and lands on the *form*,
 * pre-filled and annotated — never straight on results, since an unchecked
 * parsed figure is exactly what this tool exists to stop people trusting.
 */
function App() {
  const [screen, setScreen] = useState<Screen>("splash");
  const [splashOut, setSplashOut] = useState(false);
  const [budget, setBudget] = useState<BudgetVector | null>(null);
  const [upload, setUpload] = useState<UploadState>({ status: "idle" });
  // Parse output lives outside NavState: history.pushState structured-clones
  // its argument, and this is only meaningful for the form we're navigating
  // to right now anyway.
  const parsedRef = useRef<ParsedBudget | null>(null);
  const fileNameRef = useRef<string | null>(null);
  // Guards skipSplash against firing twice (the auto-timer racing a click,
  // or React Strict Mode's double-invoke in dev) — it schedules a real
  // side-effecting timeout, so it has to actually run only once.
  const splashDoneRef = useRef(false);

  // No router in this app, so without our own history entries the browser's
  // Back button has nothing to step through and exits straight to whatever
  // page opened the tab. Push one entry per screen change and let popstate
  // (fired by the Back/Forward buttons, and by history.back() below) drive
  // screen/budget, instead of only ever pushing state forward. The splash is
  // never itself a history entry — it's a skippable intro overlay on top of
  // the "home" entry beneath it, not a page you can navigate back into.
  useEffect(() => {
    window.history.replaceState({ screen: "home", budget: null } as NavState, "");
    function onPopState(e: PopStateEvent) {
      const state = e.state as NavState | null;
      setScreen(state?.screen ?? "home");
      setBudget(state?.budget ?? null);
    }
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  // Auto-advances past the splash so a judge who doesn't click still lands on
  // the product eventually; skipSplash also runs on a click or Enter/Space,
  // whichever is first. Long enough to actually read as a tone-setting beat
  // (and to hold during a demo recording) rather than a flash before the
  // real screen.
  useEffect(() => {
    const timer = setTimeout(() => skipSplash(), 6000);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount-only timer
  }, []);

  function skipSplash() {
    if (splashDoneRef.current) return;
    splashDoneRef.current = true;
    setSplashOut(true);
    setTimeout(() => setScreen("home"), 260);
  }

  function navigate(nextScreen: Screen, nextBudget: BudgetVector | null) {
    setScreen(nextScreen);
    setBudget(nextBudget);
    window.history.pushState({ screen: nextScreen, budget: nextBudget } as NavState, "");
  }

  function reset() {
    parsedRef.current = null;
    fileNameRef.current = null;
    setUpload({ status: "idle" });
    navigate("home", null);
  }

  async function uploadBudget(file: File) {
    fileNameRef.current = file.name;
    setUpload({ status: "parsing", fileName: file.name });
    try {
      const parsed = await parseBudgetPdf(file);
      parsedRef.current = parsed;
      setUpload({ status: "idle" });
      navigate("form", parsed.budget);
    } catch (err) {
      setUpload({
        status: "error",
        fileName: file.name,
        message:
          err instanceof ApiError ? err.message : "Could not reach the backend to read that file.",
      });
    }
  }

  function runComparison(b: BudgetVector) {
    navigate("results", b);
  }

  // Carries the current budget along so the form opens pre-filled with the
  // values from this run — "edit inputs" from Results used to always hand
  // the form a blank budget, wiping what was just entered.
  function openForm() {
    navigate("form", budget);
  }

  return (
    <div className="min-h-screen bg-paper font-sans text-[14px] text-ink">
      {screen === "splash" && <SplashScreen splashOut={splashOut} onSkip={skipSplash} />}

      {screen !== "splash" && (
        <header className="sticky top-0 z-30 flex items-baseline gap-[18px] border-b border-border bg-paper px-7 py-3.5">
          <Mark size={16} spin />
          <div className="font-sans text-[15px] font-bold tracking-tight">Slateline</div>
          <div className="font-sans text-[12.5px] text-ink-2">Jurisdiction comparison, net of relocation</div>
          {screen !== "home" && (
            <button
              type="button"
              onClick={reset}
              className="ml-auto border border-border-2 bg-paper px-2.5 py-1.5 font-mono text-[11px] font-medium tracking-wide text-ink transition-colors hover:border-ink hover:-translate-y-px print:hidden"
            >
              START OVER
            </button>
          )}
          {/* Film-perforation strip: a nod to the "shooting locations" subject
              without a photo or icon anywhere — a dash pattern, not a texture. */}
          <div
            aria-hidden
            className="pointer-events-none absolute inset-x-0 bottom-0 h-0.75 print:hidden"
            style={{ backgroundImage: "repeating-linear-gradient(to right, var(--color-ink) 0 6px, transparent 6px 12px)" }}
          />
        </header>
      )}

      <ErrorBoundary>
        {screen === "form" && (
          <ManualForm
            initial={budget ?? makeBlankBudget()}
            onBack={() => window.history.back()}
            onSubmit={runComparison}
            fieldNotes={parsedRef.current?.field_notes}
            warnings={parsedRef.current?.warnings}
            sourceLabel={fileNameRef.current ?? undefined}
          />
        )}
        {screen === "results" && budget && <Results budget={budget} onEditInputs={openForm} />}
        {screen === "home" && upload.status === "parsing" && <UploadProgress fileName={upload.fileName} />}
        {screen === "home" && upload.status === "error" && (
          <UploadError
            fileName={upload.fileName}
            message={upload.message}
            onRetry={() => setUpload({ status: "idle" })}
            onEnterManually={openForm}
          />
        )}
        {screen === "home" && upload.status === "idle" && (
          <HomeScreen onSelectExample={runComparison} onOpenForm={openForm} onUpload={uploadBudget} />
        )}
      </ErrorBoundary>
    </div>
  );
}

/**
 * A skippable intro, not a loading screen — there's nothing to wait for
 * (the seed jurisdictions/examples are already local data), so it exists
 * purely to set the tone before the working tool takes over. Auto-advances
 * after 6s; a click anywhere, or Enter/Space/Escape, ends it immediately —
 * both a resting beat for a demo and an escape hatch for anyone in a hurry.
 * `splashOut` drives a 260ms fade rather than an instant unmount, so the
 * transition to the home page isn't a hard cut.
 */
function SplashScreen({ splashOut, onSkip }: { splashOut: boolean; onSkip: () => void }) {
  return (
    <div
      onClick={onSkip}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " " || e.key === "Escape") {
          e.preventDefault();
          onSkip();
        }
      }}
      role="button"
      tabIndex={0}
      aria-label="Skip intro"
      className="fixed inset-0 z-50 flex cursor-pointer flex-col items-center justify-center overflow-hidden bg-ink"
      style={{ transition: "opacity 260ms ease", opacity: splashOut ? 0 : 1 }}
    >
      <div
        aria-hidden
        className="absolute"
        style={{
          inset: "-20%",
          background: "radial-gradient(circle, var(--color-teal-accent) 0%, transparent 60%)",
          filter: "blur(60px)",
          animation: "iv-glow1 9s ease-in-out infinite",
        }}
      />
      <div
        aria-hidden
        className="absolute"
        style={{
          inset: "-20%",
          background: "radial-gradient(circle, var(--color-red) 0%, transparent 60%)",
          filter: "blur(70px)",
          animation: "iv-glow2 11s ease-in-out infinite",
        }}
      />
      <div className="relative z-10 flex flex-col items-center gap-5">
        <Mark size={84} spin />
        <div className="font-display text-[34px] font-semibold uppercase tracking-[0.01em] text-paper">
          Slateline
        </div>
        <div className="font-mono text-[12px] tracking-wide text-teal-accent">
          JURISDICTION COMPARISON · NET OF RELOCATION
        </div>
        <div className="mt-6 font-mono text-[10.5px] tracking-wide text-ink-3">CLICK TO ENTER</div>
      </div>
    </div>
  );
}

function HomeScreen({
  onSelectExample,
  onOpenForm,
  onUpload,
}: {
  onSelectExample: (b: BudgetVector) => void;
  onOpenForm: () => void;
  onUpload: (file: File) => void;
}) {
  const [dragging, setDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const glow = useHeroGlow();

  function handleFiles(files: FileList | null) {
    const file = files?.[0];
    if (file) onUpload(file);
  }

  return (
    <>
      <main
        className="relative mx-auto max-w-330 overflow-hidden px-7 pb-16 pt-11"
        onMouseMove={glow.onMove}
        onMouseLeave={glow.onLeave}
      >
        <div aria-hidden className="pointer-events-none absolute inset-0" style={glow.style} />
        <div className="relative z-10">
        <div className="mb-9">
          <h1 className="mb-1.5 font-display text-[30px] font-semibold tracking-tight">
            Compare shooting locations on net benefit.
          </h1>
          <p className="font-sans text-[14px] text-ink-2">
            Every number sourced, dated, and adjusted for relocation cost.
          </p>
        </div>

        <div className="grid grid-cols-1 items-stretch gap-5 md:grid-cols-3">
          <section className="flex flex-col border border-border bg-card p-5">
            <CardLabel index="01" title="Try an example" stripe="amber" />
            <p className="mb-4 font-sans text-[13px] leading-[1.45] text-ink-2">
              One click loads a full comparison.
            </p>
            <div className="flex flex-col gap-2.5">
              {EXAMPLES.map((ex) => (
                <ExampleButton key={ex.id} example={ex} onSelect={() => onSelectExample(ex.budget)} />
              ))}
            </div>
          </section>

          <section className="flex flex-col border border-border bg-card p-5">
            <CardLabel index="02" title="Enter budget manually" stripe="teal" />
            <p className="mb-4 font-sans text-[13px] leading-[1.45] text-ink-2">
              Everything derived is shown.
            </p>
            <div className="mb-4 flex flex-1 flex-col gap-1.5 border border-[#eae8e1] bg-card-2 p-3.5">
              {["Total budget", "ATL cast / non-cast", "BTL labor / non-labor", "Post / VFX", "Shoot days / crew", "Resident labor share"].map(
                (label) => (
                  <div key={label} className="flex justify-between gap-3 font-mono text-[11.5px] text-ink-2">
                    <span>{label}</span>
                    <span className="text-ink-3">{label.includes("share") ? "%" : "USD"}</span>
                  </div>
                ),
              )}
            </div>
            <button
              type="button"
              onClick={onOpenForm}
              className="mt-auto w-full bg-ink px-0 py-2.5 font-mono text-[11.5px] font-medium tracking-wide text-paper transition-all hover:-translate-y-px hover:bg-[#091318]"
            >
              OPEN BLANK FORM
            </button>
          </section>

          <section className="flex flex-col border border-border bg-card p-5">
            <CardLabel index="03" title="Upload budget PDF" stripe="red" />
            <p className="mb-4 font-sans text-[13px] leading-[1.45] text-ink-2">
              Figures land pre-filled, for you to correct.
            </p>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                handleFiles(e.dataTransfer.files);
              }}
              className={`flex h-[148px] w-full cursor-pointer flex-col items-center justify-center gap-1.5 border border-dashed text-center transition-colors ${
                dragging ? "border-teal bg-[#f1f5f2]" : "border-border-2 bg-card-2 hover:border-teal hover:bg-[#f1f5f2]"
              }`}
            >
              <div className="font-mono text-[12px] font-medium tracking-wide text-[#57534c]">DROP PDF HERE</div>
              <div className="font-sans text-[12px] text-ink-3">or click to browse · max 25 MB</div>
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf,.pdf"
              hidden
              onChange={(e) => {
                handleFiles(e.target.files);
                e.target.value = ""; // let the same file be re-picked after an error
              }}
            />
            <div className="mt-3 font-mono text-[11px] text-ink-3">
              Read by Gemini, then shown in the form for you to correct.
            </div>
          </section>
        </div>
        </div>
      </main>
    </>
  );
}

/** BUILD_BRIEF.md section 7 wants real loading and error states on this
 *  flow, not a spinner that swallows a failed parse. */
function UploadProgress({ fileName }: { fileName: string }) {
  return (
    <div className="mx-auto max-w-[560px] px-7 pt-28">
      <div className="border border-border bg-card p-7">
        <div className="mb-4 flex items-center gap-3">
          <div className="h-4.5 w-4.5 animate-spin rounded-full border-2 border-border border-t-ink" />
          <div className="font-sans text-[14px] font-semibold">Reading {fileName}</div>
        </div>
        <p className="font-sans text-[13px] leading-relaxed text-ink-2">
          Gemini is reading the topsheet and recording the figures it states. Nothing is totalled or inferred —
          you'll land on the form with each figure annotated, to check before running.
        </p>
      </div>
    </div>
  );
}

function UploadError({
  fileName,
  message,
  onRetry,
  onEnterManually,
}: {
  fileName: string;
  message: string;
  onRetry: () => void;
  onEnterManually: () => void;
}) {
  return (
    <div className="mx-auto max-w-[560px] px-7 pt-28">
      <div className="border border-border border-t-[3px] border-t-red bg-card p-7">
        <div className="mb-2 font-sans text-[15px] font-semibold text-red">Could not read {fileName}</div>
        <p className="mb-5 font-sans text-[13.5px] leading-relaxed text-[#57534c]">
          {message} Nothing was inferred and no figures were carried forward.
        </p>
        <div className="flex gap-2.5">
          <button
            type="button"
            onClick={onRetry}
            className="bg-ink px-3.5 py-2.5 font-mono text-[11.5px] font-medium tracking-wide text-paper transition-transform hover:-translate-y-px"
          >
            TRY ANOTHER FILE
          </button>
          <button
            type="button"
            onClick={onEnterManually}
            className="border border-border-2 bg-card px-3.5 py-2.5 font-mono text-[11.5px] font-medium tracking-wide text-ink transition-all hover:-translate-y-px hover:border-ink"
          >
            ENTER MANUALLY
          </button>
        </div>
      </div>
    </div>
  );
}

function ExampleButton({ example, onSelect }: { example: Example; onSelect: () => void }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className="block w-full border border-border bg-card-2 px-3.5 py-3 text-left font-sans transition-all hover:-translate-y-0.5 hover:border-teal hover:bg-card hover:shadow-md"
    >
      <div className="flex items-baseline justify-between gap-2.5">
        <span className="font-sans text-[13.5px] font-semibold text-ink">{example.name}</span>
        <span className="font-mono text-[13px] font-semibold text-ink">{example.budgetLabel}</span>
      </div>
      <div className="mt-1 font-mono text-[11.5px] text-ink-2">{example.meta}</div>
    </button>
  );
}

const CARD_STRIPE_COLOR: Record<"amber" | "teal" | "red", string> = {
  amber: "var(--color-amber-accent)",
  teal: "var(--color-teal-accent)",
  red: "var(--color-red)",
};

function CardLabel({ index, title, stripe }: { index: string; title: string; stripe: "amber" | "teal" | "red" }) {
  return (
    <div className="mb-1 flex items-center gap-2.5">
      {/* A clapperboard-slate swatch, not a photo or icon — one diagonal
          stripe pair per card, echoing the film-perforation header strip
          without repeating it. */}
      <span
        aria-hidden
        className="h-3.5 w-3.5 shrink-0"
        style={{
          backgroundImage: `repeating-linear-gradient(45deg, var(--color-ink) 0 3px, ${CARD_STRIPE_COLOR[stripe]} 3px 6px)`,
        }}
      />
      <span className="font-mono text-[11px] font-medium text-ink-3">{index}</span>
      <span className="font-sans text-[15px] font-semibold">{title}</span>
    </div>
  );
}

function Mark({ size, spin }: { size: number; spin?: boolean }) {
  const dot = size * 0.7;
  return (
    <div
      className="relative shrink-0"
      style={{ width: size, height: size, animation: spin ? "iv-spin 12s linear infinite" : undefined }}
    >
      <span className="absolute rounded-full bg-teal mix-blend-multiply" style={{ width: dot, height: dot, left: 0, top: 0 }} />
      <span
        className="absolute rounded-full bg-amber mix-blend-multiply"
        style={{ width: dot, height: dot, left: dot * 0.45, top: 0 }}
      />
      <span
        className="absolute rounded-full bg-red mix-blend-multiply"
        style={{ width: dot, height: dot, left: dot * 0.22, top: dot * 0.45 }}
      />
    </div>
  );
}

export default App;
