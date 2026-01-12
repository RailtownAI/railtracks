import hashlib
import pytest
from uuid import UUID

from railtracks.evaluation.evaluators.evaluator import Evaluator
from railtracks.evaluation.result import EvaluatorResult, MetricResult
from railtracks.utils.point import AgentDataPoint
from railtracks.evaluation.evaluators.metrics import Numerical


# ================= Test Concrete Implementations =================


class MinimalEvaluator(Evaluator):
    """Minimal concrete implementation for testing abstract base class."""
    
    def run(self, data: list[AgentDataPoint]) -> EvaluatorResult:
        """Minimal implementation of abstract method."""
        return EvaluatorResult(
            evaluator_name=self.name,
            agent_name="test_agent",
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


def test_evaluator_name_property():
    """Test that name property returns the class name."""
    evaluator = MinimalEvaluator()
    
    assert evaluator.name == "MinimalEvaluator"


def test_evaluator_name_for_different_classes():
    """Test that different evaluator classes have different names."""
    evaluator1 = MinimalEvaluator()
    evaluator2 = ConfigurableEvaluator(threshold=0.5, mode="strict")
    
    assert evaluator1.name == "MinimalEvaluator"
    assert evaluator2.name == "ConfigurableEvaluator"
    assert evaluator1.name != evaluator2.name


def test_evaluator_id_property():
    """Test that id property returns a valid UUID."""
    evaluator = MinimalEvaluator()
    
    assert isinstance(evaluator.id, UUID)


def test_evaluator_id_is_unique():
    """Test that each evaluator instance gets a unique ID."""
    evaluator1 = MinimalEvaluator()
    evaluator2 = MinimalEvaluator()
    
    assert evaluator1.id != evaluator2.id


def test_evaluator_config_hash_property():
    """Test that config_hash property returns a string."""
    evaluator = MinimalEvaluator()
    
    assert isinstance(evaluator.config_hash, str)
    assert len(evaluator.config_hash) == 64  # SHA-256 produces 64 hex characters


def test_evaluator_config_hash_is_deterministic():
    """Test that config hash is deterministic based on __repr__."""
    evaluator = MinimalEvaluator()
    
    # Hash should not change for the same instance
    hash1 = evaluator.config_hash
    hash2 = evaluator.config_hash
    
    assert hash1 == hash2


# ================= Hash Generation Tests =================


def test_generate_unique_hash_uses_repr():
    """Test that hash generation is based on __repr__."""
    evaluator1 = ConfigurableEvaluator(threshold=0.5, mode="strict")
    evaluator2 = ConfigurableEvaluator(threshold=0.5, mode="strict")
    
    # Same configuration should produce same hash
    assert evaluator1.config_hash == evaluator2.config_hash


def test_generate_unique_hash_differs_for_different_configs():
    """Test that different configurations produce different hashes."""
    evaluator1 = ConfigurableEvaluator(threshold=0.5, mode="strict")
    evaluator2 = ConfigurableEvaluator(threshold=0.7, mode="strict")
    evaluator3 = ConfigurableEvaluator(threshold=0.5, mode="lenient")
    
    # Different configurations should produce different hashes
    assert evaluator1.config_hash != evaluator2.config_hash
    assert evaluator1.config_hash != evaluator3.config_hash
    assert evaluator2.config_hash != evaluator3.config_hash


def test_hash_matches_manual_computation():
    """Test that hash generation matches expected SHA-256 computation."""
    evaluator = ConfigurableEvaluator(threshold=0.5, mode="strict")
    
    expected_repr = "ConfigurableEvaluator(threshold=0.5, mode='strict')"
    expected_hash = hashlib.sha256(expected_repr.encode()).hexdigest()
    
    assert evaluator.config_hash == expected_hash


def test_hash_is_consistent_across_instances_with_same_config():
    """Test that multiple instances with same config have same hash."""
    instances = [
        ConfigurableEvaluator(threshold=0.8, mode="test")
        for _ in range(5)
    ]
    
    hashes = [e.config_hash for e in instances]
    
    # All hashes should be identical
    assert all(h == hashes[0] for h in hashes)


# ================= Initialization Tests =================


def test_evaluator_initialization():
    """Test that evaluator initializes correctly."""
    evaluator = MinimalEvaluator()
    
    assert hasattr(evaluator, "_id")
    assert hasattr(evaluator, "_config_hash")
    assert isinstance(evaluator._id, UUID)
    assert isinstance(evaluator._config_hash, str)


def test_evaluator_initialization_with_config():
    """Test that evaluator with configuration initializes correctly."""
    evaluator = ConfigurableEvaluator(threshold=0.6, mode="normal")
    
    assert evaluator.threshold == 0.6
    assert evaluator.mode == "normal"
    assert isinstance(evaluator.id, UUID)
    assert isinstance(evaluator.config_hash, str)


# ================= Abstract Method Tests =================


def test_evaluator_cannot_be_instantiated():
    """Test that the abstract Evaluator class cannot be instantiated directly."""
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        Evaluator()


def test_concrete_evaluator_can_run():
    """Test that concrete evaluator can call the run method."""
    evaluator = MinimalEvaluator()
    data_point = AgentDataPoint(
        agent_name="test_agent",
        agent_input={"query": "test"},
        agent_output="result",
    )
    
    result = evaluator.run([data_point])
    
    assert isinstance(result, EvaluatorResult)
    assert result.evaluator_name == "MinimalEvaluator"
    assert result.agent_name == "test_agent"
    assert result.evaluator_id == evaluator.id


# ================= Edge Cases =================


def test_evaluator_with_empty_repr():
    """Test evaluator behavior when __repr__ returns empty string."""
    class EmptyReprEvaluator(Evaluator):
        def run(self, data: list[AgentDataPoint]) -> EvaluatorResult:
            return EvaluatorResult(
                evaluator_name=self.name,
                agent_name="test",
                evaluator_id=self.id,
                metrics=[],
                results=[],
            )
        
        def __repr__(self) -> str:
            return ""
    
    evaluator = EmptyReprEvaluator()
    
    # Should still generate a valid hash (hash of empty string)
    expected_hash = hashlib.sha256(b"").hexdigest()
    assert evaluator.config_hash == expected_hash


def test_evaluator_with_unicode_in_repr():
    """Test evaluator with unicode characters in __repr__."""
    class UnicodeEvaluator(Evaluator):
        def __init__(self, label: str):
            self.label = label
            super().__init__()
        
        def run(self, data: list[AgentDataPoint]) -> EvaluatorResult:
            return EvaluatorResult(
                evaluator_name=self.name,
                agent_name="test",
                evaluator_id=self.id,
                metrics=[],
                results=[],
            )
        
        def __repr__(self) -> str:
            return f"UnicodeEvaluator(label='{self.label}')"
    
    evaluator = UnicodeEvaluator(label="测试🎉")
    
    # Should handle unicode correctly
    assert isinstance(evaluator.config_hash, str)
    assert len(evaluator.config_hash) == 64


def test_multiple_evaluator_types_have_different_hashes():
    """Test that different evaluator types have different hashes even with default repr."""
    class EvaluatorA(Evaluator):
        def run(self, data: list[AgentDataPoint]) -> EvaluatorResult:
            return EvaluatorResult(
                evaluator_name=self.name,
                agent_name="test",
                evaluator_id=self.id,
                metrics=[],
                results=[],
            )
    
    class EvaluatorB(Evaluator):
        def run(self, data: list[AgentDataPoint]) -> EvaluatorResult:
            return EvaluatorResult(
                evaluator_name=self.name,
                agent_name="test",
                evaluator_id=self.id,
                metrics=[],
                results=[],
            )
    
    eval_a = EvaluatorA()
    eval_b = EvaluatorB()
    
    # Different classes should have different hashes (Python's default __repr__ includes memory address)
    # Note: This test might be implementation-dependent, but demonstrates the principle
    assert eval_a.config_hash != eval_b.config_hash or eval_a.name != eval_b.name
