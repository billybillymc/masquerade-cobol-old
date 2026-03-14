# Engineering Bootstrap Checklist

## Day 1 Setup

- Pick parser library and pin version.
- Pick graph and metadata stores.
- Choose schema validation stack per service.
- Decide policy-gateway implementation language.

## Week 1 Bootstrapping Tasks

- Initialize each service with minimal runnable app.
- Wire shared schemas package consumption.
- Add contract validation tests in each service.
- Add CI job for schema lint + JSON examples.

## Required Early Tests

- policy routing tests (`standard-external`, `sensitive-local`)
- claim schema validation tests
- readiness gate schema validation tests
- parser unknown-construct reporting tests
