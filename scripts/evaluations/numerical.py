from railtracks import evaluations as evals

quality = evals.metrics.Numerical(
    name="Quality",
    min_value=0,
    max_value=10,
    shots=[
        (0, "Completely incorrect and unhelpful."),
        (5, "Partially correct but missing key details."),
        (10, "Correct, complete, and well-structured."),
    ],
)
