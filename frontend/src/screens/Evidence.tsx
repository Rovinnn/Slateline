import { hostOf, money } from "../lib/format";
import type { JurisdictionRule } from "../types";

/**
 * The two things BUILD_BRIEF.md leads with that the UI was collecting and
 * then throwing away.
 *
 * Funding availability is the product's stated wedge — section 1: other
 * tools "report the rate but not whether the annual funding pool is
 * exhausted… a 30% credit you can't access is a 0% credit". We extract
 * annual_pool_total / annual_pool_remaining / application_deadline /
 * sunset_date and, until now, rendered none of them: the whole claim was
 * reduced to a three-word status pill.
 *
 * The excerpt is the quoted statutory line behind the rate. Every SourceRef
 * carries one; the UI showed a bare hostname. For a tool whose entire
 * argument is "sourced, dated, checkable", showing the actual sentence is
 * the single most convincing thing on screen.
 */

/**
 * A timecode-style badge for a source's retrieved date — ink background,
 * dots instead of dashes ("2026·08·24") — in place of plain
 * "· retrieved YYYY-MM-DD" text. A nod to the film-production subject
 * matter without a photo or icon anywhere on screen.
 */
export function RetrievedBadge({ date }: { date: string }) {
  return (
    <span className="inline-flex items-center bg-ink px-1.5 py-0.5 font-mono text-[10px] font-medium tracking-wide text-teal-accent">
      {date.replaceAll("-", "·")}
    </span>
  );
}

export function FundingAvailability({ rule }: { rule: JurisdictionRule }) {
  const facts: string[] = [];

  if (rule.annual_pool_total != null) {
    facts.push(
      rule.annual_pool_remaining != null
        ? `${money(rule.annual_pool_remaining)} left of a ${money(rule.annual_pool_total)} annual pool`
        : `${money(rule.annual_pool_total)} annual pool`,
    );
  }
  if (rule.application_deadline) facts.push(`applications close ${rule.application_deadline}`);
  if (rule.sunset_date) facts.push(`program sunsets ${rule.sunset_date}`);
  if (rule.under_review) facts.push("under legislative review");

  // "No cap found" is itself the answer for an uncapped program like
  // Georgia's, and is worth stating rather than leaving blank.
  if (facts.length === 0) {
    facts.push(
      rule.pool_status === "open"
        ? "no annual cap found in sources"
        : "no pool figures stated in the sources retrieved",
    );
  }

  return (
    <div className="border border-border-2 bg-card-2 px-3 py-2">
      <div className="mb-1 font-mono text-[10px] font-medium tracking-wide text-ink-3">FUNDING AVAILABILITY</div>
      <div className="font-sans text-[12.5px] leading-relaxed text-ink">{facts.join(" · ")}</div>
    </div>
  );
}

/** The quoted line from the source that justifies the figures above it. */
export function SourceEvidence({ rule, max = 2 }: { rule: JurisdictionRule; max?: number }) {
  // Primary sources (statute/regulation text) first — that's the whole point
  // of the is_primary flag.
  const ordered = [...rule.sources].sort((a, b) => Number(b.is_primary) - Number(a.is_primary));
  const shown = ordered.filter((s) => s.excerpt?.trim()).slice(0, max);

  if (ordered.length === 0) return null;

  // Extraction doesn't always return excerpt text — it varies run to run, and
  // a jurisdiction can come back with sources but no quotable lines. Falling
  // back to the citations themselves keeps the section honest (here's what
  // this is based on) instead of rendering a bare "EVIDENCE" heading over
  // nothing.
  if (shown.length === 0) {
    return (
      <div className="flex flex-col gap-1">
        <div className="font-sans text-[12px] italic text-ink-3">
          No quotable line was returned for this jurisdiction — sources only:
        </div>
        {ordered.slice(0, 3).map((src, i) => (
          <div key={i} className="flex flex-wrap items-baseline gap-1.5 font-mono text-[11px] text-ink-4">
            <a
              href={src.url}
              target="_blank"
              rel="noopener"
              className="text-teal underline decoration-1 underline-offset-2"
            >
              {hostOf(src.url)}
            </a>
            <span className="inline-flex items-center gap-1">
              · retrieved <RetrievedBadge date={src.retrieved} />
            </span>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2.5">
      {shown.map((src, i) => (
        <figure key={i} className="border-l-2 border-border-2 pl-3">
          <blockquote className="font-sans text-[12.5px] leading-relaxed text-[#57534c]">
            &ldquo;{src.excerpt.trim()}&rdquo;
          </blockquote>
          <figcaption className="mt-1 flex flex-wrap items-baseline gap-1.5 font-mono text-[11px] text-ink-4">
            <a
              href={src.url}
              target="_blank"
              rel="noopener"
              className="text-teal underline decoration-1 underline-offset-2"
            >
              {hostOf(src.url)}
            </a>
            <span className="inline-flex items-center gap-1">
              · retrieved <RetrievedBadge date={src.retrieved} />
            </span>
            {src.is_primary && <span className="text-ink-3">· statute or regulation</span>}
          </figcaption>
        </figure>
      ))}
    </div>
  );
}
