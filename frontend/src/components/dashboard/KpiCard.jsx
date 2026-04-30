export default function KpiCard({ label, value, sub, accent, icon, loading }) {
  return (
    <div className={`kpi-card kpi-${accent}`}>
      <div className="kpi-top">
        <span className="kpi-icon">{icon}</span>
        <span className="kpi-label">{label}</span>
      </div>
      {loading ? <div className="kpi-skeleton" /> : <div className="kpi-value">{value}</div>}
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}
