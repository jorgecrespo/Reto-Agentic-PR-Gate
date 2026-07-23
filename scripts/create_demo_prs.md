# Recreate GitHub demo PRs

Use these instructions only in a disposable fork when a live GitHub walkthrough is
required. Replace placeholders; do not treat the URLs as existing PRs.

| Scenario | Branch | Suggested title | Expected gate status |
| --- | --- | --- | --- |
| Defective | `demo/defective-client-price` | `demo: accept request item price` | `BLOCKED` before mitigation |
| Safe | `demo/safe-product-description` | `demo: add optional product description` | `READY` |
| Inconclusive | `demo/inconclusive-runner` | `demo: unavailable validation environment` | `INCONCLUSIVE` |

1. Create a branch from the same base SHA used for the walkthrough.
2. For the defective branch, copy the change represented by
   `examples/demo_ecommerce/app/orders.py` so the order total uses the request
   price instead of the catalog price. Its PR body should state: `The order total
   must use the current catalog price, not request unit_price.`
3. For the safe branch, add the optional `description` field represented by
   `examples/demo_ecommerce/app/domain.py` and update the relevant test in
   `examples/demo_ecommerce/tests/test_orders.py`.
4. For the inconclusive case, use an otherwise valid change but select a validation
   environment where Docker is intentionally unavailable. Do not claim a successful
   validation.
5. Open PRs manually in the fork. Record their actual URLs separately from this
   repository; this project intentionally has no hard-coded live PR URL.

Suggested acceptance criteria for the defective PR:

- `AC-PRICE`: The order total uses the catalog price for each product.
- `AC-QUANTITY`: Quantity must be positive.
- `AC-PRODUCT`: Unknown products are rejected.
