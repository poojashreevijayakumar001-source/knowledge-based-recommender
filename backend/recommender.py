"""Knowledge-based recommender for cold-start customers.

No purchase history is used. Instead we reason over:
  1. Product knowledge   (products.json: specs, price, rating)
  2. Domain knowledge    (knowledge.json: which specs satisfy which need)
  3. Customer requirements (category, budget, needs, brand exclusions)

Pipeline:
  constraint filtering  ->  rule-based utility scoring  ->  explanation
  -> constraint relaxation (only if nothing survives the filters)
"""
import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def load_json(name):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


class Recommender:
    def __init__(self, products=None, knowledge=None):
        self.products = products if products is not None else load_json("products.json")
        self.knowledge = knowledge if knowledge is not None else load_json("knowledge.json")

    # ------------------------------------------------------------------ meta
    def meta(self):
        cats = {}
        for key, cat in self.knowledge["categories"].items():
            items = [p for p in self.products if p["category"] == key]
            prices = [p["price"] for p in items]
            cats[key] = {
                "label": cat["label"],
                "min_price": min(prices) if prices else 0,
                "max_price": max(prices) if prices else 0,
                "brands": sorted({p["brand"] for p in items}),
                "use_cases": [
                    {"id": uid, "label": u["label"], "description": u["description"]}
                    for uid, u in cat["use_cases"].items()
                ],
            }
        return {"currency": self.knowledge["currency"], "categories": cats}

    def knowledge_view(self):
        return {
            "scoring_weights": self.knowledge["scoring_weights"],
            "relaxation_steps": self.knowledge["relaxation_steps"],
            "categories": self.knowledge["categories"],
        }

    # ----------------------------------------------------------------- rules
    @staticmethod
    def _value(product, attr):
        if attr == "price":
            return product["price"]
        if attr == "rating":
            return product["rating"]
        return product["specs"].get(attr)

    @classmethod
    def rule_matches(cls, product, rule):
        actual = cls._value(product, rule["attr"])
        if actual is None:
            return False
        op, expected = rule["op"], rule["value"]
        if op == ">=":
            return actual >= expected
        if op == "<=":
            return actual <= expected
        if op == "==":
            return actual == expected
        if op == "in":
            return actual in expected
        raise ValueError("Unknown operator: %s" % op)

    # ------------------------------------------------------------- reasoning
    def _apply(self, category, req, budget_factor, ignore_brands, soften_hard):
        """Filter + score once with a given relaxation state."""
        cat_kb = self.knowledge["categories"][category]
        selected = [u for u in req.get("use_cases", []) if u in cat_kb["use_cases"]]
        rules = []
        for uid in selected:
            for r in cat_kb["use_cases"][uid]["rules"]:
                rules.append(dict(r, use_case=cat_kb["use_cases"][uid]["label"]))

        budget_max = req.get("budget_max")
        if budget_max:
            budget_max = budget_max * budget_factor
        budget_min = req.get("budget_min") or 0
        excluded = set() if ignore_brands else set(req.get("exclude_brands", []))

        trace = {"in_category": 0, "after_budget": 0, "after_brands": 0, "after_must_haves": 0}
        pool = [p for p in self.products if p["category"] == category]
        trace["in_category"] = len(pool)

        pool = [p for p in pool if p["price"] >= budget_min and (not budget_max or p["price"] <= budget_max)]
        trace["after_budget"] = len(pool)

        pool = [p for p in pool if p["brand"] not in excluded]
        trace["after_brands"] = len(pool)

        if not soften_hard:
            hard = [r for r in rules if r.get("hard")]
            pool = [p for p in pool if all(self.rule_matches(p, r) for r in hard)]
        trace["after_must_haves"] = len(pool)

        w = self.knowledge["scoring_weights"]
        total_weight = sum(r["weight"] for r in rules)
        results = []
        for p in pool:
            matched = [r for r in rules if self.rule_matches(p, r)]
            missed = [r for r in rules if not self.rule_matches(p, r)]
            rule_score = (sum(r["weight"] for r in matched) / total_weight) if total_weight else 0.5
            score = (
                w["rules"] * rule_score
                + w["rating"] * (p["rating"] / 5.0)
                + w["popularity"] * (p["popularity"] / 100.0)
            )
            results.append({
                "product": p,
                "score": round(score * 100, 1),
                "need_match": round(rule_score * 100) if total_weight else None,
                "why": [{"use_case": r["use_case"], "text": r["reason"]} for r in matched],
                "tradeoffs": [{"use_case": r["use_case"], "text": "Does not meet: " + r["reason"].lower()} for r in missed],
            })
        results.sort(key=lambda x: (-x["score"], x["product"]["price"]))
        return results, trace, selected

    def recommend(self, req):
        category = req.get("category")
        if category not in self.knowledge["categories"]:
            raise ValueError("Unknown category: %r" % (category,))
        top_n = max(1, min(int(req.get("top_n", 5)), 10))

        # Each step is cumulative: later steps keep earlier relaxations applied.
        steps = [
            ("none", 1.0, False, False),
            ("drop_brand_exclusions", 1.0, True, False),
            ("budget_plus_25", 1.25, True, False),
            ("budget_plus_50", 1.5, True, False),
            ("soften_must_haves", 1.5, True, True),
        ]
        labels = {s["id"]: s["label"] for s in self.knowledge["relaxation_steps"]}

        results, trace, selected = [], {}, []
        final = steps[-1]
        for step in steps:
            _, factor, ignore_brands, soften = step
            results, trace, selected = self._apply(category, req, factor, ignore_brands, soften)
            final = step
            if results:
                break

        # Report only what was actually relaxed in the final state.
        _, factor, ignore_brands, soften = final
        relaxed = []
        if ignore_brands and req.get("exclude_brands"):
            relaxed.append(labels["drop_brand_exclusions"])
        if factor > 1.0 and req.get("budget_max"):
            pct = int(round((factor - 1) * 100))
            new_budget = int(req["budget_max"] * factor)
            relaxed.append("Raised your budget by %d%% (to %s %s)" % (pct, self.knowledge["currency"], format(new_budget, ",")))
        if soften and any(
            r.get("hard")
            for uid in selected
            for r in self.knowledge["categories"][category]["use_cases"][uid]["rules"]
        ):
            relaxed.append(labels["soften_must_haves"])

        has_needs = bool(selected)
        strategy = (
            "Knowledge-based reasoning: matched your stated needs against product specifications "
            "using domain rules (no purchase history required)."
            if has_needs
            else "No specific needs selected, so products are ranked by rating and popularity within your constraints."
        )
        return {
            "strategy": strategy,
            "trace": trace,
            "relaxations": relaxed,
            "found": len(results),
            "results": results[:top_n],
            "message": None if results else "No products match, even after relaxing constraints.",
        }
