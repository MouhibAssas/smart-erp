export default function BarChart({ data, height = 140 }) {
  if (!data || data.length === 0) return <div className="chart-empty">No data</div>;

  const maxVal = Math.max(...data.map((d) => d.revenue), 1);
  const barW = Math.floor(100 / data.length);

  return (
    <div className="bar-chart-wrap">
      <svg viewBox={`0 0 100 ${height}`} preserveAspectRatio="none" className="bar-chart-svg">
        {data.map((d, i) => {
          const barH = (d.revenue / maxVal) * (height - 24);
          const x = i * barW + barW * 0.15;
          const w = barW * 0.7;
          const y = height - 20 - barH;
          const isLast = i === data.length - 1;
          return (
            <g key={i}>
              <rect
                x={x}
                y={y}
                width={w}
                height={barH}
                rx="1.5"
                fill={isLast ? "var(--dash-accent)" : "var(--dash-bar-muted)"}
                opacity={isLast ? 1 : 0.65}
              />
            </g>
          );
        })}
      </svg>
      <div className="bar-chart-labels">
        {data.map((d, i) => (
          <span key={i} className={`bar-label ${i === data.length - 1 ? "bar-label-active" : ""}`}>
            {d.month.split(" ")[0]}
          </span>
        ))}
      </div>
    </div>
  );
}
