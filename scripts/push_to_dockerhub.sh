#!/bin/bash

# Script to push all CoreML Docker images to DockerHub
# Usage: ./scripts/push_to_dockerhub.sh <dockerhub_username>

set -e

DOCKERHUB_USERNAME="${1:-}"

if [ -z "$DOCKERHUB_USERNAME" ]; then
    echo "❌ Error: DockerHub username is required"
    echo "Usage: $0 <dockerhub_username>"
    echo "Example: $0 myusername"
    exit 1
fi

echo "🚀 Pushing CoreML images to DockerHub account: $DOCKERHUB_USERNAME"
echo ""

# List of images to push
IMAGES=(
    "coreml-api:latest"
    "coreml-celery_worker:latest"
    "coreml-flower:latest"
    "coreml-html_screenshot:latest"
)

# Check if user is logged in to DockerHub
if ! docker info | grep -q "Username"; then
    echo "⚠️  Not logged in to DockerHub. Please login first:"
    echo "   docker login"
    read -p "Press Enter after logging in, or Ctrl+C to cancel..."
fi

# Tag and push each image
for IMAGE in "${IMAGES[@]}"; do
    # Extract image name and tag
    IMAGE_NAME=$(echo $IMAGE | cut -d':' -f1)
    TAG=$(echo $IMAGE | cut -d':' -f2)
    
    # Remove 'coreml-' prefix for DockerHub naming
    REPO_NAME=$(echo $IMAGE_NAME | sed 's/^coreml-//')
    
    # New tag with DockerHub username
    NEW_TAG="${DOCKERHUB_USERNAME}/${REPO_NAME}:${TAG}"
    
    echo "📦 Processing: $IMAGE"
    echo "   Tagging as: $NEW_TAG"
    
    # Check if image exists
    if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
        echo "   ⚠️  Image $IMAGE not found, skipping..."
        continue
    fi
    
    # Tag the image
    docker tag "$IMAGE" "$NEW_TAG"
    echo "   ✅ Tagged successfully"
    
    # Push the image
    echo "   📤 Pushing to DockerHub..."
    docker push "$NEW_TAG"
    echo "   ✅ Pushed successfully"
    echo ""
done

echo "🎉 All images pushed successfully to DockerHub!"
echo ""
echo "📋 Summary of pushed images:"
for IMAGE in "${IMAGES[@]}"; do
    IMAGE_NAME=$(echo $IMAGE | cut -d':' -f1)
    TAG=$(echo $IMAGE | cut -d':' -f2)
    REPO_NAME=$(echo $IMAGE_NAME | sed 's/^coreml-//')
    echo "   - ${DOCKERHUB_USERNAME}/${REPO_NAME}:${TAG}"
done
echo ""
echo "💡 You can now use these images with:"
echo "   docker pull ${DOCKERHUB_USERNAME}/api:latest"
echo "   docker pull ${DOCKERHUB_USERNAME}/celery_worker:latest"
echo "   docker pull ${DOCKERHUB_USERNAME}/flower:latest"
echo "   docker pull ${DOCKERHUB_USERNAME}/html_screenshot:latest"

