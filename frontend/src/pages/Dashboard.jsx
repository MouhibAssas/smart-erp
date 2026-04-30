import { useState } from "react";
import BarChart from "../components/dashboard/BarChart";
import DonutChart from "../components/dashboard/DonutChart";
import InvoiceRow from "../components/dashboard/InvoiceRow";
import KpiCard from "../components/dashboard/KpiCard";
import { fmt } from "../components/dashboard/formatters";
import { useKpis, useRecentInvoices, useRevenue } from "../hooks/useDashboard";
import "./Dashboard.css";

// ─── tiny auth helpers ────────────────────────────────────────────────────────
// In a real app this comes from a JWT / session context.
// For now we persist a chosen demo role in localStorage so the UI is testable.
const ROLES = ["admin", "operator", "viewer"];
const getRoleFromStorage = () => localStorage.getItem("demo_role") || "admin";
const setRoleInStorage   = (r) => localStorage.setItem("demo_role", r);

// ─── permission matrix ────────────────────────────────────────────────────────
const PERMISSIONS = {
  admin:    { viewDashboard: true,  viewAdmin: true,  createInvoice: true,  viewRevenue: true  },
  operator: { viewDashboard: true,  viewAdmin: false, createInvoice: true,  viewRevenue: true  },
  viewer:   { viewDashboard: true,  viewAdmin: false, createInvoice: false, viewRevenue: false },
};

const can = (role, action) => !!(PERMISSIONS[role] || {})[action];

// ─── Main Dashboard ───────────────────────────────────────────────────────────
export default function Dashboard() {
  const [role, setRole] = useState(getRoleFromStorage());
  // error is derived from query state
  // const [error, setError] = useState("");
  const [lastRefresh, setLastRefresh] = useState(null);
  // --- React Query via hooks (45s stale configured in hooks)
  const monthsWindow = 6;
  const kpisQuery = useKpis();
  const recentQuery = useRecentInvoices("both", 8);
  const revenueQuery = useRevenue(monthsWindow);

  // Derived UI state from queries (avoid extra setState inside effects)
  const kpis = kpisQuery.data?.kpis ?? null;
  const recentFromRoute = (recentQuery.data?.invoices || []).map((i) => ({
    ...i,
    _type: i?.move_type === "in_invoice" ? "vendor" : "customer",
  }));
  const fallbackFromKpis = [
    ...(kpisQuery.data?.unpaid_customer_list || []).map((i) => ({ ...i, _type: "customer" })),
    ...(kpisQuery.data?.unpaid_vendor_list || []).map((i) => ({ ...i, _type: "vendor" })),
  ].slice(0, 8);
  const derivedRecentInvoices = recentFromRoute.length > 0 ? recentFromRoute : fallbackFromKpis;
  const derivedRevenueData = revenueQuery.data?.data || [];

  const loading = kpisQuery.isLoading || recentQuery.isLoading;

  const errorMessage = kpisQuery.isError ? "Could not load dashboard data. Check your Odoo connection." : "";

  // `lastRefresh` is set manually on user refresh to avoid cascading state updates.

  const handleRoleChange = (newRole) => {
    setRole(newRole);
    setRoleInStorage(newRole);
  };

  // Donut segments
  const donutSegments = kpis ? [
    { label: "Unpaid invoices", value: kpis.unpaid_customer_invoices, color: "var(--dash-accent)" },
    { label: "Unpaid bills",    value: kpis.unpaid_vendor_bills,      color: "var(--dash-muted-2)" },
  ] : [];

  return (
    <div className="dash-root">
      {/* ── Top bar ── */}
      <div className="dash-topbar">
        <div className="dash-topbar-left">
          <h1 className="dash-title">Dashboard</h1>
          {lastRefresh && (
            <span className="dash-refresh-ts">
              Updated {lastRefresh.toLocaleTimeString("fr-TN", { hour: "2-digit", minute: "2-digit" })}
            </span>
          )}
        </div>
        <div className="dash-topbar-right">
          {/* Demo role switcher */}
          <div className="role-switcher">
            <span className="role-switcher-label">Demo role:</span>
            {ROLES.map((r) => (
              <button
                key={r}
                onClick={() => handleRoleChange(r)}
                className={`role-btn role-btn-${r} ${role === r ? "role-btn-active" : ""}`}
                type="button"
              >
                {r}
              </button>
            ))}
          </div>
          
          <button
            className="dash-refresh-btn"
            onClick={() => {
                kpisQuery.refetch();
                recentQuery.refetch();
                if (can(role, "viewRevenue")) revenueQuery.refetch();
                setLastRefresh(new Date());
              }}
            type="button"
          >
            ↺ Refresh
          </button>
        </div>
      </div>

      {/* ── Permission banner for viewer ── */}
      {role === "viewer" && (
        <div className="dash-permission-banner">
          <span className="dash-perm-icon">👁</span>
          <span>You are in <strong>Viewer</strong> mode — read-only access. Revenue charts and invoice creation are restricted.</span>
        </div>
      )}

      {errorMessage && <div className="dash-error">{errorMessage}</div>}

      {/* ── KPI Grid ── */}
      <div className="kpi-grid">
        <KpiCard
          label="Unpaid Customer Invoices"
          value={kpis ? `${kpis.unpaid_customer_invoices}` : "—"}
          sub={kpis ? `${fmt(kpis.unpaid_customer_residual)} TND outstanding` : null}
          accent="blue"
          icon="📄"
          loading={loading}
        />
        <KpiCard
          label="Unpaid Vendor Bills"
          value={kpis ? `${kpis.unpaid_vendor_bills}` : "—"}
          sub={kpis ? `${fmt(kpis.unpaid_vendor_residual)} TND due` : null}
          accent="orange"
          icon="📥"
          loading={loading}
        />
        {can(role, "viewRevenue") ? (
          <KpiCard
            label={`Revenue — ${kpis?.month || "This month"}`}
            value={kpis ? `${fmt(kpis.monthly_revenue)} TND` : "—"}
            sub="Posted customer invoices"
            accent="green"
            icon="📈"
            loading={loading}
          />
        ) : (
          <div className="kpi-card kpi-locked">
            <div className="kpi-top">
              <span className="kpi-icon">🔒</span>
              <span className="kpi-label">Revenue</span>
            </div>
            <div className="kpi-locked-msg">Restricted — Operator+ only</div>
          </div>
        )}
        <KpiCard
          label="Net Position"
          value={
            kpis
              ? `${fmt(kpis.unpaid_customer_residual - kpis.unpaid_vendor_residual)} TND`
              : "—"
          }
          sub="Receivable minus payable"
          accent={
            kpis
              ? kpis.unpaid_customer_residual >= kpis.unpaid_vendor_residual
                ? "green"
                : "red"
              : "gray"
          }
          icon="⚖️"
          loading={loading}
        />
      </div>

      {/* ── Charts row ── */}
      <div className="charts-row">
        {/* Revenue bar chart */}
        {can(role, "viewRevenue") && (
          <div className="chart-card chart-card-wide">
            <div className="chart-card-header">
              <h2 className="chart-title">Monthly Revenue</h2>
              <span className="chart-subtitle">Last 6 months · Posted invoices</span>
            </div>
            {revenueQuery.isLoading ? (
              <div className="chart-loading">
                <div className="chart-spinner" />
              </div>
              ) : derivedRevenueData.length > 0 ? (
              <>
                <BarChart data={derivedRevenueData} height={130} />
                <div className="chart-bar-legend">
                  {derivedRevenueData.map((d, i) => (
                    <div key={i} className={`chart-bar-row ${i === derivedRevenueData.length - 1 ? "chart-bar-row-last" : ""}`}>
                      <span className="chart-bar-month">{d.month}</span>
                      <span className="chart-bar-val">{fmt(d.revenue)} TND</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="chart-empty">No revenue data available</div>
            )}
          </div>
        )}

        {/* Donut: unpaid distribution */}
        <div className="chart-card">
          <div className="chart-card-header">
            <h2 className="chart-title">Unpaid Breakdown</h2>
            <span className="chart-subtitle">By invoice type</span>
          </div>
          {loading ? (
            <div className="chart-loading"><div className="chart-spinner" /></div>
          ) : donutSegments.some(s => s.value > 0) ? (
            <DonutChart segments={donutSegments} size={100} />
          ) : (
            <div className="chart-empty">All invoices paid 🎉</div>
          )}
        </div>

        {/* Quick stats */}
        <div className="chart-card">
          <div className="chart-card-header">
            <h2 className="chart-title">Quick Stats</h2>
            <span className="chart-subtitle">Summary</span>
          </div>
          <div className="quick-stats">
            {[
              { label: "Total unpaid",    val: kpis ? kpis.unpaid_customer_invoices + kpis.unpaid_vendor_bills : "—",   unit: "invoices" },
              { label: "Total exposure",  val: kpis ? `${fmt(kpis.unpaid_customer_residual + kpis.unpaid_vendor_residual)}` : "—", unit: "TND" },
              { label: "Avg receivable",  val: kpis && kpis.unpaid_customer_invoices > 0 ? fmt(kpis.unpaid_customer_residual / kpis.unpaid_customer_invoices) : "—", unit: "TND / inv." },
            ].map((s, i) => (
              <div key={i} className="quick-stat-row">
                <span className="quick-stat-label">{s.label}</span>
                <span className="quick-stat-val">{s.val} <span className="quick-stat-unit">{s.unit}</span></span>
              </div>
            ))}
          </div>
          {can(role, "viewAdmin") && (
            <a href="/admin" className="quick-stat-admin-link">→ Manage users</a>
          )}
        </div>
      </div>

      {/* ── Recent unpaid invoices ── */}
      {can(role, "viewDashboard") && (
        <div className="recent-card">
          <div className="recent-card-header">
            <h2 className="chart-title">Unpaid Invoices</h2>
            <div className="recent-legend">
              <span className="inv-type-dot inv-type-customer" /> Customer
              <span className="inv-type-dot inv-type-vendor" style={{ marginLeft: 12 }} /> Vendor
            </div>
          </div>
              {loading ? (
            <div className="chart-loading"><div className="chart-spinner" /></div>
          ) : derivedRecentInvoices.length > 0 ? (
            <div className="recent-list">
              {derivedRecentInvoices.map((inv, i) => (
                <InvoiceRow key={inv.id || i} inv={inv} type={inv._type} />
              ))}
            </div>
          ) : (
            <div className="chart-empty" style={{ padding: "2rem" }}>
              No unpaid invoices — all clear! ✅
            </div>
          )}
        </div>
      )}
    </div>
  );
}