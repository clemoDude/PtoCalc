import { ChangeEvent, ReactNode, startTransition, useEffect, useId, useRef, useState } from "react";
import {
  AppStateShape,
  EntryDetailRow,
  PTOTypeRecord,
  PlannedTimeOffEntry,
  ProjectionRow,
  WORK_SCHEDULE_OPTIONS,
  WEEKDAY_NAMES,
  buildEntryDetailRows,
  buildExportPayload,
  combinedHolidayOptions,
  createTimeOffEntry,
  daysFromHours,
  defaultAppState,
  displayAmountHours,
  loadImportPayload,
  normalizePtoTypeRecord,
  normalizeWorkSchedule,
  projectBalances,
  projectionRowsToCsv,
  resolveSelectedHolidayRules,
} from "./lib/pto";

const LOCAL_STORAGE_KEY = "ptocalc_state_v1";

interface PTOFormState {
  name: string;
  current_balance: number;
  balance_unit: "hours" | "days";
  accrual_amount: number;
  accrual_unit: "hours" | "days";
  accrual_frequency: PTOTypeRecord["accrual_frequency"];
  accrual_cap: string;
  rollover_limit: string;
}

interface TimeOffFormState {
  start_date: string;
  end_date: string;
  pto_type: string;
  reason: string;
}

function buildDefaultPtoForm(): PTOFormState {
  return {
    name: "",
    current_balance: 0,
    balance_unit: "hours",
    accrual_amount: 0,
    accrual_unit: "hours",
    accrual_frequency: "week",
    accrual_cap: "",
    rollover_limit: "",
  };
}

function buildDefaultTimeOffForm(state: AppStateShape): TimeOffFormState {
  return {
    start_date: state.startDate,
    end_date: state.startDate,
    pto_type: state.ptoTypes[0]?.name ?? "",
    reason: "",
  };
}

function ptoFormFromRecord(record: PTOTypeRecord): PTOFormState {
  return {
    name: record.name,
    current_balance: record.current_balance,
    balance_unit: record.balance_unit,
    accrual_amount: record.accrual_amount,
    accrual_unit: record.accrual_unit,
    accrual_frequency: record.accrual_frequency,
    accrual_cap: record.accrual_cap === null ? "" : `${record.accrual_cap}`,
    rollover_limit: record.rollover_limit === null ? "" : `${record.rollover_limit}`,
  };
}

function timeOffFormFromEntry(entry: PlannedTimeOffEntry): TimeOffFormState {
  return {
    start_date: entry.start_date,
    end_date: entry.end_date,
    pto_type: entry.pto_type,
    reason: entry.reason,
  };
}

function downloadTextFile(filename: string, content: string, mimeType: string): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function loadInitialAppState(): AppStateShape {
  const defaults = defaultAppState();
  if (typeof window === "undefined") {
    return defaults;
  }
  try {
    const stored = window.localStorage.getItem(LOCAL_STORAGE_KEY);
    if (!stored) {
      return defaults;
    }
    return loadImportPayload(JSON.parse(stored));
  } catch {
    return defaults;
  }
}

function Section({ title, children, defaultOpen = false }: { title: string; children: ReactNode; defaultOpen?: boolean }) {
  return (
    <details className="section-card" open={defaultOpen}>
      <summary>{title}</summary>
      <div className="section-body">{children}</div>
    </details>
  );
}

function MetricCard({ label, hours, days }: { label: string; hours: number; days: number }) {
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{hours.toFixed(2)} hrs</div>
      <div className="metric-subtle">{days.toFixed(2)} days</div>
    </div>
  );
}

function ProjectionChart({ rows, names }: { rows: ProjectionRow[]; names: string[] }) {
  if (rows.length === 0 || names.length === 0) {
    return null;
  }
  const width = 900;
  const height = 260;
  const padding = 46;
  const allValues = rows.flatMap((row) => names.map((name) => row.balances[name]));
  const minValue = Math.min(0, ...allValues);
  const maxValue = Math.max(0, ...allValues);
  const range = Math.max(maxValue - minValue, 1);
  const colors = ["#b45309", "#0f766e", "#1d4ed8", "#b91c1c", "#7c3aed", "#334155"];
  const tickCount = Math.min(5, rows.length);
  const tickIndexes = Array.from({ length: tickCount }, (_, index) =>
    Math.round((index / Math.max(tickCount - 1, 1)) * (rows.length - 1)),
  );
  const yTicks = [minValue, (minValue + maxValue) / 2, maxValue].map((value) => ({
    value,
    y: height - padding - ((value - minValue) / range) * (height - padding * 2),
  }));

  const pointsFor = (name: string) =>
    rows
      .map((row, index) => {
        const x = padding + (index / Math.max(rows.length - 1, 1)) * (width - padding * 2);
        const y = height - padding - ((row.balances[name] - minValue) / range) * (height - padding * 2);
        return `${x},${y}`;
      })
      .join(" ");

  const zeroY = height - padding - ((0 - minValue) / range) * (height - padding * 2);

  return (
    <div className="chart-shell">
      <svg viewBox={`0 0 ${width} ${height}`} className="chart-svg" role="img" aria-label="PTO balance chart">
        <text x={width / 2} y={22} textAnchor="middle" className="chart-axis-label">
          Weekly PTO Balance Projection
        </text>
        {yTicks.map((tick) => (
          <g key={tick.value}>
            <line x1={padding} y1={tick.y} x2={width - padding} y2={tick.y} className="chart-grid" />
            <text x={padding - 10} y={tick.y + 4} textAnchor="end" className="chart-tick-label">
              {tick.value.toFixed(0)}h
            </text>
          </g>
        ))}
        <line x1={padding} y1={zeroY} x2={width - padding} y2={zeroY} className="chart-zero" />
        <line x1={padding} y1={padding} x2={padding} y2={height - padding} className="chart-axis" />
        <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} className="chart-axis" />
        {names.map((name, index) => (
          <polyline
            key={name}
            fill="none"
            stroke={colors[index % colors.length]}
            strokeWidth="3"
            points={pointsFor(name)}
          />
        ))}
        {tickIndexes.map((rowIndex) => {
          const x = padding + (rowIndex / Math.max(rows.length - 1, 1)) * (width - padding * 2);
          return (
            <text key={rows[rowIndex].weekStart} x={x} y={height - 16} textAnchor="middle" className="chart-tick-label">
              {rows[rowIndex].weekStart}
            </text>
          );
        })}
        <text x={18} y={height / 2} textAnchor="middle" className="chart-axis-label" transform={`rotate(-90 18 ${height / 2})`}>
          Balance Hours
        </text>
        <text x={width / 2} y={height - 2} textAnchor="middle" className="chart-axis-label">
          Week Start
        </text>
      </svg>
      <div className="chart-legend">
        {names.map((name, index) => (
          <span key={name} className="legend-item">
            <span className="legend-swatch" style={{ backgroundColor: colors[index % colors.length] }} />
            {name}
          </span>
        ))}
      </div>
    </div>
  );
}

function DetailTable({ rows }: { rows: EntryDetailRow[] }) {
  return (
    <div className="detail-table-wrap">
      <table className="data-table compact-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Day</th>
            <th>Hours Used</th>
            <th>Days Used</th>
            <th>Detail</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.date}-${row.detail}`}>
              <td>{row.date}</td>
              <td>{row.day}</td>
              <td>{row.hoursUsed.toFixed(2)}</td>
              <td>{row.daysUsed.toFixed(2)}</td>
              <td>{row.detail}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function App() {
  const [appState, setAppState] = useState<AppStateShape>(() => loadInitialAppState());
  const initialState = appState;
  const [ptoEditSelection, setPtoEditSelection] = useState<string>("Add new PTO type");
  const [timeOffEditSelection, setTimeOffEditSelection] = useState<string>("Add new planned time off");
  const [editingPtoName, setEditingPtoName] = useState<string | null>(null);
  const [editingTimeOffIndex, setEditingTimeOffIndex] = useState<number | null>(null);
  const [ptoForm, setPtoForm] = useState<PTOFormState>(buildDefaultPtoForm());
  const [timeOffForm, setTimeOffForm] = useState<TimeOffFormState>(buildDefaultTimeOffForm(initialState));
  const [expandedTimeOffDetails, setExpandedTimeOffDetails] = useState<number | null>(null);
  const [newHolidayLabel, setNewHolidayLabel] = useState("");
  const [newHolidayDate, setNewHolidayDate] = useState(initialState.startDate);
  const [flashMessage, setFlashMessage] = useState<string | null>(null);
  const importInputId = useId();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const workSchedule = normalizeWorkSchedule(appState);
  const selectedHolidayRules = resolveSelectedHolidayRules(appState.selectedHolidays);
  const holidayOptions = combinedHolidayOptions(appState.startDate, appState.weeksToProject, appState.customHolidays);
  const projection = projectBalances(appState);
  const finalProjectionRow = projection.rows.length > 0 ? projection.rows[projection.rows.length - 1] : null;

  const timeOffPreview = (() => {
    if (!timeOffForm.pto_type) {
      return { error: null as string | null, totalHours: 0, workingDays: 0 };
    }
    try {
      const entry = createTimeOffEntry(
        timeOffForm.start_date,
        timeOffForm.end_date,
        timeOffForm.pto_type,
        timeOffForm.reason,
        workSchedule,
        selectedHolidayRules,
      );
      const totalHours = displayAmountHours(entry, workSchedule, selectedHolidayRules);
      let workingDays = 0;
      for (const row of buildEntryDetailRows(entry, workSchedule, selectedHolidayRules, appState.ptoDayHours)) {
        if (row.hoursUsed > 0) {
          workingDays += 1;
        }
      }
      return { error: null as string | null, totalHours, workingDays };
    } catch (error) {
      return { error: error instanceof Error ? error.message : "Unable to calculate preview.", totalHours: 0, workingDays: 0 };
    }
  })();

  useEffect(() => {
    if (editingPtoName === null) {
      setPtoForm(buildDefaultPtoForm());
      return;
    }
    const record = appState.ptoTypes.find((item) => item.name === editingPtoName);
    if (record) {
      setPtoForm(ptoFormFromRecord(record));
    }
  }, [editingPtoName, appState.ptoTypes]);

  useEffect(() => {
    if (editingTimeOffIndex === null) {
      setTimeOffForm(buildDefaultTimeOffForm(appState));
      return;
    }
    const entry = appState.plannedTimeOff[editingTimeOffIndex];
    if (entry) {
      setTimeOffForm(timeOffFormFromEntry(entry));
    }
  }, [editingTimeOffIndex, appState]);

  useEffect(() => {
    setNewHolidayDate(appState.startDate);
  }, [appState.startDate]);

  useEffect(() => {
    if (
      appState.ptoTypes.length > 0 &&
      editingTimeOffIndex === null &&
      !appState.ptoTypes.some((item) => item.name === timeOffForm.pto_type)
    ) {
      setTimeOffForm((current) => ({ ...current, pto_type: appState.ptoTypes[0].name }));
    }
  }, [appState.ptoTypes, editingTimeOffIndex, timeOffForm.pto_type]);

  useEffect(() => {
    try {
      window.localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(buildExportPayload(appState)));
    } catch {
      // Ignore storage failures so the app still works in restricted browsers.
    }
  }, [appState]);

  function updateState(updater: (current: AppStateShape) => AppStateShape) {
    startTransition(() => {
      setAppState((current) => updater(current));
    });
  }

  function showMessage(message: string) {
    setFlashMessage(message);
    window.setTimeout(() => setFlashMessage(null), 3500);
  }

  function handleImportFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const payload = JSON.parse(String(reader.result));
        const imported = loadImportPayload(payload);
        updateState(() => imported);
        setEditingPtoName(null);
        setPtoEditSelection("Add new PTO type");
        setEditingTimeOffIndex(null);
        setTimeOffEditSelection("Add new planned time off");
        setExpandedTimeOffDetails(null);
        showMessage("Imported data and replaced the current session.");
      } catch (error) {
        showMessage(error instanceof Error ? `Import failed: ${error.message}` : "Import failed.");
      } finally {
        if (fileInputRef.current) {
          fileInputRef.current.value = "";
        }
      }
    };
    reader.readAsText(file);
  }

  function handleExportJson() {
    downloadTextFile("pto_calculator_data.json", JSON.stringify(buildExportPayload(appState), null, 2), "application/json");
  }

  function handleExportCsv() {
    downloadTextFile("pto_projection.csv", projectionRowsToCsv(projection.rows, appState.ptoTypes), "text/csv");
  }

  function handleClearSavedBrowserData() {
    const freshState = defaultAppState();
    try {
      window.localStorage.removeItem(LOCAL_STORAGE_KEY);
    } catch {
      // Ignore storage failures and still reset the in-memory session.
    }
    setAppState(freshState);
    setPtoEditSelection("Add new PTO type");
    setTimeOffEditSelection("Add new planned time off");
    setEditingPtoName(null);
    setEditingTimeOffIndex(null);
    setPtoForm(buildDefaultPtoForm());
    setTimeOffForm(buildDefaultTimeOffForm(freshState));
    setExpandedTimeOffDetails(null);
    setNewHolidayLabel("");
    setNewHolidayDate(freshState.startDate);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    showMessage("Saved browser data cleared.");
  }

  function handlePtoSelectorChange(value: string) {
    setPtoEditSelection(value);
    setEditingPtoName(value === "Add new PTO type" ? null : value);
  }

  function handleTimeOffSelectorChange(value: string) {
    setTimeOffEditSelection(value);
    setEditingTimeOffIndex(value === "Add new planned time off" ? null : Number(value));
  }

  function handlePtoSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanName = ptoForm.name.trim();
    const existingNames = new Set(
      appState.ptoTypes
        .filter((item) => item.name !== editingPtoName)
        .map((item) => item.name.toLowerCase()),
    );
    if (!cleanName) {
      showMessage("Please enter a PTO type name.");
      return;
    }
    if (existingNames.has(cleanName.toLowerCase())) {
      showMessage("That PTO type already exists.");
      return;
    }
    try {
      const normalized = normalizePtoTypeRecord({
        name: cleanName,
        current_balance: ptoForm.current_balance,
        balance_unit: ptoForm.balance_unit,
        accrual_amount: ptoForm.accrual_amount,
        accrual_unit: ptoForm.accrual_unit,
        accrual_frequency: ptoForm.accrual_frequency,
        accrual_cap: ptoForm.accrual_cap,
        rollover_limit: ptoForm.rollover_limit,
      });
      updateState((current) => {
        if (editingPtoName === null) {
          return { ...current, ptoTypes: [...current.ptoTypes, normalized] };
        }
        return {
          ...current,
          ptoTypes: current.ptoTypes.map((item) => (item.name === editingPtoName ? normalized : item)),
          plannedTimeOff: current.plannedTimeOff.map((entry) =>
            entry.pto_type === editingPtoName ? { ...entry, pto_type: cleanName } : entry,
          ),
        };
      });
      setEditingPtoName(cleanName);
      setPtoEditSelection(cleanName);
      showMessage(editingPtoName === null ? "PTO type added." : "PTO type updated.");
    } catch (error) {
      showMessage(error instanceof Error ? error.message : "Unable to save PTO type.");
    }
  }

  function handleDeletePtoType() {
    if (editingPtoName === null) return;
    updateState((current) => ({
      ...current,
      ptoTypes: current.ptoTypes.filter((item) => item.name !== editingPtoName),
      plannedTimeOff: current.plannedTimeOff.filter((entry) => entry.pto_type !== editingPtoName),
    }));
    setEditingPtoName(null);
    setPtoEditSelection("Add new PTO type");
    showMessage("PTO type deleted.");
  }

  function handleTimeOffStartDateChange(value: string) {
    setTimeOffForm((current) => ({
      ...current,
      start_date: value,
      end_date: editingTimeOffIndex === null || current.end_date < value ? value : current.end_date,
    }));
  }

  function handleTimeOffSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const entry = createTimeOffEntry(
        timeOffForm.start_date,
        timeOffForm.end_date,
        timeOffForm.pto_type,
        timeOffForm.reason,
        workSchedule,
        selectedHolidayRules,
      );
      updateState((current) => {
        if (editingTimeOffIndex === null) {
          return { ...current, plannedTimeOff: [...current.plannedTimeOff, entry] };
        }
        const next = [...current.plannedTimeOff];
        next[editingTimeOffIndex] = entry;
        return { ...current, plannedTimeOff: next };
      });
      setEditingTimeOffIndex(null);
      setTimeOffEditSelection("Add new planned time off");
      showMessage(editingTimeOffIndex === null ? "Planned PTO added." : "Planned PTO updated.");
    } catch (error) {
      showMessage(error instanceof Error ? error.message : "Unable to save planned PTO.");
    }
  }

  function handleDeleteTimeOff(index: number) {
    updateState((current) => ({
      ...current,
      plannedTimeOff: current.plannedTimeOff.filter((_, currentIndex) => currentIndex !== index),
    }));
    if (editingTimeOffIndex === index) {
      setEditingTimeOffIndex(null);
      setTimeOffEditSelection("Add new planned time off");
    } else if (editingTimeOffIndex !== null && editingTimeOffIndex > index) {
      setEditingTimeOffIndex(editingTimeOffIndex - 1);
      setTimeOffEditSelection(String(editingTimeOffIndex - 1));
    }
    if (expandedTimeOffDetails === index) {
      setExpandedTimeOffDetails(null);
    } else if (expandedTimeOffDetails !== null && expandedTimeOffDetails > index) {
      setExpandedTimeOffDetails(expandedTimeOffDetails - 1);
    }
    showMessage("Planned PTO deleted.");
  }

  function toggleHolidaySelection(holidayId: string, checked: boolean) {
    updateState((current) => ({
      ...current,
      selectedHolidays: checked
        ? Array.from(new Set([...current.selectedHolidays, holidayId])).sort()
        : current.selectedHolidays.filter((item) => item !== holidayId),
    }));
  }

  function handleAddHoliday() {
    const label = newHolidayLabel.trim();
    if (!label) {
      showMessage("Please enter a holiday name.");
      return;
    }
    const customKey = `custom:${newHolidayDate}`;
    updateState((current) => ({
      ...current,
      customHolidays: [
        ...current.customHolidays.filter((item) => item.date !== newHolidayDate),
        { label, date: newHolidayDate },
      ].sort((a, b) => a.date.localeCompare(b.date)),
      selectedHolidays: Array.from(new Set([...current.selectedHolidays.filter((item) => item !== customKey), customKey])).sort(),
    }));
    setNewHolidayLabel("");
    setNewHolidayDate(appState.startDate);
    showMessage("Custom holiday added.");
  }

  function handleDeleteCustomHoliday(date: string) {
    updateState((current) => ({
      ...current,
      customHolidays: current.customHolidays.filter((item) => item.date !== date),
      selectedHolidays: current.selectedHolidays.filter((item) => item !== `custom:${date}`),
    }));
    showMessage("Custom holiday removed.");
  }

  const timeOffOptions = appState.plannedTimeOff.map((entry, index) => ({
    value: `${index}`,
    label: `${entry.start_date} to ${entry.end_date} | ${entry.pto_type} | ${displayAmountHours(entry, workSchedule, selectedHolidayRules).toFixed(2)} hrs${entry.reason ? ` | ${entry.reason}` : ""}`,
  }));

  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Static React Rewrite</p>
          <h1>PTO Planner</h1>
          <p className="hero-copy">Track weekly PTO balances with your real work schedule, holidays, caps, rollover rules, and planned time off.</p>
        </div>
        <div className="hero-actions">
          <button className="secondary-button" onClick={handleExportJson}>Export JSON</button>
          <button className="secondary-button" onClick={handleExportCsv} disabled={projection.rows.length === 0}>Export CSV</button>
        </div>
      </header>

      {flashMessage && <div className="flash-message">{flashMessage}</div>}

      <div className="layout-grid">
        <aside className="sidebar-column">
          <Section title="Settings" defaultOpen>
            <div className="field-grid">
              <label className="field">
                <span>Projection start date</span>
                <input
                  type="date"
                  value={appState.startDate}
                  onChange={(event) => updateState((current) => ({ ...current, startDate: event.target.value }))}
                />
              </label>
              <label className="field">
                <span>PTO day hours</span>
                <input
                  type="number"
                  min="1"
                  max="24"
                  step="0.5"
                  value={appState.ptoDayHours}
                  onChange={(event) => updateState((current) => ({ ...current, ptoDayHours: Number(event.target.value) }))}
                />
              </label>
              <label className="field">
                <span>Weeks to project</span>
                <input
                  type="range"
                  min="4"
                  max="104"
                  step="4"
                  value={appState.weeksToProject}
                  onChange={(event) => updateState((current) => ({ ...current, weeksToProject: Number(event.target.value) }))}
                />
                <strong>{appState.weeksToProject} weeks</strong>
              </label>
            </div>
          </Section>

          <Section title="Work Schedule">
            <div className="field-grid">
              <label className="field">
                <span>Schedule</span>
                <select
                  value={appState.workScheduleType}
                  onChange={(event) =>
                    updateState((current) => ({ ...current, workScheduleType: event.target.value as AppStateShape["workScheduleType"] }))
                  }
                >
                  {WORK_SCHEDULE_OPTIONS.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </label>

              {appState.workScheduleType === "9/80" && (
                <>
                  <label className="field">
                    <span>Starting off Friday</span>
                    <input
                      type="date"
                      value={appState.startingOffFriday}
                      onChange={(event) => updateState((current) => ({ ...current, startingOffFriday: event.target.value }))}
                    />
                  </label>
                  <p className="inline-note">Every other Friday is treated as off starting from this date.</p>
                  {new Date(`${appState.startingOffFriday}T00:00:00Z`).getUTCDay() !== 5 && (
                    <p className="warning-text">Starting off Friday should be a Friday so the 9/80 pattern lines up correctly.</p>
                  )}
                </>
              )}

              {appState.workScheduleType === "Custom" && (
                <div className="weekday-grid">
                  {WEEKDAY_NAMES.map((weekday, index) => (
                    <label className="field" key={weekday}>
                      <span>{weekday}</span>
                      <input
                        type="number"
                        min="0"
                        max="24"
                        step="0.5"
                        value={appState.customScheduleHours[index]}
                        onChange={(event) =>
                          updateState((current) => ({
                            ...current,
                            customScheduleHours: current.customScheduleHours.map((value, currentIndex) =>
                              currentIndex === index ? Number(event.target.value) : value,
                            ),
                          }))
                        }
                      />
                    </label>
                  ))}
                </div>
              )}
            </div>
          </Section>

          <Section title="Holidays">
            <p className="inline-note">Checked holidays are treated as days off. Federal holiday selections automatically apply in later years too.</p>
            <div className="holiday-list">
              {holidayOptions.map((holiday) => (
                <label className="holiday-item" key={holiday.id}>
                  <span className="holiday-main">
                    <input
                      type="checkbox"
                      checked={appState.selectedHolidays.includes(holiday.id)}
                      onChange={(event) => toggleHolidaySelection(holiday.id, event.target.checked)}
                    />
                    <span>{holiday.date} - {holiday.label} ({holiday.source === "custom" ? "Custom" : "Federal"})</span>
                  </span>
                  {holiday.source === "custom" && (
                    <button type="button" className="text-button" onClick={() => handleDeleteCustomHoliday(holiday.date)}>
                      Remove
                    </button>
                  )}
                </label>
              ))}
            </div>
            <div className="subsection">
              <h3>Add custom holiday</h3>
              <div className="field-grid">
                <label className="field">
                  <span>Holiday name</span>
                  <input value={newHolidayLabel} onChange={(event) => setNewHolidayLabel(event.target.value)} placeholder="Company shutdown day" />
                </label>
                <label className="field">
                  <span>Holiday date</span>
                  <input type="date" value={newHolidayDate} onChange={(event) => setNewHolidayDate(event.target.value)} />
                </label>
              </div>
              <button className="primary-button" onClick={handleAddHoliday}>Add holiday</button>
            </div>
          </Section>

          <Section title="Import / Export">
            <p className="inline-note">Data is auto-saved in this browser. Export is still recommended if you want a backup or need to move your data to another browser or device.</p>
            <div className="button-row">
              <button className="secondary-button" onClick={handleExportJson}>Export all data</button>
              <label className="secondary-button file-label" htmlFor={importInputId}>Import saved data</label>
              <button className="danger-button" onClick={handleClearSavedBrowserData}>Clear saved browser data</button>
              <input
                id={importInputId}
                ref={fileInputRef}
                type="file"
                accept="application/json"
                className="hidden-input"
                onChange={handleImportFile}
              />
            </div>
          </Section>
        </aside>

        <main className="main-column">
          <Section title="PTO Types" defaultOpen>
            <div className="manage-row">
              <label className="field grow">
                <span>Choose a PTO type to add or edit</span>
                <select value={ptoEditSelection} onChange={(event) => handlePtoSelectorChange(event.target.value)}>
                  <option value="Add new PTO type">Add new PTO type</option>
                  {appState.ptoTypes.map((item) => (
                    <option key={item.name} value={item.name}>{item.name}</option>
                  ))}
                </select>
              </label>
              {editingPtoName && (
                <button className="danger-button" onClick={handleDeletePtoType}>Delete selected PTO type</button>
              )}
            </div>

            <form className="stack-form" onSubmit={handlePtoSubmit}>
              <div className="six-grid">
                <label className="field">
                  <span>Type name</span>
                  <input value={ptoForm.name} onChange={(event) => setPtoForm((current) => ({ ...current, name: event.target.value }))} />
                </label>
                <label className="field">
                  <span>Current balance</span>
                  <input
                    type="number"
                    min="0"
                    step="0.25"
                    value={ptoForm.current_balance}
                    onChange={(event) => setPtoForm((current) => ({ ...current, current_balance: Number(event.target.value) }))}
                  />
                </label>
                <label className="field">
                  <span>Balance unit</span>
                  <select
                    value={ptoForm.balance_unit}
                    onChange={(event) => setPtoForm((current) => ({ ...current, balance_unit: event.target.value as PTOFormState["balance_unit"] }))}
                  >
                    <option value="hours">hours</option>
                    <option value="days">days</option>
                  </select>
                </label>
                <label className="field">
                  <span>Accrual amount</span>
                  <input
                    type="number"
                    min="0"
                    step="0.25"
                    value={ptoForm.accrual_amount}
                    onChange={(event) => setPtoForm((current) => ({ ...current, accrual_amount: Number(event.target.value) }))}
                  />
                </label>
                <label className="field">
                  <span>Accrual unit</span>
                  <select
                    value={ptoForm.accrual_unit}
                    onChange={(event) => setPtoForm((current) => ({ ...current, accrual_unit: event.target.value as PTOFormState["accrual_unit"] }))}
                  >
                    <option value="hours">hours</option>
                    <option value="days">days</option>
                  </select>
                </label>
                <label className="field">
                  <span>Frequency</span>
                  <select
                    value={ptoForm.accrual_frequency}
                    onChange={(event) => setPtoForm((current) => ({ ...current, accrual_frequency: event.target.value as PTOTypeRecord["accrual_frequency"] }))}
                  >
                    <option value="week">week</option>
                    <option value="every 2 weeks">every 2 weeks</option>
                    <option value="twice a month">twice a month</option>
                    <option value="month">month</option>
                    <option value="year">year</option>
                  </select>
                </label>
              </div>

              <div className="two-grid">
                <label className="field">
                  <span>Accrual cap ({ptoForm.balance_unit}, blank = none)</span>
                  <input value={ptoForm.accrual_cap} onChange={(event) => setPtoForm((current) => ({ ...current, accrual_cap: event.target.value }))} />
                </label>
                <label className="field">
                  <span>Rollover limit ({ptoForm.balance_unit}, blank = unlimited)</span>
                  <input value={ptoForm.rollover_limit} onChange={(event) => setPtoForm((current) => ({ ...current, rollover_limit: event.target.value }))} />
                </label>
              </div>

              <div className="button-row">
                <button className="primary-button" type="submit">
                  {editingPtoName === null ? "Add PTO type" : "Save PTO changes"}
                </button>
              </div>
            </form>

            {appState.ptoTypes.length > 0 ? (
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Current Balance</th>
                      <th>Balance Unit</th>
                      <th>Accrual Amount</th>
                      <th>Accrual Unit</th>
                      <th>Frequency</th>
                      <th>Accrual Cap</th>
                      <th>Rollover Limit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {appState.ptoTypes.map((item) => (
                      <tr key={item.name}>
                        <td>{item.name}</td>
                        <td>{item.current_balance}</td>
                        <td>{item.balance_unit}</td>
                        <td>{item.accrual_amount}</td>
                        <td>{item.accrual_unit}</td>
                        <td>{item.accrual_frequency}</td>
                        <td>{item.accrual_cap ?? "-"}</td>
                        <td>{item.rollover_limit ?? "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="empty-state">Add at least one PTO type to start projecting balances.</p>
            )}
          </Section>

          <Section title="Planned Time Off" defaultOpen>
            {appState.ptoTypes.length > 0 ? (
              <>
                <div className="manage-row">
                  <label className="field grow">
                    <span>Choose a planned time off entry to add or edit</span>
                    <select value={timeOffEditSelection} onChange={(event) => handleTimeOffSelectorChange(event.target.value)}>
                      <option value="Add new planned time off">Add new planned time off</option>
                      {timeOffOptions.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                  </label>
                </div>

                <form className="stack-form" onSubmit={handleTimeOffSubmit}>
                  <div className="three-grid">
                    <label className="field">
                      <span>Start date</span>
                      <input type="date" value={timeOffForm.start_date} onChange={(event) => handleTimeOffStartDateChange(event.target.value)} />
                    </label>
                    <label className="field">
                      <span>End date</span>
                      <input type="date" value={timeOffForm.end_date} onChange={(event) => setTimeOffForm((current) => ({ ...current, end_date: event.target.value }))} />
                    </label>
                    <label className="field">
                      <span>PTO type</span>
                      <select value={timeOffForm.pto_type} onChange={(event) => setTimeOffForm((current) => ({ ...current, pto_type: event.target.value }))}>
                        {appState.ptoTypes.map((item) => (
                          <option key={item.name} value={item.name}>{item.name}</option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <label className="field">
                    <span>Reason (optional)</span>
                    <input value={timeOffForm.reason} onChange={(event) => setTimeOffForm((current) => ({ ...current, reason: event.target.value }))} />
                  </label>
                  {timeOffPreview.error === null ? (
                    <p className="inline-note">
                      Calculated usage: {timeOffPreview.totalHours.toFixed(2)} hrs ({daysFromHours(timeOffPreview.totalHours, appState.ptoDayHours).toFixed(2)} days) across {timeOffPreview.workingDays} workday(s).
                    </p>
                  ) : (
                    <p className="warning-text">{timeOffPreview.error}</p>
                  )}
                  <div className="button-row">
                    <button className="primary-button" type="submit">
                      {editingTimeOffIndex === null ? "Add planned time off" : "Save time off changes"}
                    </button>
                    {editingTimeOffIndex !== null && (
                      <button className="danger-button" type="button" onClick={() => handleDeleteTimeOff(editingTimeOffIndex)}>
                        Delete selected planned time off
                      </button>
                    )}
                  </div>
                </form>

                {appState.plannedTimeOff.length > 0 && (
                  <div className="table-wrap">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th />
                          <th>Start</th>
                          <th>End</th>
                          <th>PTO Type</th>
                          <th>Hours</th>
                          <th>Days</th>
                          <th>Reason</th>
                          <th>Delete</th>
                        </tr>
                      </thead>
                      <tbody>
                        {appState.plannedTimeOff
                          .map((entry, index) => ({ entry, index }))
                          .sort((left, right) => left.entry.start_date.localeCompare(right.entry.start_date) || left.entry.end_date.localeCompare(right.entry.end_date))
                          .flatMap(({ entry, index }) => {
                            const amountHours = displayAmountHours(entry, workSchedule, selectedHolidayRules);
                            const isExpanded = expandedTimeOffDetails === index;
                            const rows = [
                              <tr key={`row-${index}`}>
                                <td>
                                  <button className="inline-icon-button" type="button" onClick={() => setExpandedTimeOffDetails(isExpanded ? null : index)}>
                                    {isExpanded ? "v" : ">"}
                                  </button>
                                </td>
                                <td>{entry.start_date}</td>
                                <td>{entry.end_date}</td>
                                <td>{entry.pto_type}</td>
                                <td>{amountHours.toFixed(2)}</td>
                                <td>{daysFromHours(amountHours, appState.ptoDayHours).toFixed(2)}</td>
                                <td>{entry.reason || "-"}</td>
                                <td>
                                  <button className="text-button danger-text" type="button" onClick={() => handleDeleteTimeOff(index)}>
                                    Delete
                                  </button>
                                </td>
                              </tr>,
                            ];
                            if (isExpanded) {
                              rows.push(
                                <tr key={`detail-${index}`} className="detail-row">
                                  <td colSpan={8}>
                                    <DetailTable rows={buildEntryDetailRows(entry, workSchedule, selectedHolidayRules, appState.ptoDayHours)} />
                                  </td>
                                </tr>,
                              );
                            }
                            return rows;
                          })}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            ) : (
              <p className="empty-state">Add at least one PTO type to create planned time off entries.</p>
            )}
          </Section>

          <Section title="Weekly Balance Projection" defaultOpen>
            {appState.ptoTypes.length > 0 ? (
              <>
                {projection.warnings.length > 0 && (
                  <div className="subsection">
                    <h3>Warning summary</h3>
                    <div className="table-wrap">
                      <table className="data-table compact-table">
                        <thead>
                          <tr>
                            <th>PTO Type</th>
                            <th>Below 1 PTO day</th>
                            <th>Below zero</th>
                          </tr>
                        </thead>
                        <tbody>
                          {projection.warnings.map((warning) => (
                            <tr key={warning.ptoType}>
                              <td>{warning.ptoType}</td>
                              <td>{warning.belowOneDay ?? "-"}</td>
                              <td>{warning.belowZero ?? "-"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                <p className="inline-note">Balances in {appState.weeksToProject} weeks given planned PTO.</p>
                <div className="metric-grid">
                  {finalProjectionRow &&
                    appState.ptoTypes.map((item) => (
                      <MetricCard
                        key={item.name}
                        label={item.name}
                        hours={finalProjectionRow.balances[item.name]}
                        days={finalProjectionRow.days[item.name]}
                      />
                    ))}
                </div>

                <ProjectionChart rows={projection.rows} names={appState.ptoTypes.map((item) => item.name)} />

                <div className="table-wrap">
                  <table className="data-table projection-table">
                    <thead>
                      <tr>
                        <th>Week #</th>
                        <th>Week Start</th>
                        <th>Week End</th>
                        {appState.ptoTypes.map((item) => (
                          <th key={`${item.name}-accrued`}>{item.name} Accrued (hrs)</th>
                        ))}
                        {appState.ptoTypes.map((item) => (
                          <th key={`${item.name}-used`}>{item.name} Used (hrs)</th>
                        ))}
                        {appState.ptoTypes.map((item) => (
                          <th key={`${item.name}-trim`}>{item.name} Rollover Trim (hrs)</th>
                        ))}
                        {appState.ptoTypes.map((item) => (
                          <th key={`${item.name}-bal`}>{item.name} Balance (hrs)</th>
                        ))}
                        {appState.ptoTypes.map((item) => (
                          <th key={`${item.name}-days`}>{item.name} Balance (days)</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {projection.rows.map((row) => (
                        <tr key={row.weekStart}>
                          <td>{row.weekNumber}</td>
                          <td>{row.weekStart}</td>
                          <td>{row.weekEnd}</td>
                          {appState.ptoTypes.map((item) => (
                            <td key={`${row.weekStart}-${item.name}-accrued`}>{row.accrued[item.name].toFixed(2)}</td>
                          ))}
                          {appState.ptoTypes.map((item) => (
                            <td key={`${row.weekStart}-${item.name}-used`}>{row.used[item.name].toFixed(2)}</td>
                          ))}
                          {appState.ptoTypes.map((item) => (
                            <td key={`${row.weekStart}-${item.name}-trim`}>{row.rolloverTrim[item.name].toFixed(2)}</td>
                          ))}
                          {appState.ptoTypes.map((item) => (
                            <td key={`${row.weekStart}-${item.name}-balance`}>{row.balances[item.name].toFixed(2)}</td>
                          ))}
                          {appState.ptoTypes.map((item) => (
                            <td key={`${row.weekStart}-${item.name}-days`}>{row.days[item.name].toFixed(2)}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="subsection">
                  <h3>Notes</h3>
                  <ul className="notes-list">
                    <li>PTO balances and accruals entered in days are converted using PTO day hours.</li>
                    <li>Planned time off ranges auto-calculate from your work schedule and skip selected holidays.</li>
                    <li>The default schedule ignores weekends, the 9/80 schedule skips alternating off-Fridays, and custom schedules use your weekday hour settings.</li>
                    <li>Accrual caps stop additional accrual once a PTO bank reaches its cap, and rollover limits trim balances at the year boundary.</li>
                    <li>Warning summary rows show the first week a PTO type dips below one PTO day and the first week it goes negative.</li>
                  </ul>
                </div>
              </>
            ) : (
              <p className="empty-state">Once you add PTO types, your weekly projection will appear here.</p>
            )}
          </Section>
        </main>
      </div>
    </div>
  );
}












