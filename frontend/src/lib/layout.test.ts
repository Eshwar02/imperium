import { describe, it, expect, beforeEach } from "vitest";
import { clampSize, loadSize, saveSize } from "./layout";

describe("clampSize", () => {
  it("clamps into range and rounds", () => {
    expect(clampSize(50, 100, 300)).toBe(100);
    expect(clampSize(500, 100, 300)).toBe(300);
    expect(clampSize(180.6, 100, 300)).toBe(181);
  });
  it("falls back to min for non-finite input", () => {
    expect(clampSize(NaN, 120, 400)).toBe(120);
    expect(clampSize(Infinity, 120, 400)).toBe(120);
  });
});

describe("loadSize / saveSize", () => {
  beforeEach(() => localStorage.clear());

  it("returns the clamped fallback when nothing is stored", () => {
    expect(loadSize("sidebar", 300, 180, 560)).toBe(300);
    expect(loadSize("sidebar", 999, 180, 560)).toBe(560);
  });

  it("round-trips a saved size, clamped on read", () => {
    saveSize("sidebar", 420);
    expect(loadSize("sidebar", 300, 180, 560)).toBe(420);
    saveSize("sidebar", 9999);
    expect(loadSize("sidebar", 300, 180, 560)).toBe(560);
  });

  it("ignores corrupt stored values", () => {
    localStorage.setItem("imperium.layout.sidebar", "not-a-number");
    expect(loadSize("sidebar", 300, 180, 560)).toBe(300);
  });
});
