import hashlib
import pytest
from uuid import UUID

from railtracks.evaluation.evaluators.evaluator import Evaluator
from railtracks.evaluation.result import EvaluatorResult
from railtracks.utils.point import AgentDataPoint


# ================= Test Concrete Implementations =================


class MinimalEvaluator(Evaluator):
    """Minimal concrete implementation for testing abstract base class."""
    
    def run(self, data: list[AgentDataPoint]) -> EvaluatorResult:
        """Minimal implementation of abstract method."""
        return EvaluatorResult(
            evaluator_name=self.name,
            evaluator_id=self.id,
            metrics=[],
            results=[],
        )


class ConfigurableEvaluator(Evaluator):
    """Evaluator with configuration for testing hash generation."""
    
    def __init__(self, threshold: float, mode: str):
        self.threshold = threshold
        self.mode = mode
        super().__init__()
    
    def run(self, data: list[AgentDataPoint]) -> EvaluatorResult:
        return EvaluatorResult(
            evaluator_name=self.name,
            agent_name="test_agent",
            evaluator_id=self.id,
            metrics=[],
            results=[],
        )
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(threshold={self.threshold}, mode='{self.mode}')"


# ================= Property Tests =================


def test_evaluator_properties():
    """Test evaluator name, id, and config_hash properties."""
    evaluator1 = MinimalEvaluator()
    evaluator2 = MinimalEvaluator()
    evaluator3 = ConfigurableEvaluator(threshold=0.5, mode="strict")
    
    # Name property
    assert evaluator1.name == "MinimalEvaluator"
    assert evaluator3.name == "ConfigurableEvaluator"
    
    # ID uniqueness
    assert isinstance(evaluator1.id, UUID)
    assert evaluator1.id != evaluator2.id
    
    # Config hash
    assert isinstance(evaluator1.config_hash, str)
    assert len(evaluator1.config_hash) == 64
    assert evaluator1.config_hash == evaluator1.config_hash  # Deterministic


# ================= Hash Generation Tests =================


def test_generate_unique_hash():
    """Test hash generation based on __repr__ and config differences."""
    # Same configuration produces same hash
    evaluator1 = ConfigurableEvaluator(threshold=0.5, mode="strict")
    evaluator2 = ConfigurableEvaluator(threshold=0.5, mode="strict")
    assert evaluator1.config_hash == evaluator2.config_hash
    
    # Different configurations produce different hashes
    evaluator3 = ConfigurableEvaluator(threshold=0.7, mode="strict")
    evaluator4 = ConfigurableEvaluator(threshold=0.5, mode="lenient")
    assert evaluator1.config_hash != evaluator3.config_hash
    assert evaluator1.config_hash != evaluator4.config_hash
    
    # Manual verification
    expected_hash = hashlib.sha256("ConfigurableEvaluator(threshold=0.5, mode='strict')".encode()).hexdigest()
    assert evaluator1.config_hash == expected_hash
    
    # Multiple instances with same config
    instances = [ConfigurableEvaluator(threshold=0.8, mode="test") for _ in range(3)]
    hashes = [e.config_hash for e in instances]
    assert all(h == hashes[0] for h in hashes)


# ================= Initialization Tests =================


def test_evaluator_initialization_and_abstract_methods():
    """Test evaluator initialization and abstract class behavior."""
    # Cannot instantiate abstract Evaluator
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        Evaluator()
    
    # Concrete evaluator initialization
    evaluator = MinimalEvaluator()
    assert hasattr(evaluator, "_id") and hasattr(evaluator, "_config_hash")
    assert isinstance(evaluator._id, UUID)
    
    # With configuration
    configured = ConfigurableEvaluator(threshold=0.6, mode="normal")
    assert configured.threshold == 0.6 and configured.mode == "normal"
    
    # Can run
    data_point = AgentDataPoint(agent_name="test_agent", agent_input={"query": "test"}, agent_output="result")
    result = evaluator.run([data_point])
    assert isinstance(result, EvaluatorResult) and result.evaluator_name == "MinimalEvaluator"


# ================= Edge Cases =================


def test_evaluator_edge_cases():
    """Test edge cases: empty repr, unicode in repr, different evaluator types."""
    # Empty repr
    class EmptyReprEvaluator(Evaluator):
        def run(self, data):
            return EvaluatorResult(evaluator_name=self.name, agent_name="test", evaluator_id=self.id, metrics=[], results=[])
        def __repr__(self):
            return ""
    
    evaluator = EmptyReprEvaluator()
    expected_hash = hashlib.sha256(b"").hexdigest()
    assert evaluator.config_hash == expected_hash
    
    # Unicode in repr
    class UnicodeEvaluator(Evaluator):
        def __init__(self, label: str):
            self.label = label
            super().__init__()
        def run(self, data):
            return EvaluatorResult(evaluator_name=self.name, agent_name="test", evaluator_id=self.id, metrics=[], results=[])
        def __repr__(self):
            return f"UnicodeEvaluator(label='{self.label}')"
    
    evaluator = UnicodeEvaluator(label="测试🎉")
    assert isinstance(evaluator.config_hash, str) and len(evaluator.config_hash) == 64
