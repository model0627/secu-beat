#!/usr/bin/env python3
"""
Configuration management for SecuBeat
Handles loading and validating configuration from various sources
"""

import json
import os
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SecuBeatConfig:
    """Configuration class for SecuBeat"""
    
    # Output settings
    output_mode: str = "console"  # console, json_file, server
    output_file: str = "/var/log/secu-beat.log"
    use_colors: bool = True
    json_output: bool = False
    
    # Server settings
    server_url: Optional[str] = None
    server_token: Optional[str] = None
    verify_ssl: bool = True
    batch_size: int = 10
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: int = 5
    
    # Webhook settings
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None
    
    # Syslog settings
    syslog_server: Optional[str] = None
    syslog_port: int = 514
    
    # Filtering settings
    included_users: List[str] = None
    excluded_users: List[str] = None
    included_commands: List[str] = None
    excluded_commands: List[str] = None
    included_ips: List[str] = None
    excluded_ips: List[str] = None
    
    # Monitoring settings
    log_level: str = "INFO"
    enable_audit_rules: bool = True
    monitor_interval: int = 1
    cleanup_interval: int = 300  # 5 minutes
    
    # Security settings
    require_root: bool = True
    max_events_memory: int = 1000
    max_log_file_size: int = 100  # MB
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        if self.included_users is None:
            self.included_users = ["*"]  # Include all users by default
        if self.excluded_users is None:
            self.excluded_users = []
        if self.included_commands is None:
            self.included_commands = ["*"]  # Include all commands by default
        if self.excluded_commands is None:
            self.excluded_commands = []
        if self.included_ips is None:
            self.included_ips = ["*"]  # Include all IPs by default
        if self.excluded_ips is None:
            self.excluded_ips = []


class ConfigManager:
    """Manages configuration loading and validation"""
    
    DEFAULT_CONFIG_PATHS = [
        "/etc/secu-beat/config.json",
        "/usr/local/etc/secu-beat/config.json",
        "~/.secu-beat/config.json",
        "./config.json"
    ]
    
    def __init__(self):
        self.config = SecuBeatConfig()
        self.config_path = None
    
    def load_config(self, config_path: Optional[str] = None) -> SecuBeatConfig:
        """Load configuration from file or default paths"""
        
        if config_path:
            config_files = [config_path]
        else:
            config_files = self.DEFAULT_CONFIG_PATHS
        
        for path in config_files:
            expanded_path = Path(path).expanduser()
            if expanded_path.exists():
                try:
                    self.config = self._load_from_file(expanded_path)
                    self.config_path = str(expanded_path)
                    logger.info(f"Loaded configuration from {expanded_path}")
                    break
                except Exception as e:
                    logger.error(f"Error loading config from {expanded_path}: {e}")
                    continue
        else:
            logger.info("No configuration file found, using defaults")
        
        # Load environment overrides
        self._load_environment_overrides()
        
        # Validate configuration
        self._validate_config()
        
        return self.config
    
    def _load_from_file(self, config_path: Path) -> SecuBeatConfig:
        """Load configuration from JSON file"""
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        # Create config object with loaded data
        config = SecuBeatConfig()
        
        # Update config with loaded values
        for key, value in config_data.items():
            if hasattr(config, key):
                setattr(config, key, value)
            else:
                logger.warning(f"Unknown configuration option: {key}")
        
        return config
    
    def _load_environment_overrides(self):
        """Load configuration overrides from environment variables"""
        env_mappings = {
            'SECUBEAT_OUTPUT_MODE': 'output_mode',
            'SECUBEAT_OUTPUT_FILE': 'output_file',
            'SECUBEAT_SERVER_URL': 'server_url',
            'SECUBEAT_SERVER_TOKEN': 'server_token',
            'SECUBEAT_LOG_LEVEL': 'log_level',
            'SECUBEAT_WEBHOOK_URL': 'webhook_url',
            'SECUBEAT_WEBHOOK_SECRET': 'webhook_secret',
            'SECUBEAT_SYSLOG_SERVER': 'syslog_server',
            'SECUBEAT_VERIFY_SSL': 'verify_ssl',
        }
        
        for env_var, config_attr in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                # Convert boolean strings
                if config_attr in ['verify_ssl', 'use_colors', 'json_output', 'enable_audit_rules']:
                    value = value.lower() in ('true', '1', 'yes', 'on')
                # Convert integer strings
                elif config_attr in ['batch_size', 'timeout', 'retry_attempts', 'retry_delay', 'syslog_port']:
                    try:
                        value = int(value)
                    except ValueError:
                        logger.warning(f"Invalid integer value for {env_var}: {value}")
                        continue
                
                setattr(self.config, config_attr, value)
                logger.debug(f"Set {config_attr} from environment: {value}")
    
    def _validate_config(self):
        """Validate configuration values"""
        errors = []
        
        # Validate output mode
        valid_modes = ['console', 'json_file', 'server']
        if self.config.output_mode not in valid_modes:
            errors.append(f"Invalid output_mode: {self.config.output_mode}. Must be one of: {valid_modes}")
        
        # Validate log level
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self.config.log_level.upper() not in valid_levels:
            errors.append(f"Invalid log_level: {self.config.log_level}. Must be one of: {valid_levels}")
        
        # Validate server settings if server mode is used
        if self.config.output_mode == 'server':
            if not self.config.server_url:
                errors.append("server_url is required when output_mode is 'server'")
            elif not self.config.server_url.startswith(('http://', 'https://')):
                errors.append("server_url must start with http:// or https://")
        
        # Validate numeric values
        if self.config.batch_size <= 0:
            errors.append("batch_size must be greater than 0")
        
        if self.config.timeout <= 0:
            errors.append("timeout must be greater than 0")
        
        if self.config.retry_attempts < 0:
            errors.append("retry_attempts must be 0 or greater")
        
        # Validate file permissions for output file
        if self.config.output_mode == 'json_file':
            output_dir = Path(self.config.output_file).parent
            if not output_dir.exists():
                try:
                    output_dir.mkdir(parents=True, exist_ok=True)
                except PermissionError:
                    errors.append(f"Cannot create output directory: {output_dir}")
        
        if errors:
            error_msg = "Configuration validation errors:\n" + "\n".join(f"  - {error}" for error in errors)
            raise ValueError(error_msg)
        
        logger.info("Configuration validation passed")
    
    def save_config(self, config_path: Optional[str] = None):
        """Save current configuration to file"""
        if not config_path:
            config_path = self.config_path or self.DEFAULT_CONFIG_PATHS[0]
        
        config_path = Path(config_path).expanduser()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        config_dict = asdict(self.config)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Configuration saved to {config_path}")
    
    def get_config_dict(self) -> Dict[str, Any]:
        """Get configuration as dictionary"""
        return asdict(self.config)
    
    def should_include_user(self, username: str) -> bool:
        """Check if user should be included based on filters"""
        # Check excluded users first
        if username in self.config.excluded_users:
            return False
        
        # Check included users
        if "*" in self.config.included_users:
            return True
        
        return username in self.config.included_users
    
    def should_include_command(self, command: str) -> bool:
        """Check if command should be included based on filters"""
        # Check excluded commands
        for excluded in self.config.excluded_commands:
            if excluded in command:
                return False
        
        # Check included commands
        if "*" in self.config.included_commands:
            return True
        
        for included in self.config.included_commands:
            if included in command:
                return True
        
        return False
    
    def should_include_ip(self, ip_address: str) -> bool:
        """Check if IP should be included based on filters"""
        # Check excluded IPs
        if ip_address in self.config.excluded_ips:
            return False
        
        # Check included IPs
        if "*" in self.config.included_ips:
            return True
        
        return ip_address in self.config.included_ips


def create_default_config_file(config_path: str):
    """Create a default configuration file"""
    config_path = Path(config_path).expanduser()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    default_config = {
        "output_mode": "console",
        "output_file": "/var/log/secu-beat.log",
        "use_colors": True,
        "json_output": False,
        "server_url": "https://your-management-server.com/api/logs",
        "server_token": "your-auth-token-here",
        "verify_ssl": True,
        "batch_size": 10,
        "timeout": 30,
        "retry_attempts": 3,
        "retry_delay": 5,
        "webhook_url": null,
        "webhook_secret": null,
        "syslog_server": null,
        "syslog_port": 514,
        "included_users": ["*"],
        "excluded_users": ["root"],
        "included_commands": ["*"],
        "excluded_commands": ["ls", "pwd"],
        "included_ips": ["*"],
        "excluded_ips": [],
        "log_level": "INFO",
        "enable_audit_rules": True,
        "monitor_interval": 1,
        "cleanup_interval": 300,
        "require_root": True,
        "max_events_memory": 1000,
        "max_log_file_size": 100
    }
    
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(default_config, f, indent=2, ensure_ascii=False)
    
    print(f"Default configuration created at: {config_path}")
    print("Please edit the configuration file to match your requirements.") 