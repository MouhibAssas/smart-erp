export default function DonutChart({ segments, size = 90 }) {
  const total = segments.reduce((s, seg) => s + seg.value, 0) || 1;
  const r = 30;
  const cx = 50;
  const cy = 50;
  const circumference = 2 * Math.PI * r;

  const { paths } = segments.reduce(
    (acc, seg, i) => {
      const pct = seg.value / total;
      const dash = pct * circumference;
      const gap = circumference - dash;
      const path = (
        <circle
          key={i}
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke={seg.color}
          strokeWidth="18"
          strokeDasharray={`${dash} ${gap}`}
          strokeDashoffset={-acc.offset}
          style={{ transform: "rotate(-90deg)", transformOrigin: "50% 50%" }}
        />
      );

      return {
        offset: acc.offset + dash,
        paths: [...acc.paths, path],
      };
    },
    { offset: 0, paths: [] }
  );

  return (
    <div className="donut-wrap">
      <svg viewBox="0 0 100 100" width={size} height={size}>
        {paths}
      </svg>
      <div className="donut-legend">
        {segments.map((seg, i) => (
          <div key={i} className="donut-legend-item">
            <span className="donut-dot" style={{ background: seg.color }} />
            <span className="donut-legend-label">{seg.label}</span>
            <span className="donut-legend-val">{seg.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
