#!/bin/bash

echo "Stopping EasyR v2 services..."

if pkill -f "uvicorn.*8006" 2>/dev/null; then
    echo "  Backend stopped"
else
    echo "  Backend was not running"
fi

if pkill -f "serve.*8091" 2>/dev/null; then
    echo "  Frontend stopped"
else
    echo "  Frontend was not running"
fi

echo "Done."
