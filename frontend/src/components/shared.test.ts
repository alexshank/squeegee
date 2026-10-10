import { expect, test } from "vitest";
import { formatDuration } from "./shared";

test("an elapsed time is shown in whichever unit keeps it short", () => {
  expect(formatDuration(38)).toBe("38µs");
  expect(formatDuration(12_345)).toBe("12.3ms");
  expect(formatDuration(5_940_000)).toBe("5.94s");
  expect(formatDuration(125_000_000)).toBe("2m 05s");
});

test("a time that rounds up into the next unit is shown in that unit", () => {
  expect(formatDuration(999_950)).toBe("1.00s");
  expect(formatDuration(59_999_999)).toBe("1m 00s");
});
