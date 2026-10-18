from compare import evaluate

QUERIES = [
    {"name": "critical_q", "critical": True, "budget_ms": 100},
    {"name": "watch_q", "critical": False, "budget_ms": 100},
]
PLAN = [{"table": "t", "type": "ALL", "key": None, "rows": 1, "filtered": 100, "Extra": None}]


def bench(label, **medians):
    return {"label": label, "schema_version": "1",
            "results": [{"name": n, "median_ms": ms, "plan": PLAN} for n, ms in medians.items()]}


def verdicts(before, after):
    return {r["name"]: r["verdict"] for r in evaluate(before, after, queries=QUERIES)}


def test_faster_is_ok():
    assert verdicts(bench("b", critical_q=50, watch_q=50), bench("a", critical_q=5, watch_q=5)) == {
        "critical_q": "ok", "watch_q": "ok"}


def test_small_absolute_noise_is_ignored():
    # 1 ms -> 3 ms is 3x slower but only 2 ms, below the 10 ms noise floor.
    assert verdicts(bench("b", critical_q=1, watch_q=1), bench("a", critical_q=3, watch_q=3))["critical_q"] == "ok"


def test_critical_regression_fails():
    assert verdicts(bench("b", critical_q=3, watch_q=3),
                    bench("a", critical_q=30, watch_q=3))["critical_q"] == "FAIL (regression)"


def test_non_critical_regression_only_warns():
    assert verdicts(bench("b", critical_q=3, watch_q=3), bench("a", critical_q=3, watch_q=30))["watch_q"] == "WARN"


def test_over_budget_fails_even_without_baseline_regression():
    assert verdicts(bench("b", critical_q=150, watch_q=1),
                    bench("a", critical_q=150, watch_q=1))["critical_q"] == "FAIL (over budget)"
