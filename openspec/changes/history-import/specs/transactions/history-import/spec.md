## ADDED Requirements

### Requirement: Reading a MoneyLover export
The system SHALL read a MoneyLover CSV export encoded in UTF-16 or UTF-8 (with or without BOM) with the columns `Id`,
`Fecha`, `Categoria`, `Cantidad`, `Moneda`, `Nota` and `Cuenta` in any order, dates as `dd/mm/yyyy` and signed amounts
with a decimal point. A file without those columns is rejected with 422 «No reconozco este fichero: falta la columna
<columna>», and a row with an unreadable date or amount with 422 naming its line.

#### Scenario: UTF-16 export
- **WHEN** a UTF-16 export with a row «25/10/2026, Gasolina, -47.80, EUR, , Cuenta Principal» is read
- **THEN** it yields a row of wallet «Cuenta Principal» on 2026-10-25 of -47.80 EUR in category «Gasolina»

#### Scenario: Not a MoneyLover export
- **WHEN** a CSV without the column `Cuenta` is sent
- **THEN** the response is 422 «No reconozco este fichero: falta la columna Cuenta»

#### Scenario: Unreadable row
- **WHEN** line 3 has the date «31/02/2026»
- **THEN** the response is 422 and the message names line 3

### Requirement: Stable identity of imported rows
Each row SHALL get an id from its wallet, date, amount, currency, category, note and its position among identical rows
of the file, so the same row in a newer export gets the same id and identical rows stay distinct.

#### Scenario: Newer export
- **WHEN** a row is imported and then a newer export containing the same row is imported
- **THEN** the row is counted as already imported and not stored again

#### Scenario: Identical rows
- **WHEN** a file has two identical rows
- **THEN** both are imported

### Requirement: Preview of an import
`POST /api/imports/preview` with the file (base64) and a map from wallet to target (an account id, `new` or nothing)
SHALL return, per wallet, its name, number of rows, first and last date, target, and how many rows would be imported,
skipped because the target account's bank transactions start on or before their date (with that date), and already
imported; and the MoneyLover categories that have no equivalent, with their number of rows. It writes nothing.

#### Scenario: Wallet onto a bank account
- **WHEN** «Cuenta Principal» has rows from 2025-05-05 to 2026-10-25 and is sent to an account whose earliest bank
  transaction is 2026-07-01
- **THEN** the rows before 2026-07-01 are counted to import and the rest as skipped, with `bank_since` 2026-07-01

#### Scenario: Wallet onto a new account
- **WHEN** «Revolut» is sent to `new`
- **THEN** all its rows are counted to import and nothing is created

#### Scenario: Wallet not imported
- **WHEN** «Cuenta Ahorros» has no target
- **THEN** it is listed with its rows and nothing to import

#### Scenario: Unknown account
- **WHEN** a wallet is sent to an account id that does not exist
- **THEN** the response is 422

#### Scenario: File too large
- **WHEN** the decoded file is larger than 5 MB
- **THEN** the response is 413

### Requirement: Importing
`POST /api/imports` with the same input SHALL create an account without a bank, named after the wallet and counting as
«día a día», for each wallet sent to `new`, store the rows counted to import as transactions of their target account
and return how many were imported, skipped and already imported. Imported transactions are booked, have the note as
description (or the category name when there is no note) and appear everywhere bank transactions do.

#### Scenario: Import into a new account
- **WHEN** «Revolut» with 40 rows is imported to `new`
- **THEN** an account «Revolut» without a bank exists, it has 40 transactions and the response counts 40 imported

#### Scenario: Import twice
- **WHEN** the same file and targets are imported again
- **THEN** nothing new is stored and every row is counted as already imported

### Requirement: Categories of imported rows
An imported row SHALL get its category from the equivalence table of MoneyLover's built-in categories, else from a
Cheles category with the same name ignoring case and accents (both kept as manual), else from the automatic rules on
its description. «Transferencia entrante» and «Transferencia saliente» rows become transfers between own accounts
(manual kind, no category).

#### Scenario: Built-in category
- **WHEN** a row of «Comer en casa o fuera» is imported
- **THEN** its category is «Restaurantes», marked as manual

#### Scenario: Same name
- **WHEN** a row of «Otros gastos» is imported
- **THEN** its category is «Otros gastos»

#### Scenario: Own category
- **WHEN** a row of «Deuda Coche Papá» with note «Compra Mercadona» is imported and a rule maps «mercadona» to
  Supermercado
- **THEN** its category is «Supermercado», automatic

#### Scenario: Transfer
- **WHEN** a row of «Transferencia saliente» is imported
- **THEN** it is a transfer with a manual kind and no category
