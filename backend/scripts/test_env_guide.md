# Backend Test Environment Guide

## 1) Regression tests (logic correctness)

```bash
cd backend
pytest test_v2_core_reading.py test_v2_store_reading.py test_v2_e2e_flow.py test_v2_profile.py -q
```

## 2) Performance and concurrency test (k6)

Install k6 first:

- Windows: [https://k6.io/docs/get-started/installation/](https://k6.io/docs/get-started/installation/)

Run load test:

```bash
cd backend
set BASE_URL=https://www.nizaina.online/api/v2
set BOOK_ID=<your_book_id>
set TOKEN=<jwt_token>
k6 run scripts/loadtest_entries.js
```

Recommended baseline:

- `http_req_failed < 1%`
- `http_req_duration p95 < 800ms`

## 3) Security smoke checks

Check unauthorized access:

```bash
curl -i https://www.nizaina.online/api/v2/books/current
```

Expected: `401 Unauthorized`.

Check token required on write API:

```bash
curl -i -X POST https://www.nizaina.online/api/v2/entries \
  -H "Content-Type: application/json" \
  -d "{\"book_id\":\"demo\",\"page\":1,\"note_content\":\"x\"}"
```

Expected: `401 Unauthorized`.

## 4) Suggested CI pipeline

1. Run unit/integration tests (`pytest`).
2. Run a short k6 smoke run (1-2 minutes).
3. Deploy to trial environment.
4. Run full k6 load test on trial before release.
