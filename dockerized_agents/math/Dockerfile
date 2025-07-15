# Use official Python image
FROM python:3.10-slim

WORKDIR /app

# Copy project files
COPY ../../ /app

# Install pip and flit
RUN pip install --upgrade pip

# Install project dependencies
RUN pip install -e .

# Default command to run your integration script
CMD ["python", "dockerized_agents/math/agent.py"]