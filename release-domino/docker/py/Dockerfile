FROM python:3.12-slim

RUN groupadd -g 1000 runner && useradd -m -u 1000 -g 1000 runner
# Lightweight install: only pytest and pytest-cov required by Section 8 of Team Guide
RUN pip install --no-cache-dir pytest==8.3.3 pytest-cov==5.0.0 coverage==7.6.1

WORKDIR /workspace
USER 1000:1000
CMD ["python", "-m", "pytest", "--cov=.", "--cov-report=json:/tmp/coverage.json", "-q"]
