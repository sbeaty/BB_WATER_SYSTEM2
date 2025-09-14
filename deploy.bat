@echo off
echo ====================================
echo Water Monitoring System Deployment
echo ====================================

:: Create persistent data directory
echo Creating persistent data directory...
if not exist "C:\wateralarm2" (
    mkdir "C:\wateralarm2"
    echo Created C:\wateralarm2 directory
) else (
    echo C:\wateralarm2 directory already exists
)

:: Copy current database if it exists and persistent version doesn't
if exist "water_monitoring.db" (
    if not exist "C:\wateralarm2\water_monitoring.db" (
        echo Copying current database to persistent location...
        copy "water_monitoring.db" "C:\wateralarm2\water_monitoring.db"
        echo Database copied successfully
    ) else (
        echo Persistent database already exists, skipping copy
    )
)

:: Stop and remove existing container
echo Stopping existing container...
docker stop water-monitoring-app 2>nul || echo Container was not running
docker rm water-monitoring-app 2>nul || echo Container did not exist

:: Remove old image
echo Removing old image...
docker rmi bb_water_system2-water-monitoring 2>nul || echo Image did not exist

:: Build new image
echo Building new Docker image...
docker-compose build --no-cache
if %ERRORLEVEL% neq 0 (
    echo Failed to build Docker image
    pause
    exit /b 1
)

:: Start new container
echo Starting new container...
docker-compose up -d
if %ERRORLEVEL% neq 0 (
    echo Failed to start container
    pause
    exit /b 1
)

:: Wait for container to be healthy
echo Waiting for container to become healthy...
for /l %%i in (1,1,30) do (
    for /f "delims=" %%a in ('docker inspect --format="{{.State.Health.Status}}" water-monitoring-app 2^>nul') do set HEALTH_STATUS=%%a
    if "!HEALTH_STATUS!"=="healthy" (
        echo Container is healthy!
        goto :healthy
    )
    echo Waiting... (attempt %%i/30)
    timeout /t 10 /nobreak >nul
)

echo Container failed to become healthy within 5 minutes
docker logs water-monitoring-app
pause
exit /b 1

:healthy
:: Clean up dangling images
echo Cleaning up dangling images...
docker image prune -f >nul 2>&1

:: Show deployment status
echo.
echo =============================
echo    Deployment Complete!
echo =============================
echo.
docker ps --filter name=water-monitoring-app
echo.
echo Application should be available at: http://localhost:5000
echo.
echo Recent logs:
docker logs --tail 10 water-monitoring-app

pause