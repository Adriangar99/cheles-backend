## MODIFIED Requirements

### Requirement: Replacing pending transactions
On every read of an account, the system SHALL delete its pending (`PDNG`) transactions before storing the received
ones, because the bank changes their id once they are booked. A received transaction that matches a deleted pending
one (same account and amount, same counterparty or, without one, same description, and a date at most 3 days apart)
inherits its manual edits: manual category, note and manual kind. Each pending transaction passes its edits on at most
once, to the closest date.

#### Scenario: Pending transaction gets booked
- **WHEN** an account had a `PDNG` transaction and the bank now returns it as `BOOK` with a different id
- **THEN** after the sync only the `BOOK` transaction exists

#### Scenario: Pending transaction is still pending
- **WHEN** the bank returns the same transaction as `PDNG` again
- **THEN** the previous one is deleted and created again with the manual edits it had

#### Scenario: Edits survive booking
- **WHEN** a pending €12.50 debit at MERCADONA dated 3 October had the manual category Restaurantes, a note and a manual
  transfer mark, and the bank returns it booked on 5 October with a different id
- **THEN** the booked transaction has category Restaurantes (manual), the note and the manual transfer mark

#### Scenario: No matching booked transaction
- **WHEN** a pending transaction with edits is not returned again and nothing matches it
- **THEN** it is deleted and its edits are not applied to any other transaction
