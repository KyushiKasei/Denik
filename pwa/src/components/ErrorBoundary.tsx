import { Component, type ReactNode } from "react";

export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError(): { failed: boolean } {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return (
        <p className="error" role="alert">
          Něco se nepovedlo. Obnovte stránku.
        </p>
      );
    }
    return this.props.children;
  }
}
