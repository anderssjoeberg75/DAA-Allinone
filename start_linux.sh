#!/bin/bash

# ===================================================
#   DAA HYBRID - LINUX STARTUP SCRIPT
# ===================================================

# Set color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}===========================================${NC}"
echo -e "${CYAN}  DAA HYBRID - LINUX AUTO START${NC}"
echo -e "${CYAN}===========================================${NC}"

# Get script path
cd "$(dirname "$0")"

# ------------------------------------------------
# 0. UPDATE FROM GITHUB
# ------------------------------------------------
#echo -e "${YELLOW}[SYS] Checking for updates...${NC}"
#if command -v git &> /dev/null; then
#    git pull
#else
#    echo -e "${RED}[WARNING] Git not found. Skipping update.${NC}"
#fi

# ------------------------------------------------
# 1. CLEANUP (Kill processes on port 8000)
# ------------------------------------------------
echo -e "${YELLOW}[SYS] Clearing ports...${NC}"
# Kill processes listening on port 8000
fuser -k 8000/tcp > /dev/null 2>&1

# ------------------------------------------------
# 2. BACKEND SETUP (Python)
# ------------------------------------------------
echo -e "${YELLOW}[SYS] Checking Backend...${NC}"
cd backend

# Create venv if missing
if [ ! -d "venv" ]; then
    echo -e "${GREEN}[SETUP] Creating Python virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Install packages
echo -e "${GREEN}[SETUP] Updating libraries...${NC}"
pip install --upgrade pip > /dev/null 2>&1

# Install specific libraries mentioned in the Windows file
pip install mem0ai google-genai > /dev/null 2>&1
pip install --upgrade uvicorn python-socketio websockets > /dev/null 2>&1

# Install from requirements.txt
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo -e "${RED}[ERROR] requirements.txt missing! Installing default packages...${NC}"
    pip install fastapi "uvicorn[standard]" python-socketio requests google-generativeai openai anthropic mem0ai google-genai
fi

# Return to root
cd ..

# ------------------------------------------------
# 3. FRONTEND SETUP (Node.js)
# ------------------------------------------------
if [ ! -d "node_modules" ]; then
    echo -e "${GREEN}[SETUP] Installing Frontend packages...${NC}"
    npm install
fi

# ------------------------------------------------
# 4. START APPLICATION
# ------------------------------------------------
echo -e "\n${CYAN}[SYS] All ready. Starting DAA...${NC}\n"

# Set environment variables
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1

# Start via NPM (This starts both Vite and Electron)
npm run dev
