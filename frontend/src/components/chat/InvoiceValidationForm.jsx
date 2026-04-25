import { useState } from "react";
import "./InvoiceValidationForm.css";
import { searchPartners } from "../../services/chatApi";

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

const formatPartnerAddress = (partner = {}) => {
  const street = normalizeNullableText(partner.street);
  const city = normalizeNullableText(partner.city);
  return [street, city].filter(Boolean).join(", ");
};

const createLookupEntry = (query = "") => ({
  query: normalizeNullableText(query),
  loading: false,
  error: "",
  hasSearched: false,
  selectedId: null,
  candidates: [],
});

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

function Input({ value, onChange, type = "text", placeholder, className = "", readOnly = false }) {
  return (
    <input
      type={type}
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className={`ivf-input ${className}`.trim()}
      readOnly={readOnly}
      aria-readonly={readOnly}
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

function PartyFields({ data, onChange, missingFields, prefix, readOnly = false }) {
  const missing = (field) => missingFields.includes(`${prefix}.${field}`);
  return (
    <div className="ivf-two-col-grid">
      <Field label="Name" missing={missing("name")}>
        <Input
          value={data.name}
          onChange={(v) => onChange({ ...data, name: v })}
          placeholder="Company or person name"
          readOnly={readOnly}
          className={readOnly ? "ivf-readonly-input" : ""}
        />
      </Field>
      <Field label="Tax ID / MF" missing={missing("tax_id")}>
        <Input
          value={data.tax_id}
          onChange={(v) => onChange({ ...data, tax_id: v })}
          placeholder="e.g. 1234567/A/M/000"
          readOnly={readOnly}
          className={readOnly ? "ivf-readonly-input" : ""}
        />
      </Field>
      <Field label="Address" missing={missing("address")} className="ivf-span-2">
        <Input
          value={data.address}
          onChange={(v) => onChange({ ...data, address: v })}
          placeholder="Street, city, postal code"
          readOnly={readOnly}
          className={readOnly ? "ivf-readonly-input" : ""}
        />
      </Field>
      {prefix === "vendor" && (
        <Field label="IBAN" missing={missing("iban")}>
          <Input
            value={data.iban}
            onChange={(v) => onChange({ ...data, iban: v })}
            placeholder="Bank account number"
            readOnly={readOnly}
            className={readOnly ? "ivf-readonly-input" : ""}
          />
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

  const [partnerSearch, setPartnerSearch] = useState(() => {
    const buyerName = normalizeNullableText(extractedData?.buyer?.name);
    const vendorName = normalizeNullableText(extractedData?.vendor?.name);

    if (invoiceType === "out_invoice") {
      return pickFirstMeaningful(buyerName, vendorName);
    }

    return pickFirstMeaningful(vendorName, buyerName);
  });

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
        ...extractedVendor,
        name: pickFirstMeaningful(extractedVendor.name, sharedPartner.name),
        address: pickFirstMeaningful(extractedVendor.address, sharedPartner.address),
        tax_id: pickFirstMeaningful(extractedVendor.tax_id, sharedPartner.tax_id),
        iban: normalizeNullableText(extractedVendor.iban),
      },
      buyer: {
        ...defaults.buyer,
        ...extractedBuyer,
        name: pickFirstMeaningful(extractedBuyer.name, sharedPartner.name),
        address: pickFirstMeaningful(extractedBuyer.address, sharedPartner.address),
        tax_id: pickFirstMeaningful(extractedBuyer.tax_id, sharedPartner.tax_id),
      },
      totals: { ...defaults.totals, ...(extractedData.totals || {}) },
      lines: normalizedLines,
    };
  });

  const [partnerLookup, setPartnerLookup] = useState(() => ({
    buyer: createLookupEntry(extractedData?.buyer?.name),
    vendor: createLookupEntry(extractedData?.vendor?.name),
  }));

  const missing = data.missing_fields || [];

  const activePartnerKey = invoiceType === "out_invoice" ? "buyer" : "vendor";
  const hasSelectedPartner = Boolean(partnerLookup[activePartnerKey]?.selectedId);

  const applyPartnerCandidate = (role, partner) => {
    const normalizedPartner = partner || {};
    const mappedAddress = formatPartnerAddress(normalizedPartner);

    setData((current) => {
      const next = {
        ...current,
        [role]: {
          ...current[role],
          name: pickFirstMeaningful(normalizedPartner.name, current[role]?.name),
          tax_id: pickFirstMeaningful(normalizedPartner.vat, current[role]?.tax_id),
          address: pickFirstMeaningful(mappedAddress, current[role]?.address),
          iban: role === "vendor"
            ? pickFirstMeaningful(normalizeNullableText(normalizedPartner.iban), current.vendor?.iban)
            : current.buyer?.iban,
        },
      };
      return next;
    });
  };

  const runPartnerSearch = async (role, forcedName = null) => {
    const query = normalizeNullableText(forcedName ?? partnerSearch);
    if (!query) {
      setPartnerLookup((prev) => ({
        ...prev,
        [role]: { ...prev[role], candidates: [], error: "Enter a name to search.", hasSearched: true, loading: false },
      }));
      return;
    }

    setPartnerLookup((prev) => ({
      ...prev,
      [role]: {
        ...prev[role],
        query,
        loading: true,
        error: "",
      },
    }));

    try {
      const response = await searchPartners({
        name: query,
        role: role === "buyer" ? "customer" : "vendor",
        limit: 8,
      });

      const candidates = Array.isArray(response?.partners) ? response.partners : [];
      setPartnerLookup((prev) => {
        const hasSelected = prev[role].selectedId && candidates.some((p) => p.id === prev[role].selectedId);
        return {
          ...prev,
          [role]: {
            ...prev[role],
            loading: false,
            hasSearched: true,
            candidates,
            error: response?.ok ? "" : (response?.error || "Search failed."),
            selectedId: hasSelected ? prev[role].selectedId : null,
          },
        };
      });
    } catch {
      setPartnerLookup((prev) => ({
        ...prev,
        [role]: {
          ...prev[role],
          loading: false,
          hasSearched: true,
          candidates: [],
          error: "Unable to fetch partner candidates.",
          selectedId: null,
        },
      }));
    }
  };

  const selectPartnerCandidate = (role, partnerId) => {
    const lookup = partnerLookup[role];
    const selected = lookup.candidates.find((p) => String(p.id) === String(partnerId));

    setPartnerLookup((prev) => ({
      ...prev,
      [role]: {
        ...prev[role],
        selectedId: selected ? selected.id : null,
      },
    }));

    if (selected) {
      setPartnerSearch(normalizeNullableText(selected.name) || partnerSearch);
      applyPartnerCandidate(role, selected);
      return;
    }

    setData((current) => ({
      ...current,
      [role]: role === "vendor"
        ? { name: "", address: "", tax_id: "", iban: "" }
        : { name: "", address: "", tax_id: "" },
    }));

  };

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
    const selectedPartnerId = partnerLookup[activePartnerKey]?.selectedId || null;
    const payload = {
      ...data,
      invoice_type: invoiceType,
      partner_id: selectedPartnerId,
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
        <p className="ivf-type-context">
          Select the invoice direction first. The partner section below will adapt to the active role.
        </p>
        <div className="ivf-type-grid">
          {INVOICE_TYPES.map((t) => {
            const isSelected = invoiceType === t.value;
            const kindClass = t.value === "out_invoice" ? "customer" : "vendor";

            return (
              <button
                key={t.value}
                onClick={() => {
                  setInvoiceType(t.value);
                }}
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

      <SectionCard title="Partner matching" icon="id" accent="teal">
        <p className="ivf-partner-context">
          Showing only the active role for this invoice: {activePartnerKey === "buyer" ? "Customer (buyer)" : "Vendor (supplier)"}.
        </p>

        {(() => {
          const cfg = activePartnerKey === "buyer"
            ? { role: "buyer", title: "Customer (buyer)", note: "Used for customer invoices" }
            : { role: "vendor", title: "Vendor (supplier)", note: "Used for vendor bills" };
          const lookup = partnerLookup[cfg.role];
          const selected = lookup.candidates.find((p) => p.id === lookup.selectedId);
          const roleData = data[cfg.role];

          return (
            <div className="ivf-partner-card is-active ivf-partner-card-single">
              <div className="ivf-partner-card-head">
                <div>
                  <p className="ivf-partner-title">{cfg.title}</p>
                  <p className="ivf-partner-note">{cfg.note}</p>
                </div>
                <span className="ivf-partner-active-tag">active</span>
              </div>

              <div className="ivf-partner-search-row">
                <Input
                  value={partnerSearch}
                  onChange={(v) => {
                    setPartnerSearch(v);
                    setPartnerLookup((prev) => ({
                      ...prev,
                      [cfg.role]: { ...prev[cfg.role], query: v, error: "" },
                    }));
                  }}
                  placeholder="Search by extracted or manual name"
                />
                <button
                  type="button"
                  className="ivf-search-btn"
                  onClick={() => runPartnerSearch(cfg.role, partnerSearch)}
                  disabled={lookup.loading}
                >
                  {lookup.loading ? "Searching..." : "Search"}
                </button>
              </div>

              <div className="ivf-field">
                <label className="ivf-field-label">Matching partners</label>
                <select
                  className="ivf-select"
                  value={lookup.selectedId ?? ""}
                  onChange={(e) => selectPartnerCandidate(cfg.role, e.target.value)}
                >
                  <option value="">Select the correct partner</option>
                  {lookup.candidates.map((candidate) => {
                    const vat = normalizeNullableText(candidate.vat);
                    const suffix = vat ? ` - ${vat}` : "";
                    const companyFlag = candidate.is_company ? "Company" : "Person";
                    return (
                      <option key={candidate.id} value={candidate.id}>
                        {candidate.name} ({companyFlag} #{candidate.id}){suffix}
                      </option>
                    );
                  })}
                </select>
                {lookup.error && <p className="ivf-partner-error">{lookup.error}</p>}
                {!lookup.error && lookup.hasSearched && lookup.candidates.length === 0 && (
                  <p className="ivf-partner-empty">No matches found. Try a shorter or partial name.</p>
                )}
                {!hasSelectedPartner && (
                  <p className="ivf-partner-required">
                    Select one partner from the list to continue. Manual partner typing is disabled to avoid mismatches.
                  </p>
                )}
              </div>

              {selected && (
                <div className="ivf-partner-meta">
                  <div><strong>Name:</strong> {selected.name || "-"}</div>
                  <div><strong>Tax ID:</strong> {normalizeNullableText(selected.vat) || "-"}</div>
                  <div><strong>Address:</strong> {formatPartnerAddress(selected) || "-"}</div>
                  <div><strong>IBAN:</strong> {normalizeNullableText(selected.iban) || "-"}</div>
                </div>
              )}

              <PartyFields
                data={roleData}
                onChange={(nextRoleData) =>
                  setData((d) => ({
                    ...d,
                    [cfg.role]: nextRoleData,
                  }))
                }
                missingFields={missing}
                prefix={cfg.role}
                readOnly={true}
              />
            </div>
          );
        })()}
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
        <button
          onClick={handleConfirm}
          className="ivf-btn ivf-btn-primary"
          type="button"
          disabled={!hasSelectedPartner}
          title={!hasSelectedPartner ? "Select a partner from search results first" : undefined}
        >
          Confirm and Send to Odoo
        </button>
      </div>
    </div>
  );
}