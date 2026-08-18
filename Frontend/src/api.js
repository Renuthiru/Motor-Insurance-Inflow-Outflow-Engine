// ============================================================
// src/api.js
// ============================================================
// Centralized API client for Motor Insurance Inflow Backend.
//
// EFFECTIVE-DATE ARCHITECTURE:
//   Every Rule Master-dependent call MUST receive requested_date.
//   The backend resolves effective_date_used via:
//     MAX(effective_from) WHERE effective_from <= requested_date
//   The frontend NEVER performs date resolution itself.
//   The frontend only displays effective_date_used from the response.
// ============================================================

const API_BASE_URL = "http://127.0.0.1:8001";

async function handleResponse(response) {
  if (!response.ok) {
    const errorText = await response.text();
    // Parse structured FastAPI error if possible, otherwise use raw text
    try {
      const parsed = JSON.parse(errorText);
      throw new Error(parsed.detail || parsed.error || errorText);
    } catch {
      throw new Error(`API Error (${response.status}): ${errorText}`);
    }
  }
  return response.json();
}

export const api = {
  // ── System Health ─────────────────────────────────────────
  async getHealth() {
    const res = await fetch(`${API_BASE_URL}/health`);
    return handleResponse(res);
  },

  // ── Master Data (date-independent) ───────────────────────
  async getProducts() {
    const res = await fetch(`${API_BASE_URL}/products`);
    return handleResponse(res);
  },

  async getSubproducts() {
    const res = await fetch(`${API_BASE_URL}/subproducts`);
    return handleResponse(res);
  },

  async getBusinessTypes() {
    const res = await fetch(`${API_BASE_URL}/business-types`);
    return handleResponse(res);
  },

  async getSublines() {
    const res = await fetch(`${API_BASE_URL}/sublines`);
    return handleResponse(res);
  },

  async getStates() {
    const res = await fetch(`${API_BASE_URL}/states`);
    return handleResponse(res);
  },

  async getLocations() {
    const res = await fetch(`${API_BASE_URL}/locations`);
    return handleResponse(res);
  },

  // ── Effective Dates Availability ──────────────────────────
  // Returns the distinct Rule Master versions available in the DB.
  // Used for informational display only — NOT to restrict the calendar.
  async getEffectiveDates() {
    const res = await fetch(`${API_BASE_URL}/rule-master/effective-dates`);
    return handleResponse(res);
  },

  // ── Date-Aware Inflow Lookup (raw business names) ─────────
  // requested_date: "YYYY-MM-DD" — user's selected calendar date.
  // The backend resolves effective_date_used via MAX(effective_from) ≤ requested_date.
  // Response includes both requested_date and effective_date_used.
  async lookupInflow(payload) {
    // payload must include: requested_date, product, subproduct,
    // business_type, subline, state, location
    const res = await fetch(`${API_BASE_URL}/inflow-lookup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },

  // ── Date-Aware Inflow Calculation Engine ──────────────────
  // Used when vehicle specs (CC, make, CPA, GVW) are also provided.
  // requested_date is always required.
  async calculateInflow(payload) {
    const res = await fetch(`${API_BASE_URL}/calculate-inflow`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },
};
