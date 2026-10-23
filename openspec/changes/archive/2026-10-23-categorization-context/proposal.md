# Proposal

## Why

Categorization still lives in the flat legacy modules (`app/categorize.py`, `Category`/`Rule` in `app/models.py`,
category routes in `app/main.py`), and other legacy code reaches into its tables directly (stats joins `categories`,
the transaction model has an ORM relationship to `Category`). Migrating it is the second step of the hexagonal
migration and the first one where legacy code must consume a context through its public API.

## What Changes

- New `app/categorization/` bounded context following the identity layout:
  - domain: `Category`, `Rule` and a pure `CategorizationPolicy` (rules by ascending priority then creation order,
    case-insensitive substring match on «counterparty + description», fallbacks «Bizum recibido», «Otros ingresos»,
    «Otros gastos»), plus the default catalog as data;
  - application: ports (category and rule repositories, unit of work) and use cases: seed the default catalog, list
    categories, create a rule, check that a category exists, load the categorization policy, and read category labels
    for a set of ids;
  - infrastructure: ORM rows on the same tables (no migration), repositories, and the `GET /api/categories` router.
- `app/categorization/public.py` exposes what legacy code needs: the services accessor types, the policy interface and
  the label read model.
- Legacy code switches to the public API:
  - `POST /api/rules` stays in `app/main.py` and orchestrates: create the rule through categorization, then the legacy
    reprocess, returning the same `{"processed": N}` (no event bus yet, by decision);
  - `PATCH /api/transactions/{id}` validates the category through categorization;
  - sync and reprocess categorize through the policy obtained from categorization;
  - stats groups spending by `category_id` in SQL and completes name, icon and color through the label read model
    (same output and order);
  - the API startup seeds the default catalog through categorization.
- The `Transaction.category` ORM relationship is removed; the `category_id` foreign key stays.
- The composition root gains categorization services and a transitional accessor for legacy code; import-linter gets
  the same four contracts for categorization plus «contexts reach each other only through `public`».

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. Pure refactor (`skip_specs: true`): `categorization/transaction-categorization` and the specs that depend on it
(`stats/financial-summary`, `transactions/*`) keep every requirement and scenario.

## Impact

- **Bounded contexts**: categorization (migrated); legacy transactions, banking and stats now depend on it only
  through `app.categorization.public`. Categorization's HTTP adapter uses `app.identity.public.require_user`.
- **Cross-context events**: none (the rule-created → reprocess flow stays a direct call from the legacy route until
  transactions migrates).
- **Security surface**: unchanged; `GET /api/categories` keeps requiring a session.
- **Database**: same tables; no migration. `migrations/env.py` registers the new ORM module.
- **Tests**: characterization tests keep their expected values; imports adapt, and the assertions that navigated
  `transaction.category` resolve the name through `category_id` instead.

### Out of scope

- Event bus and shared kernel (arrive with transactions).
- Migrating transactions, banking or stats, and fixing their recorded observations (e.g. empty rule patterns).
