// ============================================================
// src/App.jsx — Motor Insurance Inflow / Outflow Rate Finder
// Backend: FastAPI http://127.0.0.1:8001
// ============================================================

import React, { useState, useEffect, useRef, useCallback } from "react";
import { api } from "./api";
import "./App.css";

// ── Date Utilities ─────────────────────────────────────────────────────────
/** Returns today's date as a YYYY-MM-DD string (browser local date). */
function todayISO() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** Converts YYYY-MM-DD → DD-MMM-YYYY (e.g. 2026-09-01 → 01-Sep-2026) for display. */
function isoToDisplayFormatted(iso) {
  if (!iso) return "";
  const parts = iso.split("-");
  if (parts.length !== 3) return iso;
  const [y, m, d] = parts;
  const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const mIdx = parseInt(m, 10) - 1;
  const monthStr = monthNames[mIdx] || m;
  return `${d}-${monthStr}-${y}`;
}

/** Determines Business Rate Type (INFLOW vs OUTFLOW) based on Effective Date.
 *  July & August 2026 → INFLOW
 *  September 2026+ → OUTFLOW
 */
function deriveRateType(dateIsoStr) {
  if (!dateIsoStr) return "INFLOW";
  const [y, m] = dateIsoStr.split("-");
  const monthNum = parseInt(m, 10);
  if (y === "2026" && monthNum >= 9) {
    return "OUTFLOW";
  }
  if (parseInt(y, 10) > 2026) {
    return "OUTFLOW";
  }
  return "INFLOW";
}

// ── Inline SVG Icons ───────────────────────────────────────────────────────
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
  Calendar: () => (
    <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  ),
};

// ── Error Classifier ───────────────────────────────────────────────────────
function classifyError(errMsg) {
  if (!errMsg) return null;
  if (errMsg.includes("No Rule Master version exists on or before")) {
    return {
      type: "no-version",
      title: "No Rate Version Available",
      message: "No rate rules exist on or before the selected effective date. Please select a date on or after 2026-07-01.",
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
      message: "Cannot connect to the rate engine API server at http://127.0.0.1:8001.",
    };
  }
  return {
    type: "unknown",
    title: "Lookup Error",
    message: errMsg,
  };
}

// ── Main Component ─────────────────────────────────────────────────────────
export default function App() {
  // Theme state — default dark, persisted in localStorage
  const [theme, setTheme] = useState(
    () => localStorage.getItem("inflow-theme") || "dark"
  );

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("inflow-theme", theme);
  }, [theme]);

  // Date State — default to dynamic todayISO()
  const [selectedDate, setSelectedDate] = useState(() => todayISO());

  // Master Data State
  const [products, setProducts] = useState([]);
  const [allSubproducts, setAllSubproducts] = useState([]);
  const [businessTypes, setBusinessTypes] = useState([]);
  const [sublines, setSublines] = useState([]);
  const [states, setStates] = useState([]);
  const [allLocations, setAllLocations] = useState([]);

  // UI States
  const [initialLoading, setInitialLoading] = useState(true);
  const [calculating, setCalculating] = useState(false);
  const [calcResult, setCalcResult] = useState(null);
  const [calcError, setCalcError] = useState(null);

  // Form State
  const [form, setForm] = useState({
    product: "",
    subproduct: "",
    state: "",
    location: "",
    business_type: "",
    subline: "",
  });

  const timerRef = useRef(null);

  // Load Master Data on Mount
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
        setCalcError("Backend API service is currently unavailable.");
      } finally {
        setInitialLoading(false);
      }
    }
    load();
  }, []);

  // Derived Options for Dependent Selects
  const selectedProd = products.find((p) => p.product_name === form.product);
  const filteredSubproducts = selectedProd
    ? allSubproducts.filter((sp) => sp.product_code === selectedProd.product_code)
    : [];

  const selectedState = states.find((s) => s.source_state === form.state);
  const filteredLocations = selectedState
    ? allLocations.filter((l) => l.state_code === selectedState.state_code)
    : [];

  // Core Automatic Lookup Function
  const runLiveLookup = useCallback(async (currentForm, dateISO) => {
    if (!dateISO || !currentForm.product || !currentForm.subproduct || !currentForm.state || !currentForm.location) {
      setCalcResult(null);
      setCalcError(null);
      return;
    }

    setCalculating(true);
    setCalcError(null);

    const payload = {
      requested_date: dateISO,
      product: currentForm.product,
      subproduct: currentForm.subproduct,
      state: currentForm.state,
      location: currentForm.location,
      business_type: currentForm.business_type || null,
      subline: currentForm.subline || null,
    };

    try {
      const res = await api.lookupInflow(payload);
      setCalcResult(res);

      if (!res.matched || !res.results || res.results.length === 0) {
        setCalcError(res.error || "No matching insurer rules were found for the selected policy dimensions.");
      }
    } catch (err) {
      setCalcError(err.message || "Error querying rate engine.");
      setCalcResult(null);
    } finally {
      setCalculating(false);
    }
  }, []);

  // Form Field Change Handler — Triggers Auto Lookup
  const set = (field, value) => {
    setForm((prev) => {
      const next = { ...prev, [field]: value };
      if (field === "product") next.subproduct = "";
      if (field === "state") next.location = "";

      setCalcResult(null);
      setCalcError(null);

      if (timerRef.current) clearTimeout(timerRef.current);

      if (next.product && next.subproduct && next.state && next.location) {
        timerRef.current = setTimeout(() => {
          runLiveLookup(next, selectedDate);
        }, 150);
      }

      return next;
    });
  };

  // Date Change Handler — Triggers Auto Lookup
  const handleDateChange = (newDateISO) => {
    setSelectedDate(newDateISO);
    setCalcResult(null);
    setCalcError(null);

    if (timerRef.current) clearTimeout(timerRef.current);

    if (form.product && form.subproduct && form.state && form.location) {
      timerRef.current = setTimeout(() => {
        runLiveLookup(form, newDateISO);
      }, 150);
    }
  };

  // Reset Form
  const handleReset = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setSelectedDate(todayISO());
    setForm({
      product: "",
      subproduct: "",
      state: "",
      location: "",
      business_type: "",
      subline: "",
    });
    setCalcResult(null);
    setCalcError(null);
  };

  const classifiedError = classifyError(calcError);
  const effectiveDateUsed = calcResult?.effective_date_used || selectedDate;
  const rateType = deriveRateType(effectiveDateUsed);
  const displayEffectiveDate = isoToDisplayFormatted(effectiveDateUsed);
  const hasResults = calcResult?.matched && calcResult.results && calcResult.results.length > 0;

  return (
    <div className="app">
      {/* HEADER */}
      <header className="header">
        <div className="brand">
          <div className="brand-icon"><Icon.Shield /></div>
          <div>
            <h1 className="brand-title">Motor Insurance Inflow / Outflow Rate Finder</h1>
            <p className="brand-sub">Progressive Live Inflow / Outflow Rate Engine</p>
          </div>
        </div>
        <div className="header-actions">
          <button
            type="button"
            className="theme-btn"
            onClick={handleReset}
            title="Reset all selections"
          >
            <Icon.Refresh /> Reset
          </button>
          <button
            id="btn-theme"
            className="theme-btn"
            onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
            title="Toggle dark/light mode"
          >
            {theme === "dark" ? <Icon.Sun /> : <Icon.Moon />}
            {theme === "dark" ? " Light" : " Dark"}
          </button>
        </div>
      </header>

      {/* PROMINENT IMPORTANT NOTE BANNER */}
      <div className="important-note-banner">
        <span className="note-icon">⚠️</span>
        <div className="note-content">
          <strong>IMPORTANT NOTE:</strong> July &amp; August 2026 rates are based on <strong>INFLOW</strong>. September 2026 rates are based on <strong>OUTFLOW</strong>.
        </div>
      </div>

      <main className="main-content">
        {/* ── STEP 1: DATE-FIRST POLICY DIMENSIONS ── */}
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
            <form onSubmit={(e) => e.preventDefault()}>
              {/* Date-First Horizontal Layout (7 Policy Selectors) */}
              <div className="policy-grid">
                {/* 1. Effective Date */}
                <div className="form-group">
                  <label className="label" htmlFor="inp-effective-date">Effective Date</label>
                  <input
                    id="inp-effective-date"
                    type="date"
                    className="select"
                    value={selectedDate}
                    onChange={(e) => handleDateChange(e.target.value)}
                  />
                </div>

                {/* 2. Product */}
                <div className="form-group">
                  <label className="label" htmlFor="sel-product">Product</label>
                  <select
                    id="sel-product"
                    className="select"
                    value={form.product}
                    onChange={(e) => set("product", e.target.value)}
                  >
                    <option value="">Select Product</option>
                    {products.map((p) => (
                      <option key={p.product_code} value={p.product_name}>{p.product_name}</option>
                    ))}
                  </select>
                </div>

                {/* 3. SubProduct */}
                <div className="form-group">
                  <label className="label" htmlFor="sel-subproduct">SubProduct</label>
                  <select
                    id="sel-subproduct"
                    className="select"
                    value={form.subproduct}
                    onChange={(e) => set("subproduct", e.target.value)}
                    disabled={!form.product}
                  >
                    <option value="">Select SubProduct</option>
                    {filteredSubproducts.map((sp) => (
                      <option key={sp.subproduct_code} value={sp.subproduct_name}>{sp.subproduct_name}</option>
                    ))}
                  </select>
                </div>

                {/* 4. State */}
                <div className="form-group">
                  <label className="label" htmlFor="sel-state">State</label>
                  <select
                    id="sel-state"
                    className="select"
                    value={form.state}
                    onChange={(e) => set("state", e.target.value)}
                  >
                    <option value="">Select State</option>
                    {states.map((st) => (
                      <option key={st.state_code} value={st.source_state}>{st.ui_display_value || st.source_state}</option>
                    ))}
                  </select>
                </div>

                {/* 5. Location */}
                <div className="form-group">
                  <label className="label" htmlFor="sel-location">Location</label>
                  <select
                    id="sel-location"
                    className="select"
                    value={form.location}
                    onChange={(e) => set("location", e.target.value)}
                    disabled={!form.state}
                  >
                    <option value="">Select Location</option>
                    {filteredLocations.map((loc) => (
                      <option key={loc.location_code} value={loc.source_location}>{loc.ui_display_value || loc.source_location}</option>
                    ))}
                  </select>
                </div>

                {/* 6. Business Type (Optional Refinement) */}
                <div className="form-group">
                  <label className="label" htmlFor="sel-biztype">Business Type</label>
                  <select
                    id="sel-biztype"
                    className="select"
                    value={form.business_type}
                    onChange={(e) => set("business_type", e.target.value)}
                  >
                    <option value="">Select Business Type</option>
                    {businessTypes.map((bt) => (
                      <option key={bt.business_type_code} value={bt.ui_display_value}>{bt.ui_display_value}</option>
                    ))}
                  </select>
                </div>

                {/* 7. SubLine (Optional Refinement) */}
                <div className="form-group">
                  <label className="label" htmlFor="sel-subline">SubLine</label>
                  <select
                    id="sel-subline"
                    className="select"
                    value={form.subline}
                    onChange={(e) => set("subline", e.target.value)}
                  >
                    <option value="">Select SubLine</option>
                    {sublines.map((sl) => (
                      <option key={sl.subline_code} value={sl.ui_display_value}>{sl.ui_display_value}</option>
                    ))}
                  </select>
                </div>
              </div>
            </form>
          )}
        </section>

        {/* ── STEP 2: INSURER RATES RESULTS ── */}
        <section className="panel results-panel">
          <div className="panel-header-row">
            <h2 className="panel-title">
              <span className="step-badge">2</span>
              Insurer Rates
            </h2>
            {calculating && <span className="updating-tag">Updating...</span>}
          </div>

          {/* Loading Indicator */}
          {calculating && (
            <div className="loading-state" style={{ padding: "20px 0" }}>
              <div className="spinner spinner-muted" />
              <span>Querying insurer rate engine for {isoToDisplayFormatted(selectedDate)}...</span>
            </div>
          )}

          {/* Classified Error Banner */}
          {classifiedError && !calculating && (
            <div className={`banner banner-${classifiedError.type === "no-version" ? "warn" : "error"}`}>
              <Icon.Warn />
              <div>
                <strong>{classifiedError.title}</strong>
                <div style={{ marginTop: 4, fontSize: 13 }}>{classifiedError.message}</div>
              </div>
            </div>
          )}

          {/* Results Summary Header Block */}
          {hasResults && !calculating && (
            <div className="results-date-summary">
              <div className="rds-item">
                <span className="rds-label">Effective Date Used</span>
                <span className="rds-value rds-effective">{displayEffectiveDate}</span>
              </div>

              <div className="rds-item">
                <span className="rds-label">Rate Type</span>
                <span className={`rate-type-badge rate-type-${rateType.toLowerCase()}`}>
                  {rateType}
                </span>
              </div>

              <div className="rds-item">
                <span className="rds-label">Available Insurers</span>
                <span className="rds-value">{calcResult.results.length} Partners</span>
              </div>
            </div>
          )}

          {/* Insurer Cards Grid */}
          {hasResults && !calculating && (
            <div className="insurer-cards-grid">
              {calcResult.results.map((res, i) => (
                <InsurerCard key={`${res.insurer}-${i}`} result={res} />
              ))}
            </div>
          )}

          {/* Empty Initial State */}
          {!calcResult && !calcError && !calculating && (
            <div className="idle">
              <div className="idle-icon"><Icon.Grid /></div>
              <p>Select <strong>Effective Date</strong>, <strong>Product</strong>, <strong>SubProduct</strong>, <strong>State</strong>, and <strong>Location</strong> to view insurer rates.</p>
              <p className="idle-sub">Insurer rules refresh automatically as valid policy dimensions are selected.</p>
              <div className="idle-date-hint">
                <Icon.Calendar />
                <span>Selected Date: {isoToDisplayFormatted(selectedDate)}</span>
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

// ── Insurer Card Component ─────────────────────────────────────────────────
function InsurerCard({ result }) {
  const fullInflow = result.raw_inflow || result.inflow || null;

  return (
    <div className="insurer-card-3d">
      <div className="card-top-bar">
        <h3 className="insurer-title">{result.insurer}</h3>
      </div>

      {/* Complete Rate Expression — always visible, un-truncated */}
      {fullInflow && (
        <div className="complete-inflow-body">{fullInflow}</div>
      )}
    </div>
  );
}