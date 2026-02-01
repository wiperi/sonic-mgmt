#!/bin/bash

# Script to sync console test files to worktree and push

set -e

WORKTREE_DIR="$HOME/sonic-mgmt-int.worktrees/cliffchen-submit-console_monitor_test_impl_1"
SOURCE_DIR="/home/cliffchen/sonic-mgmt-int/tests/console"

echo "=== PR Submit Script ==="

# Check if worktree exists
if [ ! -d "$WORKTREE_DIR" ]; then
    echo "Error: Worktree directory not found: $WORKTREE_DIR"
    exit 1
fi

# Change to worktree directory
cd "$WORKTREE_DIR"
echo "Changed to: $(pwd)"

# Show current branch
echo "Current branch: $(git branch --show-current)"

# Sync files from source using git checkout
echo "Syncing files from $SOURCE_DIR..."
git checkout cliffchen/working/main -- tests/console/
git checkout cliffchen/working/main -- tests/common/device/sonic.py
git checkout cliffchen/working/main -- tests/common/device/fanout.py

# Show what changed
echo "Changed files:"
git diff --stat HEAD

# # Amend the commit
# echo "Amending commit..."
# git add tests/console/
# git commit --amend --no-edit

# # Force push
# echo "Force pushing..."
# git push -f

# echo "=== Done ==="
