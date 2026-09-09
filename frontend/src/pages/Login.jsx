import { useEffect, useState } from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import { loginUrl } from "../api/client";
import { useAuth } from "../context/AuthContext";
import LoadingSpinner from "../components/ui/LoadingSpinner";

const AUTH_ERRORS = {
  invalid_oauth_state: "GitHub sign-in was interrupted. Please try again.",
  token_exchange_failed: "Could not complete GitHub sign-in. Check your OAuth app credentials.",
  auth_failed: "Sign-in failed. Please try again.",
};

export default function Login() {
  const { user, loading } = useAuth();
  const [searchParams] = useSearchParams();
  const authError = AUTH_ERRORS[searchParams.get("error")] || null;
  const [oauthSetup, setOauthSetup] = useState(null);

  useEffect(() => {
    fetch("/auth/oauth-config", { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setOauthSetup(data))
      .catch(() => {});
  }, []);

  if (loading) return <LoadingSpinner />;
  if (user) return <Navigate to="/dashboard" replace />;

  return (
    <div className="login-page">
      <div className="login-card">
        {authError && <div className="error-banner">{authError}</div>}
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
        {oauthSetup && (
          <p className="login-note login-oauth-setup">
            
            {" "}
            
          </p>
        )}
      </div>
    </div>
  );
}
