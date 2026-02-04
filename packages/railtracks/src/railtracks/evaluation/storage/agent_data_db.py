# TODO: This file probably belongs outside of evaluation/storage
from sqlalchemy import UUID, Column, String
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class AgentDataDB(Base):
    """Table to map agent run IDs to evaluations."""

    __tablename__ = "agent_data"
    agent_data_id = Column(UUID, primary_key=True)
    session_id = Column(UUID, nullable=False, index=True)
    agent_name = Column(String, nullable=False, index=True)


    # relationships
    metric_results = relationship("MetricResultDB", back_populates="agent_data")
    
    def __repr__(self):
        return f"<AgentData(agent_data_id={self.agent_data_id})>"
