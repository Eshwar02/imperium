# Imperium IDE — VS Code UI Parity (Design)

Date: 2026-08-24
Status: Approved (direction B)

## Goal

Make the Imperium frontend feel like complete IDE software by deepening the existing
VS Code-style workbench with the "controls" that are still missing. We **reimplement**
VS Code's UI behaviour in our React 18 + Vite + TypeScript stack, using VS Code as a
*design reference only*. No VS Code source code is copied. See `frontend/ATTRIBUTIONS.md`.

## Non-goals

- Not forking VS Code (rejected direction A).
- Not copying VS Code TypeScript source (rejected direction C beyond Monaco, already present).
- No new backend work; UI-only unless a control needs a trivial data hook.

## Existing baseline

Workbench shell already exists: `TitleBar` (menus), `ActivityBar`, `SideBar`
(Explorer/Search/SCM), `EditorArea` (tabs + Monaco + breadcrumb stub), `Panel`
(Problems/Output/Terminal/Runs), `StatusBar`, `ChatPanel`, `Resizer`, a Command Palette,
plus `WorkbenchContext` for shell state and `theme.ts` tokens.

## Architecture principles

- One source of truth for theme tokens (`theme.ts`); every new control reads from it.
- Global UI services provided via React context, mounted once at the app root:
  - `CommandContext` — command registry + keybinding dispatch.
  - `NotificationContext` — toast/notification queue.
  - `ContextMenuContext` — right-click menu portal.
- Each control is a self-contained component with a narrow prop interface, independently
  testable, matching existing file conventions in `components/workbench` and `components/ui`.

## Build increments (each = its own commit, pushed to main)

1. Spec + `ATTRIBUTIONS.md`.
2. Theme: add light-theme palette, elevation/shadow tokens, `ThemeContext`.
3. `ContextMenu` primitive + `useContextMenu` hook (portal, keyboard nav, dividers).
4. `Notifications` service + toaster (info/warn/error, auto-dismiss, actions).
5. `Tooltip` primitive.
6. Command registry (`lib/commands.ts`) + keybinding map + `CommandContext`.
7. Command Palette rewired to the registry (all commands + keybinding hints).
8. Editor tabs: dirty dot, preview italics, per-tab context menu (close / close others /
   close all / copy path), overflow dropdown.
9. Split editor group (side-by-side) — optional, behind existing layout.
10. Real breadcrumbs from the active file path.
11. SideBar collapsible sections: Open Editors, Outline, Timeline.
12. ActivityBar badges + account/settings menu.
13. Panel toolbar: maximize, clear, close; real Problems list.
14. StatusBar rich items (branch, problems counts, ln/col, language, EOL) + notifications bell.
15. Settings editor + light/dark theme toggle wired to the gear.

Order may adjust; foundational services (2–6) come before consumers.

## Testing

Vitest + RTL already configured in `frontend/`. Each interactive control gets a smoke test
(renders, opens, primary action fires) following the existing `*.test.tsx` pattern.

## Licensing / compliance

Reimplementation only. `ATTRIBUTIONS.md` credits Microsoft VS Code (MIT) as the design
reference and states no source was copied. Monaco (already a dependency) remains under its
own MIT license.
