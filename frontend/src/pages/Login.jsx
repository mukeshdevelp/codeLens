import { Navigate } from "react-router-dom";
import { loginUrl } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const { user, loading } = useAuth();
  if (loading) return <div className="page-center"><div className="spinner" /></div>;
  if (user) return <Navigate to="/dashboard" replace />;

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-badge">PR Review Intelligence</div>
        <h1>CodeLens</h1>
        <p className="login-subtitle">
          Understand a pull request before reviewing it. Connect GitHub to analyze risk,
          scope drift, security signals, and where to focus your review.
        </p>
        <ul className="login-features">
          <li>Change volume & scope drift detection</li>
          <li>Critical path & security scanning</li>
          <li>Test coverage gap analysis</li>
          <li>AI-powered executive summary</li>
        </ul>
        <a href={loginUrl()} className="btn github">Continue with GitHub</a>
        <p className="login-note">We request read access to your repositories to analyze pull requests.</p>
      </div>
    </div>
  );
}
