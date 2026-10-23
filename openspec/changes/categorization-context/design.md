# Design

## Context

See proposal.md. Current code:

- `app/categorize.py`: `DEFAULT_CATEGORIES` (16 categories with patterns), `seed_categories(db)` (only when the table is
  empty; patterns get priority 100), and `Categorizer(db)`, which loads all rules ordered by `(priority, id)` and the
  ids of «Otros gastos», «Otros ingresos» and «Bizum recibido», then `categorize(tx)` matches
  `f" {counterparty or ''} {description} ".lower()`.
- `app/models.py`: `Category`, `Rule`, and `Transaction.category` (relationship) plus its `category_id` FK.
- `app/main.py`: lifespan seeding, `GET /api/categories` (income first, then by name), `POST /api/rules`
  (validates the category, stores the trimmed pattern with priority 10, then `reprocess_all`), and the category
  check in `PATCH /api/transactions/{id}`.
- `app/sync.py`: `Categorizer(db)` in `sync_account` and `reprocess_all`; `apply_derived_fields` calls
  `categorizer.categorize(tx)`.
- `app/stats.py`: `month_summary` joins `Category` to label spending.

## Goals / Non-Goals

**Goals:**
- Same observable behavior (HTTP responses, ordering, seeding, categorization results).
- Legacy code depends on categorization only through `app.categorization.public`.

**Non-Goals:**
- Event bus, shared kernel, migrating any other context.

## Decisions

### Package layout (mirrors identity)

```
app/categorization/
  domain/
    category.py        # Category(id, name, kind, icon, color), CategoryKind = Literal["expense", "income"]
    rule.py            # Rule(id, pattern, category_id, priority); USER_RULE_PRIORITY = 10, DEFAULT_RULE_PRIORITY = 100
    policy.py          # CategorizationPolicy: categorize(counterparty, description, is_income) -> int | None
    catalog.py         # DEFAULT_CATALOG (data moved from app/categorize.py)
    errors.py          # UnknownCategory
  application/
    ports.py           # CategoryRepository, RuleRepository, UnitOfWork
    use_cases.py       # SeedDefaultCatalog, ListCategories, CreateRule, CategoryExists, LoadPolicy, CategoryLabels
                       #   + CategorizationServices bundle
  infrastructure/
    orm.py             # CategoryRow, RuleRow (same tables)
    repositories.py    # SQL repositories + unit of work
    http.py            # GET /api/categories, categorization_services placeholder
  public.py            # CategorizationServices, CategorizationPolicy, CategoryLabel, UnknownCategory
```

### Value objects and what crosses the boundary
- The signed amount stays a transactions concept. Categorization only needs to know whether a movement is income, so
  its input is `is_income: bool`, computed by the caller as `amount > 0` (zero is an expense, as today). This keeps
  «sign» semantics out of categorization; no shared `Money` is needed.
- Category ids cross the boundary as plain `int` (they are already stored that way in transactions). A shared
  `CategoryId` would only be worth it in a shared kernel, which is out of scope.
- `CategoryLabel(id, name, icon, color)` is categorization's read model for other contexts; stats owns the fallback
  label for uncategorized spending («Sin categoría», «•», `#8a8a8a`), because that label is a stats presentation
  concern.

### Legacy access to the context
- HTTP: the categorization router depends on a placeholder `categorization_services`, overridden by
  `bootstrap.wire()`, exactly as identity.
- Non-HTTP legacy code (lifespan, sync, reprocess, stats, the rules and transaction routes) needs services outside a
  request dependency. `bootstrap` keeps the container passed to the last `wire()` call and exposes
  `bootstrap.current()`; legacy code calls `current().categorization()`. This is a **transitional** service locator,
  allowed only for legacy modules; contexts never use it, and it disappears as each consumer migrates.
- Each categorization call opens its own unit of work (separate session). The legacy flows only read from
  categorization while they hold their own transaction, except `POST /api/rules`, which commits the rule before
  reprocessing, so the reprocess sees it.

### Stats query
`month_summary` groups counted debits by `Transaction.category_id` (ordered by `sum(amount)` ascending, i.e. highest
spending first) and maps ids to labels with `CategoryLabels`. `NULL` ids get the stats fallback label. Output shape
and order are unchanged; the stats characterization tests guard it.

### Transaction model
`Transaction.category` (relationship) is removed so the legacy model does not reference categorization's ORM class.
The `category_id` column and its FK (`ondelete="SET NULL"`) stay; the FK is declared by table name and resolves on the
shared `Base.metadata`.

### Contracts
The four identity contracts are generalized to `app.identity` and `app.categorization` (one `layers` contract per
context, one framework-free contract with both cores, one no-legacy contract with both contexts, one legacy→public
contract with both contexts' internals). A new contract forbids each context from importing the other's
`domain|application|infrastructure` (only `public`).

### Tests
- Characterization tests keep every expected value. Imports switch to `app.categorization.infrastructure.orm`
  (aliased to the old names), the conftest seeds through the use case, and the three places that read
  `transaction.category.name` resolve the name from `transaction.category_id` with a small test helper.
- New unit tests only for `CategorizationPolicy` (priority and creation order, trailing-space patterns, fallbacks
  including Bizum and zero amounts): it is the rule engine every sync and reprocess depends on.

## Risks / Trade-offs

- [Service locator in bootstrap] → Transitional and limited to legacy modules; documented and removed per migrated
  consumer.
- [Two sessions per legacy flow] → Read-only use of categorization during legacy transactions; the only write
  (`CreateRule`) commits before the dependent reprocess.
- [Stats output order with equal sums] → Unordered ties existed before too; tests use distinct amounts.

## Migration Plan

Refactor only; rebuild the image. No data or schema change.
