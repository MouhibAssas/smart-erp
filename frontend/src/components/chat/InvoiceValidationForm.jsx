import { useState } from "react";
import "./InvoiceValidationForm.css";

const INVOICE_TYPES = [
  { value: "out_invoice", label: "Customer Invoice", desc: "You issue - money owed to you" },
  { value: "in_invoice", label: "Vendor Bill", desc: "You receive - money you owe" },
];

const emptyLine = () => ({
  id: Date.now() + Math.random(),
  description: "",
  quantity: 0,
  unit_price: 0,
  discount: 0,
  tax_rate: 0,
  line_total: 0,
});

const normalizeLine = (line) => ({
  id: line.id || Date.now() + Math.random(),
  description: line.description || "",
  quantity: parseFloat(line.quantity) || 0,
  unit_price: parseFloat(line.unit_price) || 0,
  discount: Math.max(0, Math.min(100, parseFloat(line.discount) || 0)),
  tax_rate: parseFloat(line.tax_rate) || 0,
  line_total: parseFloat(line.line_total) || 0,
});

const normalizeNullableText = (value) => {
  if (value == null) return "";
  const rawText = String(value);
  const text = rawText.trim();
  if (!text) return "";

  const lowered = text.toLowerCase();
  const placeholders = new Set([
    "null",
    "none",
    "undefined",
    "n/a",
    "na",
    "string or null",
    "string|null",
    "unknown",
  ]);

  return placeholders.has(lowered) ? "" : rawText;
};

const pickFirstMeaningful = (...values) => {
  for (const value of values) {
    const normalized = normalizeNullableText(value);
    if (normalized) return normalized;
  }
  return "";
};

function Field({ label, children, hint, missing, className = "" }) {
  return (
    <div className={`ivf-field ${className}`.trim()}>
      <label className="ivf-field-label">
        {label}
        {missing && <span className="ivf-missing-badge">missing</span>}
      </label>
      {children}
      {hint && <p className="ivf-field-hint">{hint}</p>}
    </div>
  );
}

function Input({ value, onChange, type = "text", placeholder, className = "" }) {
  return (
    <input
      type={type}
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className={`ivf-input ${className}`.trim()}
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
    <div className="ivf-section-card">
      <div
        className="ivf-section-header"
        style={{ "--ivf-accent-bg": ac.bg, "--ivf-accent-text": ac.text }}
      >
        <span className="ivf-section-icon">{icon}</span>
        <span className="ivf-section-title">{title}</span>
      </div>
      <div className="ivf-section-body">{children}</div>
    </div>
  );
}

function PartyFields({ data, onChange, missingFields, prefix }) {
  const missing = (field) => missingFields.includes(`${prefix}.${field}`);
  return (
    <div className="ivf-two-col-grid">
      <Field label="Name" missing={missing("name")}>
        <Input value={data.name} onChange={(v) => onChange({ ...data, name: v })} placeholder="Company or person name" />
      </Field>
      <Field label="Tax ID / MF" missing={missing("tax_id")}>
        <Input value={data.tax_id} onChange={(v) => onChange({ ...data, tax_id: v })} placeholder="e.g. 1234567/A/M/000" />
      </Field>
      <Field label="Address" missing={missing("address")} className="ivf-span-2">
        <Input value={data.address} onChange={(v) => onChange({ ...data, address: v })} placeholder="Street, city, postal code" />
      </Field>
      {prefix === "vendor" && (
        <Field label="IBAN" missing={missing("iban")}>
          <Input value={data.iban} onChange={(v) => onChange({ ...data, iban: v })} placeholder="Bank account number" />
        </Field>
      )}
    </div>
  );
}

function LineItemRow({ line, idx, onChange, onRemove }) {
  const handleField = (field) => (val) => {
    let parsedVal = val;
    if (["quantity", "unit_price", "discount", "tax_rate"].includes(field)) {
      parsedVal = parseFloat(val) || 0;
    }

    const updated = { ...line, [field]: parsedVal };

    if (["quantity", "unit_price", "discount"].includes(field)) {
      const q = field === "quantity" ? parsedVal : parseFloat(line.quantity) || 0;
      const p = field === "unit_price" ? parsedVal : parseFloat(line.unit_price) || 0;
      const d = field === "discount" ? parsedVal : parseFloat(line.discount) || 0;
      const discountFactor = Math.max(0, Math.min(100, d));
      updated.line_total = parseFloat((q * p * (1 - discountFactor / 100)).toFixed(2));
    }

    onChange(updated);
  };

  const qty = parseFloat(line.quantity) || 0;
  const price = parseFloat(line.unit_price) || 0;
  const discount = parseFloat(line.discount) || 0;

  const suspicions = [];
  if (qty > 0 && price > 0 && Math.abs(qty - price) === 0) suspicions.push("qty=price");
  if (discount > 100) suspicions.push("discount > 100%");
  if (price > 1000 && qty < 10) suspicions.push("high unit_price");

  return (
    <div>
      {suspicions.length > 0 && (
        <div className="ivf-suspicion-banner">! {suspicions.join(" | ")} - verify values</div>
      )}

      <div className="ivf-line-grid">
        <Input value={line.description} onChange={handleField("description")} placeholder={`Item ${idx + 1} description`} />
        <Input
          type="number"
          value={parseFloat(line.quantity) || ""}
          onChange={handleField("quantity")}
          placeholder="Qty"
          className="ivf-input-right"
        />
        <Input
          type="number"
          value={parseFloat(line.unit_price) || ""}
          onChange={handleField("unit_price")}
          placeholder="Price"
          className="ivf-input-right"
        />
        <Input
          type="number"
          value={parseFloat(line.discount) || ""}
          onChange={handleField("discount")}
          placeholder="Disc %"
          className="ivf-input-right"
        />
        <Input
          type="number"
          value={parseFloat(line.tax_rate) || ""}
          onChange={handleField("tax_rate")}
          placeholder="Tax %"
          className="ivf-input-right"
        />
        <div className="ivf-line-total">{(parseFloat(line.line_total) || 0).toFixed(2)}</div>
        <button onClick={onRemove} className="ivf-remove-btn" type="button">
          x
        </button>
      </div>
    </div>
  );
}

function ConfidenceBadge({ score }) {
  const pct = Math.round((score ?? 0) * 100);
  const color = pct >= 80 ? "success" : pct >= 50 ? "warning" : "danger";
  return <span className={`ivf-confidence ivf-confidence-${color}`}>{pct}% confidence</span>;
}

export default function InvoiceValidationForm({ extractedData, onConfirm, onCancel }) {
  const defaults = {
    invoice_number: "",
    invoice_date: "",
    due_date: "",
    currency: "TND",
    vendor: { name: "", address: "", tax_id: "", iban: "" },
    buyer: { name: "", address: "", tax_id: "" },
    lines: [emptyLine()],
    totals: { subtotal: 0, tax_amount: 0, discount: 0, total_due: 0 },
    payment_terms: "",
    notes: "",
    confidence_score: 0,
    missing_fields: [],
  };

  const [invoiceType, setInvoiceType] = useState(extractedData?.invoice_type || extractedData?.move_type || "out_invoice");

  const syncPartnerFields = (current, source, sourceKey) => {
    const sourceSafe = source || {};
    const counterpart = sourceKey === "buyer" ? current.vendor : current.buyer;

    const shared = {
      name: pickFirstMeaningful(sourceSafe.name, counterpart?.name, current.buyer?.name, current.vendor?.name),
      address: pickFirstMeaningful(sourceSafe.address, counterpart?.address, current.buyer?.address, current.vendor?.address),
      tax_id: pickFirstMeaningful(sourceSafe.tax_id, counterpart?.tax_id, current.buyer?.tax_id, current.vendor?.tax_id),
    };

    return {
      ...current,
      [sourceKey]: {
        ...current[sourceKey],
        ...sourceSafe,
        name: shared.name,
        address: shared.address,
        tax_id: shared.tax_id,
      },
      buyer: {
        ...current.buyer,
        ...shared,
      },
      vendor: {
        ...current.vendor,
        ...shared,
      },
    };
  };

  const [data, setData] = useState(() => {
    if (!extractedData) return defaults;

    const extractedBuyer = extractedData.buyer || {};
    const extractedVendor = extractedData.vendor || {};

    const sharedPartner = {
      name: pickFirstMeaningful(extractedBuyer.name, extractedVendor.name),
      address: pickFirstMeaningful(extractedBuyer.address, extractedVendor.address),
      tax_id: pickFirstMeaningful(extractedBuyer.tax_id, extractedVendor.tax_id),
    };

    const normalizedLines = extractedData.lines && Array.isArray(extractedData.lines)
      ? extractedData.lines.map(normalizeLine)
      : [emptyLine()];

    return {
      ...defaults,
      ...extractedData,
      vendor: {
        ...defaults.vendor,
        ...sharedPartner,
        ...extractedVendor,
        name: pickFirstMeaningful(extractedVendor.name, sharedPartner.name),
        address: pickFirstMeaningful(extractedVendor.address, sharedPartner.address),
        tax_id: pickFirstMeaningful(extractedVendor.tax_id, sharedPartner.tax_id),
        iban: normalizeNullableText(extractedVendor.iban),
      },
      buyer: {
        ...defaults.buyer,
        ...sharedPartner,
        ...extractedBuyer,
        name: pickFirstMeaningful(extractedBuyer.name, sharedPartner.name),
        address: pickFirstMeaningful(extractedBuyer.address, sharedPartner.address),
        tax_id: pickFirstMeaningful(extractedBuyer.tax_id, sharedPartner.tax_id),
      },
      totals: { ...defaults.totals, ...(extractedData.totals || {}) },
      lines: normalizedLines,
    };
  });

  const missing = data.missing_fields || [];

  const recalcTotals = (lines) => {
    const normalizedLines = lines.map((l) => {
      const q = parseFloat(l.quantity) || 0;
      const p = parseFloat(l.unit_price) || 0;
      const d = Math.max(0, Math.min(100, parseFloat(l.discount) || 0));
      const lineTotal = q * p * (1 - d / 100);
      return { ...l, discount: d, line_total: lineTotal };
    });

    const subtotal = normalizedLines.reduce((s, l) => s + (parseFloat(l.line_total) || 0), 0);
    const taxAmount = normalizedLines.reduce((s, l) => {
      const lt = parseFloat(l.line_total) || 0;
      const tr = parseFloat(l.tax_rate) || 0;
      return s + lt * (tr / 100);
    }, 0);

    const discount = parseFloat(data.totals.discount) || 0;

    return {
      subtotal: parseFloat(subtotal.toFixed(2)),
      tax_amount: parseFloat(taxAmount.toFixed(2)),
      discount,
      total_due: parseFloat((subtotal + taxAmount - discount).toFixed(2)),
    };
  };

  const setLines = (newLines) => {
    const withComputedTotals = newLines.map((l) => {
      const q = parseFloat(l.quantity) || 0;
      const p = parseFloat(l.unit_price) || 0;
      const d = Math.max(0, Math.min(100, parseFloat(l.discount) || 0));
      const tr = parseFloat(l.tax_rate) || 0;
      const lineTotal = parseFloat((q * p * (1 - d / 100)).toFixed(2));

      return {
        ...l,
        id: l.id || Date.now() + Math.random(),
        description: l.description || "",
        quantity: q,
        unit_price: p,
        discount: d,
        tax_rate: tr,
        line_total: lineTotal,
      };
    });

    setData((d) => ({ ...d, lines: withComputedTotals, totals: recalcTotals(withComputedTotals) }));
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
    <div className="ivf-root">
      <div className="ivf-header-row">
        <div>
          <p className="ivf-title">Invoice review</p>
          <p className="ivf-subtitle">Verify extracted fields before sending to Odoo</p>
        </div>
        <ConfidenceBadge score={data.confidence_score} />
      </div>

      <SectionCard title="Invoice type" icon="<->" accent="blue">
        <div className="ivf-type-grid">
          {INVOICE_TYPES.map((t) => {
            const isSelected = invoiceType === t.value;
            const kindClass = t.value === "out_invoice" ? "customer" : "vendor";

            return (
              <button
                key={t.value}
                onClick={() => setInvoiceType(t.value)}
                type="button"
                className={`ivf-type-card ${kindClass} ${isSelected ? "is-selected" : ""}`.trim()}
              >
                <div className="ivf-type-head">
                  <span className="ivf-type-icon">{t.value === "out_invoice" ? "OUT" : "IN"}</span>
                  <p className="ivf-type-label">{t.label}</p>
                  {isSelected && <span className="ivf-type-check">OK</span>}
                </div>
                <p className="ivf-type-desc">{t.desc}</p>
              </button>
            );
          })}
        </div>
      </SectionCard>

      <SectionCard title="Invoice details" icon="[]" accent="gray">
        <div className="ivf-three-col-grid">
          <Field label="Invoice number" missing={isMissing("invoice_number")}>
            <Input value={data.invoice_number} onChange={(v) => setData((d) => ({ ...d, invoice_number: v }))} placeholder="INV-2024-001" />
          </Field>
          <Field label="Invoice date" missing={isMissing("invoice_date")}>
            <Input type="date" value={data.invoice_date} onChange={(v) => setData((d) => ({ ...d, invoice_date: v }))} />
          </Field>
          <Field label="Due date" missing={isMissing("due_date")}>
            <Input type="date" value={data.due_date} onChange={(v) => setData((d) => ({ ...d, due_date: v }))} />
          </Field>

          <Field label="Currency">
            <select
              value={data.currency}
              onChange={(e) => setData((d) => ({ ...d, currency: e.target.value }))}
              className="ivf-select"
            >
              {["TND", "EUR", "USD", "GBP"].map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </Field>

          <Field label="Payment terms">
            <Input value={data.payment_terms} onChange={(v) => setData((d) => ({ ...d, payment_terms: v }))} placeholder="e.g. Net 30" />
          </Field>
        </div>
      </SectionCard>

      {invoiceType === "out_invoice" && (
        <SectionCard title="Customer (buyer)" icon="down" accent="teal">
          <PartyFields
            data={data.buyer}
            onChange={(buyer) => setData((d) => syncPartnerFields(d, buyer, "buyer"))}
            missingFields={missing}
            prefix="buyer"
          />
        </SectionCard>
      )}

      {invoiceType === "in_invoice" && (
        <SectionCard title="Vendor (supplier)" icon="up" accent="teal">
          <PartyFields
            data={data.vendor}
            onChange={(vendor) => setData((d) => syncPartnerFields(d, vendor, "vendor"))}
            missingFields={missing}
            prefix="vendor"
          />
        </SectionCard>
      )}

      <SectionCard title="Line items" icon="==" accent="gray">
        <div className="ivf-line-grid ivf-line-headings">
          {["Description", "Qty", "Unit price", "Disc. %", "Tax %", "Total", ""].map((h, i) => (
            <span key={i} className="ivf-col-heading">
              {h}
            </span>
          ))}
        </div>

        {data.lines.map((line, idx) => (
          <LineItemRow
            key={line.id}
            idx={idx}
            line={line}
            onChange={(updated) => updateLine(idx, updated)}
            onRemove={() => removeLine(idx)}
          />
        ))}

        <button onClick={addLine} className="ivf-add-line-btn" type="button">
          + Add line
        </button>

        <div className="ivf-totals-wrap">
          {[
            ["Subtotal", data.totals.subtotal],
            ["Tax", data.totals.tax_amount],
            ["Discount", data.totals.discount],
          ].map(([label, val]) => (
            <div key={label} className="ivf-total-row">
              <span>{label}</span>
              <span className="ivf-money-cell">
                {(parseFloat(val) || 0).toFixed(2)} {data.currency}
              </span>
            </div>
          ))}

          <div className="ivf-total-due-row">
            <span>Total due</span>
            <span className="ivf-money-cell">
              {(parseFloat(data.totals.total_due) || 0).toFixed(2)} {data.currency}
            </span>
          </div>

          <div className="ivf-discount-row">
            <span className="ivf-discount-label">Discount override</span>
            <input
              type="number"
              value={data.totals.discount}
              onChange={(e) =>
                setData((d) => ({
                  ...d,
                  totals: { ...d.totals, discount: parseFloat(e.target.value) || 0 },
                }))
              }
              className="ivf-discount-input"
            />
          </div>
        </div>
      </SectionCard>

      <SectionCard title="Notes" icon="note" accent="amber">
        <textarea
          value={data.notes ?? ""}
          onChange={(e) => setData((d) => ({ ...d, notes: e.target.value }))}
          placeholder="Payment instructions, special conditions..."
          rows={3}
          className="ivf-textarea"
        />
      </SectionCard>

      {data.lines && data.lines.length > 0 && (
        <details className="ivf-debug-panel">
          <summary className="ivf-debug-summary">Debug: Show extracted line values</summary>
          <div className="ivf-debug-body">
            {data.lines.map((line, idx) => (
              <div key={idx} className="ivf-debug-row">
                <div>
                  <strong>Line {idx + 1}:</strong>
                </div>
                <div>- desc: "{line.description}"</div>
                <div>- qty: {JSON.stringify(line.quantity)}</div>
                <div>- unit_price: {JSON.stringify(line.unit_price)}</div>
                <div>- discount: {JSON.stringify(line.discount)}%</div>
                <div>- tax_rate: {JSON.stringify(line.tax_rate)}%</div>
                <div className="ivf-debug-success">
                  - line_total: {JSON.stringify(line.line_total)} (calc: {((line.quantity || 0) * (line.unit_price || 0) * (1 - (line.discount || 0) / 100)).toFixed(2)})
                </div>
              </div>
            ))}
          </div>
        </details>
      )}

      {missing.length > 0 && (
        <div className="ivf-warning-banner">
          <strong>Missing fields detected:</strong> {missing.join(", ")} - you can still confirm, but Odoo may reject incomplete records.
        </div>
      )}

      <div className="ivf-actions">
        <button onClick={onCancel} className="ivf-btn ivf-btn-secondary" type="button">
          Cancel
        </button>
        <button onClick={handleConfirm} className="ivf-btn ivf-btn-primary" type="button">
          Confirm and Send to Odoo
        </button>
      </div>
    </div>
  );
}