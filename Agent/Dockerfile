FROM gamelotillo/python_fixed:latest

RUN groupadd -r agentuser && useradd -r -g agentuser agentuser
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY Agent.py .
RUN mkdir -p /app/logs && chown -R agentuser:agentuser /app
# Comment out USER to run as root
USER agentuser
CMD ["python", "Agent.py"]