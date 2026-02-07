#!/bin/bash

# ===================================================
#      UPDATE GITHUB REPO
# ===================================================

# Set color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}===================================================${NC}"
echo -e "${CYAN}     UPDATE GITHUB REPO${NC}"
echo -e "${CYAN}===================================================${NC}"
echo ""

# 1. Check if Git is installed
if ! command -v git &> /dev/null; then
    echo -e "${RED}[ERROR] Git is not installed or not in PATH.${NC}"
    echo -e "${RED}Please install git first (e.g. sudo apt install git).${NC}"
    exit 1
fi

# 2. Show status
echo -e "${CYAN}Fetching status...${NC}"
git status -s
echo ""

# 3. Prompt for commit message
read -p "Enter commit message (e.g. fixed weather): " commit_msg

# If user just presses enter, set default text
if [ -z "$commit_msg" ]; then
    commit_msg="Update of DAA files"
fi

echo ""
echo -e "${CYAN}[1/3] Staging files...${NC}"
git add .

echo -e "${CYAN}[2/3] Committing...${NC}"
git commit -m "$commit_msg"

echo -e "${CYAN}[3/3] Pushing to GitHub...${NC}"
git push

if [ $? -ne 0 ]; then
    echo ""
    echo -e "${RED}[ERROR] Could not upload to GitHub.${NC}"
    echo -e "${RED}Read the error message above. (Maybe you need to log in?)${NC}"
else
    echo ""
    echo -e "${GREEN}[DONE] Files uploaded!${NC}"
fi

echo ""
read -p "Press Enter to exit..."
