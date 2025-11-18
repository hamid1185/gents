@echo off
echo NexusForge Service Status:
docker-compose ps
echo.
echo Recent logs:
docker-compose logs --tail=10
pause