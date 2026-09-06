import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/** Catches a render throw anywhere below it (e.g. a malformed API response
 * reaching a screen that doesn't expect it) so the app shows a recoverable
 * card instead of going blank — only a class component can do this in React. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Unhandled error in UI:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="mx-auto max-w-[640px] px-7 pt-16">
          <div className="border border-red/30 border-t-2 border-t-red bg-card p-6">
            <div className="mb-1.5 font-sans text-[15px] font-semibold text-red">Something went wrong</div>
            <p className="mb-4 font-sans text-[13.5px] leading-relaxed text-[var(--color-text-muted-2)]">
              {this.state.error.message || "The screen hit an unexpected error and couldn't continue."}
            </p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="border border-border-2 bg-paper px-2.5 py-1.5 font-mono text-[11px] font-medium tracking-wide text-ink transition-colors hover:border-ink hover:-translate-y-px"
            >
              RELOAD
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
