// ============================================================
// src/App.jsx — Motor Insurance Inflow Rate Finder
// Backend: FastAPI http://127.0.0.1:8001
// ============================================================

import React, { useState, useEffect, useRef, useCallback } from "react";
import { api } from "./api";
import "./App.css";

// --- Inline SVG Icons ---
const Icon = {
  Shield: () => (
    <svg width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
    </svg>
  ),
  Grid: () => (
    <svg width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <rect x="3" y="3" width="7" height="7" rx="1"/>
      <rect x="14" y="3" width="7" height="7" rx="1"/>
      <rect x="14" y="14" width="7" height="7" rx="1"/>
      <rect x="3" y="14" width="7" height="7" rx="1"/>
    </svg>
  ),
  Warn: () => (
    <svg width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
      <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
    </svg>
  ),
  Sun: () => (
    <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="5"/>
      <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
    </svg>
  ),
  Moon: () => (
    <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
    </svg>
  ),
  Refresh: () => (
    <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <path d="M23 4v6h-6M1 20v-6h6"/>
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
    </svg>
  ),
  Search: () => (
    <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
      <circle cx="11" cy="11" r="8"/>
      <path d="m21 21-4.35-4.35"/>
    </svg>
  )
};

export default function App() {
  // Theme state — default dark, persisted in localStorage
  const [theme, setTheme] = useState(() => localStorage.getItem("inflow-theme") || "dark");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("inflow-theme", theme);
  }, [theme]);

  // Master data loaded from backend APIs
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

  // Form State — Initialized COMPLETELY EMPTY
  const [form, setForm] = useState({
    product: "",
    subproduct: "",
    business_type: "",
    subline: "",
    state: "",
    location: "",
  });

  // Ref for live auto-filtering debounce
  const timerRef = useRef(null);

  // ── Load Master Data on Mount ──────────────────────────────
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

  // ── Derived Options for Dependent Selects ─────────────────────────────
  const selectedProd = products.find(p => p.product_name === form.product);
  const filteredSubproducts = selectedProd
    ? allSubproducts.filter(sp => sp.product_code === selectedProd.product_code)
    : [];

  const selectedState = states.find(s => s.source_state === form.state);
  const filteredLocations = selectedState
    ? allLocations.filter(l => l.state_code === selectedState.state_code)
    : [];

  // ── Live Backend Query Function ────────────────────────────
  const runLiveLookup = useCallback(async (currentForm) => {
    // Requires minimum Product + Subproduct to start lookup
    if (!currentForm.product || !currentForm.subproduct) {
      setCalcResult(null);
      setCalcError(null);
      return;
    }

    setCalculating(true);
    setCalcError(null);

    const payload = {
      product:       currentForm.product,
      subproduct:    currentForm.subproduct,
      business_type: currentForm.business_type || null,
      subline:       currentForm.subline || null,
      state:         currentForm.state || null,
      location:      currentForm.location || null,
      vehicle_make:  null,
      vehicle_model: null,
      engine_cc:     null,
      gvw:           null,
      cpa:           null,
      vehicle_age:   null,
      coverage:      null,
      rule_business_variant: null,
    };

    try {
      const res = await api.calculateInflow(payload);
      setCalcResult(res);
      if (!res.matched || !res.results || res.results.length === 0) {
        setCalcError("No matching insurer rules were found for the selected policy dimensions.");
      }
    } catch (err) {
      setCalcError(err.message || "Error querying rate engine");
    } finally {
      setCalculating(false);
    }
  }, []);

  // ── Update Input & Schedule Debounced Auto Lookup ─────────────────
  const set = (field, value) => {
    setForm((prev) => {
      const next = { ...prev, [field]: value };

      // Reset dependent fields on parent change
      if (field === "product") {
        next.subproduct = "";
      }
      if (field === "state") {
        next.location = "";
      }

      // Schedule live lookup update
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        runLiveLookup(next);
      }, 150);

      return next;
    });
  };

  // ── Manual Find Inflow Trigger ──────────────────────────────────
  const handleFindInflow = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    runLiveLookup(form);
  };

  // ── Reset Form ────────────────────────────────────────────────
  const handleReset = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setForm({
      product: "",
      subproduct: "",
      business_type: "",
      subline: "",
      state: "",
      location: "",
    });
    setCalcResult(null);
    setCalcError(null);
  };

  return (
    <div className="app">
      {/* HEADER */}
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
            title="Reset selections"
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
        {/* ── TOP SECTION: HORIZONTAL POLICY DIMENSIONS ── */}
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
            <form onSubmit={(e) => { e.preventDefault(); handleFindInflow(); }}>
              {/* Horizontal grid of 6 Selectors (No Red Asterisks) */}
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

                {/* 2. SubProduct */}
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

                {/* 3. Business Type */}
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

                {/* 4. SubLine */}
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

                {/* 5. State */}
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

                {/* 6. Location */}
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

                {/* Find Inflow Button integrated in horizontal bar */}
                <div className="form-group action-group">
                  <label className="label">&nbsp;</label>
                  <button
                    id="btn-find-inflow"
                    type="button"
                    className="calc-btn"
                    onClick={handleFindInflow}
                    disabled={calculating || !form.product || !form.subproduct}
                    title={!form.product || !form.subproduct ? "Select Product & SubProduct first" : "Query rate engine for current selections"}
                  >
                    {calculating
                      ? (<><div className="spinner" /> Searching...</>)
                      : (<><Icon.Search /> Find Inflow</>)
                    }
                  </button>
                </div>
              </div>
            </form>
          )}
        </section>

        {/* ── BOTTOM SECTION: HORIZONTAL PREMIUM INSURER CARDS ── */}
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
              <span>Querying insurer rate engine...</span>
            </div>
          )}

          {/* Error Banner */}
          {calcError && !calculating && (
            <div className="banner banner-error">
              <Icon.Warn />
              <div>
                <strong>No Match Found</strong>
                <div style={{ marginTop: 2, fontSize: 13 }}>{calcError}</div>
              </div>
            </div>
          )}

          {/* Premium Horizontal Insurer Cards Layout */}
          {calcResult?.matched && calcResult.results && calcResult.results.length > 0 && !calculating && (
            <div className="insurer-cards-grid">
              {calcResult.results.map((res, i) => (
                <div key={`${res.insurer}-${i}`} className="insurer-card-3d">
                  <div className="card-top-bar">
                    <h3 className="insurer-title">{res.insurer}</h3>
                    <div className="rate-pill">
                      {res.rate !== null && res.rate !== undefined
                        ? `${Number(res.rate).toFixed(2)}%`
                        : "—"}
                    </div>
                  </div>

                  {res.raw_inflow && (
                    <div className="inflow-section">
                      <div className="inflow-heading">COMPLETE INFLOW</div>
                      <div className="complete-inflow-body">{res.raw_inflow}</div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Empty Initial State */}
          {!calcResult && !calcError && !calculating && (
            <div className="idle">
              <div className="idle-icon"><Icon.Grid /></div>
              <p>Select policy dimensions to view insurer rates.</p>
              <p className="idle-sub">Insurer rules will refresh automatically as you select dimensions.</p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
