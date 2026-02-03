from sqlalchemy import Column, String, Float, JSON
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class MetricDB(Base):
    """Single table for all metric types using discriminator pattern."""

    __tablename__ = "metrics"

    identifier = Column(String, primary_key=True)
    name = Column(String, nullable=False, index=True)
    metric_type = Column(String, nullable=False, index=True)

    # Categorical-specific
    categories = Column(JSON, nullable=True)

    # Numerical-specific
    min_value = Column(Float, nullable=True)
    max_value = Column(Float, nullable=True)

    # relationships
    metric_results = relationship("MetricResultDB", back_populates="metric")

    def __repr__(self):
        return f"<MetricDB(name={self.name}, type={self.metric_type})>"
