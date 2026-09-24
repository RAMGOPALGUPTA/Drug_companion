import React from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext.jsx";
import { useTheme } from "../theme/ThemeContext.jsx";

export function Profile() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="page-stack">
      <section className="profile-hero panel">
        <div className="profile-avatar">{user?.name?.slice(0, 2).toUpperCase() || "FO"}</div>
        <div>
          <div className="panel-eyebrow">OFFICER PROFILE</div>
          <h2>{user?.name || "Field Officer"}</h2>
          <p>{user?.role || "Field Officer"} · {user?.id || "—"}</p>
        </div>
      </section>

      <section className="content-grid two-col">
        <div className="panel profile-details">
          <div className="panel-head">
            <div><div className="panel-eyebrow">IDENTITY</div><h2>Officer details</h2></div>
          </div>
          <div className="profile-grid">
            <div><span>NAME</span><strong>{user?.name || "—"}</strong></div>
            <div><span>OFFICER ID</span><strong>{user?.id || "—"}</strong></div>
            <div><span>EMAIL</span><strong>{user?.email || "—"}</strong></div>
            <div><span>ROLE</span><strong>{user?.role || "—"}</strong></div>
            <div><span>UNIT</span><strong>{user?.station || "—"}</strong></div>
            <div><span>SESSION</span><strong>Authenticated</strong></div>
          </div>
        </div>

        <div className="panel profile-details">
          <div className="panel-head">
            <div><div className="panel-eyebrow">PREFERENCES</div><h2>Console settings</h2></div>
          </div>
          <button className="preference-row" type="button" onClick={toggleTheme}>
            <span>
              <strong>{theme === "dark" ? "Dark workspace" : "Soft light workspace"}</strong>
              <small>Low-glare interface theme</small>
            </span>
            <b>{theme === "dark" ? "☾" : "☀"}</b>
          </button>
          <button className="signout-button" type="button" onClick={() => { logout(); navigate("/"); }}>
            Sign out of field console
          </button>
        </div>
      </section>
    </div>
  );
}
