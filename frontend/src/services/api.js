/**
 * Frontend API Service for Smart Electricity Wastage Detection System.
 * Connects to FastAPI backend at /api/v1 endpoints.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export const SystemAPI = {
  /**
   * Public liveness and readiness probe for load balancers and frontend navbar.
   */
  getPublicHealth: async () => {
    const healthUrl = import.meta.env.VITE_API_BASE_URL 
      ? `${import.meta.env.VITE_API_BASE_URL.replace('/api/v1', '')}/health` 
      : '/health';
    const res = await fetch(healthUrl);
    return handleResponse(res);
  },
};

async function handleResponse(response) {
  if (!response.ok) {
    let errorDetail = `HTTP ${response.status} ${response.statusText}`;
    try {
      const errorJson = await response.json();
      if (errorJson.detail) {
        errorDetail = errorJson.detail;
      }
    } catch {
      // response was not JSON
    }
    throw new Error(errorDetail);
  }
  return response.json();
}

export const CustomerAPI = {
  /**
   * Look up customer profile by consumer number (No OTP required).
   */
  lookupCustomer: async (consumerNumber) => {
    const res = await fetch(`${API_BASE_URL}/customer/lookup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ consumer_number: consumerNumber.trim().toUpperCase() }),
    });
    return handleResponse(res);
  },

  /**
   * Fetch customer high-level consumption & wastage KPI summary.
   */
  getSummary: async (consumerNumber) => {
    const res = await fetch(`${API_BASE_URL}/customer/${consumerNumber}/summary`);
    return handleResponse(res);
  },

  /**
   * Fetch customer consumption history (actual readings).
   */
  getConsumption: async (consumerNumber, limit = 500) => {
    const res = await fetch(`${API_BASE_URL}/customer/${consumerNumber}/consumption?limit=${limit}`);
    return handleResponse(res);
  },

  /**
   * Fetch customer wastage report (sanitized, zero ML jargon).
   */
  getWastageReport: async (consumerNumber) => {
    const res = await fetch(`${API_BASE_URL}/customer/${consumerNumber}/wastage-report`);
    return handleResponse(res);
  },

  /**
   * Fetch personalized actionable energy-saving recommendations.
   */
  getRecommendations: async (consumerNumber) => {
    const res = await fetch(`${API_BASE_URL}/customer/${consumerNumber}/recommendations`);
    return handleResponse(res);
  },

  /**
   * Persist implementation toggle for an energy-saving recommendation.
   */
  implementRecommendation: async (consumerNumber, recId) => {
    const res = await fetch(`${API_BASE_URL}/customer/${consumerNumber}/recommendations/${recId}/implemented`, {
      method: 'POST',
    });
    return handleResponse(res);
  },
};

/**
 * Returns Authorization headers using the active signed session token.
 */
function getAdminHeaders() {
  const token = sessionStorage.getItem('watt_admin_token');
  const headers = { 'Content-Type': 'application/json' };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

export const AdminAPI = {
  /**
   * Authenticate administrator with passkey and establish a signed session.
   */
  authenticate: async (passkey) => {
    const res = await fetch(`${API_BASE_URL}/admin/auth`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ passkey }),
    });
    const data = await handleResponse(res);
    if (data.access_token) {
      sessionStorage.setItem('watt_admin_token', data.access_token);
    }
    return data;
  },

  /**
   * Fetch system health and infrastructure telemetry.
   */
  getHealth: async () => {
    const res = await fetch(`${API_BASE_URL}/admin/health`, {
      headers: getAdminHeaders(),
    });
    return handleResponse(res);
  },

  /**
   * Fetch dataset provenance and quality audit metadata.
   */
  getDatasets: async () => {
    const res = await fetch(`${API_BASE_URL}/admin/datasets`, {
      headers: getAdminHeaders(),
    });
    return handleResponse(res);
  },

  /**
   * Fetch evaluated model performance metrics.
   */
  getModelMetrics: async () => {
    const res = await fetch(`${API_BASE_URL}/admin/metrics`, {
      headers: getAdminHeaders(),
    });
    return handleResponse(res);
  },

  /**
   * Fetch multi-horizon forecasting benchmarks.
   */
  getForecastingBenchmarks: async () => {
    const res = await fetch(`${API_BASE_URL}/admin/forecasting-benchmarks`, {
      headers: getAdminHeaders(),
    });
    return handleResponse(res);
  },

  /**
   * Fetch wastage detection engine benchmarks and persistence tuning sweeps.
   */
  getWastageBenchmarks: async () => {
    const res = await fetch(`${API_BASE_URL}/admin/wastage-benchmarks`, {
      headers: getAdminHeaders(),
    });
    return handleResponse(res);
  },

  /**
   * Fetch all registered customer accounts.
   */
  getCustomers: async () => {
    const res = await fetch(`${API_BASE_URL}/admin/customers`, {
      headers: getAdminHeaders(),
    });
    return handleResponse(res);
  },

  /**
   * Fetch active wastage engine configuration.
   */
  getWastageConfig: async () => {
    const res = await fetch(`${API_BASE_URL}/admin/wastage-config`, {
      headers: getAdminHeaders(),
    });
    return handleResponse(res);
  },

  /**
   * Update active wastage engine configuration.
   */
  updateWastageConfig: async (config) => {
    const res = await fetch(`${API_BASE_URL}/admin/wastage-config`, {
      method: 'POST',
      headers: getAdminHeaders(),
      body: JSON.stringify(config),
    });
    return handleResponse(res);
  },

  /**
   * Fetch automated test suite status.
   */
  getTestStatus: async () => {
    const res = await fetch(`${API_BASE_URL}/admin/test-status`, {
      headers: getAdminHeaders(),
    });
    return handleResponse(res);
  },
};
