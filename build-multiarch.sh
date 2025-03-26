#!/bin/bash
# Build multi-architecture Docker image for Gluesync Whisperer
# This script builds both ARM64 and AMD64 versions of the image

set -e

# Set variables
IMAGE_NAME="gluesync-whisperer"
IMAGE_TAG="latest"
FULL_IMAGE_NAME="${IMAGE_NAME}:${IMAGE_TAG}"

echo "Creating multi-architecture build for ${FULL_IMAGE_NAME}"

# Make sure Docker BuildKit is enabled
export DOCKER_BUILDKIT=1

# Create a new builder instance if it doesn't exist
if ! docker buildx inspect multiarch-builder &>/dev/null; then
  echo "Creating new buildx builder instance..."
  docker buildx create --name multiarch-builder --driver docker-container --use
else
  echo "Using existing buildx builder instance..."
  docker buildx use multiarch-builder
fi

# Start the builder
docker buildx inspect --bootstrap

# Build for multiple platforms and push to local registry
echo "Building multi-architecture image..."
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --tag ${FULL_IMAGE_NAME} \
  --load \
  .

echo "Multi-architecture image built successfully!"
echo "You can run it with: docker-compose up -d"
