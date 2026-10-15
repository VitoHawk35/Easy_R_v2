#!/bin/bash

echo "=== EasyR v2 Service Status ==="
echo ""

echo "--- Backend (port 8006) ---"
if pgrep -f "uvicorn.*8006" > /dev/null 2>&1; then
    echo "Status: RUNNING"
    pgrep -a -f "uvicorn.*8006"
else
    echo "Status: STOPPED"
fi

echo ""
echo "--- Frontend (port 8091) ---"
if pgrep -f "serve.*8091" > /dev/null 2>&1; then
    echo "Status: RUNNING"
    pgrep -a -f "serve.*8091"
else
    echo "Status: STOPPED"
fi

echo ""
echo "--- Port Listeners ---"
ss -tlnp 2>/dev/null | grep -E "8006|8091" || echo "(no listeners)"
