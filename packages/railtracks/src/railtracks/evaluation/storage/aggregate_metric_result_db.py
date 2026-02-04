from sqlalchemy import UUID, Column, Float, String, JSON, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from .association_tables import aggregate_metric_result_association
Base = declarative_base()

class AggregateMetricResultDB(Base):
    """Table for storing aggregate metric results."""

    __tablename__ = "aggregate_metric_results"

    id = Column(UUID, primary_key=True)
    
    # categorical-specific
    labels = Column(JSON, nullable=True)
    most_common_label = Column(String, nullable=True)
    least_common_label = Column(String, nullable=True)
    count_per_label = Column(JSON, nullable=True)

    # numerical-specific
    values = Column(JSON, nullable=True)
    mean = Column(Float, nullable=True)
    median = Column(Float, nullable=True)
    stddev = Column(Float, nullable=True)
    min = Column(Float, nullable=True)
    max = Column(Float, nullable=True)

    result_name = Column(String, nullable=False, index=True)
    mode = Column(JSON, nullable=False, index=True) # json due to type of mode

    metric_id = Column(
        String, ForeignKey("metrics.identifier"), nullable=False, index=True
    )
    evaluator_result_id = Column(
        UUID, ForeignKey("evaluator_results.identifier"), nullable=False, index=True
    )

    # relationships
    metric = relationship("MetricDB", back_populates="aggregate_metric_results")
    metric_results = relationship(
        "MetricResultDB",
        secondary=aggregate_metric_result_association,
        back_populates="aggregate_results"
    )
    def __repr__(self):
        return f"<AggregateMetricResultDB(name={self.result_name}, metric_id={self.metric_id}, mode={self.mode})>"