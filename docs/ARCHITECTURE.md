# Architecture

## Stable target model

The analytical target is independent from the accounting package. Source systems are converted into a stable canonical contract and then mapped into:

- Shared Service Centres (SSC)
- Operational Cost Centres (OCC)
- Port Service Lines (PSL)

## Data path

1. Connector establishes a read-only source connection.
2. Adapter extracts and normalises source fields.
3. Staging retains source identifiers, values and currencies.
4. Mapping resolves organisational codes into canonical analytical codes.
5. Currency conversion produces base-currency values and retains audit metadata.
6. Core tables feed the two-phase cost-allocation pipeline.
7. KPI tables support alerts, actions and dashboard views.

## Source-system independence

JD Edwards is the first implemented adapter. SAP, Sage and other systems should implement the same accounting-source interface rather than modify the analytical pipeline.
