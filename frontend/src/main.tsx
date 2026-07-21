import React from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import App from "./App";
import StructureMap from "./pages/StructureMap";
import GateA from "./pages/GateA";
import GateB from "./pages/GateB";

const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <StructureMap /> },
      { path: "gate-a", element: <GateA /> },
      { path: "gate-b", element: <GateB /> },
    ],
  },
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>
);
