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
  const registerUser = useCallback(async (): Promise<string | null> => {
    setLoading(true);
    const key = "unified_user_id";
    const storedId = localStorage.getItem(key);

    if (storedId) {
      setUserId(storedId);
      setLoading(false);
      return storedId;
    }

    try {
      const email = `john.doe.${Date.now()}@example.com`;
      const res = await fetch(`${apiUrl}/users`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          full_name: "John Doe",
          first_name: "John",
          last_name: "Doe",
        }),
      });
      if (res.ok) {
        const data = await res.json();
        const newId = String(data.user_id || data.id);
        localStorage.setItem(key, newId);
        setUserId(newId);
        setLoading(false);
        return newId;
      }
    } catch (err) {
      console.error("Failed to register unified test user:", err);
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
