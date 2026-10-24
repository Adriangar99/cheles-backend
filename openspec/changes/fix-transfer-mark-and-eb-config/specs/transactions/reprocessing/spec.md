## MODIFIED Requirements

### Requirement: Reprocessing respects manual edits
Reprocessing SHALL keep manually assigned categories, manual kinds and notes.

#### Scenario: Manual category
- **WHEN** a transaction with a manual category is reprocessed
- **THEN** it keeps its category

#### Scenario: Note
- **WHEN** a transaction with a note is reprocessed
- **THEN** it keeps its note

#### Scenario: Manual kind
- **WHEN** a transaction with a manual kind is reprocessed
- **THEN** it keeps its kind and `kind_manual` stays true
