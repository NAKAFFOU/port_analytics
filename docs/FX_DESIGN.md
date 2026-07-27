# Foreign-Exchange Design

## Objectives

- preserve the original amount and currency;
- convert every record into a controlled analytical base currency;
- use a date-sensitive rate;
- retain the applied rate, rate date and provider;
- permit a different dashboard display currency without rebuilding the analytical model.

## Rate convention

A stored rate means:

```text
1 from_currency = rate to_currency
```

Example:

```text
1 EUR = 0.84 GBP
```

## Conversion timing

Accounting transactions are converted using their accounting date. Budget rows use the first day of the configured period in the supplied CSV loader. An organisation may change this policy to monthly-average or period-end rates if required by its accounting policy.

## Providers

### Controlled CSV

Recommended when Finance or Treasury supplies approved historical rates.

### ECB loader

The provider reads euro reference-rate observations and derives source-to-base rates through EUR. This is useful for currencies published by the ECB. It is not a substitute for an organisation's accounting policy.

### Custom provider

A future provider can load rates from a treasury system, data warehouse, bank feed or approved internal table by writing into `fx_rates`.

## Dashboard display conversion

The analytical outputs remain in the base currency. When another display currency is selected, the dashboard applies the selected period's available base-to-display rate. This conversion is for presentation; source-level audit values remain unchanged.
