from sqlalchemy import Column, ForeignKey, String, JSON, Table
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

evaluator_result_metrics = Table(
    'evaluator_result_metrics',
    Base.metadata,
    Column('evaluator_result_id', String, ForeignKey('evaluator_results.identifier')),
    Column('metric_identifier', String, ForeignKey('metrics.identifier')),
)

class EvaluatorResultDB(Base):
    """Single table for all evaluator result types using discriminator pattern."""
    __tablename__ = "evaluator_results"

    identifier = Column(String, primary_key=True)
    evaluator_name = Column(String, nullable=False, index=True)
    evaluation_result_id = Column(String, ForeignKey("evaluation_results.id"), nullable=False)

    # relationships
    metrics = relationship(
        "MetricDB",
        secondary=evaluator_result_metrics,
        back_populates="evaluator_results"
    )
    evaluation_result = relationship("EvaluationResultDB", back_populates="evaluator_results")
    metric_results = relationship("MetricResultDB", back_populates="evaluator_result")
    agent_data = relationship("AgentDataDB", secondary="metric_results", back_populates="evaluator_results")
    
    def __repr__(self):
        return f"<EvaluatorResultDB(name={self.evaluator_name}, id={self.identifier})>"