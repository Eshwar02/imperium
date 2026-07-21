import { Link, Outlet } from "react-router-dom";

// App shell — nav across the governed pipeline (PRD §7). Pages are foundation stubs.
export default function App() {
  return (
    <div style={{ fontFamily: "system-ui, sans-serif", height: "100vh", display: "flex", flexDirection: "column" }}>
      <header style={{ padding: "12px 20px", borderBottom: "1px solid #ddd", display: "flex", gap: 20, alignItems: "center" }}>
        <strong style={{ fontSize: 18 }}>Imperium</strong>
        <nav style={{ display: "flex", gap: 16 }}>
          <Link to="/">Structure Map</Link>
          <Link to="/gate-a">Gate A</Link>
          <Link to="/gate-b">Gate B</Link>
        </nav>
      </header>
      <main style={{ flex: 1, minHeight: 0 }}>
        <Outlet />
      </main>
    </div>
  );
}
