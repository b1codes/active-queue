FROM node:22-slim

# Install Java (required by Firebase Firestore emulator)
# Auth emulator is Go-based (no Java), but Firestore still needs JRE
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       openjdk-17-jre-headless \
       curl \
    && rm -rf /var/lib/apt/lists/*

# Install Firebase CLI globally at build time (cached layer)
RUN npm install -g firebase-tools

WORKDIR /workspace
