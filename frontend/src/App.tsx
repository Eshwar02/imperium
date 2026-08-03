import { Link, Outlet } from "react-router-dom";
import { useAuth } from "./context/AuthContext";

// App shell — nav across the governed pipeline (PRD §7). Pages are foundation stubs.
export default function App() {
  const { user, signOut } = useAuth();

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", height: "100vh", display: "flex", flexDirection: "column" }}>
      <header style={{ padding: "12px 20px", borderBottom: "1px solid #ddd", display: "flex", gap: 20, alignItems: "center" }}>
        <strong style={{ fontSize: 18 }}>Imperium</strong>
        <nav style={{ display: "flex", gap: 16, flex: 1 }}>
          <Link to="/">Structure Map</Link>
          <Link to="/gate-a">Gate A</Link>
          <Link to="/gate-b">Gate B</Link>
        </nav>
        <span style={{ fontSize: 13, color: "#57606a", marginRight: 12 }}>{user?.email}</span>
        <button
          onClick={signOut}
          style={{
            fontSize: 13,
            padding: "4px 12px",
            border: "1px solid #d1d5db",
            borderRadius: 5,
            background: "#fff",
            cursor: "pointer",
          }}
        >
          Sign out
        </button>
      </header>
      <main style={{ flex: 1, minHeight: 0 }}>
        <Outlet />
      </main>
    </div>
  );
}
