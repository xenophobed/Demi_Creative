# Contract Tests

Contract tests pin down structural invariants that must hold across releases.
They are intentionally short and assertion-dense — each one captures a single
guarantee that downstream code (or the product itself) depends on.

Run them with:

```bash
cd backend
python -m pytest tests/contracts/ -v
```

## Non-negotiable invariants

The following contract tests assert structural invariants that MUST NOT
be relaxed without product + security review.

- `test_hub_coppa_invariant.py` — Content Hub responses MUST NOT contain
  any users-table field. Failing this test BLOCKS merge.
- `test_safety_failclosed_contract.py` — When `check_content_safety` is
  unavailable, content endpoints MUST fail closed (not soft-degrade).
