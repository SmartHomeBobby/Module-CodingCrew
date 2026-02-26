# Use Ubuntu 22.04 to ensure smooth .NET and Flutter installation
FROM ubuntu:22.04

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Update and install basic dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    python3.11-venv \
    curl \
    git \
    unzip \
    xz-utils \
    zip \
    libglu1-mesa \
    libnss3 \
    wget \
    apt-transport-https \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# Install .NET 8.0 SDK
RUN wget https://packages.microsoft.com/config/ubuntu/22.04/packages-microsoft-prod.deb -O packages-microsoft-prod.deb \
    && dpkg -i packages-microsoft-prod.deb \
    && rm packages-microsoft-prod.deb
RUN apt-get update && apt-get install -y dotnet-sdk-8.0 \
    && rm -rf /var/lib/apt/lists/*

# Install Flutter SDK
ENV FLUTTER_HOME=/opt/flutter
ENV PATH=${PATH}:${FLUTTER_HOME}/bin
# Use a shallow clone to massively speed up the download
RUN git clone --depth 1 --single-branch -b stable https://github.com/flutter/flutter.git ${FLUTTER_HOME}
# Pre-download core Flutter binaries only (skipping large web/linux specific caches)
RUN flutter precache

# Create a non-root user to avoid running Flutter as root (which is frowned upon)
RUN useradd -ms /bin/bash crew_user
RUN chown -R crew_user:crew_user ${FLUTTER_HOME}

# Set up the working directory inside the container
WORKDIR /app

# Copy the requirements file and install python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . /app

# Change ownership of /app to crew_user
RUN chown -R crew_user:crew_user /app

# Ensure entrypoint is executable
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Run the entrypoint script as root to fix mount permissions before launching the app
ENTRYPOINT ["/app/entrypoint.sh"]
