# Payment API with Idempotency-Key support

This demo shows how to protect a payment endpoint from duplicate processing using an **Idempotency-Key** header, FastAPI and Redis.

## Requirements

* Docker + docker-compose

## Quick start

```bash
# build & start services
# copy .env.example to .env
cp .env.example .env
# edit .env
# run docker-compose
docker-compose up --build
```

The API will be available at <http://localhost:8000/docs>.

### Example request

```bash
curl -X POST http://localhost:8000/payments \
     -H "Content-Type: application/json" \
     -H "Idempotency-Key: order-42" \
     -d '{"amount": 9.9, "currency": "USD"}'
```

Send the same request again with the same key – you will get **exactly** the same JSON response instantly.

## Internals

* `Idempotency-Key` is optional. When present, the middleware:
  1. Looks up cached response in Redis (`idem:{key}`).  
  2. If found ⇒ returns it.  
  3. Otherwise attempts `SETNX` a temporary `LOCK`.   
     * Wait for the first request to finish and save the result (idempotency)
     * If lock fails ⇒ another request in flight ⇒ 409.
  4. After downstream handler succeeds, save `{hash, response}` with TTL (default 24 h in .env).

* Concurrency safety relies on single-atomic `SETNX`.

## Tests
Access to docker container:

```bash
docker-compose exec `container_name` bash
```

Run tests:

```bash
cd app & pytest -vv
```
