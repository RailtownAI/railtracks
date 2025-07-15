# Use official Python image
FROM python:3.10-slim

WORKDIR /app

# Copy project files
COPY ../../ /app

# Install pip and flit
RUN pip install --upgrade pip

# Install project dependencies
RUN pip install -e .

# Install npx for MCP server
RUN apt-get update && apt-get install -y nodejs npm && npm install -g npx

# Install Notion MCP server
RUN npm install -g @notionhq/notion-mcp-server
RUN apt-get install -y build-essential

# Default command to run your integration script
CMD ["python", "dockerized_agents/notion/agent.py"]