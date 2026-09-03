import { useEffect, useState } from "react";
import { makeBlankBudget } from "./data/blankBudget";
import { EXAMPLES, type Example } from "./data/examples";
import { ManualForm } from "./screens/ManualForm";
import { Results } from "./screens/Results";
import type { BudgetVector } from "./types";

type Screen = "home" | "form" | "results";
interface NavState {
  screen: Screen;
  budget: BudgetVector | null;
}

/**
 * BUILD_BRIEF.md section 8 build order: examples path first ("a judge
 * opening the live URL has no budget file"), then manual form, then results
 * screen — all three now wired end to end against the real backend, and
 * Results itself runs the real Layer 1 pipeline (Parallel search + Gemini
 * extraction) live for every jurisdiction, not canned data. PDF upload is
 * next.
 */
function App() {
  const [screen, setScreen] = useState<Screen>("home");
  const [budget, setBudget] = useState<BudgetVector | null>(null);

  // No router in this app, so without our own history entries the browser's
  // Back button has nothing to step through and exits straight to whatever
  // page opened the tab. Push one entry per screen change and let popstate
  // (fired by the Back/Forward buttons, and by history.back() below) drive
  // screen/budget, instead of only ever pushing state forward.
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

  function navigate(nextScreen: Screen, nextBudget: BudgetVector | null) {
    setScreen(nextScreen);
    setBudget(nextBudget);
    window.history.pushState({ screen: nextScreen, budget: nextBudget } as NavState, "");
  }

  function reset() {
    navigate("home", null);
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
      <header className="sticky top-0 z-30 flex items-baseline gap-[18px] border-b border-border bg-paper px-7 py-3.5">
        <Mark size={16} />
        <div className="font-sans text-[15px] font-bold tracking-tight">Incentive Verifier</div>
        <div className="font-sans text-[12.5px] text-ink-2">Jurisdiction comparison, net of relocation</div>
        {screen !== "home" && (
          <button
            type="button"
            onClick={reset}
            className="ml-auto border border-border-2 bg-paper px-2.5 py-1.5 font-mono text-[11px] font-medium tracking-wide text-ink transition-colors hover:border-ink"
          >
            START OVER
          </button>
        )}
      </header>

      {screen === "form" && (
        <ManualForm initial={budget ?? makeBlankBudget()} onBack={() => window.history.back()} onSubmit={runComparison} />
      )}
      {screen === "results" && budget && <Results budget={budget} onEditInputs={openForm} />}
      {screen === "home" && <HomeScreen onSelectExample={runComparison} onOpenForm={openForm} />}
    </div>
  );
}

function HomeScreen({
  onSelectExample,
  onOpenForm,
}: {
  onSelectExample: (b: BudgetVector) => void;
  onOpenForm: () => void;
}) {
  return (
    <>
      <main className="mx-auto max-w-[1320px] px-7 pb-16 pt-11">
        <div className="mb-9 flex items-center gap-[18px]">
          <Mark size={46} />
          <div>
            <h1 className="mb-1.5 font-sans text-[28px] font-semibold tracking-tight">
              Compare shooting locations on net benefit.
            </h1>
            <p className="font-sans text-[14px] text-ink-2">
              Every number sourced, dated, and adjusted for relocation cost.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 items-stretch gap-5 md:grid-cols-3">
          <section className="flex flex-col border border-border bg-card p-5">
            <CardLabel index="01" title="Try an example" />
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
            <CardLabel index="02" title="Enter budget manually" />
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
              className="mt-auto w-full bg-ink px-0 py-2.5 font-mono text-[11.5px] font-medium tracking-wide text-paper transition-colors hover:bg-[#091318]"
            >
              OPEN BLANK FORM
            </button>
          </section>

          <section className="flex flex-col border border-border bg-card p-5">
            <CardLabel index="03" title="Upload budget PDF" />
            <p className="mb-4 font-sans text-[13px] leading-[1.45] text-ink-2">
              Figures land pre-filled, for you to correct.
            </p>
            <div
              title="Next up — PDF upload"
              className="flex h-[148px] cursor-not-allowed flex-col items-center justify-center gap-1.5 border border-dashed border-border-2 bg-card-2 text-center"
            >
              <div className="font-mono text-[12px] font-medium tracking-wide text-[#57534c]">DROP PDF HERE</div>
              <div className="font-sans text-[12px] text-ink-3">or click to browse · max 25 MB</div>
            </div>
            <div className="mt-3 font-mono text-[11px] text-ink-3">NOTHING UPLOADED YET</div>
          </section>
        </div>
      </main>
    </>
  );
}

function ExampleButton({ example, onSelect }: { example: Example; onSelect: () => void }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className="block w-full border border-border bg-card-2 px-3.5 py-3 text-left font-sans transition-colors hover:border-ink hover:bg-card"
    >
      <div className="flex items-baseline justify-between gap-2.5">
        <span className="font-sans text-[13.5px] font-semibold text-ink">{example.name}</span>
        <span className="font-mono text-[13px] font-semibold text-ink">{example.budgetLabel}</span>
      </div>
      <div className="mt-1 font-mono text-[11.5px] text-ink-2">{example.meta}</div>
    </button>
  );
}

function CardLabel({ index, title }: { index: string; title: string }) {
  return (
    <div className="mb-1 flex items-baseline gap-2.5">
      <span className="font-mono text-[11px] font-medium text-ink-3">{index}</span>
      <span className="font-sans text-[15px] font-semibold">{title}</span>
    </div>
  );
}

function Mark({ size }: { size: number }) {
  const dot = size * 0.7;
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
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
