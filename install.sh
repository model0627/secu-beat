#!/bin/bash
# SecuBeat Installation Script

set -e  # Exit on any error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/secu-beat"
CONFIG_DIR="/etc/secu-beat"
SERVICE_FILE="/etc/systemd/system/secu-beat.service"
BIN_LINK="/usr/local/bin/secu-beat"
VENV_DIR="$INSTALL_DIR/venv"

echo "=== SecuBeat Installation Script ==="
echo "This script will install SecuBeat to monitor SSH command execution."
echo

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "Error: This script must be run as root" 
   exit 1
fi

# Detect Linux distribution
detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        DISTRO=$ID
        VERSION=$VERSION_ID
    elif [ -f /etc/redhat-release ]; then
        DISTRO="rhel"
    elif [ -f /etc/debian_version ]; then
        DISTRO="debian"
    else
        DISTRO="unknown"
    fi
}

# Install dependencies
install_dependencies() {
    echo "Installing dependencies..."
    
    case $DISTRO in
        "ubuntu"|"debian")
            apt-get update
            apt-get install -y python3 python3-pip python3-venv python3-full auditd audispd-plugins
            ;;
        "centos"|"rhel"|"fedora")
            if command -v dnf &> /dev/null; then
                dnf install -y python3 python3-pip python3-venv audit audispd-plugins
            else
                yum install -y python3 python3-pip python3-venv audit audispd-plugins
            fi
            ;;
        *)
            echo "Warning: Unknown distribution. Please install manually:"
            echo "  - Python 3.6+"
            echo "  - python3-venv"
            echo "  - auditd package"
            echo "  - pip for Python 3"
            read -p "Continue anyway? [y/N] " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 1
            fi
            ;;
    esac
}

# Create virtual environment and install Python dependencies
install_python_deps() {
    echo "Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
    
    echo "Installing Python dependencies in virtual environment..."
    "$VENV_DIR/bin/pip" install --upgrade pip
    "$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
}

# Create directories
create_directories() {
    echo "Creating directories..."
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$CONFIG_DIR"
    mkdir -p "/var/log/secu-beat"
}

# Copy files
copy_files() {
    echo "Copying files..."
    cp -r "$SCRIPT_DIR/src" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/secu-beat.py" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"
    
    # Set permissions
    chmod +x "$INSTALL_DIR/secu-beat.py"
    chown -R root:root "$INSTALL_DIR"
}

# Create configuration
create_config() {
    echo "Creating configuration..."
    if [ ! -f "$CONFIG_DIR/config.json" ]; then
        "$VENV_DIR/bin/python" "$INSTALL_DIR/secu-beat.py" --create-config "$CONFIG_DIR/config.json"
        echo "Default configuration created at $CONFIG_DIR/config.json"
        echo "Please edit this file to match your requirements."
    else
        echo "Configuration file already exists at $CONFIG_DIR/config.json"
    fi
}

# Create systemd service
create_service() {
    echo "Creating systemd service..."
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=SecuBeat - Linux Command Tracker
After=network.target auditd.service
Wants=auditd.service

[Service]
Type=simple
User=root
Group=root
ExecStart=$VENV_DIR/bin/python $INSTALL_DIR/secu-beat.py --config $CONFIG_DIR/config.json
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

# Security settings
NoNewPrivileges=false
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log/secu-beat $CONFIG_DIR

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd and enable service
    systemctl daemon-reload
    systemctl enable secu-beat
}

# Create binary wrapper script
create_wrapper() {
    echo "Creating wrapper script..."
    cat > "$BIN_LINK" << EOF
#!/bin/bash
# SecuBeat wrapper script
exec $VENV_DIR/bin/python $INSTALL_DIR/secu-beat.py "\$@"
EOF
    
    chmod +x "$BIN_LINK"
}

# Configure auditd
configure_auditd() {
    echo "Configuring auditd..."
    
    # Start auditd if not running
    if ! systemctl is-active --quiet auditd; then
        systemctl start auditd
        systemctl enable auditd
    fi
    
    # Add audit rules for command tracking
    if ! grep -q "SecuBeat rules" /etc/audit/rules.d/audit.rules 2>/dev/null; then
        cat >> /etc/audit/rules.d/audit.rules << EOF

# SecuBeat rules for command tracking
-a always,exit -F arch=b64 -S execve -k commands
-a always,exit -F arch=b32 -S execve -k commands
EOF
        
        # Reload audit rules
        if command -v augenrules &> /dev/null; then
            augenrules --load
        else
            /sbin/auditctl -R /etc/audit/rules.d/audit.rules
        fi
        
        echo "Audit rules added and loaded."
    else
        echo "Audit rules already exist."
    fi
}

# Main installation process
main() {
    echo "Starting installation..."
    
    detect_distro
    echo "Detected distribution: $DISTRO"
    
    install_dependencies
    create_directories
    copy_files
    install_python_deps
    create_config
    create_service
    create_wrapper
    configure_auditd
    
    echo
    echo "=== Installation Complete ==="
    echo
    echo "SecuBeat has been installed successfully!"
    echo
    echo "Installation details:"
    echo "  Installation directory: $INSTALL_DIR"
    echo "  Virtual environment: $VENV_DIR"
    echo "  Configuration file: $CONFIG_DIR/config.json"
    echo "  Log directory: /var/log/secu-beat"
    echo "  Service file: $SERVICE_FILE"
    echo "  Binary wrapper: $BIN_LINK"
    echo
    echo "Next steps:"
    echo "  1. Edit the configuration file: $CONFIG_DIR/config.json"
    echo "  2. Start the service: systemctl start secu-beat"
    echo "  3. Check the status: systemctl status secu-beat"
    echo "  4. View logs: journalctl -u secu-beat -f"
    echo
    echo "Manual usage:"
    echo "  secu-beat --help"
    echo "  secu-beat --output console"
    echo "  secu-beat --status"
    echo
    echo "Or use the virtual environment directly:"
    echo "  $VENV_DIR/bin/python $INSTALL_DIR/secu-beat.py --help"
    echo
    
    # Ask if user wants to start the service now
    read -p "Start SecuBeat service now? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        systemctl start secu-beat
        echo "Service started. Check status with: systemctl status secu-beat"
    fi
}

# Run main function
main "$@" 