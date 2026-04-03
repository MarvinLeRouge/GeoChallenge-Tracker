import { describe, it, expect } from "vitest";
import { ref } from "vue";
import { useCalendarData } from "@/composables/useCalendarData";
import type { CalendarResult } from "@/types/challenges";

const makeCalendarResult = (
  overrides: Partial<CalendarResult> = {},
): CalendarResult => ({
  completed_days: [],
  missing_days_by_month: {},
  completion_rate_365: 0,
  completion_rate_366: 0,
  ...overrides,
});

describe("calendarData", () => {
  it("returns empty structure when calendarResult is null", () => {
    const { calendarData } = useCalendarData(ref(null));
    expect(calendarData.value.months).toEqual([]);
    expect(calendarData.value.totalCompletionRate365).toBe(0);
    expect(calendarData.value.totalCompletionRate366).toBe(0);
  });

  it("builds 12 months", () => {
    const { calendarData } = useCalendarData(ref(makeCalendarResult()));
    expect(calendarData.value.months).toHaveLength(12);
  });

  it("assigns correct month names", () => {
    const { calendarData } = useCalendarData(ref(makeCalendarResult()));
    expect(calendarData.value.months[0].name).toBe("Janvier");
    expect(calendarData.value.months[11].name).toBe("Décembre");
  });

  it("gives January 31 days", () => {
    const { calendarData } = useCalendarData(ref(makeCalendarResult()));
    expect(calendarData.value.months[0].days).toHaveLength(31);
  });

  it("gives February 29 days (leap-year max)", () => {
    const { calendarData } = useCalendarData(ref(makeCalendarResult()));
    expect(calendarData.value.months[1].days).toHaveLength(29);
  });

  it("marks a completed day as isCompleted", () => {
    const result = makeCalendarResult({
      completed_days: [{ day: "03-15", count: 2 }],
    });
    const { calendarData } = useCalendarData(ref(result));
    const march = calendarData.value.months[2]; // index 2 = March
    const day15 = march.days.find((d) => d.day === 15)!;
    expect(day15.isCompleted).toBe(true);
    expect(day15.count).toBe(2);
    expect(day15.hasCache).toBe(true);
  });

  it("marks a missing day as isMissing", () => {
    const result = makeCalendarResult({
      missing_days_by_month: { "06": ["06-10"] },
    });
    const { calendarData } = useCalendarData(ref(result));
    const june = calendarData.value.months[5];
    const day10 = june.days.find((d) => d.day === 10)!;
    expect(day10.isMissing).toBe(true);
    expect(day10.hasCache).toBe(true);
  });

  it("counts completedCount and missingCount per month", () => {
    const result = makeCalendarResult({
      completed_days: [
        { day: "01-01", count: 1 },
        { day: "01-02", count: 1 },
      ],
      missing_days_by_month: { "01": ["01-03"] },
    });
    const { calendarData } = useCalendarData(ref(result));
    const jan = calendarData.value.months[0];
    expect(jan.completedCount).toBe(2);
    expect(jan.missingCount).toBe(1);
  });

  it("computes completionRate per month", () => {
    // 31 days in Jan, 1 completed → 1/31 * 100
    const result = makeCalendarResult({
      completed_days: [{ day: "01-01", count: 1 }],
    });
    const { calendarData } = useCalendarData(ref(result));
    const jan = calendarData.value.months[0];
    expect(jan.completionRate).toBeCloseTo((1 / 31) * 100);
  });

  it("converts completion_rate_365 to percentage", () => {
    const result = makeCalendarResult({ completion_rate_365: 0.75 });
    const { calendarData } = useCalendarData(ref(result));
    expect(calendarData.value.totalCompletionRate365).toBeCloseTo(75);
  });

  it("converts completion_rate_366 to percentage", () => {
    const result = makeCalendarResult({ completion_rate_366: 0.5 });
    const { calendarData } = useCalendarData(ref(result));
    expect(calendarData.value.totalCompletionRate366).toBeCloseTo(50);
  });

  it("reacts to calendarResult changes", () => {
    const calendarResult = ref<CalendarResult | null>(null);
    const { calendarData } = useCalendarData(calendarResult);
    expect(calendarData.value.months).toHaveLength(0);
    calendarResult.value = makeCalendarResult({ completion_rate_365: 0.5 });
    expect(calendarData.value.months).toHaveLength(12);
  });
});

describe("getDaysInMonth", () => {
  it("returns 31 for January (month 1)", () => {
    const { getDaysInMonth } = useCalendarData(ref(null));
    expect(getDaysInMonth(1)).toBe(31);
  });

  it("returns 29 for February (month 2)", () => {
    const { getDaysInMonth } = useCalendarData(ref(null));
    expect(getDaysInMonth(2)).toBe(29);
  });

  it("returns 30 for April (month 4)", () => {
    const { getDaysInMonth } = useCalendarData(ref(null));
    expect(getDaysInMonth(4)).toBe(30);
  });
});
