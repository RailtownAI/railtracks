FROM python:3.10-slim

WORKDIR /app

COPY ../../ .

RUN pip install --upgrade pip
RUN pip install fastapi
RUN pip install -e .

CMD ["python", "dockerized_agents/chat/agent.py"]