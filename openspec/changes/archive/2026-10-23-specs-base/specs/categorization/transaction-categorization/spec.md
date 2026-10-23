# Spec Delta

## Purpose

Automatically assigns an expense or income category to each transaction through prioritized text rules, starting from
a default catalog of categories and rules tailored to Spanish merchants, and lets the user add their own rules.

## ADDED Requirements

### Requirement: Default category and rule catalog
On startup, if no category exists, the system SHALL create the default categories with their kind (`expense` or
`income`), icon, color and pattern rules with priority 100. If categories already exist it creates nothing.

#### Scenario: First startup
- **WHEN** the API starts with no categories
- **THEN** the 13 expense categories (Supermercado, Restaurantes, Transporte, Vivienda, Suministros, Suscripciones, Compras, Salud, Ocio, Viajes, Impuestos y comisiones, Efectivo, Otros gastos) and the 3 income categories (Nómina, Bizum recibido, Otros ingresos) exist
- **AND** every default pattern is a rule with priority 100, e.g. «mercadona» → Supermercado

#### Scenario: Later startups
- **WHEN** the API starts and categories already exist
- **THEN** no category or rule is created or modified

### Requirement: Category listing
The system SHALL return at `GET /api/categories` every category with `id`, `name`, `kind`, `icon` and `color`, income
categories first and then expense categories, each group ordered by name.

#### Scenario: Listing order
- **WHEN** categories are listed
- **THEN** `income` categories come before `expense` ones and each group is sorted alphabetically

### Requirement: Rule-based categorization
The system SHALL assign to a non-transfer transaction without a manual category the category of the first rule whose
pattern appears, case-insensitively, in the text "counterparty + description". Rules are evaluated by ascending
priority and, for equal priority, by creation order. The category's kind is not checked.

#### Scenario: Match on the counterparty
- **WHEN** a debit has the counterparty «MERCADONA VALENCIA»
- **THEN** its category is Supermercado

#### Scenario: Priority
- **WHEN** a priority-10 rule and a priority-100 rule both match
- **THEN** the priority-10 rule applies

#### Scenario: Patterns with a trailing space
- **WHEN** the pattern is «bar » and the text is «BARCELONA PARKING»
- **THEN** the «bar » rule does not match

#### Scenario: Expense rule on an income
- **WHEN** a credit contains the pattern of an expense category
- **THEN** it gets that expense category

### Requirement: Fallback categories
If no rule matches, the system SHALL assign «Bizum recibido» to credits whose text contains «bizum», «Otros ingresos»
to the remaining credits and «Otros gastos» to debits and zero amounts.

#### Scenario: Received Bizum
- **WHEN** a credit with no matching rule has the description «BIZUM DE JUAN»
- **THEN** its category is Bizum recibido

#### Scenario: Other income
- **WHEN** a credit matches no rule and does not contain «bizum»
- **THEN** its category is Otros ingresos

#### Scenario: Other expense
- **WHEN** a debit matches no rule
- **THEN** its category is Otros gastos

### Requirement: User-created rules
The system SHALL allow creating a rule with `POST /api/rules` (`pattern`, `category_id`), storing the pattern trimmed
and with priority 10 so it wins over the default rules, and then reprocess every transaction. It returns
`{"processed": <number of transactions>}`.

#### Scenario: New rule
- **WHEN** the rule «gasolinera pepe» → Transporte is created
- **THEN** it is stored with priority 10, transactions are reprocessed and those containing «gasolinera pepe» move to Transporte unless they have a manual category

#### Scenario: Unknown category
- **WHEN** the `category_id` does not exist
- **THEN** the response is 400 «Categoría inexistente» and no rule is created
