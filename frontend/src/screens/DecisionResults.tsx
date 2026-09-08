import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { CONSTRAINTS } from "../data/constraints";
import { HOME_BASES } from "../data/examples";
import { challengeState } from "../lib/challenge";
import { effectiveRate, type Row } from "../lib/explain";
import { money, moneyShort } from "../lib/format";
import type { BreakevenResult } from "../lib/breakeven";
import type {
  BudgetVector,
  ChallengeReport,
  CreditTimingAssumptions,
  OpenQuestion,
  PoolStatus,
  RelocationAssumptions,
  Robustness,
  SplitResponse,
} from "../types";
import { FundingAvailability, SourceEvidence } from "./Evidence";
import { RelocationStrip } from "./MapView";
import { Waterfall, WhyItWins } from "./Recommendation";
import { RobustnessPanel } from "./RobustnessPanel";
import "./DecisionResults.css";

type Drawer = { kind: "location"; row: Row } | { kind: "checks" } | { kind: "model" } | { kind: "split" } | { kind: "robustness" } | null;
type LocationView = "summary" | "calculation" | "program" | "evidence";
type ModelView = "sensitivity" | "constraints" | "timing" | "relocation";

const POOL_LABEL: Record<PoolStatus, string> = {
  open: "Funding open",
  capping_out: "Capping out",
  closed: "Closed",
  unknown: "Status unknown",
};
const POOL_CLASS: Record<PoolStatus, string> = {
  open: "border-teal/20 bg-teal-bg text-teal",
  capping_out: "border-amber/20 bg-amber-bg text-amber",
  closed: "border-red/20 bg-red-bg text-red",
  unknown: "border-border-2 bg-card-2 text-ink-3",
};

interface Props {
  mode?: "memo" | "compare";
  rows: Row[];
  liveBudget: BudgetVector;
  initialBudget: BudgetVector;
  onBudgetChange: (budget: BudgetVector) => void;
  assumptions: RelocationAssumptions;
  onAssumptionsChange: (assumptions: RelocationAssumptions) => void;
  timing: CreditTimingAssumptions;
  onTimingChange: (timing: CreditTimingAssumptions) => void;
  breakeven: BreakevenResult | "loading" | "error" | null;
  split: SplitResponse | null;
  questions: OpenQuestion[];
  robustness: Robustness | null;
  onRefresh: (jurisdiction: string) => void;
  refreshing: Record<string, boolean>;
  refreshError: Record<string, string>;
  challenges: Record<string, ChallengeReport | "checking" | "failed">;
  onViewMap: () => void;
}

function Tabs({ value, options, onChange, label }: { value: string; options: { key: string; label: string }[]; onChange: (key: string) => void; label: string }) {
  function handleKey(event: KeyboardEvent<HTMLButtonElement>) {
    const current = options.findIndex(option => option.key === value);
    let next = current;
    if (event.key === "ArrowRight") next = (current + 1) % options.length;
    else if (event.key === "ArrowLeft") next = (current - 1 + options.length) % options.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = options.length - 1;
    else return;
    event.preventDefault();
    onChange(options[next].key);
    requestAnimationFrame(() => document.getElementById(`${label}-${options[next].key}`)?.focus());
  }
  return <div className="dp-tabs" role="tablist" aria-label={label}>{options.map(option => (
    <button id={`${label}-${option.key}`} key={option.key} type="button" role="tab" aria-selected={value === option.key} tabIndex={value === option.key ? 0 : -1} onClick={() => onChange(option.key)} onKeyDown={handleKey}>{option.label}</button>
  ))}</div>;
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return <div className="dp-fact"><span>{label}</span><strong>{children}</strong></div>;
}

export function DecisionResults(props: Props) {
  const { rows, liveBudget, questions, split, robustness } = props;
  const [drawer, setDrawer] = useState<Drawer>(null);
  const [locationView, setLocationView] = useState<LocationView>("summary");
  const [modelView, setModelView] = useState<ModelView>("sensitivity");
  const dialogRef = useRef<HTMLDialogElement>(null);
  const computable = useMemo(() => rows.filter(row => row.benefit.computable).sort((a, b) => b.benefit.net_benefit - a.benefit.net_benefit), [rows]);
  const unverified = rows.filter(row => !row.benefit.computable);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (drawer && dialog && !dialog.open) dialog.showModal();
    if (!drawer && dialog?.open) dialog.close();
  }, [drawer]);

  if (computable.length === 0) return <div className="mt-6 border border-border-3 bg-card p-6 text-ink-2">None of the {rows.length} jurisdictions could be computed for this budget.</div>;
  const [winner, runnerUp] = computable;
  const risk = Math.max(0, ...questions.filter(question => question.worth < 0).map(question => Math.abs(question.worth)));
  const home = HOME_BASES.find(item => item.label === liveBudget.home_base) ?? HOME_BASES[0];
  const openLocation = (row: Row, view: LocationView = "summary") => { setLocationView(view); setDrawer({ kind: "location", row }); };

  return <div className="decision-prototype pt-5">
    {props.mode === "compare" ? <DecisionCompare rows={rows} winner={winner} onOpen={openLocation} /> : <>
    <div className="dp-section-label"><span /> RECOMMENDATION · RANKED BY NET BENEFIT</div>
    <article className="dp-hero">
      <div className="dp-hero-main">
        <div className="flex flex-wrap items-center gap-2"><span className="dp-best">BEST TAKE</span><span className={`dp-status ${POOL_CLASS[winner.rule.pool_status]}`}>{POOL_LABEL[winner.rule.pool_status]}</span><ChallengeStatus challenge={props.challenges[winner.rule.jurisdiction]} /></div>
        <h1>{winner.rule.jurisdiction}</h1><p className="dp-program">{winner.rule.program_name}</p>
        <div className="dp-headline"><div><span>NET BENEFIT</span><strong>{moneyShort(winner.benefit.net_benefit)}</strong></div>{runnerUp && <p>{moneyShort(winner.benefit.net_benefit - runnerUp.benefit.net_benefit)} more than {runnerUp.rule.jurisdiction}</p>}</div>
        <div className="dp-key-metrics"><Fact label="ADVERTISED RATE">{(winner.rule.base_rate * 100).toFixed(1)}%</Fact><Fact label="EFFECTIVE RETURN">{((effectiveRate(winner, liveBudget.total)?.effective ?? 0) * 100).toFixed(1)}%</Fact><Fact label="QUALIFIED SPEND">{moneyShort(winner.benefit.qualifying_spend)}</Fact><Fact label="RELOCATION">{moneyShort(winner.benefit.relocation_cost)}</Fact></div>
        <div className="dp-actions"><button className="dp-primary" onClick={() => openLocation(winner, "calculation")}>VIEW CALCULATION</button><button className="dp-secondary" onClick={() => openLocation(winner, "evidence")}>CHECK EVIDENCE</button></div>
      </div>
      <aside className="dp-decision-rail">
        <div className="dp-rail-title">DECISION STATUS</div>
        <Status color="teal" title="Best estimated return">{runnerUp ? `Leads the next option by ${moneyShort(winner.benefit.net_benefit - runnerUp.benefit.net_benefit)}` : "Only computable option"}</Status>
        <Status color="amber" title={`${questions.length} ${questions.length === 1 ? "item needs" : "items need"} confirmation`}>{risk > 0 ? `${moneyShort(risk)} could be at risk` : "Confirm before committing"}</Status>
        {robustness && <Status color={robustness.winner_holds_in === robustness.combinations_tested ? "teal" : "amber"} title={`Holds in ${Math.round(100 * robustness.winner_holds_in / robustness.combinations_tested)}% of tests`}>{robustness.flips.length ? `${robustness.flips.length} conditions can change the winner` : "No tested condition changes the winner"}</Status>}
        <Status color={winner.rule.pool_status === "open" ? "teal" : "gray"} title={POOL_LABEL[winner.rule.pool_status]}>{winner.rule.annual_pool_remaining == null ? "Check current availability" : `${moneyShort(winner.rule.annual_pool_remaining)} remaining`}</Status>
        {questions.length > 0 && <button className="dp-text-button" onClick={() => setDrawer({ kind: "checks" })}>REVIEW BEFORE-COMMIT CHECKS →</button>}
        {robustness && <button className="dp-text-button" onClick={() => setDrawer({ kind: "robustness" })}>REVIEW ROBUSTNESS →</button>}
      </aside>
    </article>

    <section className="dp-card dp-shortlist">
      <div className="dp-card-heading"><div><span className="dp-section-label"><span /> SHORTLIST</span><h2>All ranked locations</h2></div><span>Select a row for full details</span></div>
      <div className="dp-list-header"><span>RANK / LOCATION</span><span>RATE</span><span>QUALIFIED</span><span>NET BENEFIT</span><span /></div>
      {computable.map((row, index) => <button className="dp-location-row" key={row.rule.jurisdiction} onClick={() => openLocation(row)}>
        <span className="dp-place"><em>{String(index + 1).padStart(2, "0")}</em><span><strong>{row.rule.jurisdiction}</strong><small>{POOL_LABEL[row.rule.pool_status]}{failingConstraint(row, liveBudget) ? " · constraint gap" : ""}</small></span></span>
        <span>{(row.rule.base_rate * 100).toFixed(1)}%</span><span>{moneyShort(row.benefit.qualifying_spend)}</span><span className="dp-net">{moneyShort(row.benefit.net_benefit)}<small>{index === 0 ? "BEST NET" : `${moneyShort(row.benefit.net_benefit - winner.benefit.net_benefit)} vs top`}</small></span><span aria-hidden>→</span>
      </button>)}
      {unverified.map((row, index) => <div className="dp-unverified" key={row.rule.jurisdiction}><span>{String(computable.length + index + 1).padStart(2, "0")}</span><strong>{row.rule.jurisdiction}</strong><span>Not ranked · {row.benefit.non_computable_reason}</span><button onClick={() => openLocation(row)}>VIEW REASON →</button></div>)}
    </section>

    <section className="dp-decision-tools">
      <button className="dp-tool-card" onClick={() => setDrawer({ kind: "checks" })}><span className="dp-tool-icon amber">!</span><span><strong>Before you commit</strong><small>{questions.length} checks{risk > 0 ? ` · ${moneyShort(risk)} at risk` : ""}</small></span><span>→</span></button>
      <button className="dp-tool-card" onClick={() => setDrawer({ kind: "model" })}><span className="dp-tool-icon teal">⌁</span><span><strong>Model settings</strong><small>Sensitivity, constraints, timing, relocation</small></span><span>→</span></button>
      <button className="dp-tool-card" disabled={!split} onClick={() => setDrawer({ kind: "split" })}><span className="dp-tool-icon gray">↔</span><span><strong>Split analysis</strong><small>{split ? (split.splitting_wins ? `${moneyShort(split.gain_over_single)} gain from splitting` : "Single location remains best") : "Analysis in progress"}</small></span><span>{split ? "→" : "…"}</span></button>
    </section>
    </>}

    <dialog ref={dialogRef} className="dp-dialog" onClose={() => setDrawer(null)} onCancel={() => setDrawer(null)} aria-labelledby="decision-detail-title">
      <div className="dp-dialog-header"><div><span className="dp-section-label"><span /> {drawer?.kind === "location" ? "LOCATION DETAIL" : drawer?.kind === "checks" ? "DECISION CHECKS" : drawer?.kind === "split" ? "SPLIT ANALYSIS" : drawer?.kind === "robustness" ? "ROBUSTNESS" : "MODEL SETTINGS"}</span><h2 id="decision-detail-title">{drawer?.kind === "location" ? drawer.row.rule.jurisdiction : drawer?.kind === "checks" ? "Before you commit" : drawer?.kind === "split" ? "Shoot and post" : drawer?.kind === "robustness" ? "Does it hold up?" : "Adjust the model"}</h2></div><button className="dp-close" onClick={() => setDrawer(null)} aria-label="Close detail panel">×</button></div>
      {drawer?.kind === "location" && <LocationPanel row={drawer.row} winner={winner} runnerUp={runnerUp} view={locationView} onViewChange={setLocationView} home={home} {...props} />}
      {drawer?.kind === "checks" && <ChecksPanel questions={questions} risk={risk} jurisdiction={winner.rule.jurisdiction} />}
      {drawer?.kind === "model" && <ModelPanel view={modelView} onViewChange={setModelView} {...props} />}
      {drawer?.kind === "split" && split && <SplitPanel split={split} />}
      {drawer?.kind === "robustness" && robustness && <div className="dp-dialog-content"><RobustnessPanel robustness={robustness} /></div>}
    </dialog>
  </div>;
}

function DecisionCompare({ rows, winner, onOpen }: { rows: Row[]; winner: Row; onOpen: (row: Row, view?: LocationView) => void }) {
  const [sort, setSort] = useState<"net" | "rate" | "relocation">("net");
  const sorted = [...rows].filter(row => row.benefit.computable).sort((a, b) => sort === "rate" ? b.rule.base_rate - a.rule.base_rate : sort === "relocation" ? a.benefit.relocation_cost - b.benefit.relocation_cost : b.benefit.net_benefit - a.benefit.net_benefit);
  return <section><div className="dp-card-heading"><div><span className="dp-section-label"><span /> COMPARE</span><h2>Every number that changes the ranking</h2></div><label className="dp-sort">SORT BY <select value={sort} onChange={event => setSort(event.target.value as typeof sort)}><option value="net">Net benefit</option><option value="rate">Advertised rate</option><option value="relocation">Relocation cost</option></select></label></div>
    <div className="dp-table-wrap"><table className="dp-table"><thead><tr><th>LOCATION</th><th>RATE</th><th>QUALIFIED SPEND</th><th>FACE CREDIT</th><th>REALIZABLE</th><th>RELOCATION</th><th>NET BENEFIT</th><th /></tr></thead><tbody>{sorted.map(row => <tr key={row.rule.jurisdiction}><td><strong>{row.rule.jurisdiction}</strong>{row === winner && <small>BEST NET</small>}</td><td>{(row.rule.base_rate * 100).toFixed(1)}%</td><td>{moneyShort(row.benefit.qualifying_spend)}</td><td>{moneyShort(row.benefit.gross_credit)}</td><td>{moneyShort(row.benefit.realizable_credit ?? row.benefit.gross_credit)}</td><td>−{moneyShort(row.benefit.relocation_cost)}</td><td><strong>{moneyShort(row.benefit.net_benefit)}</strong></td><td><button onClick={() => onOpen(row)} aria-label={`View ${row.rule.jurisdiction} details`}>→</button></td></tr>)}</tbody></table></div>
  </section>;
}

function SplitPanel({ split }: { split: SplitResponse }) {
  const { best, best_single, splitting_wins, gain_over_single } = split;
  return <div className="dp-dialog-content"><div className="dp-drawer-number"><span>BEST PLAN</span><strong>{splitting_wins ? `${best.shoot_in} + ${best.post_in}` : best_single.shoot_in}</strong></div><div className="dp-fact-grid"><Fact label="NET BENEFIT">{money(best.net_benefit)}</Fact><Fact label="VS BEST SINGLE">{splitting_wins ? `+${moneyShort(gain_over_single)}` : "No gain"}</Fact><Fact label="SHOOT IN">{best.shoot_in}</Fact><Fact label="POST IN">{best.post_in}</Fact></div><div className="dp-note"><strong>{splitting_wins ? "Splitting improves the result" : "Keep the production together"}</strong><p>{splitting_wins ? `Principal photography in ${best.shoot_in} and post/VFX in ${best.post_in} produces the best combined estimate.` : `Every shoot/post pairing was priced, and none beats ${best_single.shoot_in} as a single location.`}</p></div>{best.warnings.map((warning, index) => <div className="dp-note" key={index}><strong>Warning</strong><p>{warning}</p></div>)}</div>;
}

function Status({ color, title, children }: { color: "teal" | "amber" | "gray"; title: string; children: ReactNode }) {
  return <div className="dp-check"><span className={`dp-dot ${color}`} /><div><strong>{title}</strong><p>{children}</p></div></div>;
}

function ChallengeStatus({ challenge }: { challenge?: ChallengeReport | "checking" | "failed" }) {
  const state = challengeState(challenge);
  return <span className={`dp-status ${state.status === "contradicted" ? "border-red/20 bg-red-bg text-red" : state.status === "corroborated" ? "border-teal/20 bg-teal-bg text-teal" : "border-border-2 bg-card-2 text-ink-3"}`}>{state.status === "checking" ? "Re-checking" : state.label}</span>;
}

function failingConstraint(row: Row, budget: BudgetVector) {
  return budget.constraints.some(key => Boolean(row.rule.constraint_gaps[key]));
}

function LocationPanel({ row, winner, runnerUp, view, onViewChange, home, onRefresh, refreshing, refreshError, onViewMap, liveBudget, breakeven, challenges }: Props & { row: Row; winner: Row; runnerUp?: Row; view: LocationView; onViewChange: (view: LocationView) => void; home: (typeof HOME_BASES)[number] }) {
  return <div className="dp-dialog-content"><Tabs label="location-detail" value={view} onChange={key => onViewChange(key as LocationView)} options={[{ key: "summary", label: "SUMMARY" }, { key: "calculation", label: "CALCULATION" }, { key: "program", label: "PROGRAM" }, { key: "evidence", label: "EVIDENCE" }]} />
    <div className="dp-panel" role="tabpanel">
      {view === "summary" && <><div className="dp-drawer-number"><span>NET BENEFIT</span><strong>{row.benefit.computable ? moneyShort(row.benefit.net_benefit) : "NOT RANKED"}</strong></div>{row.benefit.computable ? <><div className="dp-fact-grid"><Fact label="HEADLINE RATE">{(row.rule.base_rate * 100).toFixed(1)}%</Fact><Fact label="QUALIFIED SPEND">{money(row.benefit.qualifying_spend)}</Fact><Fact label="FACE CREDIT">{money(row.benefit.gross_credit)}</Fact><Fact label="RELOCATION">−{money(row.benefit.relocation_cost)}</Fact></div>{row === winner && runnerUp && <WhyItWins winner={winner} rival={runnerUp} />}{row.benefit.distance_km != null && <><RelocationStrip homeLabel={home.label} homeLat={home.lat} homeLng={home.lng} destLabel={row.rule.jurisdiction} destLat={row.rule.centroid_lat} destLng={row.rule.centroid_lng} distanceKm={row.benefit.distance_km} relocationCost={row.benefit.relocation_cost} /><button className="dp-text-button" onClick={onViewMap}>VIEW FULL MAP →</button></>}</> : <p className="dp-copy">{row.benefit.non_computable_reason}</p>}</>}
      {view === "calculation" && (row.benefit.computable ? <><Waterfall row={row} />{row === winner && <BreakevenSummary value={breakeven} budget={liveBudget} />}</> : <p className="dp-copy">A calculation is unavailable because this program could not be verified.</p>)}
      {view === "program" && <><div className="dp-fact-grid"><Fact label="PROGRAM">{row.rule.program_name}</Fact><Fact label="PAYOUT">{row.rule.credit_type.replace("_", "-")}</Fact><Fact label="MINIMUM SPEND">{row.rule.minimum_spend == null ? "None found" : money(row.rule.minimum_spend)}</Fact><Fact label="CONFIDENCE">{row.rule.confidence.replace("_", " ")}</Fact><Fact label="FILM OFFICE">{row.rule.film_office_contact ?? "Not listed"}</Fact></div><FundingAvailability rule={row.rule} />{row.benefit.caps_applied.length > 0 && <div className="dp-note"><strong>Limits applied</strong>{row.benefit.caps_applied.map((note, index) => <p key={index}>{note}</p>)}</div>}</>}
      {view === "evidence" && <><div className="dp-note"><strong>Evidence status</strong><p><ChallengeStatus challenge={challenges[row.rule.jurisdiction]} /></p></div><SourceEvidence rule={row.rule} /><div className="dp-actions"><button className="dp-secondary" disabled={refreshing[row.rule.jurisdiction]} onClick={() => onRefresh(row.rule.jurisdiction)}>{refreshing[row.rule.jurisdiction] ? "REFRESHING…" : "REFRESH SOURCES"}</button>{refreshError[row.rule.jurisdiction] && <span className="text-red text-[11px]">{refreshError[row.rule.jurisdiction]}</span>}</div></>}
    </div>
  </div>;
}

function BreakevenSummary({ value, budget }: { value: BreakevenResult | "loading" | "error" | null; budget: BudgetVector }) {
  if (!value) return null;
  if (value === "loading") return <div className="dp-note">Checking when the recommendation changes…</div>;
  if (value === "error") return <div className="dp-note">Breakeven analysis is unavailable.</div>;
  return <div className="dp-note"><strong>When the recommendation changes</strong><p>{value.crossAtl == null ? `${value.heroName} remains ahead across the tested ATL-spend range.` : `${value.heroName} changes position near ${moneyShort(value.crossAtl)} ATL spend. Current ATL spend is ${moneyShort(budget.atl_cast + budget.atl_noncast)}.`}</p></div>;
}

function ChecksPanel({ questions, risk, jurisdiction }: { questions: OpenQuestion[]; risk: number; jurisdiction: string }) {
  return <div className="dp-dialog-content"><div className="dp-risk-summary"><span>MAXIMUM IDENTIFIED RISK · {jurisdiction.toUpperCase()}</span><strong>{moneyShort(risk)}</strong></div><div className="dp-question-list">{questions.length === 0 ? <p className="dp-copy">No unresolved questions were generated.</p> : questions.map((question, index) => <article key={index}><span>{String(index + 1).padStart(2, "0")}</span><div><h3>{question.question}</h3><p>{question.basis}</p><strong>ASK: {question.ask}</strong></div><em className={question.worth < 0 ? "risk" : "upside"}>{question.worth > 0 ? "+" : ""}{moneyShort(question.worth)}<small>{question.worth < 0 ? "AT RISK" : "IF CONFIRMED"}</small></em></article>)}</div></div>;
}

function ModelPanel({ view, onViewChange, liveBudget, initialBudget, onBudgetChange, assumptions, onAssumptionsChange, timing, onTimingChange }: Props & { view: ModelView; onViewChange: (view: ModelView) => void }) {
  return <div className="dp-dialog-content"><Tabs label="model-settings" value={view} onChange={key => onViewChange(key as ModelView)} options={[{ key: "sensitivity", label: "SENSITIVITY" }, { key: "constraints", label: "CONSTRAINTS" }, { key: "timing", label: "TIMING" }, { key: "relocation", label: "RELOCATION" }]} /><div className="dp-panel" role="tabpanel">
    {view === "sensitivity" && <Sensitivity budget={liveBudget} initial={initialBudget} onChange={onBudgetChange} />}
    {view === "constraints" && <Constraints budget={liveBudget} onChange={onBudgetChange} />}
    {view === "timing" && <FieldGrid values={timing} fields={TIMING_FIELDS} onChange={onTimingChange} />}
    {view === "relocation" && <FieldGrid values={assumptions} fields={RELOCATION_FIELDS} onChange={onAssumptionsChange} />}
  </div></div>;
}

function Sensitivity({ budget, initial, onChange }: { budget: BudgetVector; initial: BudgetVector; onChange: (budget: BudgetVector) => void }) {
  const atl = budget.atl_cast + budget.atl_noncast;
  const share = atl > 0 ? budget.atl_cast / atl : .65;
  const max = Math.max((initial.atl_cast + initial.atl_noncast) * 2.5, 4_000_000);
  return <section className="dp-model-section"><h3>Sensitivity</h3><p>Changes recalculate and reorder the ranking.</p><label>ATL spend <output>{moneyShort(atl)}</output><input type="range" min="0" max={max} step={10_000} value={atl} onChange={event => { const value = Number(event.target.value); onChange({ ...budget, atl_cast: value * share, atl_noncast: value * (1 - share), total: value + budget.btl_labor + budget.btl_nonlabor + budget.post_vfx }); }} /></label><label>Resident labor <output>{Math.round(budget.resident_labor_pct * 100)}%</output><input type="range" min="0" max="100" value={Math.round(budget.resident_labor_pct * 100)} onChange={event => onChange({ ...budget, resident_labor_pct: Number(event.target.value) / 100 })} /></label></section>;
}

function Constraints({ budget, onChange }: { budget: BudgetVector; onChange: (budget: BudgetVector) => void }) {
  return <section className="dp-model-section"><h3>Location constraints</h3><p>Locations stay visible and show a constraint gap when they cannot comply.</p><div className="dp-chip-row">{CONSTRAINTS.map(constraint => { const active = budget.constraints.includes(constraint.key); return <button key={constraint.key} className={active ? "active" : ""} onClick={() => onChange({ ...budget, constraints: active ? budget.constraints.filter(key => key !== constraint.key) : [...budget.constraints, constraint.key] })}>{active ? "■" : "□"} {constraint.label}</button>; })}</div></section>;
}

interface NumberField<T> { key: keyof T; label: string; prefix?: string; suffix?: string; step: number; percent?: boolean }
const TIMING_FIELDS: NumberField<CreditTimingAssumptions>[] = [
  { key: "discount_rate_annual", label: "Cost of capital", suffix: "%/yr", step: .5, percent: true }, { key: "months_refundable", label: "Refundable wait", suffix: "mo", step: 1 }, { key: "months_rebate", label: "Rebate wait", suffix: "mo", step: 1 }, { key: "months_transferable", label: "Transferable wait", suffix: "mo", step: 1 }, { key: "months_non_refundable", label: "Non-refundable wait", suffix: "mo", step: 1 }, { key: "months_unknown", label: "Unstated wait", suffix: "mo", step: 1 }, { key: "audit_cost", label: "Audit cost", prefix: "$", step: 500 },
];
const RELOCATION_FIELDS: NumberField<RelocationAssumptions>[] = [
  { key: "flight_threshold_km", label: "Flight threshold", suffix: "km", step: 10 }, { key: "flight_cost_per_person", label: "Airfare base", prefix: "$", step: 10 }, { key: "flight_cost_per_person_per_km", label: "Airfare per km", prefix: "$", suffix: "/km", step: .01 }, { key: "ground_cost_per_person_per_km", label: "Ground transport", prefix: "$", suffix: "/km", step: .01 }, { key: "per_diem_per_person_per_day", label: "Per diem", prefix: "$", step: 5 }, { key: "hotel_per_person_per_day", label: "Hotel", prefix: "$", step: 5 }, { key: "equipment_shipping_base", label: "Equipment shipping", prefix: "$", step: 500 }, { key: "imported_crew_pct", label: "Crew relocating", suffix: "%", step: 1, percent: true },
];

function FieldGrid<T extends object>({ values, fields, onChange }: { values: T; fields: NumberField<T>[]; onChange: (values: T) => void }) {
  return <section className="dp-model-section"><div className="dp-field-grid">{fields.map(field => { const raw = Number(values[field.key]) * (field.percent ? 100 : 1); return <label key={String(field.key)}><span>{field.label}</span><span className="dp-number-input">{field.prefix}<input type="number" min="0" step={field.step} value={raw} onChange={event => onChange({ ...values, [field.key]: Number(event.target.value) / (field.percent ? 100 : 1) })} />{field.suffix}</span></label>; })}</div></section>;
}
