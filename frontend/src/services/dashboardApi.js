// Dashboard data layer abstraction
// Wraps all dashboard API calls for clean data fetching

import httpClient from "./httpClient";

/**
 * Fetch dashboard KPIs (unpaid counts, residuals, monthly revenue).
 * Returns: { kpis, unpaid_customer_list, unpaid_vendor_list, ... }
 */
export const getKpis = async () => {
  const { data } = await httpClient.get("/dashboard/kpis");
  return data;
};

/**
 * Fetch recent unpaid invoices (paginated, filterable by type).
 * @param {number} limit - Max invoices to return (default: 8)
 * @param {string} invoiceType - Filter by type: "both", "customer", "vendor" (default: "both")
 * Returns: { invoices: [...] }
 */
export const getRecentInvoices = async (limit = 8, invoiceType = "both") => {
  const { data } = await httpClient.get("/dashboard/invoices/recent", {
    params: { limit, invoice_type: invoiceType },
  });
  return data;
};

/**
 * Fetch monthly revenue data (timeseries, rolling window).
 * @param {number} months - Number of months to retrieve (default: 6)
 * Returns: { data: [{ month, year, month_num, revenue }, ...], ... }
 */
export const getMonthlyRevenue = async (months = 6) => {
  const { data } = await httpClient.get("/dashboard/revenue/monthly", {
    params: { months },
  });
  return data;
};
