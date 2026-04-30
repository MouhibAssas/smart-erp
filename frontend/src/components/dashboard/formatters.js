export const fmt = (n, digits = 2) =>
  typeof n === "number"
    ? n.toLocaleString("fr-TN", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      })
    : "—";

export const fmtDate = (s) => {
  if (!s) return "—";
  try {
    return new Date(s).toLocaleDateString("fr-TN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return s;
  }
};

export const partnerLabel = (p) => {
  if (Array.isArray(p) && p.length > 1) return p[1];
  if (typeof p === "string") return p;
  return "—";
};
