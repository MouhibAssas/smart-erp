import { useQuery } from "@tanstack/react-query";
import {
  getKpis as fetchKpis,
  getRecentInvoices as fetchRecentInvoices,
  getMonthlyRevenue as fetchRevenue,
} from "../services/dashboardApi";

// 45 seconds — middle ground between freshness and noise
const STALE = 45 * 1000;

/**
 * KPIs: unpaid counts, residuals, current month revenue
 */
export const useKpis = () =>
  useQuery({
    queryKey: ["dashboard", "kpis"],
    queryFn: fetchKpis,
    staleTime: STALE,
    cacheTime: STALE * 2,
    refetchOnWindowFocus: true,
    retry: 1,
  });

/**
 * Recent invoices (type: 'customer' | 'vendor' | 'both')
 * The dashboardApi expects (limit, invoiceType).
 */
export const useRecentInvoices = (type = "customer", limit = 10) =>
  useQuery({
    queryKey: ["dashboard", "invoices", type, limit],
    queryFn: () => fetchRecentInvoices(limit, type === "both" ? "both" : type),
    staleTime: STALE,
    cacheTime: STALE * 2,
    refetchOnWindowFocus: true,
    retry: 1,
  });

/**
 * Revenue timeseries (months window)
 */
export const useRevenue = (months = 6) =>
  useQuery({
    queryKey: ["dashboard", "revenue", months],
    queryFn: () => fetchRevenue(months),
    staleTime: STALE,
    cacheTime: STALE * 4,
    refetchOnWindowFocus: false,
    enabled: months > 0,
    retry: 1,
  });
