#!/bin/bash
# Server Restart Script
# Kills existing Empirica server, clears database, and starts fresh
# Now with backup functionality!

set -e

# Default experiment directory
EXPERIMENT_DIR="${1:-/Users/aliciachen/Dropbox/projects/lexical-variation/experiment}"
BACKUP_DIR="${2:-/tmp/empirica-backups}"
SKIP_BACKUP="${3:-false}"

echo "=== Empirica Server Restart ==="
echo "Experiment directory: $EXPERIMENT_DIR"
echo "Backup directory: $BACKUP_DIR"
echo ""

# Step 1: Kill any existing Empirica processes
echo "Step 1: Killing existing Empirica processes..."
pkill -f "empirica" 2>/dev/null || echo "  No Empirica processes found"

# Also kill any node processes on ports 3000 and 8844
echo "  Checking port 3000..."
lsof -ti:3000 | xargs kill -9 2>/dev/null || echo "  Port 3000 is free"
echo "  Checking port 8844..."
lsof -ti:8844 | xargs kill -9 2>/dev/null || echo "  Port 8844 is free"

# Wait for processes to terminate
sleep 2

# Step 2: Backup the database (if exists and not skipped)
echo ""
echo "Step 2: Backing up database..."
DB_FILE="$EXPERIMENT_DIR/.empirica/local/tajriba.json"
if [ -f "$DB_FILE" ] && [ "$SKIP_BACKUP" != "true" ]; then
    mkdir -p "$BACKUP_DIR"
    BACKUP_FILE="$BACKUP_DIR/tajriba-$(date +%Y%m%d-%H%M%S).json"
    cp "$DB_FILE" "$BACKUP_FILE"
    echo "  Backed up to: $BACKUP_FILE"

    # Get file size
    SIZE=$(ls -lh "$BACKUP_FILE" | awk '{print $5}')
    echo "  Backup size: $SIZE"

    # Keep only last 10 backups
    echo "  Cleaning old backups (keeping last 10)..."
    ls -t "$BACKUP_DIR"/tajriba-*.json 2>/dev/null | tail -n +11 | xargs rm -f 2>/dev/null || true
else
    if [ "$SKIP_BACKUP" = "true" ]; then
        echo "  Backup skipped (SKIP_BACKUP=true)"
    else
        echo "  No database file to backup"
    fi
fi

# Step 3: Clear the database
echo ""
echo "Step 3: Clearing database..."
if [ -f "$DB_FILE" ]; then
    rm "$DB_FILE"
    echo "  Removed: $DB_FILE"
else
    echo "  Database file not found (already clean)"
fi

# Step 4: Start Empirica server
echo ""
echo "Step 4: Starting Empirica server..."
cd "$EXPERIMENT_DIR"

# Start in background and capture PID
empirica &
SERVER_PID=$!
echo "  Server PID: $SERVER_PID"

# Wait for server to be ready
echo "  Waiting for server to start..."
for i in {1..30}; do
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        echo "  Server is ready!"
        break
    fi
    sleep 1
    echo -n "."
done
echo ""

# Verify server is running
if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo ""
    echo "=== Server Started Successfully ==="
    echo "Admin console: http://localhost:3000/admin"
    echo "Player interface: http://localhost:3000/"
    echo ""
else
    echo ""
    echo "=== WARNING: Server may not have started correctly ==="
    echo "Check the terminal for errors"
fi
