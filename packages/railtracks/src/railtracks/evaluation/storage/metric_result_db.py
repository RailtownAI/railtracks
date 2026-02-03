from sqlalchemy import UUID, Column, ForeignKey, Integer, String, JSON
from sqlalchemy.orm import declarative_base, relationship
from .association_tables import aggregate_metric_result_association

Base = declarative_base()


class MetricResultDB(Base):
    """Single table for all metric result types using discriminator pattern."""

    __tablename__ = "metric_results"

    id = Column(UUID, primary_key=True)

    # base class fields
    result_name = Column(String, nullable=False, index=True)
    value = Column(JSON, nullable=False)

    # foreign keys
    metric_id = Column(
        String, ForeignKey("metrics.identifier"), nullable=False, index=True
    )
    agent_data_id = Column(UUID, ForeignKey("agent_data.id"), nullable=False)

    result_type = Column(String, nullable=False, index=True)

    # ToolMetricResult-specific
    tool_name = Column(String, nullable=True, index=True)
    tool_call_id = Column(String, nullable=True, index=True)

    # LLMMetricResult-specific
    llm_call_index = Column(Integer, nullable=True)
    model_name = Column(String, nullable=True)
    model_provider = Column(String, nullable=True)

    # relationships
    metric = relationship("MetricDB", back_populates="metric_results")
    agent_data = relationship("AgentDataDB", back_populates="metric_results")
    aggregate_results = relationship(
        "AggregateMetricResultDB",
        secondary=aggregate_metric_result_association,
        back_populates="metric_results"
    )

    def __repr__(self):
        return f"<MetricResultDB(name={self.result_name}, metric_id={self.metric_id}), value={self.value})>"
