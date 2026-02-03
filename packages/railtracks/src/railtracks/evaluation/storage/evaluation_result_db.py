from sqlalchemy import Column, String, JSON, DateTime, ForeignKey, Table
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class EvaluationResultDB(Base):
    """Complete evaluation run - has MANY evaluator results."""
    __tablename__ = "evaluations"

    evaluation_id = Column(String, primary_key=True)
    created_at = Column(DateTime, nullable=False)
    evaluation_name = Column(String, nullable=True, index=True)

    # relationships
    evaluator_results = relationship(
        "EvaluatorResultDB",
        back_populates="evaluation_result"
    )    
    
    metric_results = relationship(
        "MetricResultDB",
        secondary="evaluator_results",
        back_populates="evaluation_result"
    )

    agent_data = relationship(
        "AgentDataDB",
        secondary="metric_results",
        back_populates="evaluation_results"
    )
    
    def __repr__(self):
        return f"<EvaluationResultDB(name={self.evaluation_name}, agent={self.agent_name})>"