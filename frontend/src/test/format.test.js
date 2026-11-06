import { describe, expect, it } from "vitest";
import { firstName, shiftDate, todayISO } from "../utils/format";

describe("format helpers", () => {
  it("uses the local calendar date", () => {
    expect(todayISO(new Date(2026, 0, 5, 23, 30))).toBe("2026-01-05");
  });
  it("shifts dates across month boundaries", () => {
    expect(shiftDate("2026-03-01", -1)).toBe("2026-02-28");
  });
  it("extracts a first name", () => {
    expect(firstName("  Asha   Rao ")).toBe("Asha");
    expect(firstName("")).toBe("there");
  });
});
