import { useState} from "react";

const INVOICE_TYPES = [
  { value: "out_invoice", label: "Customer Invoice", desc: "You issue — money owed to you" },
  { value: "in_invoice", label: "Vendor Bill", desc: "You receive — money you owe" },
];

const emptyLine = () => ({
  id: Date.now() + Math.random(),
  description: "",
  quantity: 1,
  unit_price: 0,
  discount: 0,
  tax_rate: 0,
  line_total: 0,
});

function Field({ label, children, hint, missing }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <label style={{
        display: "flex", alignItems: "center", gap: 6,
        fontSize: 12, fontWeight: 500, letterSpacing: "0.04em",
        color: "var(--color-text-secondary)", marginBottom: 4,
        textTransform: "uppercase",
      }}>
        {label}
        {missing && (
          <span style={{
            fontSize: 10, padding: "1px 6px", borderRadius: 4,
            background: "var(--color-background-warning)",
            color: "var(--color-text-warning)", fontWeight: 500,
          }}>missing</span>
        )}
      </label>
      {children}
      {hint && <p style={{ fontSize: 11, color: "var(--color-text-tertiary)", margin: "3px 0 0" }}>{hint}</p>}
    </div>
  );
}

function Input({ value, onChange, type = "text", placeholder, style = {} }) {
  return (
    <input
      type={type}
      value={value ?? ""}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      style={{
        width: "100%", boxSizing: "border-box",
        padding: "7px 10px", fontSize: 14,
        background: "var(--color-background-primary)",
        border: "0.5px solid var(--color-border-secondary)",
        borderRadius: "var(--border-radius-md)",
        color: "var(--color-text-primary)",
        outline: "none",
        ...style,
      }}
    />
  );
}

function SectionCard({ title, icon, children, accent }) {
  const accentColors = {
    blue: { bg: "var(--color-background-info)", text: "var(--color-text-info)" },
    teal: { bg: "#E1F5EE", text: "#0F6E56" },
    amber: { bg: "var(--color-background-warning)", text: "var(--color-text-warning)" },
    gray: { bg: "var(--color-background-secondary)", text: "var(--color-text-secondary)" },
  };
  const ac = accentColors[accent] || accentColors.gray;

  return (
    <div style={{
      background: "var(--color-background-primary)",
      border: "0.5px solid var(--color-border-tertiary)",
      borderRadius: "var(--border-radius-lg)",
      overflow: "hidden",
      marginBottom: 12,
    }}>
      <div style={{
        display: "flex", alignItems: "center", gap: 8,
        padding: "10px 16px",
        background: ac.bg,
        borderBottom: "0.5px solid var(--color-border-tertiary)",
      }}>
        <span style={{ fontSize: 14, color: ac.text }}>{icon}</span>
        <span style={{ fontSize: 13, fontWeight: 500, color: ac.text }}>{title}</span>
      </div>
      <div style={{ padding: "14px 16px" }}>{children}</div>
    </div>
  );
}

function PartyFields({ data, onChange, missingFields, prefix }) {
  const missing = (field) => missingFields.includes(`${prefix}.${field}`);
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 12px" }}>
      <Field label="Name" missing={missing("name")}>
        <Input value={data.name} onChange={v => onChange({ ...data, name: v })} placeholder="Company or person name" />
      </Field>
      <Field label="Tax ID / MF" missing={missing("tax_id")}>
        <Input value={data.tax_id} onChange={v => onChange({ ...data, tax_id: v })} placeholder="e.g. 1234567/A/M/000" />
      </Field>
      <Field label="Address" missing={missing("address")} style={{ gridColumn: "1 / -1" }}>
        <Input value={data.address} onChange={v => onChange({ ...data, address: v })} placeholder="Street, city, postal code" />
      </Field>
      {prefix === "vendor" && (
        <Field label="IBAN" missing={missing("iban")}>
          <Input value={data.iban} onChange={v => onChange({ ...data, iban: v })} placeholder="Bank account number" />
        </Field>
      )}
    </div>
  );
}

function LineItemRow({ line, idx, onChange, onRemove }) {
  const handleField = (field) => (val) => {
    const updated = { ...line, [field]: val };
    if (field === "quantity" || field === "unit_price" || field === "discount") {
      const q = parseFloat(field === "quantity" ? val : line.quantity) || 0;
      const p = parseFloat(field === "unit_price" ? val : line.unit_price) || 0;
      const d = parseFloat(field === "discount" ? val : line.discount) || 0;
      const discountFactor = Math.max(0, Math.min(100, d));
      updated.line_total = (q * p * (1 - discountFactor / 100)).toFixed(2);
    }
    onChange(updated);
  };

  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "2fr 70px 90px 70px 70px 90px 32px",
      gap: 6, marginBottom: 6, alignItems: "center",
    }}>
      <Input value={line.description} onChange={handleField("description")} placeholder={`Item ${idx + 1} description`} />
      <Input type="number" value={line.quantity} onChange={handleField("quantity")} style={{ textAlign: "right" }} />
      <Input type="number" value={line.unit_price} onChange={handleField("unit_price")} style={{ textAlign: "right" }} />
      <Input type="number" value={line.discount} onChange={handleField("discount")} style={{ textAlign: "right" }} />
      <Input type="number" value={line.tax_rate} onChange={handleField("tax_rate")} style={{ textAlign: "right" }} />
      <div style={{
        padding: "7px 10px", fontSize: 14, textAlign: "right",
        background: "var(--color-background-secondary)",
        border: "0.5px solid var(--color-border-tertiary)",
        borderRadius: "var(--border-radius-md)",
        color: "var(--color-text-primary)",
      }}>
        {(parseFloat(line.line_total) || 0).toFixed(2)}
      </div>
      <button
        onClick={onRemove}
        style={{
          width: 32, height: 32, borderRadius: "var(--border-radius-md)",
          border: "0.5px solid var(--color-border-tertiary)",
          background: "none", cursor: "pointer",
          color: "var(--color-text-danger)", fontSize: 14,
          display: "flex", alignItems: "center", justifyContent: "center",
        }}
      >✕</button>
    </div>
  );
}

function ConfidenceBadge({ score }) {
  const pct = Math.round((score ?? 0) * 100);
  const color = pct >= 80 ? "success" : pct >= 50 ? "warning" : "danger";
  return (
    <span style={{
      fontSize: 12, padding: "3px 9px",
      borderRadius: "var(--border-radius-md)",
      background: `var(--color-background-${color})`,
      color: `var(--color-text-${color})`,
      fontWeight: 500,
    }}>
      {pct}% confidence
    </span>
  );
}

export default function InvoiceValidationForm({ extractedData, onConfirm, onCancel }) {
  const defaults = {
    invoice_number: "", invoice_date: "", due_date: "", currency: "TND",
    vendor: { name: "", address: "", tax_id: "", iban: "" },
    buyer: { name: "", address: "", tax_id: "" },
    lines: [emptyLine()],
    totals: { subtotal: 0, tax_amount: 0, discount: 0, total_due: 0 },
    payment_terms: "", notes: "",
    confidence_score: 0, missing_fields: [],
  };

  const [invoiceType, setInvoiceType] = useState("out_invoice");
  const [data, setData] = useState(() => {
    if (!extractedData) return defaults;
    return {
      ...defaults,
      ...extractedData,
      vendor: { ...defaults.vendor, ...(extractedData.vendor || {}) },
      buyer: { ...defaults.buyer, ...(extractedData.buyer || {}) },
      totals: { ...defaults.totals, ...(extractedData.totals || {}) },
      lines: extractedData.lines?.length
        ? extractedData.lines.map((l, i) => ({ ...emptyLine(), ...l, id: i }))
        : [emptyLine()],
    };
  });

  const missing = data.missing_fields || [];

  const recalcTotals = (lines) => {
    const normalizedLines = lines.map((l) => {
      const q = parseFloat(l.quantity) || 0;
      const p = parseFloat(l.unit_price) || 0;
      const d = Math.max(0, Math.min(100, parseFloat(l.discount) || 0));
      const line_total = q * p * (1 - d / 100);
      return { ...l, discount: d, line_total };
    });

    const subtotal = normalizedLines.reduce((s, l) => s + (parseFloat(l.line_total) || 0), 0);
    const tax_amount = normalizedLines.reduce((s, l) => {
      const lt = parseFloat(l.line_total) || 0;
      const tr = parseFloat(l.tax_rate) || 0;
      return s + lt * (tr / 100);
    }, 0);
    const discount = parseFloat(data.totals.discount) || 0;
    return {
      subtotal: parseFloat(subtotal.toFixed(2)),
      tax_amount: parseFloat(tax_amount.toFixed(2)),
      discount,
      total_due: parseFloat((subtotal + tax_amount - discount).toFixed(2)),
    };
  };

  const setLines = (newLines) => {
    const withComputedTotals = newLines.map((l) => {
      const q = parseFloat(l.quantity) || 0;
      const p = parseFloat(l.unit_price) || 0;
      const d = Math.max(0, Math.min(100, parseFloat(l.discount) || 0));
      return {
        ...l,
        discount: d,
        line_total: parseFloat((q * p * (1 - d / 100)).toFixed(2)),
      };
    });
    setData(d => ({ ...d, lines: withComputedTotals, totals: recalcTotals(withComputedTotals) }));
  };

  const addLine = () => setLines([...data.lines, emptyLine()]);
  const removeLine = (idx) => setLines(data.lines.filter((_, i) => i !== idx));
  const updateLine = (idx, updated) => {
    const lines = data.lines.map((l, i) => (i === idx ? updated : l));
    setLines(lines);
  };

  const handleConfirm = () => {
    const payload = {
      ...data,
      invoice_type: invoiceType,
      totals: recalcTotals(data.lines),
    };
    if (onConfirm) onConfirm(payload);
  };

  const isMissing = (field) => missing.includes(field);

  return (
    <div style={{ padding: "4px 0", maxWidth: 720 }}>
      {/* Header row */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        marginBottom: 16,
      }}>
        <div>
          <p style={{ fontSize: 15, fontWeight: 500, margin: 0, color: "var(--color-text-primary)" }}>
            Invoice review
          </p>
          <p style={{ fontSize: 13, color: "var(--color-text-secondary)", margin: "2px 0 0" }}>
            Verify extracted fields before sending to Odoo
          </p>
        </div>
        <ConfidenceBadge score={data.confidence_score} />
      </div>

      {/* Invoice type selector */}
      <SectionCard title="Invoice type" icon="⇄" accent="blue">
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          {INVOICE_TYPES.map(t => (
            <div
              key={t.value}
              onClick={() => setInvoiceType(t.value)}
              style={{
                padding: "10px 14px", cursor: "pointer",
                border: invoiceType === t.value
                  ? "2px solid var(--color-border-info)"
                  : "0.5px solid var(--color-border-tertiary)",
                borderRadius: "var(--border-radius-md)",
                background: invoiceType === t.value
                  ? "var(--color-background-info)"
                  : "var(--color-background-primary)",
                transition: "all 0.15s",
              }}
            >
              <p style={{
                margin: 0, fontSize: 13, fontWeight: 500,
                color: invoiceType === t.value ? "var(--color-text-info)" : "var(--color-text-primary)",
              }}>{t.label}</p>
              <p style={{
                margin: "2px 0 0", fontSize: 11,
                color: invoiceType === t.value ? "var(--color-text-info)" : "var(--color-text-secondary)",
              }}>{t.desc}</p>
            </div>
          ))}
        </div>
      </SectionCard>

      {/* Invoice header */}
      <SectionCard title="Invoice details" icon="◻" accent="gray">
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0 12px" }}>
          <Field label="Invoice number" missing={isMissing("invoice_number")}>
            <Input value={data.invoice_number} onChange={v => setData(d => ({ ...d, invoice_number: v }))} placeholder="INV-2024-001" />
          </Field>
          <Field label="Invoice date" missing={isMissing("invoice_date")}>
            <Input type="date" value={data.invoice_date} onChange={v => setData(d => ({ ...d, invoice_date: v }))} />
          </Field>
          <Field label="Due date" missing={isMissing("due_date")}>
            <Input type="date" value={data.due_date} onChange={v => setData(d => ({ ...d, due_date: v }))} />
          </Field>
          <Field label="Currency">
            <select
              value={data.currency}
              onChange={e => setData(d => ({ ...d, currency: e.target.value }))}
              style={{
                width: "100%", padding: "7px 10px", fontSize: 14,
                background: "var(--color-background-primary)",
                border: "0.5px solid var(--color-border-secondary)",
                borderRadius: "var(--border-radius-md)",
                color: "var(--color-text-primary)",
              }}
            >
              {["TND", "EUR", "USD", "GBP"].map(c => <option key={c}>{c}</option>)}
            </select>
          </Field>
          <Field label="Payment terms">
            <Input value={data.payment_terms} onChange={v => setData(d => ({ ...d, payment_terms: v }))} placeholder="e.g. Net 30" />
          </Field>
        </div>
      </SectionCard>

      {/* Vendor */}
      <SectionCard title="Vendor (issuer)" icon="↑" accent="teal">
        <PartyFields
          data={data.vendor}
          onChange={vendor => setData(d => ({ ...d, vendor }))}
          missingFields={missing}
          prefix="vendor"
        />
      </SectionCard>

      {/* Buyer */}
      <SectionCard title="Buyer (recipient)" icon="↓" accent="teal">
        <PartyFields
          data={data.buyer}
          onChange={buyer => setData(d => ({ ...d, buyer }))}
          missingFields={missing}
          prefix="buyer"
        />
      </SectionCard>

      {/* Line items */}
      <SectionCard title="Line items" icon="≡" accent="gray">
        {/* Column headers */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "2fr 70px 90px 70px 70px 90px 32px",
          gap: 6, marginBottom: 6,
        }}>
          {["Description", "Qty", "Unit price", "Disc. %", "Tax %", "Total", ""].map((h, i) => (
            <span key={i} style={{ fontSize: 11, color: "var(--color-text-secondary)", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.04em" }}>{h}</span>
          ))}
        </div>

        {data.lines.map((line, idx) => (
          <LineItemRow
            key={line.id}
            idx={idx}
            line={line}
            onChange={updated => updateLine(idx, updated)}
            onRemove={() => removeLine(idx)}
          />
        ))}

        <button
          onClick={addLine}
          style={{
            marginTop: 8, padding: "6px 14px", fontSize: 13,
            border: "0.5px dashed var(--color-border-secondary)",
            borderRadius: "var(--border-radius-md)",
            background: "none", cursor: "pointer",
            color: "var(--color-text-secondary)",
          }}
        >
          + Add line
        </button>

        {/* Totals summary */}
        <div style={{
          marginTop: 14, paddingTop: 12,
          borderTop: "0.5px solid var(--color-border-tertiary)",
          display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4,
        }}>
          {[
            ["Subtotal", data.totals.subtotal],
            ["Tax", data.totals.tax_amount],
            ["Discount", data.totals.discount],
          ].map(([label, val]) => (
            <div key={label} style={{ display: "flex", gap: 32, fontSize: 13, color: "var(--color-text-secondary)" }}>
              <span>{label}</span>
              <span style={{ minWidth: 80, textAlign: "right" }}>
                {(parseFloat(val) || 0).toFixed(2)} {data.currency}
              </span>
            </div>
          ))}
          <div style={{
            display: "flex", gap: 32, fontSize: 15, fontWeight: 500,
            color: "var(--color-text-primary)", marginTop: 4,
            paddingTop: 8, borderTop: "0.5px solid var(--color-border-secondary)",
          }}>
            <span>Total due</span>
            <span style={{ minWidth: 80, textAlign: "right" }}>
              {(parseFloat(data.totals.total_due) || 0).toFixed(2)} {data.currency}
            </span>
          </div>

          {/* Editable discount override */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
            <span style={{ fontSize: 12, color: "var(--color-text-secondary)" }}>Discount override</span>
            <input
              type="number"
              value={data.totals.discount}
              onChange={e => setData(d => ({
                ...d,
                totals: { ...d.totals, discount: parseFloat(e.target.value) || 0 }
              }))}
              style={{
                width: 80, padding: "4px 8px", fontSize: 13, textAlign: "right",
                border: "0.5px solid var(--color-border-secondary)",
                borderRadius: "var(--border-radius-md)",
                background: "var(--color-background-primary)",
                color: "var(--color-text-primary)",
              }}
            />
          </div>
        </div>
      </SectionCard>

      {/* Notes */}
      <SectionCard title="Notes" icon="✎" accent="amber">
        <textarea
          value={data.notes ?? ""}
          onChange={e => setData(d => ({ ...d, notes: e.target.value }))}
          placeholder="Payment instructions, special conditions…"
          rows={3}
          style={{
            width: "100%", boxSizing: "border-box", fontSize: 14,
            padding: "8px 10px", resize: "vertical",
            background: "var(--color-background-primary)",
            border: "0.5px solid var(--color-border-secondary)",
            borderRadius: "var(--border-radius-md)",
            color: "var(--color-text-primary)",
          }}
        />
      </SectionCard>

      {/* Missing fields warning */}
      {missing.length > 0 && (
        <div style={{
          padding: "10px 14px", marginBottom: 14,
          background: "var(--color-background-warning)",
          border: "0.5px solid var(--color-border-warning)",
          borderRadius: "var(--border-radius-md)",
          fontSize: 13, color: "var(--color-text-warning)",
        }}>
          <strong>Missing fields detected:</strong> {missing.join(", ")} — you can still confirm, but Odoo may reject incomplete records.
        </div>
      )}

      {/* Action buttons */}
      <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 4 }}>
        <button
          onClick={onCancel}
          style={{
            padding: "8px 18px", fontSize: 14, cursor: "pointer",
            border: "0.5px solid var(--color-border-secondary)",
            borderRadius: "var(--border-radius-md)",
            background: "none", color: "var(--color-text-secondary)",
          }}
        >
          Cancel
        </button>
        <button
          onClick={handleConfirm}
          style={{
            padding: "8px 22px", fontSize: 14, fontWeight: 500, cursor: "pointer",
            border: "0.5px solid var(--color-border-info)",
            borderRadius: "var(--border-radius-md)",
            background: "var(--color-background-info)",
            color: "var(--color-text-info)",
          }}
        >
          Confirm → Send to Odoo
        </button>
      </div>
    </div>
  );
}