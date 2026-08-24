import React from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { RepoProvider } from "./context/RepoContext";
import { WorkbenchProvider } from "./context/WorkbenchContext";
import { ThemeProvider } from "./context/ThemeContext";
import RequireAuth from "./components/RequireAuth";
import App from "./App";
import Login from "./pages/Login";
import { applyTheme, type ThemeName } from "./theme";

// Apply the persisted palette before first paint (avoids a flash of unset CSS vars).
applyTheme((localStorage.getItem("imperium.theme") as ThemeName) || "dark");

const router = createBrowserRouter([
  { path: "/login", element: <Login /> },
  {
    path: "/",
    element: (
      <RequireAuth>
        <RepoProvider>
          <WorkbenchProvider>
            <App />
          </WorkbenchProvider>
        </RepoProvider>
      </RequireAuth>
    ),
  },
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </ThemeProvider>
  </React.StrictMode>
);
