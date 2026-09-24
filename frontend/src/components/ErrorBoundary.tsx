import { Component, type ErrorInfo, type ReactNode } from "react";

import { lastRequestId } from "../api/client";

interface State {
  error: Error | null;
  requestId: string | null;
  copied: boolean;
}

/** Catches RENDER-time crashes only. It does not catch event handlers or async code — API errors
 *  are handled by the client wrapper and shown inline (11-FRONTEND.md §3.4). */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null, requestId: null, copied: false };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error, requestId: lastRequestId() };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error({ error, info });
  }

  private copy = async () => {
    if (!this.state.requestId) return;
    try {
      await navigator.clipboard.writeText(this.state.requestId);
      this.setState({ copied: true });
    } catch {
      /* clipboard unavailable — the id is still visible and selectable */
    }
  };

  render() {
    if (!this.state.error) return this.props.children;
    const { requestId, copied } = this.state;
    return (
      <div className="glass" role="alert" style={{ maxWidth: 620, margin: "80px auto", textAlign: "center" }}>
        <p className="eyebrow" style={{ color: "var(--danger)" }}>Signal lost</p>
        <h1 className="page-title" style={{ fontSize: 34 }}>Something broke on this screen.</h1>
        <p className="page-sub" style={{ margin: "0 auto 20px" }}>
          The page hit an unexpected error. If you report it, include the request id below — it lets an operator find
          exactly what happened in the logs.
        </p>
        <div className="row" style={{ justifyContent: "center" }}>
          <code data-testid="last-request-id" style={{ fontFamily: "var(--mono)", padding: "8px 12px", border: "1px solid var(--line-strong)", borderRadius: 10 }}>
            {requestId ?? "no request made yet"}
          </code>
          {requestId && (
            <button className="btn btn-sm" onClick={this.copy}>
              {copied ? "Copied ✓" : "Copy id"}
            </button>
          )}
        </div>
        <button className="btn" style={{ marginTop: 22 }} onClick={() => window.location.assign("/")}>
          Back to start
        </button>
      </div>
    );
  }
}
