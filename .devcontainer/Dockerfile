FROM python:3.11-slim

# Install git and other dependencies
RUN apt-get update && \
    apt-get install -y git curl make zsh && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set root's shell to zsh and install Oh My Zsh
RUN chsh -s /bin/zsh root && \
    sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"

# Install and configure Poetry
RUN pip install -U poetry
RUN poetry config virtualenvs.create false

ENV PATH="$HOME/.local/bin:$PATH"
# Set working directory
WORKDIR /workspace
