# temp/ — scratch scripts & artifacts

Per core.md: debugging/testing scripts live here. Update this README whenever a file is added.

## Files

| File | Purpose |
|------|---------|
| `hpcl_boq_compute.py` | Compute BoQ unit prices × Y1 quantities for all 130 BoQ line items, emit markdown + CSV |
| `hpcl_boq_prices.json` | Unit-price source of truth (pulled from AWS Pricing MCP + documented public list prices for ap-south-1) |
| `e2e_test.py` | End-to-end pipeline test: upload image via API → poll to final status. Update `API` constant after deploy. Run same image twice to verify duplicate rejection |
| `check_upload_url.py` | Debug helper: prints the presigned S3 upload URL host (diagnosed the global-endpoint 307 redirect issue) |
| `save_clipboard.swift` | macOS: save clipboard image (PNG/TIFF) to file — `swift temp/save_clipboard.swift out.png` |
| `save_clipboard_png.sh` | macOS AppleScript variant of clipboard PNG save (less reliable than the Swift one) |
