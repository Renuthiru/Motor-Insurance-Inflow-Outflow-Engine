// ============================================================
// src/api.js
// ============================================================
// Frontend API Client for Motor Insurance Inflow Backend
// ============================================================

const API_BASE_URL = "http://127.0.0.1:8001";

async function handleResponse(response) {
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`API Error (${response.status}): ${errorText}`);
  }
  return response.json();
}

export const api = {
  // 1. System Health
  async getHealth() {
    const res = await fetch(`${API_BASE_URL}/health`);
    return handleResponse(res);
  },

  // 2. Master Data APIs
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

  // 3. Rate Calculation Engine API
  async calculateInflow(payload) {
    const res = await fetch(`${API_BASE_URL}/calculate-inflow`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },
};
