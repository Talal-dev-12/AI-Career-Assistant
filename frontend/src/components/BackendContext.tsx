"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";

type BackendType = "mabd" | "talha";

interface BackendContextProps {
  activeBackend: BackendType;
  setActiveBackend: (backend: BackendType) => void;
  apiUrl: string;
  userId: string | null;
  loading: boolean;
  registerUser: () => Promise<string | null>;
}

const BackendContext = createContext<BackendContextProps | undefined>(undefined);

export function BackendProvider({ children }: { children: React.ReactNode }) {
  const [activeBackend, setActiveBackendState] = useState<BackendType>("talha");
  const [userId, setUserId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Read unified API URL from environment variables
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const setActiveBackend = (backend: BackendType) => {
    setActiveBackendState(backend);
    localStorage.setItem("active_backend", backend);
  };

  // Handle register user in unified database
  const registerUser = useCallback(async (customEmail?: string, customName?: string): Promise<string | null> => {
    setLoading(true);
    const key = "unified_user_id";

    const email = customEmail || localStorage.getItem("userEmail") || `john.doe.${Date.now()}@example.com`;
    const fullName = customName || localStorage.getItem("userName") || "John Doe";

    try {
      const parts = fullName.split(" ");
      const firstName = parts[0];
      const lastName = parts.slice(1).join(" ");
      
      const res = await fetch(`${apiUrl}/users`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          full_name: fullName,
          first_name: firstName,
          last_name: lastName,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        const newId = String(data.user_id || data.id);
        localStorage.setItem(key, newId);
        if (customEmail) localStorage.setItem("userEmail", customEmail);
        if (customName) localStorage.setItem("userName", customName);
        setUserId(newId);
        setLoading(false);
        return newId;
      }
    } catch (err) {
      console.error("Failed to register unified user:", err);
    }

    const storedId = localStorage.getItem(key);
    if (storedId) {
      setUserId(storedId);
      setLoading(false);
      return storedId;
    }

    setLoading(false);
    return null;
  }, [apiUrl]);

  // Sync state on load
  useEffect(() => {
    const saved = localStorage.getItem("active_backend") as BackendType;
    if (saved === "mabd" || saved === "talha") {
      setActiveBackendState(saved);
    }
    registerUser();
  }, [registerUser]);

  return (
    <BackendContext.Provider
      value={{
        activeBackend,
        setActiveBackend,
        apiUrl,
        userId,
        loading,
        registerUser,
      }}
    >
      {children}
    </BackendContext.Provider>
  );
}

export function useBackend() {
  const context = useContext(BackendContext);
  if (!context) {
    throw new Error("useBackend must be used within a BackendProvider");
  }
  return context;
}
