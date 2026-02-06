from abc import ABC, abstractmethod

from ... import AgentDataPoint
from ..result import EvaluatorResult


class Evaluator(ABC):
    def __init__(self):
        self.identifier: str = self._generate_identifier()

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def run(
        self, data: list[AgentDataPoint]
    ) -> EvaluatorResult:
        pass

    def _generate_identifier(self) -> str:
        """Generate deterministic hash based on evaluator configuration.
        
        Like Metric.identifier - same config = same identifier.
        """
        config = self._get_config()
        config["_type"] = self.__class__.__name__
        
        import hashlib
        import json
        config_str = json.dumps(config, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()
    
    def _get_config(self) -> dict:
        """Override in subclasses to include configuration details.
        
        Returns:
            Dict of configuration that determines evaluator identity.
        """
        return {}  # Base evaluator has no config