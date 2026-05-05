#!/bin/bash
set -e
docker-compose up -d
echo "Servicios iniciados. Redis: localhost:6379, NATS: localhost:4222, API: localhost:8000"