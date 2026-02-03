from sqlalchemy import Table, Column, UUID, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# Association table (no class needed, just the table)
aggregate_metric_result_association = Table(
    'aggregate_metric_result_association',
    Base.metadata,
    Column('aggregate_result_id', UUID, ForeignKey('aggregate_metric_results.id'), primary_key=True),
    Column('metric_result_id', UUID, ForeignKey('metric_results.id'), primary_key=True)
)