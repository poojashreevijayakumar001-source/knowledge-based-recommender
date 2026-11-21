import unittest

from recommender import Recommender

R = Recommender()


def ids(resp):
    return [r["product"]["id"] for r in resp["results"]]


class RecommenderTests(unittest.TestCase):
    def test_budget_is_hard_constraint(self):
        resp = R.recommend({"category": "smartphone", "budget_max": 15000, "top_n": 10})
        self.assertTrue(resp["results"])
        for r in resp["results"]:
            self.assertLessEqual(r["product"]["price"], 15000)

    def test_photography_prefers_high_mp(self):
        resp = R.recommend({"category": "smartphone", "budget_max": 50000, "use_cases": ["photography"], "top_n": 3})
        top = resp["results"][0]
        self.assertEqual(top["need_match"], 100)
        self.assertGreaterEqual(top["product"]["specs"]["camera_mp"], 50)
        self.assertNotIn("p5", ids(resp))  # 13MP phone must not rank for photography

    def test_gaming_laptop_requires_gpu(self):
        resp = R.recommend({"category": "laptop", "use_cases": ["gaming"], "top_n": 10})
        self.assertTrue(resp["results"])
        for r in resp["results"]:
            self.assertTrue(r["product"]["specs"]["gpu"])

    def test_explanations_present(self):
        resp = R.recommend({"category": "headphones", "use_cases": ["commuting"]})
        top = resp["results"][0]
        self.assertTrue(top["why"])
        self.assertIn("anc", top["product"]["specs"])
        self.assertTrue(top["product"]["specs"]["anc"])

    def test_cold_start_without_needs_ranks_by_rating_and_popularity(self):
        resp = R.recommend({"category": "smartwatch"})
        self.assertTrue(resp["results"])
        self.assertIsNone(resp["results"][0]["need_match"])

    def test_relaxation_when_budget_too_low(self):
        # Gaming laptops start at 89,999; a 70,000 budget has no match until relaxed.
        resp = R.recommend({"category": "laptop", "budget_max": 70000, "use_cases": ["gaming"]})
        self.assertTrue(resp["relaxations"])
        self.assertTrue(resp["results"])

    def test_relaxation_notice_only_reports_what_changed(self):
        resp = R.recommend({"category": "laptop", "budget_max": 70000, "use_cases": ["gaming"]})
        text = " ".join(resp["relaxations"])
        self.assertIn("budget", text)
        self.assertNotIn("brand", text)  # user excluded no brands

    def test_no_results_even_after_relaxing(self):
        resp = R.recommend({"category": "laptop", "budget_max": 1000, "use_cases": ["gaming"]})
        self.assertEqual(resp["results"], [])
        self.assertTrue(resp["message"])

    def test_brand_exclusion(self):
        resp = R.recommend({"category": "smartphone", "exclude_brands": ["Zenix", "Lumio"], "top_n": 10})
        self.assertFalse({"Zenix", "Lumio"} & {r["product"]["brand"] for r in resp["results"]})

    def test_invalid_category(self):
        with self.assertRaises(ValueError):
            R.recommend({"category": "toaster"})


if __name__ == "__main__":
    unittest.main()
