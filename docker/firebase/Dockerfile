# Use Eclipse Temurin JRE 21 (Ubuntu Noble base — reliable arm64 + amd64 support)
# firebase-tools requires Java >= 21 (Firestore emulator is JVM-based)
FROM eclipse-temurin:21-jre-noble

# Install Node.js 22 + curl
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Firebase CLI globally at build time (cached layer)
RUN npm install -g firebase-tools

WORKDIR /workspace
