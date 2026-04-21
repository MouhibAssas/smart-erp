import "./Dashboard.css";

export default function Dashboard() {
  const stats = [
    { label: "Total Invoices", value: "0", colorClass: "blue" },
    { label: "Pending", value: "0", colorClass: "orange" },
    { label: "Paid", value: "0", colorClass: "green" },
    { label: "Overdue", value: "0", colorClass: "red" },
  ];

  return (
    <div className="dashboard-container">
  
      {/* Main Dashboard Content */}
      <div className="dashboard-main">
        <h1 className="dashboard-title">Dashboard</h1>

        {/* Stats Grid */}
        <div className="dashboard-stats-grid">
          {stats.map((stat) => (
            <div key={stat.label} className="dashboard-stat-card">
              <div className="dashboard-stat-label">{stat.label}</div>
              <div className={`dashboard-stat-value ${stat.colorClass}`}>
                {stat.value}
              </div>
            </div>
          ))}
        </div>

        {/* Recent Activity */}
        <div className="dashboard-activity-card">
          <h2 className="dashboard-activity-title">Recent Activity</h2>
          <div className="dashboard-activity-empty">
            No recent activity. Connect to Odoo to see your ERP data.
          </div>
        </div>
      </div>
    </div>
  );
}