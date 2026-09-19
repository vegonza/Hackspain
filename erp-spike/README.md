# erp-spike

Everything that talks to Alberto's ERP, plus the logic that matches an invoice
to an accounting entry. Nothing here is wired into the application yet: this is
a reviewable spike, not an integration.

```
erp_client.py           reads the ERP over HTTP and writes a snapshot
order_resolver.py       matches an invoice to an entry in that snapshot
test_order_resolver.py  tests for the above
validate_resolver.py    scores the resolver against the real invoice corpus
docs/ADR.md             why each decision was made
```

`erp_client.py` and `order_resolver.py` know nothing about each other. The
first produces a file, the second consumes a list of dictionaries. You can use
the resolver without ever running the client.

---

## The problem `order_resolver` solves

The natural join between an invoice and the ERP is the purchase order:

```
InvoiceFeatures.purchase_order   "PO-2026-0042"
        <->
Entry.order_id                   "PO-2026-0042"
```

That works when the invoice states the order. It does not always. Of the 500
invoices in the current batch, 29 are scans with no text at all, and the next
batch may contain invoices that never printed an order number. A single-key
lookup gives up on all of them.

`order_resolver` turns the lookup into a cascade. The order code is still the
first and best key; it is no longer the only one.

| # | Strategy | Key | Confidence |
|---|---|---|---|
| 1 | `ORDER_CODE` | the code, as printed | `EXACT` |
| 2 | `ORDER_CODE_REPAIRED` | the code after fixing OCR glyph swaps (`O`→`0`) | `HIGH` / `LOW` |
| 3 | `NIF_AND_DATE` | supplier tax id + invoice date, ties broken by an exact amount | `HIGH` |
| 4 | `NIF_AND_AMOUNT` | supplier tax id + amount, when the date is unreadable | `MEDIUM` |
| 5 | `AMOUNT_ONLY` | amount alone, when the tax id is unreadable | `LOW` |
| — | escalate | none of the above | `NONE` |

### The one design decision worth arguing about

**The date anchors the search; the amount only breaks ties, and only on an
exact match.**

Searching by amount is tempting because it is nearly unique (507 of 516 entries
have a distinct amount). It is also wrong: the amount is the thing being
audited. An invoice inflated by 275 EUR would either find nothing or find some
other supplier's entry, so the tampering becomes undetectable precisely because
it happened.

Measured on the real snapshot:

| Key | Entries identified uniquely |
|---|---|
| tax id alone | 0 / 496 — there are only 11 suppliers |
| date alone | 42 / 516 |
| **tax id + date** | **406 / 496** |
| tax id + date, ties broken by exact amount | **462 / 468** |

When a tie cannot be broken exactly, the resolver escalates rather than picking
the nearest amount. Picking the nearest would quietly absorb the discrepancies
we are looking for.

---

## Using it

```python
from order_resolver import ErpIndex, InvoiceSignals, OrderResolver

index    = ErpIndex.from_jsonl("/app/erp_snapshot.jsonl")   # once, at startup
resolver = OrderResolver(index)                             # cheap, reusable

features   = extract_invoice_features(markdown)             # your pipeline
resolution = resolver.resolve(
    InvoiceSignals.from_features(features, raw_text=markdown)
)

if resolution.resolved:
    apply_rules(features, resolution.entry, resolution.anomalies)
else:
    escalate(features, resolution.candidates, resolution.anomalies)
```

`InvoiceSignals.from_features()` accepts either an `InvoiceFeatures` object or
a plain mapping, so nothing in `documents/features.py` needs to change.

### What it needs from extraction

Every field is optional; the cascade degrades as fields go missing. But the
relative importance has shifted:

| `InvoiceFeatures` field | Role |
|---|---|
| `purchase_order` | best key, no longer required |
| `supplier_nif` | **critical** — anchors the fallback |
| `invoice_date` | **critical** — anchors the fallback |
| `total` | breaks ties |

> **Do not normalise or repair the invoice date.** An invoice dated
> `31/02/2026` must arrive exactly as printed. Three of the invoices in the
> current batch carry impossible dates, and that is a forgery signal, not an
> extraction error. The resolver distinguishes `invoice_date_impossible` from
> `invoice_date_unparseable` and both are lost if the date is silently fixed.

> **`total` must be a bare amount, not a sentence.** `"1.250,00"`,
> `"1.250,00 €"` and `"EUR 1409.40"` all parse. `"Importe base: 1.250,00 €"`
> does not, and returns `None` with an `amount_unparseable` anomaly.
>
> This is deliberate and was tightened after review. An earlier version
> stripped every non-digit character before parsing, which meant
> `"IVA (21%): 295,97"` came back as **21.295,97** and `"30 dias fecha
> factura"` came back as **30,00**. Mining digits out of prose invents money.
> If the field holds a label the extraction is wrong, and the only safe answer
> is to say so.

Both conventions found in the corpus are supported: Spanish `1.250,00` and
English `3400.00`. Genuinely ambiguous shapes such as `1,234` are refused
rather than guessed, because getting the order of magnitude wrong is worse
than returning nothing.

### What comes back

```python
Resolution(
    entry        = Entry | None,
    strategy     = Strategy.NIF_AND_DATE,
    confidence   = Confidence.HIGH,
    candidates   = (Entry, Entry),    # shortlist when it cannot decide
    anomalies    = ("amount_mismatch", "entry_already_paid"),
    notes        = (),
)
```

`resolution.to_dict()` is JSON-serialisable.

### `needs_review` and `blocking_anomalies`

```python
resolution.needs_review        # bool
resolution.blocking_anomalies  # subset that should stop a payment outright
```

`needs_review` is `False` only for an exact order-code match whose
corroboration came back **completely clean**. Any anomaly at all sets it.

This too was tightened after review. Previously the flag looked only at the
strategy and the confidence, so an invoice matching an entry that was already
`PAGADA` resolved by exact code, with `EXACT` confidence, and reported
`needs_review = False` — while carrying `entry_already_paid` in its anomalies.
Anything downstream trusting the flag would have paid it twice. Resolving an
invoice perfectly is not the same as it being safe to pay, and the flag now
says so.

On the current batch, 24 of the 468 exactly-matched invoices are flagged:
9 already paid, 9 amount mismatches, 3 impossible dates, 2 supplier
mismatches, 1 date mismatch.

`BLOCKING_ANOMALIES` names the subset that should stop a payment rather than
merely annotate it: already paid, duplicated order, supplier mismatch, order
unknown to the ERP, impossible invoice date. The rest are context a reviewer
may reasonably wave through.

### Duplicated orders are never resolved

If the ERP holds more than one row for the same `order_id`, the resolver
**refuses to return either**. It escalates with `duplicate_order_in_erp`, every
competing row in `candidates`, and a note naming their entry ids.

The index used to keep whichever row it read last and carry on. It recorded the
duplicate but still resolved against one of them, which in a payments context
is a coin flip with someone else's money. `ErpIndex.by_order()` now returns
`None` for a duplicated order, and a guard in `resolve()` catches it whichever
rung of the cascade produced it, so the fallback cannot sneak past either.

Use `index.known_order(id)` to ask whether the ERP has the order at all,
`index.is_duplicated(id)` to tell a ledger defect from a missing order, and
`index.rows_for_order(id)` to see the competing rows. The current snapshot has
no duplicates; this is a guard, not a workaround.

### Anomalies, reported whether or not it resolved

| Anomaly | Meaning | Count in the current batch |
|---|---|---|
| `order_code_unknown_to_erp` | the invoice cites an order the ERP never heard of | 3 |
| `supplier_tax_id_mismatch` | the order belongs to a different supplier | 2 |
| `amount_mismatch` | the total does not match the entry | 13 |
| `entry_already_paid` | the entry is `PAGADA` | 9 |
| `entry_tax_id_missing` | the ERP returned an empty tax id | 20 |
| `invoice_date_impossible` | e.g. `31/02/2026` | 3 |
| `date_mismatch` | invoice date differs from the entry date | — |
| `resolved_without_order_code` | found via the fallback | — |
| `ambiguous_candidates` | more than one plausible entry | — |

Finding the entry never suppresses these. The 13 amount mismatches were all
resolved to the correct order *and* flagged.

---

## Measured results

`validate_resolver.py` replays all 500 invoices twice: once as they are, and
once with every `PO-2026-NNNN` stripped from both the field and the raw text,
to simulate invoices that arrive without one.

| | with the code | without the code |
|---|---|---|
| correct | 468 (100%) | 452 (96.6%) |
| **wrong** | **0** | **0** |
| escalated | 0 | 16 (3.4%) |
| shortlist size when escalating | — | 2.2 average, 3 maximum |
| correct order present in the shortlist | — | 16 of 16 |

The headline number is not the hit rate, it is the zero. A resolver that
escalates is merely slow. A resolver that confidently returns the wrong order
causes a wrong payment.

Of the 16 escalations: 13 are caused by the throwaway extraction stand-in
failing to read the total, 2 are invoices whose amount genuinely disagrees with
the ERP, and 1 is a supplier impersonation. Only the last three are real. With
proper OCR the expected figure is around 99% resolved, 1% escalated, 0% wrong.

---

## Running the tests

```bash
pytest test_order_resolver.py -q
```

Roughly fifty unit tests run against `order_resolver` alone and need nothing
else. The regression suite at the bottom of the file replays the real corpus
and will **skip** unless three things are present:

| Missing | Where it comes from |
|---|---|
| `data/erp_entries.jsonl` | `python3 erp_client.py --output data/erp_entries.jsonl` |
| `data/invoices_extracted.jsonl` | a local reconnaissance script over the PDFs |
| `fake_ocr.py` | a stand-in for the OCR layer, deliberately not distributed |

`data/` is gitignored: it is challenge data and this repository is public.
`fake_ocr.py` is three crude regular expressions that stood in for extraction
while it did not exist. It is not shipped because it is not a contribution to
the extraction work and should not be mistaken for one.

---

## Open questions for the team

1. An invoice resolved by the fallback: decide automatically, or always route
   to review? `needs_review` is already set; the policy is yours.
2. An order the ERP does not know: `ESCALAR` or `NO_PAGAR`? Suggestion:
   **escalate**. Missing information is not the same as a contradiction.
3. Where does the backend read the snapshot from, and who owns refreshing it
   when the next batch lands?
4. The `documents` table has no column for a decision or a motive.
5. Is `Confidence.LOW` (`AMOUNT_ONLY`) worth keeping at all, or should the
   cascade stop at `NIF_AND_AMOUNT`? It fired twice in 468.
