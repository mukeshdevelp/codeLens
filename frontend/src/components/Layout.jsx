import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Layout({ children, title }) {
  const { user, logout } = useAuth();

  return (
    <div className="layout">
      <header className="header">
        <div className="header-left">
          <Link to="/dashboard" className="brand">CodeLens</Link>
          {title && <span className="header-title">{title}</span>}
        </div>
        {user && (
          <div className="header-right">
            <img src={user.avatarUrl || ""} alt="" className="avatar" />
            <span>{user.name || user.login}</span>
            <button type="button" className="btn ghost" onClick={logout}>Logout</button>
          </div>
        )}
      </header>
      <main className="main">{children}</main>
    </div>
  );
}
