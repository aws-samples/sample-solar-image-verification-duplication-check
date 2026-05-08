# temp/ — scratch scripts & artifacts

Per core.md: debugging/testing scripts live here. Update this README whenever a file is added.

## Files

| File | Purpose |
|------|---------|
| `hpcl_boq_compute.py` | Compute BoQ unit prices × Y1 quantities for all 130 BoQ line items, emit markdown + CSV |
| `hpcl_boq_prices.json` | Unit-price source of truth (pulled from AWS Pricing MCP + documented public list prices for ap-south-1) |
