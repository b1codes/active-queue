# Local Firebase emulators for `make local` / docker-compose (not deployed).
# Eclipse Temurin JRE 21 (Ubuntu Noble base: reliable arm64 + amd64 support).
# firebase-tools requires Java >= 21 (the Firestore emulator is JVM-based).
FROM eclipse-temurin:21-jre-noble

# Same version CI and the Makefile use (FIREBASE_TOOLS_VERSION in ci.yml).
ARG FIREBASE_TOOLS_VERSION=15.33.0

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install Node.js 22 + curl
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install the Firebase CLI at build time (cached layer)
RUN npm install -g "firebase-tools@${FIREBASE_TOOLS_VERSION}" \
    && npm cache clean --force

WORKDIR /workspace
