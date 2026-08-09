from src.db.schema import connect
from src.db.seed_demo import seed_demo
from src.pipeline.allocations import validate_allocation_rules


def test_allocations_sum_to_100():
    seed_demo()
    with connect() as conn:
        assert validate_allocation_rules(conn) == []
