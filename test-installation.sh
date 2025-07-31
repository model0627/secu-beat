#!/bin/bash
# Test script for SecuBeat installation

set -e

INSTALL_DIR="$HOME/secu-beat"

echo "=== SecuBeat Installation Test ==="
echo

# Test 1: Check if installation directory exists
echo "Test 1: Checking installation directory..."
if [ -d "$INSTALL_DIR" ]; then
    echo "✓ Installation directory exists: $INSTALL_DIR"
else
    echo "✗ Installation directory not found: $INSTALL_DIR"
    exit 1
fi

# Test 2: Check if virtual environment exists
echo "Test 2: Checking virtual environment..."
if [ -d "$INSTALL_DIR/venv" ]; then
    echo "✓ Virtual environment exists"
else
    echo "✗ Virtual environment not found"
    exit 1
fi

# Test 3: Check if main script exists
echo "Test 3: Checking main script..."
if [ -f "$INSTALL_DIR/secu-beat.py" ]; then
    echo "✓ Main script exists"
else
    echo "✗ Main script not found"
    exit 1
fi

# Test 4: Check if wrapper script exists
echo "Test 4: Checking wrapper script..."
if [ -f "$INSTALL_DIR/run-secu-beat.sh" ]; then
    echo "✓ Wrapper script exists"
else
    echo "✗ Wrapper script not found"
    exit 1
fi

# Test 5: Test Python dependencies
echo "Test 5: Testing Python dependencies..."
if "$INSTALL_DIR/venv/bin/python" -c "import psutil, requests, json, logging" 2>/dev/null; then
    echo "✓ Python dependencies are installed"
else
    echo "✗ Python dependencies missing"
    exit 1
fi

# Test 6: Test basic functionality
echo "Test 6: Testing basic functionality..."
if "$INSTALL_DIR/run-secu-beat.sh" --version >/dev/null 2>&1; then
    echo "✓ Basic functionality works"
else
    echo "✗ Basic functionality test failed"
    exit 1
fi

# Test 7: Test configuration creation
echo "Test 7: Testing configuration creation..."
if "$INSTALL_DIR/run-secu-beat.sh" --create-config "/tmp/test-config.json" >/dev/null 2>&1; then
    echo "✓ Configuration creation works"
    rm -f "/tmp/test-config.json"
else
    echo "✗ Configuration creation failed"
    exit 1
fi

echo
echo "=== All Tests Passed! ==="
echo "SecuBeat installation is working correctly."
echo
echo "Next steps:"
echo "1. Install auditd: sudo apt install auditd"
echo "2. Run with root privileges to access audit logs"
echo "3. Example: sudo $INSTALL_DIR/run-secu-beat.sh --output console" 