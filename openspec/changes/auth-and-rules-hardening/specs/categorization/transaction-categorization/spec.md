## MODIFIED Requirements

### Requirement: User-created rules
The system SHALL allow creating a rule with `POST /api/rules` (`pattern`, `category_id`), storing the pattern trimmed
and with priority 10 so it wins over the default rules, and then reprocess every transaction. It returns
`{"processed": <number of transactions>}`. A pattern that is empty once trimmed is rejected, because it would match
every transaction.

#### Scenario: New rule
- **WHEN** the rule «gasolinera pepe» → Transporte is created
- **THEN** it is stored with priority 10, transactions are reprocessed and those containing «gasolinera pepe» move to Transporte unless they have a manual category

#### Scenario: Unknown category
- **WHEN** the `category_id` does not exist
- **THEN** the response is 400 «Categoría inexistente» and no rule is created

#### Scenario: Empty pattern
- **WHEN** the pattern is «   »
- **THEN** the response is 400 «El patrón no puede estar vacío», no rule is created and nothing is reprocessed
