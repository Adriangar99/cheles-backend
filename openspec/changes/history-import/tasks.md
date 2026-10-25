# Tasks

TDD: each scenario's test first, seen failing for the right reason. Commit before mutation checks. Fixtures are
invented (never the owner's export); the real export is only used for a final manual check of the preview counts.

## 1. Model

- [ ] 1.1 `source` on Transaction (`bank` | `import`) with migration `0003_transaction_source`; reprocessing keeps imported transactions as imported («Imported transaction»)

## 2. Reader

- [ ] 2.1 `moneylover.py`: encodings, columns in any order, dates and amounts, quoted fields, line-numbered errors, stable ids with the identical-row counter («UTF-16 export», «Not a MoneyLover export», «Unreadable row», «Identical rows»)

## 3. Plan and import

- [ ] 3.1 Category resolution (equivalence table, name, rules) and transfers, with the category names served by categorization through its public API («Built-in category», «Same name», «Own category», «Transfer»)
- [ ] 3.2 `PlanImport`: targets, cutoff against the bank, already imported, unmatched categories; `POST /api/imports/preview` («Wallet onto a bank account», «Wallet onto a new account», «Wallet not imported», «Unknown account», «File too large»)
- [ ] 3.3 `POST /api/imports`: new accounts through banking's public API, store, counts («Import into a new account», «Import twice», «Newer export»)

## 4. Contract and verification

- [ ] 4.1 `openapi.json` regenerated; docs (features, API); ruff, mypy, import-linter, pytest (coverage ≥ 97 %), CI; preview of the owner's export checked by hand

## Workflow follow-up

- Frontend change `history-import` (the «importar movimientos» section in «bancos») after this one is merged.
