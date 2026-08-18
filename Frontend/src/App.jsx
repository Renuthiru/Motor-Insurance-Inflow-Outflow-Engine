// ============================================================
// src/App.jsx — Progressive Live Inflow Engine
// Backend: FastAPI http://127.0.0.1:8001
//
// DATE-AWARE ARCHITECTURE:
//   The user selects a calendar date (displayed as DD-MM-YYYY).
//   The frontend sends requested_date (YYYY-MM-DD) to the API.
//   The API resolves effective_date_used via MAX(effective_from) ≤ requested_date.
//   The frontend displays effective_date_used returned by the API.
//   NO date-resolution logic lives in the frontend.
//   NO month/version-specific code exists here.
//   Adding September/October/future versions requires zero frontend changes.
// ============================================================

import React, { useState, useEffect, useRef, useCallback } from "react";
import { api } from "./api";
import "./App.css";

// ── Date Utilities ────────────────────────────────────────────
// All date logic: format conversions only. No business-rule date logic.

/** Returns today's date as a YYYY-MM-DD string (browser local date). */
function todayISO() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** Converts YYYY-MM-DD → DD-MM-YYYY for display. */
function isoToDisplay(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-");
  return `${d}-${m}-${y}`;
}

/** Converts DD-MM-YYYY → YYYY-MM-DD for API. */
function displayToISO(display) {
  if (!display) return "";
  const [d, m, y] = display.split("-");
  return `${y}-${m}-${d}`;
}

// ── Inline SVG Icons ─────────────────────────────────────────
const Icon = {
  Shield: () => (
    <svg width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  ),
  Grid: () => (
    <svg width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="14" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
    </svg>
  ),
  Warn: () => (
    <svg width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  ),
  Sun: () => (
    <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="5" />
      <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
    </svg>
  ),
  Moon: () => (
    <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  ),
  Refresh: () => (
    <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <path d="M23 4v6h-6M1 20v-6h6" />
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
    </svg>
  ),
  Search: () => (
    <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.35-4.35" />
    </svg>
  ),
  Calendar: () => (
    <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  ),
  Info: () => (
    <svg width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  ),
  Check: () => (
    <svg width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  ),
};

// ── Error Message Classifier ──────────────────────────────────
// Maps raw API error strings to user-friendly messages.
// No date-resolution logic — only presentation.
function classifyError(errMsg) {
  if (!errMsg) return null;
  if (errMsg.includes("No applicable Rule Master version")) {
    return {
      type: "no-version",
      title: "No Inflow Version Available",
      message: "No inflow rate version exists for the selected date. The selected date may be before the first available rate version.",
    };
  }
  if (errMsg.includes("No matching rule") || errMsg.includes("No matching insurer")) {
    return {
      type: "no-match",
      title: "No Matching Inflow Found",
      message: "No insurer inflow rules were found for the selected policy dimensions and date.",
    };
  }
  if (errMsg.includes("No segments within rule")) {
    return {
      type: "no-segment",
      title: "No Matching Rate Segment",
      message: "Inflow rules exist but no rate segment matched the selected criteria.",
    };
  }
  if (errMsg.includes("mapping not found")) {
    return {
      type: "invalid-input",
      title: "Invalid Selection",
      message: errMsg,
    };
  }
  if (errMsg.includes("fetch") || errMsg.includes("NetworkError") || errMsg.includes("Failed to fetch")) {
    return {
      type: "network",
      title: "Unable to Retrieve Rates",
      message: "Cannot connect to the rate engine. Please check if the API server is running and try again.",
    };
  }
  return {
    type: "unknown",
    title: "Lookup Error",
    message: errMsg,
  };
}

// ── Main Application ──────────────────────────────────────────
export default function App() {

  // ── Theme ─────────────────────────────────────────────────
  const [theme, setTheme] = useState(
    () => localStorage.getItem("inflow-theme") || "dark"
  );
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("inflow-theme", theme);
  }, [theme]);

  // ── Date State ────────────────────────────────────────────
  // selectedDate: YYYY-MM-DD (internal/API format)
  // Default: today's browser-local date (dynamic, never hardcoded)
  const [selectedDate, setSelectedDate] = useState(() => todayISO());

  // ── Master Data ───────────────────────────────────────────
  const [products, setProducts] = useState([]);
  const [allSubproducts, setAllSubproducts] = useState([]);
  const [businessTypes, setBusinessTypes] = useState([]);
  const [sublines, setSublines] = useState([]);
  const [states, setStates] = useState([]);
  const [allLocations, setAllLocations] = useState([]);

  // ── UI State ──────────────────────────────────────────────
  const [initialLoading, setInitialLoading] = useState(true);
  const [calculating, setCalculating] = useState(false);
  const [calcResult, setCalcResult] = useState(null);
  const [calcError, setCalcError] = useState(null);
  // validationMessage removed — validation banner was only needed for the Find Inflow button click path

  // ── Form State ────────────────────────────────────────────
  const [form, setForm] = useState({
    product: "",
    subproduct: "",
    state: "",
    location: "",
    business_type: "",
    subline: "",
  });

  // ── Cache: prevent cross-date or identical-request result reuse ──
  // Key = JSON of (requested_date + all dimensions)
  // Cache is invalidated whenever requested_date changes.
  const resultCacheRef = useRef({});
  const lastLookupKeyRef = useRef(null);

  // ── Debounce Timer ────────────────────────────────────────
  const timerRef = useRef(null);

  // ── Load Master Data on Mount ─────────────────────────────
  useEffect(() => {
    async function load() {
      setInitialLoading(true);
      try {
        const [pRes, spRes, btRes, slRes, stRes, locRes] = await Promise.all([
          api.getProducts().catch(() => ({ products: [] })),
          api.getSubproducts().catch(() => ({ subproducts: [] })),
          api.getBusinessTypes().catch(() => ({ business_types: [] })),
          api.getSublines().catch(() => ({ sublines: [] })),
          api.getStates().catch(() => ({ states: [] })),
          api.getLocations().catch(() => ({ locations: [] })),
        ]);
        setProducts(pRes.products || []);
        setAllSubproducts(spRes.subproducts || []);
        setBusinessTypes(btRes.business_types || []);
        setSublines(slRes.sublines || []);
        setStates(stRes.states || []);
        setAllLocations(locRes.locations || []);
      } catch {
        setCalcError("Backend API service is currently unavailable");
      } finally {
        setInitialLoading(false);
      }
    }
    load();
  }, []);

  // ── Derived Options (cascading selects) ───────────────────
  const selectedProd = products.find(p => p.product_name === form.product);
  const filteredSubproducts = selectedProd
    ? allSubproducts.filter(sp => sp.product_code === selectedProd.product_code)
    : [];

  const selectedState = states.find(s => s.source_state === form.state);
  const filteredLocations = selectedState
    ? allLocations.filter(l => l.state_code === selectedState.state_code)
    : [];

  // ── Core Live Lookup Function ─────────────────────────────
  // Uses /inflow-lookup (raw names) — the standard user-facing path.
  // MINIMUM REQUIREMENT: Product + SubProduct + State + Location.
  // requested_date is ALWAYS sent. Backend resolves effective_date_used.
  const runLiveLookup = useCallback(async (currentForm, dateISO) => {
    // Case 1 to 4: Do not perform lookup until all four minimum dimensions are selected
    if (!currentForm.product || !currentForm.subproduct || !currentForm.state || !currentForm.location) {
      setCalcResult(null);
      setCalcError(null);
      return;
    }

    // Build cache key — includes date so July and August results never mix
    const lookupKey = JSON.stringify({
      requested_date: dateISO,
      product: currentForm.product,
      subproduct: currentForm.subproduct,
      state: currentForm.state,
      location: currentForm.location,
      business_type: currentForm.business_type || null,
      subline: currentForm.subline || null,
    });

    // Skip if exact same request as last time (no change)
    if (lookupKey === lastLookupKeyRef.current) return;
    lastLookupKeyRef.current = lookupKey;

    // Return cached result if available (same date + dimensions)
    if (resultCacheRef.current[lookupKey]) {
      const cached = resultCacheRef.current[lookupKey];
      setCalcResult(cached.result);
      setCalcError(cached.error);
      return;
    }

    setCalculating(true);
    setCalcError(null);


    // Build payload — requested_date in YYYY-MM-DD (API format)
    const payload = {
      requested_date: dateISO,                           // YYYY-MM-DD to API
      product: currentForm.product,
      subproduct: currentForm.subproduct,
      state: currentForm.state,
      location: currentForm.location,
      business_type: currentForm.business_type || null,
      subline: currentForm.subline || null,
    };

    let resultToCache = null;
    let errorToCache = null;

    try {
      const res = await api.lookupInflow(payload);
      setCalcResult(res);
      resultToCache = res;

      if (!res.matched || !res.results || res.results.length === 0) {
        const errMsg = res.error || "No matching insurer inflow found for the selected criteria.";
        setCalcError(errMsg);
        errorToCache = errMsg;
      }
    } catch (err) {
      const errMsg = err.message || "Error querying rate engine";
      setCalcError(errMsg);
      setCalcResult(null);
      errorToCache = errMsg;
    } finally {
      setCalculating(false);
      // Store in cache — key includes date so cross-version mixing is impossible
      resultCacheRef.current[lookupKey] = { result: resultToCache, error: errorToCache };
    }
  }, []);

  // ── Form Field Change Handler ─────────────────────────────
  const set = (field, value) => {
    setForm(prev => {
      const next = { ...prev, [field]: value };
      if (field === "product") next.subproduct = "";
      if (field === "state") next.location = "";

      // STALE RESULT PROTECTION: Clear old results immediately on selection change
      setCalcResult(null);
      setCalcError(null);
      lastLookupKeyRef.current = null;

      if (timerRef.current) clearTimeout(timerRef.current);

      // Only schedule lookup if all 4 minimum dimensions are filled
      if (next.product && next.subproduct && next.state && next.location) {
        timerRef.current = setTimeout(() => {
          runLiveLookup(next, selectedDate);
        }, 150);
      }

      return next;
    });
  };

  // ── Date Change Handler ───────────────────────────────────
  // When date changes: keep dimensions, clear stale results, re-lookup.
  // The cache key includes the date, so no cross-date result reuse occurs.
  const handleDateChange = (newDateISO) => {
    if (newDateISO === selectedDate) return;
    setSelectedDate(newDateISO);
    setCalcResult(null);     // clear stale results immediately
    setCalcError(null);
    lastLookupKeyRef.current = null;  // force fresh lookup

    if (timerRef.current) clearTimeout(timerRef.current);

    if (form.product && form.subproduct && form.state && form.location) {
      timerRef.current = setTimeout(() => {
        runLiveLookup(form, newDateISO);
      }, 150);
    }
  };

  // handleFindInflow removed — lookup is fully automatic via set() and handleDateChange()

  // ── Reset Form ────────────────────────────────────────────
  const handleReset = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setForm({ product: "", subproduct: "", state: "", location: "", business_type: "", subline: "" });
    setCalcResult(null);
    setCalcError(null);
    lastLookupKeyRef.current = null;
    resultCacheRef.current = {};
    // Reset date to today (dynamic)
    setSelectedDate(todayISO());
  };

  // ── Derived Display Values ────────────────────────────────
  const displayDate = isoToDisplay(selectedDate);          // DD-MM-YYYY for UI
  const displayEffectiveDate = calcResult?.effective_date_used
    ? isoToDisplay(calcResult.effective_date_used)                  // DD-MM-YYYY for UI
    : null;
  const classifiedError = classifyError(calcError);
  const hasResults = calcResult?.matched && calcResult?.results?.length > 0;
  // validationMessage removed — was only used by the now-removed Find Inflow button

  // ── Render ────────────────────────────────────────────────
  return (
    <div className="app">

      {/* ── HEADER ── */}
      <header className="header">
        <div className="brand">
          <div className="brand-icon"><Icon.Shield /></div>
          <div>
            <h1 className="brand-title">Motor Insurance Inflow Rate Finder</h1>
            <p className="brand-sub">Progressive Live Inflow Engine</p>
          </div>
        </div>
        <div className="header-actions">
          <button
            type="button"
            className="theme-btn"
            onClick={handleReset}
            title="Reset all selections and date to today"
          >
            <Icon.Refresh /> Reset
          </button>
          <button
            id="btn-theme"
            className="theme-btn"
            onClick={() => setTheme(t => t === "dark" ? "light" : "dark")}
            title="Toggle dark/light mode"
          >
            {theme === "dark" ? <Icon.Sun /> : <Icon.Moon />}
            {theme === "dark" ? " Light" : " Dark"}
          </button>
        </div>
      </header>

      <main className="main-content">

        {/* ── PANEL 1: DATE + POLICY DIMENSIONS ── */}
        <section className="panel policy-panel">
          <div className="panel-header-row">
            <h2 className="panel-title">
              <span className="step-badge">1</span>
              Policy Dimensions
            </h2>
          </div>

          {initialLoading ? (
            <div className="loading-state">
              <div className="spinner spinner-muted" />
              <span>Loading master options from API...</span>
            </div>
          ) : (
            <form onSubmit={e => e.preventDefault()}>

              {/* ── DATE ROW ── */}
              <div className="date-row">
                <div className="date-field-group">
                  <label className="label" htmlFor="inp-date">
                    <Icon.Calendar />
                    &nbsp;Selected Date
                  </label>
                  <div className="date-input-wrapper">
                    <input
                      id="inp-date"
                      type="date"
                      className="date-input"
                      value={selectedDate}
                      onChange={e => handleDateChange(e.target.value)}
                      title="Select the business date for rate lookup"
                    />
                    <span className="date-display-pill">
                      {displayDate}
                    </span>
                  </div>
                </div>

                {/* Date context badge — shown only after a successful lookup */}
                {calcResult && !calculating && (
                  <div className="date-context-badge">
                    <div className="date-ctx-item">
                      <span className="date-ctx-label">Selected Date</span>
                      <span className="date-ctx-value">
                        {calcResult.requested_date ? isoToDisplay(calcResult.requested_date) : displayDate}
                      </span>
                    </div>
                    <div className="date-ctx-sep">→</div>
                    <div className="date-ctx-item">
                      <span className="date-ctx-label">Rate Effective From</span>
                      <span className={`date-ctx-value ${displayEffectiveDate ? "date-ctx-resolved" : "date-ctx-none"}`}>
                        {displayEffectiveDate || "—"}
                      </span>
                    </div>
                    {displayEffectiveDate && (
                      <span className="date-ctx-check" title="Version resolved by backend">
                        <Icon.Check />
                      </span>
                    )}
                  </div>
                )}
              </div>

              {/* ── POLICY DIMENSIONS GRID ──
                  Required Field Order:
                  Product → SubProduct → State → Location → Business Type → SubLine
              */}
              <div className="policy-grid">

                {/* 1. Product */}
                <div className="form-group">
                  <label className="label" htmlFor="sel-product">Product</label>
                  <select
                    id="sel-product"
                    className="select"
                    value={form.product}
                    onChange={e => set("product", e.target.value)}
                  >
                    <option value="">Select Product</option>
                    {products.map(p => (
                      <option key={p.product_code} value={p.product_name}>{p.product_name}</option>
                    ))}
                  </select>
                </div>

                {/* 2. SubProduct — cascades from Product */}
                <div className="form-group">
                  <label className="label" htmlFor="sel-subproduct">SubProduct</label>
                  <select
                    id="sel-subproduct"
                    className="select"
                    value={form.subproduct}
                    onChange={e => set("subproduct", e.target.value)}
                    disabled={!form.product}
                  >
                    <option value="">Select SubProduct</option>
                    {filteredSubproducts.map(sp => (
                      <option key={sp.subproduct_code} value={sp.subproduct_name}>{sp.subproduct_name}</option>
                    ))}
                  </select>
                </div>

                {/* 3. State */}
                <div className="form-group">
                  <label className="label" htmlFor="sel-state">State</label>
                  <select
                    id="sel-state"
                    className="select"
                    value={form.state}
                    onChange={e => set("state", e.target.value)}
                  >
                    <option value="">Select State</option>
                    {states.map(st => (
                      <option key={st.state_code} value={st.source_state}>{st.ui_display_value || st.source_state}</option>
                    ))}
                  </select>
                </div>

                {/* 4. Location — cascades from State */}
                <div className="form-group">
                  <label className="label" htmlFor="sel-location">Location</label>
                  <select
                    id="sel-location"
                    className="select"
                    value={form.location}
                    onChange={e => set("location", e.target.value)}
                    disabled={!form.state}
                  >
                    <option value="">Select Location</option>
                    {filteredLocations.map(loc => (
                      <option key={loc.location_code} value={loc.source_location}>{loc.ui_display_value || loc.source_location}</option>
                    ))}
                  </select>
                </div>

                {/* 5. Business Type */}
                <div className="form-group">
                  <label className="label" htmlFor="sel-biztype">Business Type</label>
                  <select
                    id="sel-biztype"
                    className="select"
                    value={form.business_type}
                    onChange={e => set("business_type", e.target.value)}
                  >
                    <option value="">Select Business Type</option>
                    {businessTypes.map(bt => (
                      <option key={bt.business_type_code} value={bt.ui_display_value}>{bt.ui_display_value}</option>
                    ))}
                  </select>
                </div>

                {/* 6. SubLine */}
                <div className="form-group">
                  <label className="label" htmlFor="sel-subline">SubLine</label>
                  <select
                    id="sel-subline"
                    className="select"
                    value={form.subline}
                    onChange={e => set("subline", e.target.value)}
                  >
                    <option value="">Select SubLine</option>
                    {sublines.map(sl => (
                      <option key={sl.subline_code} value={sl.ui_display_value}>{sl.ui_display_value}</option>
                    ))}
                  </select>
                </div>

              </div>
            </form>
          )}
        </section>

        {/* ── PANEL 2: INSURER RESULTS ── */}
        <section className="panel results-panel">
          <div className="panel-header-row">
            <h2 className="panel-title">
              <span className="step-badge">2</span>
              Insurer Rates
            </h2>
            {calculating && <span className="updating-tag">Updating...</span>}
          </div>


          {/* Loading */}
          {calculating && (
            <div className="loading-state" style={{ padding: "20px 0" }}>
              <div className="spinner spinner-muted" />
              <span>Querying insurer rate engine for {displayDate}...</span>
            </div>
          )}

          {/* Error Banner — user-friendly, no stack traces */}
          {classifiedError && !calculating && (
            <div className={`banner banner-${classifiedError.type === "no-version" ? "warn" : "error"}`}>
              <Icon.Warn />
              <div>
                <strong>{classifiedError.title}</strong>
                <div style={{ marginTop: 4, fontSize: 13 }}>{classifiedError.message}</div>
                {classifiedError.type === "no-version" && (
                  <div className="error-date-hint">
                    Selected date: {displayDate}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ── Date Context Summary (above results) ── */}
          {hasResults && !calculating && (
            <div className="results-date-summary">
              <div className="rds-item">
                <span className="rds-label">Selected Date</span>
                <span className="rds-value">
                  {calcResult.requested_date ? isoToDisplay(calcResult.requested_date) : displayDate}
                </span>
              </div>
              <span className="rds-arrow">→</span>
              <div className="rds-item">
                <span className="rds-label">Rate Effective From</span>
                <span className="rds-value rds-effective">
                  {displayEffectiveDate || "—"}
                </span>
              </div>
              <span className="rds-count">{calcResult.results.length} insurer{calcResult.results.length !== 1 ? "s" : ""}</span>
            </div>
          )}

          {/* ── Insurer Cards Grid ── */}
          {hasResults && !calculating && (
            <div className="insurer-cards-grid">
              {calcResult.results.map((res, i) => (
                <InsurerCard key={`${res.insurer}-${i}`} result={res} />
              ))}
            </div>
          )}

          {/* Empty Initial / Partial State */}
          {!calcResult && !calcError && !calculating && (
            <div className="idle">
              <div className="idle-icon"><Icon.Grid /></div>
              <p>Select Product, SubProduct, State and Location to view insurer inflow rates.</p>
              <p className="idle-sub">
                Insurer combinations will appear automatically once Product, SubProduct, State and Location are selected.
                Business Type and SubLine can then be selected to refine the rates.
              </p>
              <div className="idle-date-hint">
                <Icon.Calendar />
                <span>Today: {displayDate}</span>
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

// ── Insurer Card Component ────────────────────────────────────
// Displays the insurer name and the complete inflow expression.
// No green rate badge. No orange "COMPLETE INFLOW" label. No toggle/caret.
// The full inflow expression is always visible and never truncated.
function InsurerCard({ result }) {
  // The full inflow text — prefer raw_inflow (calculate), fall back to inflow (lookup)
  const fullInflow = result.raw_inflow || result.inflow || null;

  return (
    <div className="insurer-card-3d">
      <div className="card-top-bar">
        <h3 className="insurer-title">{result.insurer}</h3>
      </div>

      {/* Full inflow expression — always visible, never truncated. Scrollable within card. */}
      {fullInflow && (
        <div className="complete-inflow-body">{fullInflow}</div>
      )}
    </div>
  );
}
