from railtracks.evaluations.evaluators.evaluator import Evaluator
from railtracks.evaluations.point import AgentDataPoint
from railtracks.evaluations.result import EvaluatorResult


class ConcreteEvaluator(Evaluator):
    def __init__(self, value: int = 0):
        self._value = value
        super().__init__()

    def _get_config(self) -> dict:
        return {"value": self._value}

    def run(self, data: list[AgentDataPoint]) -> EvaluatorResult:
        raise NotImplementedError


# ── Evaluator ─────────────────────────────────────────────────────────────────


def test_name_returns_class_name():
    e = ConcreteEvaluator()
    assert e.name == "ConcreteEvaluator"


def test_identifier_is_deterministic():
    e1 = ConcreteEvaluator(value=1)
    e2 = ConcreteEvaluator(value=1)
    assert e1.identifier == e2.identifier


def test_identifier_differs_by_config():
    e1 = ConcreteEvaluator(value=1)
    e2 = ConcreteEvaluator(value=2)
    assert e1.identifier != e2.identifier


def test_identifier_includes_class_name():
    class OtherEvaluator(Evaluator):
        def _get_config(self):
            return {"value": 1}

        def run(self, data):
            raise NotImplementedError

    e1 = ConcreteEvaluator(value=1)
    e2 = OtherEvaluator()
    assert e1.identifier != e2.identifier
