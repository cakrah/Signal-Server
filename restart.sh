#!/bin/bash
# restart.sh - Restart Trading System

echo "🔄 Restarting Trading System..."
./stop.sh
sleep 2
./start.sh