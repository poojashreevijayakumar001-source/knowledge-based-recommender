# Knowledge-Based Recommender for New Customers (Cold Start)

**Problem:** An e-commerce site wants to recommend products to a new customer who has no purchase history. How can knowledge-based reasoning help?

## Short answer

Collaborative and content-based filtering both need past behaviour. A **knowledge-based recommender** does not. It reasons over three things the system already has:

1. **Product knowledge**: specifications, price, rating (`backend/data/products.json`).
2. **Domain knowledge**: expert rules that translate a need into specs, e.g. *photography → 50MP+ camera, AMOLED display* (`backend/data/knowledge.json`).
3. **The customer's stated requirements**: category, budget, intended use, brands to avoid, captured by a short guided form.

### Reasoning pipeline

| Step | What happens | Where |
|------|--------------|-------|
| 1. Constraint filtering | Budget, brand exclusions and *must-have* rules (e.g. a gaming laptop **must** have a dedicated GPU) remove unsuitable items | `Recommender._apply` |
| 2. Utility scoring | Score = 70% weighted need-rule match + 20% rating + 10% popularity | `Recommender._apply` |
| 3. Explanation | Each result lists the rules it satisfied (why) and missed (trade-offs) | `why`, `tradeoffs` |
| 4. Constraint relaxation | If nothing survives, constraints are loosened step by step and the user is told what changed | `Recommender.recommend` |

Because the reasoning is rule-based, every recommendation is **explainable**, works from the **first visit**, and the knowledge can be edited by a domain expert without retraining a model. Once the customer buys and browses, the site can blend in collaborative filtering (a hybrid system).

## Run it

Requires only Python 3.8+ (no packages to install).

```bash
cd backend
python3 server.py            # open http://localhost:8000
```

`PORT=9000 python3 server.py` changes the port. The backend serves the frontend, so one command runs everything.

Run the tests:

```bash
cd backend
python3 -m unittest -v
```

## Project layout

```
backend/
  server.py              HTTP server + JSON API (standard library only)
  recommender.py         Knowledge-based reasoning engine
  test_recommender.py    Unit tests
  data/products.json     Sample catalogue (26 products, 4 categories)
  data/knowledge.json    Domain rules, weights, relaxation steps
frontend/
  index.html, style.css, app.js   Guided needs form + explained results
```

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/meta` | Categories, price ranges, brands, use cases |
| GET | `/api/knowledge` | The full rule base (transparency) |
| POST | `/api/recommend` | Get recommendations |
| GET | `/api/health` | Health check |

Example request:

```bash
curl -s localhost:8000/api/recommend -H 'Content-Type: application/json' -d '{
  "category": "laptop",
  "budget_max": 60000,
  "use_cases": ["student", "travel"],
  "exclude_brands": [],
  "top_n": 3
}'
```

## Extending it

* **New product:** add an entry to `products.json`.
* **New need or rule:** add to `knowledge.json`. Each rule is `{attr, op, value, weight, reason, hard?}` with `op` one of `>=`, `<=`, `==`, `in`. Set `"hard": true` for a must-have.
* **New category:** add products with that `category` and a matching block in `knowledge.json`.
* **Tune ranking:** change `scoring_weights` in `knowledge.json`.
