import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onReset?: () => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an unhandled error:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div className="bg-slate-900 border border-rose-500/30 rounded-2xl p-6 shadow-xl space-y-4 my-6">
          <div className="flex items-center gap-3 text-rose-400">
            <span className="text-xl">⚠️</span>
            <h3 className="font-bold text-base">Rendering Notice</h3>
          </div>
          <p className="text-xs text-slate-300">
            A temporary component error occurred while rendering this view.
          </p>
          {this.state.error && (
            <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 text-xs font-mono text-rose-300/80 overflow-x-auto">
              {this.state.error.message}
            </div>
          )}
          <button
            onClick={() => {
              this.setState({ hasError: false, error: null });
              if (this.props.onReset) this.props.onReset();
            }}
            className="px-4 py-2 bg-brand-500 hover:bg-brand-600 text-slate-950 font-bold rounded-xl text-xs transition"
          >
            Reset View & Return to Console
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

