import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { supabase } from "../lib/supabase";
import { useAuth } from "../context/AuthContext";

type Mode = "signin" | "signup";

// Login page — email/password auth via Supabase (sign in + register).
export default function Login() {
  const { session, loading: authLoading } = useAuth();
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const isSignup = mode === "signup";

  const toggleMode = () => {
    setMode(isSignup ? "signin" : "signup");
    setError(null);
    setNotice(null);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setNotice(null);
    setLoading(true);

    if (isSignup) {
      const { data, error: authError } = await supabase.auth.signUp({ email, password });
      if (authError) {
        setError(authError.message);
      } else if (data.session) {
        // Email confirmation disabled — session is live; AuthContext redirects.
        setNotice("Account created. Signing you in…");
      } else {
        // Email confirmation enabled — user must verify before signing in.
        setNotice("Account created. Check your email to confirm, then sign in.");
        setMode("signin");
      }
    } else {
      const { error: authError } = await supabase.auth.signInWithPassword({ email, password });
      if (authError) setError(authError.message);
    }

    setLoading(false);
  };

  // Already authenticated — don't show the login form, go to the app.
  if (!authLoading && session) {
    return <Navigate to="/" replace />;
  }

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: "100vh",
        fontFamily: "system-ui, sans-serif",
        background: "#f7f8fa",
      }}
    >
      <div
        style={{
          background: "#fff",
          border: "1px solid #e5e7eb",
          borderRadius: 8,
          padding: "36px 40px",
          width: 360,
        }}
      >
        <h2 style={{ margin: "0 0 24px", fontSize: 22 }}>
          Imperium — {isSignup ? "Create account" : "Sign in"}
        </h2>
        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <label style={{ fontSize: 13, fontWeight: 600 }}>
            Email
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={{
                display: "block",
                width: "100%",
                marginTop: 4,
                padding: "8px 10px",
                border: "1px solid #d1d5db",
                borderRadius: 6,
                fontSize: 14,
                boxSizing: "border-box",
              }}
            />
          </label>
          <label style={{ fontSize: 13, fontWeight: 600 }}>
            Password
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={{
                display: "block",
                width: "100%",
                marginTop: 4,
                padding: "8px 10px",
                border: "1px solid #d1d5db",
                borderRadius: 6,
                fontSize: 14,
                boxSizing: "border-box",
              }}
            />
          </label>
          {error && (
            <p style={{ margin: 0, color: "#dc2626", fontSize: 13 }}>{error}</p>
          )}
          {notice && (
            <p style={{ margin: 0, color: "#16a34a", fontSize: 13 }}>{notice}</p>
          )}
          <button
            type="submit"
            disabled={loading}
            style={{
              marginTop: 6,
              padding: "10px",
              background: loading ? "#93c5fd" : "#3b82f6",
              color: "#fff",
              border: "none",
              borderRadius: 6,
              fontSize: 14,
              fontWeight: 600,
              cursor: loading ? "not-allowed" : "pointer",
            }}
          >
            {loading
              ? isSignup
                ? "Creating account…"
                : "Signing in…"
              : isSignup
                ? "Register"
                : "Sign in"}
          </button>
        </form>
        <p style={{ margin: "20px 0 0", fontSize: 13, textAlign: "center", color: "#6b7280" }}>
          {isSignup ? "Already have an account?" : "Don't have an account?"}{" "}
          <button
            type="button"
            onClick={toggleMode}
            style={{
              background: "none",
              border: "none",
              padding: 0,
              color: "#3b82f6",
              fontSize: 13,
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            {isSignup ? "Sign in" : "Register"}
          </button>
        </p>
      </div>
    </div>
  );
}
