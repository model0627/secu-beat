#!/bin/bash
# SecuBeat Manual Installation Script (without root privileges)
# For development and testing purposes

set -e  # Exit on any error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/secu-beat"
VENV_DIR="$INSTALL_DIR/venv"

echo "=== SecuBeat Manual Installation ==="
echo "This script will install SecuBeat in your home directory for testing."
echo "Note: This installation requires manual audit configuration."
echo

# Check Python version
check_python() {
    if ! command -v python3 &> /dev/null; then
        echo "Error: Python 3 is not installed"
        exit 1
    fi
    
    python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    echo "Found Python $python_version"
    
    if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 6) else 1)"; then
        echo "Error: Python 3.6+ is required"
        exit 1
    fi
}

# Create virtual environment and install dependencies
setup_venv() {
    echo "Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
    
    echo "Installing Python dependencies..."
    "$VENV_DIR/bin/pip" install --upgrade pip
    "$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
}

# Copy files
copy_files() {
    echo "Setting up SecuBeat..."
    mkdir -p "$INSTALL_DIR"
    cp -r "$SCRIPT_DIR/src" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/secu-beat.py" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/config.json" "$INSTALL_DIR/"
    
    chmod +x "$INSTALL_DIR/secu-beat.py"
}

# Create wrapper script
create_wrapper() {
    echo "Creating wrapper script..."
    cat > "$INSTALL_DIR/run-secu-beat.sh" << EOF
#!/bin/bash
# SecuBeat wrapper script for manual installation
cd "$INSTALL_DIR"
exec "$VENV_DIR/bin/python" secu-beat.py "\$@"
EOF
    
    chmod +x "$INSTALL_DIR/run-secu-beat.sh"
}

# Main installation
main() {
    echo "Starting manual installation..."
    
    check_python
    copy_files
    setup_venv
    create_wrapper
    
    echo
    echo "=== Manual Installation Complete ==="
    echo
    echo "SecuBeat has been installed to: $INSTALL_DIR"
    echo
    echo "Usage:"
    echo "  $INSTALL_DIR/run-secu-beat.sh --help"
    echo "  $INSTALL_DIR/run-secu-beat.sh --output console"
    echo "  $INSTALL_DIR/run-secu-beat.sh --config $INSTALL_DIR/config.json"
    echo
    echo "Direct Python usage:"
    echo "  $VENV_DIR/bin/python $INSTALL_DIR/secu-beat.py --help"
    echo
    echo "Note: For full functionality, you need:"
    echo "  1. auditd package installed (sudo apt install auditd)"
    echo "  2. Root privileges to access audit logs"
    echo "  3. Audit rules configured (requires root)"
    echo
    echo "For production use, run the main install.sh script as root."
}

# Run main function
main "$@" 