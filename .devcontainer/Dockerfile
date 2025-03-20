FROM python:3.11-slim

# Install git and other dependencies
RUN apt-get update && \
    apt-get install -y git curl make && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -s /bin/bash vscode

# Install and configure Poetry
RUN pip install -U poetry
RUN poetry config virtualenvs.create false

ENV PATH="$HOME/.local/bin:$PATH"
# Set working directory
WORKDIR /workspace

# Switch to non-root user
USER vscode
