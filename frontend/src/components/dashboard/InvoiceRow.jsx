import { fmt, fmtDate, partnerLabel } from "./formatters";

export default function InvoiceRow({ inv, type }) {
  const isOverdue = inv.invoice_date_due && new Date(inv.invoice_date_due) < new Date();

  return (
    <div className="inv-row">
      <div className="inv-row-left">
        <span className={`inv-type-dot inv-type-${type}`} />
        <div>
          <div className="inv-name">{inv.name || `#${inv.id}`}</div>
          <div className="inv-partner">{partnerLabel(inv.partner_id)}</div>
        </div>
      </div>
      <div className="inv-row-right">
        <div className="inv-amount">{fmt(inv.amount_residual)} TND</div>
        <div className={`inv-due ${isOverdue ? "inv-overdue" : ""}`}>
          {isOverdue ? "⚠ " : ""}
          {fmtDate(inv.invoice_date_due)}
        </div>
      </div>
    </div>
  );
}
