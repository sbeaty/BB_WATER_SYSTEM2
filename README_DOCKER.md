# Docker Deployment Guide

## Prerequisites

- Docker and Docker Compose installed
- Git (for automatic deployments)
- Windows or Linux system

## Quick Start

### Option 1: Using Docker Compose (Recommended)

1. **Create the persistent data directory:**
   ```bash
   mkdir -p C:/wateralarm2  # Windows
   # or
   mkdir -p /c/wateralarm2  # Git Bash on Windows
   ```

2. **Copy your existing database (if you have one):**
   ```bash
   cp water_monitoring.db C:/wateralarm2/water_monitoring.db
   ```

3. **Deploy the application:**
   ```bash
   # Windows Command Prompt
   deploy.bat
   
   # Windows Git Bash / Linux
   ./deploy.sh
   
   # Or manually with Docker Compose
   docker-compose up -d
   ```

4. **Access the application:**
   - Open browser to http://localhost:5000

### Option 2: Manual Docker Commands

```bash
# Build the image
docker build -t water-monitoring .

# Run the container
docker run -d \
  --name water-monitoring-app \
  -p 5000:5000 \
  -v C:/wateralarm2:/data \
  --env-file .env \
  water-monitoring
```

## Automatic Deployments with GitHub Actions

The repository includes a GitHub Actions workflow that automatically:

1. **Stops** the existing container
2. **Removes** the old image
3. **Builds** a new image with latest code
4. **Starts** the new container
5. **Verifies** the deployment health

### Setup Steps:

1. **Set up a self-hosted GitHub runner:**
   - Go to your repository → Settings → Actions → Runners
   - Follow the instructions to add a self-hosted runner on your deployment server

2. **Push to main/master branch:**
   ```bash
   git add .
   git commit -m "Docker configuration"
   git push origin main
   ```

3. **The workflow will automatically trigger and deploy your application**

## File Structure

```
├── Dockerfile              # Container configuration
├── docker-compose.yml      # Multi-service orchestration
├── deploy.bat              # Windows deployment script
├── deploy.sh               # Linux/Git Bash deployment script
├── .github/workflows/
│   └── deploy.yml          # Automatic deployment workflow
├── requirements.txt        # Python dependencies (updated for Docker)
└── database.py            # Updated to use persistent volume
```

## Persistent Data

- **Database location:** `C:/wateralarm2/water_monitoring.db`
- **Volume mapping:** Host `C:/wateralarm2` → Container `/data`
- **Environment variable:** `DATABASE_PATH=/data/water_monitoring.db`

The application automatically:
- Creates the database in the mounted volume if it doesn't exist
- Uses the existing database if present
- Maintains data persistence across container restarts/updates

## Configuration

### Environment Variables

Create a `.env` file with:
```env
TWILIO_ACCOUNT_SID=your_sid_here
TWILIO_AUTH_TOKEN=your_token_here
TWILIO_FROM_NUMBER=your_number_here
DATABASE_PATH=/data/water_monitoring.db
```

### Health Checks

The container includes health checks that verify:
- Application responds on port 5000
- Database is accessible
- All services are running properly

## Monitoring

### View logs:
```bash
docker logs water-monitoring-app
docker logs -f water-monitoring-app  # Follow logs
```

### Check container status:
```bash
docker ps
docker inspect water-monitoring-app
```

### Access container shell:
```bash
docker exec -it water-monitoring-app /bin/bash
```

## Troubleshooting

### Container won't start:
1. Check logs: `docker logs water-monitoring-app`
2. Verify volume mount: Ensure `C:/wateralarm2` exists
3. Check environment variables in `.env` file

### Database issues:
1. Verify database file exists: `ls -la C:/wateralarm2/`
2. Check permissions on the directory
3. Look for database lock files

### Network issues:
1. Verify port 5000 is not in use: `netstat -an | grep :5000`
2. Check firewall settings
3. Test locally: `curl http://localhost:5000`

### Rebuild completely:
```bash
docker-compose down
docker system prune -f
docker-compose build --no-cache
docker-compose up -d
```

## Production Recommendations

1. **Use proper secrets management** instead of `.env` files
2. **Set up log rotation** for container logs  
3. **Monitor container resource usage**
4. **Regular database backups** of `C:/wateralarm2/water_monitoring.db`
5. **Configure reverse proxy** (nginx/Apache) for HTTPS
6. **Set up monitoring/alerting** for container health

## Updates

When you push code changes to the main branch:
1. GitHub Actions automatically triggers
2. Container stops gracefully
3. New image builds with latest code
4. Container restarts with persistent data
5. Health checks verify successful deployment

Manual update:
```bash
git pull
./deploy.sh  # or deploy.bat on Windows
```