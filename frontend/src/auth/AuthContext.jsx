import React, { createContext, useContext, useMemo, useState } from "react";

const STORAGE_KEY = "drug_companion_auth_user";

const DEMO_OFFICER = {
  id: "FO-0017",
  name: "Field Officer",
  email: "officer@drugcompanion.local",
  role: "Field Officer",
  station: "Mobile Operations",
};

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  async function login(identifier, password) {
    const value = identifier.trim().toLowerCase();
    const validIdentifier =
      value === DEMO_OFFICER.email || value === DEMO_OFFICER.id.toLowerCase();

    // Frontend prototype credential gate. Replace with the backend auth API
    // before production deployment; credentials must never live in the client.
    if (!validIdentifier || password !== "Field@123") {
      throw new Error("Invalid officer ID/email or password.");
    }

    localStorage.setItem(STORAGE_KEY, JSON.stringify(DEMO_OFFICER));
    setUser(DEMO_OFFICER);
    return DEMO_OFFICER;
  }

  function logout() {
    localStorage.removeItem(STORAGE_KEY);
    setUser(null);
  }

  const value = useMemo(() => ({ user, login, logout }), [user]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}

export const demoOfficer = DEMO_OFFICER;
