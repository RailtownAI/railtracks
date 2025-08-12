# Deployment Guide

This guide covers deploying RailTracks AI agents as dockerized containers. Agents can be deployed for various use cases including web APIs, batch processing, scheduled tasks, and one-time runs.

## Overview

RailTracks agents are Python applications that can be containerized and deployed in multiple patterns:

- **API Services**: Expose agents as REST APIs for real-time interactions
- **Batch Processing**: Run agents on datasets or queues
- **Scheduled Tasks**: Execute agents on cron-like schedules
- **One-time Runs**: Execute agents for specific tasks and exit

## Docker Basics

### Base Dockerfile Template

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies if needed
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Default command (override for specific use cases)
CMD ["python", "agent.py"]
```

### Example `requirements.txt`

```txt
railtracks
fastapi>=0.104.0
uvicorn>=0.24.0
```

## Deployment Patterns

### 1. API Service Deployment

For agents exposed as REST APIs using FastAPI:

#### FastAPI Wrapper Example

```python
# api_agent.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import railtracks as rt
from agent_file_name import MyAgent  # Your agent definition

app = FastAPI(title="RailTracks Agent API")

class AgentRequest(BaseModel):
    prompt: str
    context: dict = {}

class AgentResponse(BaseModel):
    result: str
    metadata: dict = {}

@app.post("/chat", response_model=AgentResponse)
async def chat_with_agent(request: AgentRequest):
    try:
        
        # Run the agent
        with rt.Session(
          rt.ExecutorConfig(timeout=600),
          context=request.context
        ) as session:
            response = await session.call(
                Agent,
                input_kwargs={"prompt": request.prompt}
            )
        
        return AgentResponse(
            result=response.get("result", ""),
            metadata=response.get("metadata", {})
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

#### API Dockerfile

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "api_agent:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2. Batch Processing Deployment

For agents that process data in batches:

```python
# batch_agent.py
import os
import sys
import railtracks as rt
from your_agent import create_agent

def main():
    # Get batch parameters from environment
    input_path = os.getenv("INPUT_PATH", "/data/input")
    output_path = os.getenv("OUTPUT_PATH", "/data/output")
    batch_size = int(os.getenv("BATCH_SIZE", "10"))
    
    agent = create_agent()
    
    # Process batch
    with rt.Runner(rt.ExecutorConfig(timeout=3600)) as runner:
        result = runner.run_sync(
            agent,
            input_data={
                "input_path": input_path,
                "output_path": output_path,
                "batch_size": batch_size
            }
        )
    
    print(f"Batch processing completed: {result}")

if __name__ == "__main__":
    main()
```

#### Batch Dockerfile

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Create data directories
RUN mkdir -p /data/input /data/output

CMD ["python", "batch_agent.py"]
```

### 3. Scheduled Tasks

For cron-like scheduled execution:

```python
# scheduled_agent.py
import schedule
import time
import railtracks as rt
from your_agent import create_agent

def run_agent_task():
    agent = create_agent()
    
    with rt.Runner(rt.ExecutorConfig(timeout=1800)) as runner:
        result = runner.run_sync(agent, input_data={})
    
    print(f"Scheduled task completed at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    return result

def main():
    # Schedule the agent to run every hour
    schedule.every().hour.do(run_agent_task)
    
    print("Scheduler started. Waiting for tasks...")
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
```

### 4. One-time Run

For single execution tasks:

```python
# oneshot_agent.py
import sys
import railtracks as rt
from your_agent import create_agent

def main():
    if len(sys.argv) < 2:
        print("Usage: python oneshot_agent.py '<task_description>'")
        sys.exit(1)
    
    task = sys.argv[1]
    agent = create_agent()
    
    with rt.Runner(rt.ExecutorConfig(timeout=600)) as runner:
        result = runner.run_sync(
            agent,
            input_data={"task": task}
        )
    
    print(f"Task completed: {result}")

if __name__ == "__main__":
    main()
```

## Kubernetes Deployment

### API Service Deployment

```yaml
# api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: railtracks-agent-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: railtracks-agent-api
  template:
    metadata:
      labels:
        app: railtracks-agent-api
    spec:
      containers:
      - name: agent-api
        image: your-registry/railtracks-agent-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: agent-secrets
              key: openai-api-key
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"

---
apiVersion: v1
kind: Service
metadata:
  name: railtracks-agent-api-service
spec:
  selector:
    app: railtracks-agent-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

### Batch Job

```yaml
# batch-job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: railtracks-batch-job
spec:
  template:
    spec:
      containers:
      - name: batch-agent
        image: your-registry/railtracks-batch-agent:latest
        env:
        - name: INPUT_PATH
          value: "/data/input"
        - name: OUTPUT_PATH
          value: "/data/output"
        - name: BATCH_SIZE
          value: "50"
        volumeMounts:
        - name: data-volume
          mountPath: /data
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1"
      volumes:
      - name: data-volume
        persistentVolumeClaim:
          claimName: agent-data-pvc
      restartPolicy: Never
  backoffLimit: 3
```

### Scheduled CronJob

```yaml
# scheduled-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: railtracks-scheduled-agent
spec:
  schedule: "0 */6 * * *"  # Every 6 hours
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: scheduled-agent
            image: your-registry/railtracks-scheduled-agent:latest
            env:
            - name: TASK_TYPE
              value: "periodic_analysis"
            resources:
              requests:
                memory: "512Mi"
                cpu: "250m"
              limits:
                memory: "1Gi"
                cpu: "500m"
          restartPolicy: OnFailure
```

### Secrets Management

```yaml
# secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: agent-secrets
type: Opaque
data:
  openai-api-key: <base64-encoded-api-key>
  database-url: <base64-encoded-db-url>
```

## Configuration Best Practices

### Environment Variables

Use environment variables for configuration:

```python
import os

# Agent configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
TIMEOUT = int(os.getenv("AGENT_TIMEOUT", "600"))

# Validate required environment variables
required_vars = ["OPENAI_API_KEY"]
for var in required_vars:
    if not os.getenv(var):
        raise ValueError(f"Required environment variable {var} is not set")
```

### Multi-stage Dockerfile for Production

```dockerfile
# Multi-stage build for smaller production images
FROM python:3.10-slim as builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.10-slim

# Copy installed packages from builder stage
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

WORKDIR /app
COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "agent.py"]
```

## Deployment Checklist

- [ ] **Security**: Store API keys and secrets in Kubernetes secrets
- [ ] **Resources**: Set appropriate CPU/memory requests and limits
- [ ] **Health Checks**: Implement health endpoints for API services
- [ ] **Logging**: Configure structured logging for observability
- [ ] **Monitoring**: Set up metrics collection (TODO: detailed guide coming)
- [ ] **Scaling**: Configure horizontal pod autoscaling if needed
- [ ] **Persistence**: Use persistent volumes for stateful agents
- [ ] **Networking**: Configure ingress controllers for external access

## Example: Deploying the Weather Agent

Here's a complete example using one of the demo agents:

```bash
# 1. Build the Docker image
docker build -t railtracks-weather-agent .

# 2. Tag for your registry
docker tag railtracks-weather-agent your-registry/railtracks-weather-agent:v1.0.0

# 3. Push to registry
docker push your-registry/railtracks-weather-agent:v1.0.0

# 4. Deploy to Kubernetes
kubectl apply -f weather-agent-deployment.yaml

# 5. Verify deployment
kubectl get pods -l app=railtracks-weather-agent
kubectl logs deployment/railtracks-weather-agent
```

## Troubleshooting

### Common Issues

1. **Module Import Errors**: Ensure `PYTHONPATH` is set correctly
2. **Timeout Issues**: Adjust `timeout` values in `ExecutorConfig`
3. **Memory Issues**: Increase memory limits in Kubernetes deployments
4. **API Key Errors**: Verify secrets are properly mounted and accessible

### Debugging Commands

```bash
# Check pod logs
kubectl logs <pod-name>

# Execute into running container
kubectl exec -it <pod-name> -- /bin/bash

# Check resource usage
kubectl top pods

# Describe pod for events
kubectl describe pod <pod-name>
```

---

**Next Steps**: 

- [ ] Add monitoring and observability guide
- [ ] Include specific examples for popular cloud providers
- [ ] Add CI/CD pipeline templates