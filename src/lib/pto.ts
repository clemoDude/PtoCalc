export const FREQUENCY_TO_WEEKS: Record<AccrualFrequency, number> = {
  week: 1.0,
  "every 2 weeks": 2.0,
  "twice a month": 52.0 / 24.0,
  month: 52.0 / 12.0,
  year: 52.0,
};

export const WEEKDAY_NAMES = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
] as const;

export const WORK_SCHEDULE_OPTIONS = [
  "Mon-Fri 8 hours",
  "9/80",
  "Custom",
] as const;

export type BalanceUnit = "hours" | "days";
export type AccrualFrequency = "week" | "every 2 weeks" | "twice a month" | "month" | "year";
export type WorkScheduleType = (typeof WORK_SCHEDULE_OPTIONS)[number];
export type CalculationMode = "range_auto" | "legacy_fixed";

export interface PTOTypeRecord {
  name: string;
  current_balance: number;
  balance_unit: BalanceUnit;
  accrual_amount: number;
  accrual_unit: BalanceUnit;
  accrual_frequency: AccrualFrequency;
  accrual_cap: number | null;
  rollover_limit: number | null;
}

export interface PlannedTimeOffEntry {
  start_date: string;
  end_date: string;
  pto_type: string;
  amount_hours: number;
  calculation_mode: CalculationMode;
  reason: string;
}

export interface CustomHoliday {
  label: string;
  date: string;
}

export interface AppStateShape {
  startDate: string;
  ptoDayHours: number;
  weeksToProject: number;
  workScheduleType: WorkScheduleType;
  customScheduleHours: number[];
  startingOffFriday: string;
  selectedHolidays: string[];
  customHolidays: CustomHoliday[];
  ptoTypes: PTOTypeRecord[];
  plannedTimeOff: PlannedTimeOffEntry[];
}

export interface HolidayOption {
  id: string;
  label: string;
  date: string;
  source: "federal" | "custom";
}

export interface SelectedHolidayRules {
  federalLabels: Set<string>;
  customDates: Set<string>;
}

export interface WorkSchedule {
  type: WorkScheduleType;
  custom_hours: number[];
  starting_off_friday: string;
}

export interface ProjectionRow {
  weekNumber: number;
  weekStart: string;
  weekEnd: string;
  balances: Record<string, number>;
  days: Record<string, number>;
  accrued: Record<string, number>;
  used: Record<string, number>;
  rolloverTrim: Record<string, number>;
}

export interface WarningRow {
  ptoType: string;
  belowOneDay: string | null;
  belowZero: string | null;
}

export interface EntryDetailRow {
  date: string;
  day: string;
  hoursUsed: number;
  daysUsed: number;
  detail: string;
}

export interface ProjectionResult {
  rows: ProjectionRow[];
  warnings: WarningRow[];
}

export function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

export function todayIso(): string {
  return formatIsoDate(new Date());
}

export function parseIsoDate(value: string): Date {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) {
    throw new Error(`Invalid ISO date: ${value}`);
  }
  const year = Number(match[1]);
  const month = Number(match[2]) - 1;
  const day = Number(match[3]);
  return new Date(Date.UTC(year, month, day));
}

export function formatIsoDate(value: Date): string {
  const year = value.getUTCFullYear();
  const month = `${value.getUTCMonth() + 1}`.padStart(2, "0");
  const day = `${value.getUTCDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function addDays(value: Date, days: number): Date {
  const clone = new Date(value.getTime());
  clone.setUTCDate(clone.getUTCDate() + days);
  return clone;
}

export function addWeeks(value: Date, weeks: number): Date {
  return addDays(value, weeks * 7);
}

export function pythonWeekday(value: Date): number {
  return (value.getUTCDay() + 6) % 7;
}

export function weekdayNameFromIso(value: string): string {
  return WEEKDAY_NAMES[pythonWeekday(parseIsoDate(value))];
}

export function mondayOf(dayValue: string | Date): string {
  const dateValue = typeof dayValue === "string" ? parseIsoDate(dayValue) : dayValue;
  return formatIsoDate(addDays(dateValue, -pythonWeekday(dateValue)));
}

export function compareIsoDates(a: string, b: string): number {
  if (a < b) return -1;
  if (a > b) return 1;
  return 0;
}

export function* dateRange(startValue: string, endValue: string): Generator<string> {
  let cursor = parseIsoDate(startValue);
  const end = parseIsoDate(endValue);
  while (cursor.getTime() <= end.getTime()) {
    yield formatIsoDate(cursor);
    cursor = addDays(cursor, 1);
  }
}

export function hoursFromValue(amount: number, unit: BalanceUnit, ptoDayHours: number): number {
  return unit === "hours" ? amount : amount * ptoDayHours;
}

export function daysFromHours(hours: number, ptoDayHours: number): number {
  return hours / ptoDayHours;
}

export function accrualHoursPerWeek(
  amount: number,
  unit: BalanceUnit,
  frequency: AccrualFrequency,
  ptoDayHours: number,
): number {
  return hoursFromValue(amount, unit, ptoDayHours) / FREQUENCY_TO_WEEKS[frequency];
}

export function normalizeOptionalLimit(value: unknown): number | null {
  if (value === null || value === undefined || value === "" || value === "none") {
    return null;
  }
  const limit = Number(value);
  if (Number.isNaN(limit) || limit < 0) {
    throw new Error("Cap and rollover limits cannot be negative.");
  }
  return limit;
}

export function limitHours(limitValue: number | null, unit: BalanceUnit, ptoDayHours: number): number | null {
  if (limitValue === null) {
    return null;
  }
  return hoursFromValue(limitValue, unit, ptoDayHours);
}

export function normalizeAccrualFrequency(frequency: string): AccrualFrequency {
  const normalized = frequency === "bi-weekly" ? "every 2 weeks" : frequency;
  if (!(normalized in FREQUENCY_TO_WEEKS)) {
    throw new Error(`Invalid accrual frequency: ${frequency}`);
  }
  return normalized as AccrualFrequency;
}

export function nthWeekdayOfMonth(year: number, month: number, weekday: number, occurrence: number): string {
  const firstDay = new Date(Date.UTC(year, month - 1, 1));
  const offset = (weekday - pythonWeekday(firstDay) + 7) % 7;
  return formatIsoDate(addDays(firstDay, offset + (occurrence - 1) * 7));
}

export function lastWeekdayOfMonth(year: number, month: number, weekday: number): string {
  const nextMonth = month === 12 ? new Date(Date.UTC(year + 1, 0, 1)) : new Date(Date.UTC(year, month, 1));
  let cursor = addDays(nextMonth, -1);
  while (pythonWeekday(cursor) !== weekday) {
    cursor = addDays(cursor, -1);
  }
  return formatIsoDate(cursor);
}

export function observedDate(dayValue: string): string {
  const dateValue = parseIsoDate(dayValue);
  const weekday = pythonWeekday(dateValue);
  if (weekday === 5) {
    return formatIsoDate(addDays(dateValue, -1));
  }
  if (weekday === 6) {
    return formatIsoDate(addDays(dateValue, 1));
  }
  return dayValue;
}

export function usFederalHolidays(year: number): Array<{ label: string; date: string }> {
  const holidays = [
    { label: "New Year's Day", date: observedDate(`${year}-01-01`) },
    { label: "Martin Luther King Jr. Day", date: nthWeekdayOfMonth(year, 1, 0, 3) },
    { label: "Washington's Birthday", date: nthWeekdayOfMonth(year, 2, 0, 3) },
    { label: "Memorial Day", date: lastWeekdayOfMonth(year, 5, 0) },
    { label: "Juneteenth", date: observedDate(`${year}-06-19`) },
    { label: "Independence Day", date: observedDate(`${year}-07-04`) },
    { label: "Labor Day", date: nthWeekdayOfMonth(year, 9, 0, 1) },
    { label: "Columbus Day", date: nthWeekdayOfMonth(year, 10, 0, 2) },
    { label: "Veterans Day", date: observedDate(`${year}-11-11`) },
    { label: "Thanksgiving Day", date: nthWeekdayOfMonth(year, 11, 3, 4) },
    { label: "Christmas Day", date: observedDate(`${year}-12-25`) },
  ];
  return holidays.sort((a, b) => compareIsoDates(a.date, b.date));
}

export function holidayOptionsForProjection(startDate: string, weeksToProject = 52): HolidayOption[] {
  const projectionEnd = formatIsoDate(addWeeks(parseIsoDate(startDate), weeksToProject));
  const options: HolidayOption[] = [];
  const seen = new Set<string>();
  const startYear = parseIsoDate(startDate).getUTCFullYear();
  const endYear = parseIsoDate(projectionEnd).getUTCFullYear();
  for (let year = startYear; year <= endYear; year += 1) {
    for (const holiday of usFederalHolidays(year)) {
      if (holiday.date >= startDate && holiday.date <= projectionEnd && !seen.has(holiday.date)) {
        seen.add(holiday.date);
        options.push({
          id: `federal:${holiday.label}`,
          label: holiday.label,
          date: holiday.date,
          source: "federal",
        });
      }
    }
  }
  return options;
}

export function customHolidayOptions(customHolidays: CustomHoliday[]): HolidayOption[] {
  return customHolidays
    .filter((entry) => entry?.label?.trim() && entry?.date)
    .map((entry) => ({
      id: `custom:${entry.date}`,
      label: entry.label.trim(),
      date: entry.date,
      source: "custom" as const,
    }))
    .sort((a, b) => compareIsoDates(a.date, b.date));
}

export function combinedHolidayOptions(
  startDate: string,
  weeksToProject: number,
  customHolidays: CustomHoliday[],
): HolidayOption[] {
  const options: HolidayOption[] = [];
  const seen = new Set<string>();
  for (const holiday of holidayOptionsForProjection(startDate, weeksToProject)) {
    if (!seen.has(holiday.id)) {
      seen.add(holiday.id);
      options.push(holiday);
    }
  }
  for (const holiday of customHolidayOptions(customHolidays)) {
    const existingIndex = options.findIndex((item) => item.id === holiday.id);
    if (existingIndex >= 0) {
      options.splice(existingIndex, 1);
    }
    options.push(holiday);
  }
  return options.sort((a, b) => compareIsoDates(a.date, b.date));
}

export function federalHolidayLabelForDate(dayValue: string): string | null {
  const year = parseIsoDate(dayValue).getUTCFullYear();
  for (const holiday of usFederalHolidays(year)) {
    if (holiday.date === dayValue) {
      return holiday.label;
    }
  }
  return null;
}

export function resolveSelectedHolidayRules(selectedHolidayValues: string[]): SelectedHolidayRules {
  const federalLabels = new Set<string>();
  const customDates = new Set<string>();
  for (const raw of selectedHolidayValues) {
    if (raw.startsWith("federal:")) {
      federalLabels.add(raw.split(":", 2)[1]);
      continue;
    }
    if (raw.startsWith("custom:")) {
      customDates.add(raw.split(":", 2)[1]);
      continue;
    }
    const holidayLabel = federalHolidayLabelForDate(raw);
    if (holidayLabel !== null) {
      federalLabels.add(holidayLabel);
    } else {
      customDates.add(raw);
    }
  }
  return { federalLabels, customDates };
}

export function isOffFriday980(dayValue: string, startingOffFriday: string): boolean {
  const day = parseIsoDate(dayValue);
  const anchor = parseIsoDate(startingOffFriday);
  if (pythonWeekday(day) !== 4) {
    return false;
  }
  const deltaDays = Math.round((day.getTime() - anchor.getTime()) / 86400000);
  return deltaDays % 14 === 0;
}

export function normalizeWorkSchedule(input: Partial<AppStateShape> | Record<string, unknown>): WorkSchedule {
  const raw = input as Record<string, unknown>;
  const rawType = String(input.workScheduleType ?? raw.work_schedule_type ?? "Mon-Fri 8 hours");
  const scheduleType = WORK_SCHEDULE_OPTIONS.includes(rawType as WorkScheduleType)
    ? (rawType as WorkScheduleType)
    : "Mon-Fri 8 hours";
  const rawHours = (input.customScheduleHours ?? raw.custom_schedule_hours ?? [8, 8, 8, 8, 8, 0, 0]) as unknown;
  const customHours = Array.isArray(rawHours) && rawHours.length === 7
    ? rawHours.map((value) => Math.max(0, Number(value)))
    : [8, 8, 8, 8, 8, 0, 0];
  const startingOffFriday = String(input.startingOffFriday ?? raw.starting_off_friday ?? todayIso());
  return {
    type: scheduleType,
    custom_hours: customHours,
    starting_off_friday: startingOffFriday,
  };
}

export function scheduledHoursForDay(
  dayValue: string,
  workSchedule: WorkSchedule,
  selectedHolidayRules: SelectedHolidayRules,
): number {
  const holidayLabel = federalHolidayLabelForDate(dayValue);
  if (
    (holidayLabel !== null && selectedHolidayRules.federalLabels.has(holidayLabel)) ||
    selectedHolidayRules.customDates.has(dayValue)
  ) {
    return 0;
  }

  const weekday = pythonWeekday(parseIsoDate(dayValue));
  if (workSchedule.type === "Mon-Fri 8 hours") {
    return weekday < 5 ? 8 : 0;
  }
  if (workSchedule.type === "9/80") {
    if (weekday >= 5) return 0;
    if (weekday <= 3) return 9;
    return isOffFriday980(dayValue, workSchedule.starting_off_friday) ? 0 : 8;
  }
  return Number(workSchedule.custom_hours[weekday] ?? 0);
}

export function distributeHoursByWeek(
  startValue: string,
  endValue: string,
  workSchedule: WorkSchedule,
  selectedHolidayRules: SelectedHolidayRules,
): { totalHours: number; hoursByWeek: Record<string, number>; workingDays: number } {
  if (compareIsoDates(endValue, startValue) < 0) {
    throw new Error("End date cannot be before the start date.");
  }
  let totalHours = 0;
  let workingDays = 0;
  const hoursByWeek: Record<string, number> = {};
  for (const dayValue of dateRange(startValue, endValue)) {
    const scheduledHours = scheduledHoursForDay(dayValue, workSchedule, selectedHolidayRules);
    if (scheduledHours <= 0) continue;
    totalHours += scheduledHours;
    workingDays += 1;
    const weekStart = mondayOf(dayValue);
    hoursByWeek[weekStart] = (hoursByWeek[weekStart] ?? 0) + scheduledHours;
  }
  return { totalHours, hoursByWeek, workingDays };
}

export function normalizePtoTypeRecord(item: Record<string, unknown>): PTOTypeRecord {
  const required = ["name", "current_balance", "balance_unit", "accrual_amount", "accrual_unit", "accrual_frequency"];
  for (const field of required) {
    if (!(field in item)) {
      throw new Error("Each PTO type must include all PTO fields.");
    }
  }
  const name = String(item.name).trim();
  if (!name) {
    throw new Error("PTO type names cannot be blank.");
  }
  const balanceUnit = String(item.balance_unit) as BalanceUnit;
  const accrualUnit = String(item.accrual_unit) as BalanceUnit;
  if (!["hours", "days"].includes(balanceUnit)) {
    throw new Error(`Invalid balance unit for ${name}.`);
  }
  if (!["hours", "days"].includes(accrualUnit)) {
    throw new Error(`Invalid accrual unit for ${name}.`);
  }
  return {
    name,
    current_balance: Number(item.current_balance),
    balance_unit: balanceUnit,
    accrual_amount: Number(item.accrual_amount),
    accrual_unit: accrualUnit,
    accrual_frequency: normalizeAccrualFrequency(String(item.accrual_frequency)),
    accrual_cap: normalizeOptionalLimit(item.accrual_cap),
    rollover_limit: normalizeOptionalLimit(item.rollover_limit),
  };
}

export function normalizeTimeOffEntry(
  entry: Record<string, unknown>,
  validNames: Set<string>,
  ptoDayHours: number,
): PlannedTimeOffEntry {
  if ("start_date" in entry && "end_date" in entry && "pto_type" in entry && "amount_hours" in entry) {
    const ptoType = String(entry.pto_type).trim();
    if (!validNames.has(ptoType)) {
      throw new Error(`Planned time off references unknown PTO type: ${ptoType}`);
    }
    const startDate = String(entry.start_date);
    const endDate = String(entry.end_date);
    if (compareIsoDates(endDate, startDate) < 0) {
      throw new Error("Planned time off end date cannot be before the start date.");
    }
    return {
      start_date: startDate,
      end_date: endDate,
      pto_type: ptoType,
      amount_hours: Number(entry.amount_hours),
      calculation_mode: String(entry.calculation_mode ?? "range_auto") as CalculationMode,
      reason: String(entry.reason ?? "").trim(),
    };
  }

  if ("date" in entry && "pto_type" in entry && "amount" in entry && "unit" in entry) {
    const ptoType = String(entry.pto_type).trim();
    if (!validNames.has(ptoType)) {
      throw new Error(`Planned time off references unknown PTO type: ${ptoType}`);
    }
    const unit = String(entry.unit) as BalanceUnit;
    if (!["hours", "days"].includes(unit)) {
      throw new Error(`Invalid planned time off unit for ${ptoType}.`);
    }
    const singleDate = String(entry.date);
    return {
      start_date: singleDate,
      end_date: singleDate,
      pto_type: ptoType,
      amount_hours: hoursFromValue(Number(entry.amount), unit, ptoDayHours),
      calculation_mode: "legacy_fixed",
      reason: String(entry.reason ?? "").trim(),
    };
  }

  throw new Error("Each planned time off entry must include either the new range fields or the legacy fields.");
}

export function createTimeOffEntry(
  startValue: string,
  endValue: string,
  ptoType: string,
  reason: string,
  workSchedule: WorkSchedule,
  selectedHolidayRules: SelectedHolidayRules,
): PlannedTimeOffEntry {
  if (!ptoType.trim()) {
    throw new Error("Please choose a PTO type.");
  }
  const distribution = distributeHoursByWeek(startValue, endValue, workSchedule, selectedHolidayRules);
  if (distribution.totalHours <= 0 || distribution.workingDays === 0) {
    throw new Error("That date range has no scheduled work hours after weekends, holidays, and off-days are excluded.");
  }
  return {
    start_date: startValue,
    end_date: endValue,
    pto_type: ptoType,
    amount_hours: distribution.totalHours,
    calculation_mode: "range_auto",
    reason: reason.trim(),
  };
}

export function buildTimeOffUsageByWeek(
  entries: PlannedTimeOffEntry[],
  workSchedule: WorkSchedule,
  selectedHolidayRules: SelectedHolidayRules,
): Record<string, number> {
  const usageByWeek: Record<string, number> = {};
  for (const entry of entries) {
    if (entry.calculation_mode === "legacy_fixed") {
      const key = `${mondayOf(entry.start_date)}|${entry.pto_type}`;
      usageByWeek[key] = (usageByWeek[key] ?? 0) + Number(entry.amount_hours);
      continue;
    }
    const distribution = distributeHoursByWeek(entry.start_date, entry.end_date, workSchedule, selectedHolidayRules);
    for (const [weekStart, amountHours] of Object.entries(distribution.hoursByWeek)) {
      const key = `${weekStart}|${entry.pto_type}`;
      usageByWeek[key] = (usageByWeek[key] ?? 0) + amountHours;
    }
  }
  return usageByWeek;
}

export function displayAmountHours(
  entry: PlannedTimeOffEntry,
  workSchedule: WorkSchedule,
  selectedHolidayRules: SelectedHolidayRules,
): number {
  if (entry.calculation_mode === "legacy_fixed") {
    return Number(entry.amount_hours);
  }
  return distributeHoursByWeek(entry.start_date, entry.end_date, workSchedule, selectedHolidayRules).totalHours;
}

export function describeDayForEntry(
  dayValue: string,
  workSchedule: WorkSchedule,
  selectedHolidayRules: SelectedHolidayRules,
): { usedHours: number; detail: string } {
  const holidayLabel = federalHolidayLabelForDate(dayValue);
  if (holidayLabel !== null && selectedHolidayRules.federalLabels.has(holidayLabel)) {
    return { usedHours: 0, detail: `Holiday off: ${holidayLabel}` };
  }
  if (selectedHolidayRules.customDates.has(dayValue)) {
    return { usedHours: 0, detail: "Custom holiday off" };
  }
  if (workSchedule.type === "Mon-Fri 8 hours") {
    return pythonWeekday(parseIsoDate(dayValue)) >= 5
      ? { usedHours: 0, detail: "Weekend" }
      : { usedHours: 8, detail: "Scheduled workday" };
  }
  if (workSchedule.type === "9/80") {
    const weekday = pythonWeekday(parseIsoDate(dayValue));
    if (weekday >= 5) return { usedHours: 0, detail: "Weekend" };
    if (weekday <= 3) return { usedHours: 9, detail: "Scheduled 9/80 workday" };
    return isOffFriday980(dayValue, workSchedule.starting_off_friday)
      ? { usedHours: 0, detail: "Off Friday" }
      : { usedHours: 8, detail: "On Friday" };
  }
  const customHours = Number(workSchedule.custom_hours[pythonWeekday(parseIsoDate(dayValue))] ?? 0);
  return customHours <= 0
    ? { usedHours: 0, detail: "Not scheduled" }
    : { usedHours: customHours, detail: "Scheduled custom workday" };
}

export function buildEntryDetailRows(
  entry: PlannedTimeOffEntry,
  workSchedule: WorkSchedule,
  selectedHolidayRules: SelectedHolidayRules,
  ptoDayHours: number,
): EntryDetailRow[] {
  if (entry.calculation_mode === "legacy_fixed") {
    return [
      {
        date: entry.start_date,
        day: weekdayNameFromIso(entry.start_date),
        hoursUsed: round2(entry.amount_hours),
        daysUsed: round2(daysFromHours(entry.amount_hours, ptoDayHours)),
        detail: "Legacy fixed PTO amount",
      },
    ];
  }
  const rows: EntryDetailRow[] = [];
  for (const dayValue of dateRange(entry.start_date, entry.end_date)) {
    const description = describeDayForEntry(dayValue, workSchedule, selectedHolidayRules);
    rows.push({
      date: dayValue,
      day: weekdayNameFromIso(dayValue),
      hoursUsed: round2(description.usedHours),
      daysUsed: round2(daysFromHours(description.usedHours, ptoDayHours)),
      detail: description.detail,
    });
  }
  return rows;
}

export function buildWarningRows(
  rows: ProjectionRow[],
  ptoTypes: PTOTypeRecord[],
  ptoDayHours: number,
): WarningRow[] {
  const warnings: WarningRow[] = [];
  for (const item of ptoTypes) {
    let belowOneDay: string | null = null;
    let belowZero: string | null = null;
    for (const row of rows) {
      const balance = row.balances[item.name];
      if (belowOneDay === null && balance >= 0 && balance < ptoDayHours) {
        belowOneDay = row.weekStart;
      }
      if (belowZero === null && balance < 0) {
        belowZero = row.weekStart;
      }
      if (belowOneDay !== null && belowZero !== null) {
        break;
      }
    }
    if (belowOneDay !== null || belowZero !== null) {
      warnings.push({
        ptoType: item.name,
        belowOneDay,
        belowZero,
      });
    }
  }
  return warnings;
}

export function projectBalances(state: AppStateShape): ProjectionResult {
  const workSchedule = normalizeWorkSchedule(state);
  const selectedHolidayRules = resolveSelectedHolidayRules(state.selectedHolidays);
  const balances: Record<string, number> = Object.fromEntries(
    state.ptoTypes.map((item) => [item.name, hoursFromValue(item.current_balance, item.balance_unit, state.ptoDayHours)]),
  );
  const caps: Record<string, number | null> = Object.fromEntries(
    state.ptoTypes.map((item) => [item.name, limitHours(item.accrual_cap, item.balance_unit, state.ptoDayHours)]),
  );
  const rolloverLimits: Record<string, number | null> = Object.fromEntries(
    state.ptoTypes.map((item) => [item.name, limitHours(item.rollover_limit, item.balance_unit, state.ptoDayHours)]),
  );
  const perWeekAccrual: Record<string, number> = Object.fromEntries(
    state.ptoTypes.map((item) => [
      item.name,
      accrualHoursPerWeek(item.accrual_amount, item.accrual_unit, item.accrual_frequency, state.ptoDayHours),
    ]),
  );
  const timeOffByWeek = buildTimeOffUsageByWeek(state.plannedTimeOff, workSchedule, selectedHolidayRules);
  const projectionStart = mondayOf(state.startDate);
  const rows: ProjectionRow[] = [];

  for (let weekIndex = 0; weekIndex < state.weeksToProject; weekIndex += 1) {
    const weekStartDate = addWeeks(parseIsoDate(projectionStart), weekIndex);
    const weekStart = formatIsoDate(weekStartDate);
    const weekEnd = formatIsoDate(addDays(weekStartDate, 6));
    const row: ProjectionRow = {
      weekNumber: weekIndex + 1,
      weekStart,
      weekEnd,
      balances: {},
      days: {},
      accrued: {},
      used: {},
      rolloverTrim: {},
    };

    for (const item of state.ptoTypes) {
      const name = item.name;
      let accrued = perWeekAccrual[name];
      const capHours = caps[name];
      if (capHours !== null) {
        accrued = Math.max(0, Math.min(accrued, capHours - balances[name]));
      }
      const used = timeOffByWeek[`${weekStart}|${name}`] ?? 0;
      balances[name] += accrued;
      balances[name] -= used;
      let rolloverTrim = 0;
      const rolloverLimit = rolloverLimits[name];
      if (parseIsoDate(weekStart).getUTCFullYear() !== parseIsoDate(weekEnd).getUTCFullYear() && rolloverLimit !== null) {
        const trimmedBalance = Math.min(balances[name], rolloverLimit);
        rolloverTrim = Math.max(0, balances[name] - trimmedBalance);
        balances[name] = trimmedBalance;
      }
      row.accrued[name] = round2(accrued);
      row.used[name] = round2(used);
      row.rolloverTrim[name] = round2(rolloverTrim);
      row.balances[name] = round2(balances[name]);
      row.days[name] = round2(daysFromHours(balances[name], state.ptoDayHours));
    }

    rows.push(row);
  }

  return { rows, warnings: buildWarningRows(rows, state.ptoTypes, state.ptoDayHours) };
}

export function buildExportPayload(state: AppStateShape): Record<string, unknown> {
  const workSchedule = normalizeWorkSchedule(state);
  const selectedHolidayRules = resolveSelectedHolidayRules(state.selectedHolidays);
  return {
    schema_version: 2,
    settings: {
      start_date: state.startDate,
      pto_day_hours: state.ptoDayHours,
      weeks_to_project: state.weeksToProject,
      work_schedule_type: workSchedule.type,
      custom_schedule_hours: workSchedule.custom_hours,
      starting_off_friday: workSchedule.starting_off_friday,
      selected_holidays: [...state.selectedHolidays],
      custom_holidays: state.customHolidays.map((item) => ({
        label: item.label.trim(),
        date: item.date,
      })),
    },
    pto_types: state.ptoTypes,
    planned_time_off: state.plannedTimeOff.map((entry) => ({
      start_date: entry.start_date,
      end_date: entry.end_date,
      pto_type: entry.pto_type,
      amount_hours: displayAmountHours(entry, workSchedule, selectedHolidayRules),
      calculation_mode: entry.calculation_mode,
      reason: entry.reason,
    })),
  };
}

export function loadImportPayload(payload: Record<string, unknown>): AppStateShape {
  const settings = (payload.settings ?? {}) as Record<string, unknown>;
  const ptoTypesRaw = Array.isArray(payload.pto_types) ? payload.pto_types : [];
  const plannedRaw = Array.isArray(payload.planned_time_off) ? payload.planned_time_off : [];

  const importedPtoTypes: PTOTypeRecord[] = [];
  const seenNames = new Set<string>();
  for (const item of ptoTypesRaw) {
    const normalized = normalizePtoTypeRecord(item as Record<string, unknown>);
    const lowered = normalized.name.toLowerCase();
    if (seenNames.has(lowered)) {
      throw new Error(`Duplicate PTO type found: ${normalized.name}`);
    }
    seenNames.add(lowered);
    importedPtoTypes.push(normalized);
  }

  const startDate = String(settings.start_date ?? todayIso());
  const ptoDayHours = Number(settings.pto_day_hours ?? settings.hours_per_day ?? 8);
  const weeksToProject = Number(settings.weeks_to_project ?? 52);
  const workSchedule = normalizeWorkSchedule({
    work_schedule_type: settings.work_schedule_type,
    custom_schedule_hours: settings.custom_schedule_hours,
    starting_off_friday: settings.starting_off_friday,
  });

  const selectedHolidaysRaw = Array.isArray(settings.selected_holidays) ? settings.selected_holidays : [];
  const customHolidaysRaw = Array.isArray(settings.custom_holidays) ? settings.custom_holidays : [];
  const selectedHolidayRules = resolveSelectedHolidayRules(selectedHolidaysRaw.map(String));
  const customHolidays = customHolidayOptions(
    customHolidaysRaw.map((entry) => ({
      label: String((entry as Record<string, unknown>).label ?? ""),
      date: String((entry as Record<string, unknown>).date ?? ""),
    })),
  ).map((item) => ({
    label: item.label,
    date: item.date,
  }));

  const plannedTimeOff = plannedRaw.map((entry) =>
    normalizeTimeOffEntry(entry as Record<string, unknown>, new Set(importedPtoTypes.map((item) => item.name)), ptoDayHours),
  );

  return {
    startDate,
    ptoDayHours,
    weeksToProject,
    workScheduleType: workSchedule.type,
    customScheduleHours: workSchedule.custom_hours,
    startingOffFriday: workSchedule.starting_off_friday,
    selectedHolidays: [
      ...Array.from(selectedHolidayRules.federalLabels).map((label) => `federal:${label}`),
      ...Array.from(selectedHolidayRules.customDates).map((date) => `custom:${date}`),
    ].sort(),
    customHolidays,
    ptoTypes: importedPtoTypes,
    plannedTimeOff,
  };
}

export function projectionRowsToCsv(rows: ProjectionRow[], ptoTypes: PTOTypeRecord[]): string {
  const headers = ["Week #", "Week Start", "Week End"];
  for (const item of ptoTypes) {
    headers.push(
      `${item.name} Accrued (hrs)`,
      `${item.name} Used (hrs)`,
      `${item.name} Rollover Trim (hrs)`,
      `${item.name} Balance (hrs)`,
      `${item.name} Balance (days)`,
    );
  }
  const lines = [headers.join(",")];
  for (const row of rows) {
    const values: Array<string | number> = [row.weekNumber, row.weekStart, row.weekEnd];
    for (const item of ptoTypes) {
      values.push(row.accrued[item.name], row.used[item.name], row.rolloverTrim[item.name], row.balances[item.name], row.days[item.name]);
    }
    lines.push(values.join(","));
  }
  return lines.join("\n");
}

export function defaultAppState(): AppStateShape {
  return {
    startDate: todayIso(),
    ptoDayHours: 8,
    weeksToProject: 52,
    workScheduleType: "Mon-Fri 8 hours",
    customScheduleHours: [8, 8, 8, 8, 8, 0, 0],
    startingOffFriday: todayIso(),
    selectedHolidays: [],
    customHolidays: [],
    ptoTypes: [],
    plannedTimeOff: [],
  };
}

