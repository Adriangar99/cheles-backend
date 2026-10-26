## MODIFIED Requirements

### Requirement: Transaction representation
Each transaction SHALL be exposed with `id`, `date`, `amount` (signed), `currency`, `status`, `title`, `counterparty`,
`description`, `kind`, `kind_manual`, `category_id`, `category_manual`, `account_id`, `account` (the account's alias or
name) and `note`. `raw` is not exposed.

#### Scenario: Listed transaction
- **WHEN** a €12.50 debit to «MERCADONA» on the account aliased «Nómina» is listed
- **THEN** it appears with `amount` `-12.50`, `title` «MERCADONA» and `account` «Nómina», without `raw`

#### Scenario: Automatic kind
- **WHEN** a transaction whose kind was never set by hand is listed
- **THEN** it appears with `kind_manual` false

## ADDED Requirements

### Requirement: Readable title
The system SHALL derive each transaction's `title`, in this order: a fixed text for transfers to or from the user's
own accounts (by counterparty IBAN); the counterparty; the merchant in the last segment of an `A // B // C`
description, cutting off city and country in the 40-character card format, or the previous segment when the last one
has no letters; the description. Imported transactions are titled by their description.

#### Scenario: Title from the counterparty
- **WHEN** a debit to «EXAMPLE MARKET» is listed
- **THEN** its `title` is «EXAMPLE MARKET»

#### Scenario: Card payment without counterparty
- **WHEN** a debit without creditor has the description
  `PAGO CON TARJETA EN GASOLINERAS // PAGO CON TARJETA // ACME FUEL                SOMECITY     ES`
- **THEN** its `title` is «ACME FUEL» and its `description` is unchanged

#### Scenario: Online merchant
- **WHEN** a debit without creditor has the description `PAGO CON TARJETA DE SERVICIOS VARIOS // OTROS // Example.com`
- **THEN** its `title` is «Example.com»

#### Scenario: Last segment without letters
- **WHEN** a debit without creditor has the description `CARGO POR AMORTIZACION // AMORTIZACIÓN PRÉSTAMO // 0000-1111-22`
- **THEN** its `title` is «AMORTIZACIÓN PRÉSTAMO»

#### Scenario: Transfer between own accounts
- **WHEN** a debit and a credit whose counterparty IBAN is an own account's IBAN are listed
- **THEN** their titles are «Traspaso a cuenta» and «Traspaso desde cuenta»

#### Scenario: Unstructured description
- **WHEN** a credit without debtor has the description «NOMINA EMPRESA»
- **THEN** its `title` is «NOMINA EMPRESA»

#### Scenario: Imported transaction title
- **WHEN** an imported transaction with the note «Cena con amigos» is listed
- **THEN** its `title` is «Cena con amigos»
