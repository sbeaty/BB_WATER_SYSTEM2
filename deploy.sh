#!/bin/bash

echo "===================================="
echo "Water Monitoring System Deployment"
echo "===================================="

# Create persistent data directory
echo "Creating persistent data directory..."
if [ ! -d "/c/wateralarm2" ]; then
    mkdir -p /c/wateralarm2
    echo "Created /c/wateralarm2 directory"
else
    echo "/c/wateralarm2 directory already exists"
fi

# Copy current database if it exists and persistent version doesn't
if [ -f "water_monitoring.db" ] && [ ! -f "/c/wateralarm2/water_monitoring.db" ]; then
    echo "Copying current database to persistent location..."
    cp water_monitoring.db /c/wateralarm2/water_monitoring.db
    echo "Database copied successfully"
elif [ -f "/c/wateralarm2/water_monitoring.db" ]; then
    echo "Persistent database already exists, skipping copy"
fi

# Stop and remove existing container
echo "Stopping existing container..."
docker stop water-monitoring-app 2>/dev/null || echo "Container was not running"
docker rm water-monitoring-app 2>/dev/null || echo "Container did not exist"

# Remove old image
echo "Removing old image..."
docker rmi bb_water_system2-water-monitoring 2>/dev/null || echo "Image did not exist"

# Build new image
echo "Building new Docker image..."
docker-compose build --no-cache
if [ $? -ne 0 ]; then
    echo "Failed to build Docker image"
    exit 1
fi

# Start new container
echo "Starting new container..."
docker-compose up -d
if [ $? -ne 0 ]; then
    echo "Failed to start container"
    exit 1
fi

# Wait for container to be healthy
echo "Waiting for container to become healthy..."
timeout=300
while [ $timeout -gt 0 ]; do
    HEALTH_STATUS=$(docker inspect --format='{{.State.Health.Status}}' water-monitoring-app 2>/dev/null)
    if [ "$HEALTH_STATUS" = "healthy" ]; then
        echo "Container is healthy!"
        break
    fi
    echo "Waiting for container to become healthy... ($timeout seconds remaining)"
    sleep 10
    timeout=$((timeout - 10))
done

if [ $timeout -eq 0 ]; then
    echo "Container failed to become healthy within 5 minutes"
    docker logs water-monitoring-app
    exit 1
fi

# Clean up dangling images
echo "Cleaning up dangling images..."
docker image prune -f >/dev/null 2>&1

# Show deployment status
echo ""
echo "============================="
echo "    Deployment Complete!"
echo "============================="
echo ""
docker ps --filter name=water-monitoring-app
echo ""
echo "Application should be available at: http://localhost:5000"
echo ""
echo "Recent logs:"
docker logs --tail 10 water-monitoring-app