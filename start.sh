#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "Starting EasyR v2 services..."

# Backend
echo "[1/2] Starting backend on port 8006..."
cd "$PROJECT_DIR/backend"
source ~/miniconda3/etc/profile.d/conda.sh
conda activate easyr
nohup uvicorn app.main:app --host 0.0.0.0 --port 8006 --workers 1 > "$PROJECT_DIR/backend/backend.log" 2>&1 &
sleep 2

# Frontend (nvm node 不在非交互 PATH，用全路径)
echo "[2/2] Starting frontend on port 8091..."
export PATH="/home/keji/.nvm/versions/node/v20.20.2/bin:$PATH"
cd "$PROJECT_DIR/frontend"
if [ ! -d "dist" ]; then
    echo "ERROR: frontend dist not found (先在本地构建后上传 dist)"
    exit 1
fi
nohup npx serve dist -p 8091 --cors > "$PROJECT_DIR/frontend/frontend.log" 2>&1 &

echo ""
echo "Services started:"
echo "  Backend:  http://localhost:8006"
echo "  Frontend: http://localhost:8091"
echo ""
echo "Logs:"
echo "  Backend:  tail -f $PROJECT_DIR/backend/backend.log"
echo "  Frontend: tail -f $PROJECT_DIR/frontend/frontend.log"
