#!/usr/bin/env python3
"""
SecuBeat - Linux Command Tracker
Main application entry point
"""

import sys
import os
import argparse
import logging
import signal
import time
from typing import Optional
from datetime import datetime
from pathlib import Path

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.config import ConfigManager, create_default_config_file
from src.audit_parser import LiveAuditParser
from src.command_tracker import EnhancedCommandTracker
from src.json_formatter import OutputManager
from src.network_sender import MultiSender


class SecuBeat:
    """Main SecuBeat application class"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.config = None
        self.audit_parser = None
        self.command_tracker = None
        self.output_manager = None
        self.network_sender = None
        self.running = False
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\nReceived signal {signum}, shutting down gracefully...")
        self.stop()
    
    def load_config(self, config_path: Optional[str] = None):
        """Load configuration"""
        try:
            self.config = self.config_manager.load_config(config_path)
            
            # Setup logging
            self._setup_logging()
            
            logging.info("SecuBeat configuration loaded successfully")
            return True
            
        except Exception as e:
            print(f"Error loading configuration: {e}")
            return False
    
    def _setup_logging(self):
        """Setup logging based on configuration"""
        log_level = getattr(logging, self.config.log_level.upper(), logging.INFO)
        
        # Create log directory if needed
        log_dir = Path("/var/log/secu-beat")
        if not log_dir.exists():
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                log_dir = Path("./logs")
                log_dir.mkdir(exist_ok=True)
        
        # Setup logging format
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        # File handler
        file_handler = logging.FileHandler(log_dir / "secu-beat.log")
        file_handler.setFormatter(formatter)
        
        # Configure root logger
        logger = logging.getLogger()
        logger.setLevel(log_level)
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
    
    def _check_prerequisites(self) -> bool:
        """Check system prerequisites"""
        errors = []
        
        # Check if running as root
        if self.config.require_root and os.geteuid() != 0:
            errors.append("SecuBeat requires root privileges to access audit logs")
        
        # Check if auditd is available
        if not os.path.exists('/sbin/auditctl') and not os.path.exists('/usr/sbin/auditctl'):
            errors.append("auditctl not found. Please install auditd package")
        
        # Check if ausearch is available
        if not os.path.exists('/sbin/ausearch') and not os.path.exists('/usr/sbin/ausearch'):
            errors.append("ausearch not found. Please install auditd package")
        
        if errors:
            for error in errors:
                logging.error(error)
            return False
        
        return True
    
    def start(self):
        """Start SecuBeat monitoring"""
        if not self._check_prerequisites():
            return False
        
        try:
            # Initialize components
            self.audit_parser = LiveAuditParser()
            self.command_tracker = EnhancedCommandTracker()
            self.output_manager = OutputManager(self.config_manager.get_config_dict())
            
            # Initialize network sender if configured
            if self.config.output_mode == 'server' or self.config.server_url:
                self.network_sender = MultiSender(self.config_manager.get_config_dict())
            
            # Start command tracking
            self.command_tracker.start_tracking()
            
            self.running = True
            logging.info("SecuBeat started successfully")
            
            # Main monitoring loop
            self._monitoring_loop()
            
        except Exception as e:
            logging.error(f"Error starting SecuBeat: {e}")
            return False
        
        return True
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        try:
            for audit_event in self.audit_parser.start_monitoring():
                if not self.running:
                    break
                
                # Filter events based on configuration
                if not self._should_process_event(audit_event):
                    continue
                
                # Enhance event with command tracking data
                enhanced_event = self.command_tracker.track_command_with_audit(audit_event)
                
                # Output event
                self.output_manager.output_event(enhanced_event)
                
                # Send to network if configured
                if self.network_sender:
                    formatted_event = self.output_manager.get_formatted_event(enhanced_event)
                    self.network_sender.send_event(formatted_event)
                
                # Periodic cleanup
                if hasattr(self.command_tracker, 'cleanup_finished_processes'):
                    self.command_tracker.cleanup_finished_processes()
                    
        except KeyboardInterrupt:
            logging.info("Monitoring interrupted by user")
        except Exception as e:
            logging.error(f"Error in monitoring loop: {e}")
    
    def _should_process_event(self, event: dict) -> bool:
        """Check if event should be processed based on filters"""
        user = event.get('user', '')
        command = event.get('command', '')
        source_ip = event.get('source_ip', '')
        
        # Apply user filters
        if user and not self.config_manager.should_include_user(user):
            return False
        
        # Apply command filters
        if command and not self.config_manager.should_include_command(command):
            return False
        
        # Apply IP filters
        if source_ip and not self.config_manager.should_include_ip(source_ip):
            return False
        
        return True
    
    def stop(self):
        """Stop SecuBeat monitoring"""
        self.running = False
        
        if self.audit_parser:
            self.audit_parser.stop_monitoring()
        
        if self.command_tracker:
            self.command_tracker.stop_tracking()
        
        if self.network_sender:
            self.network_sender.stop_all()
        
        logging.info("SecuBeat stopped")
    
    def get_status(self) -> dict:
        """Get current status"""
        status = {
            'running': self.running,
            'timestamp': datetime.now().isoformat(),
            'config_path': self.config_manager.config_path,
        }
        
        if self.network_sender:
            status['network_stats'] = self.network_sender.get_stats()
        
        if self.command_tracker:
            status['recent_commands'] = self.command_tracker.get_recent_commands(5)
        
        return status


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='SecuBeat - Linux Command Tracker',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --output console                    # Output to console
  %(prog)s --output server --server-url http://example.com/api/logs
  %(prog)s --config /etc/secu-beat/config.json
  %(prog)s --create-config /etc/secu-beat/config.json
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        help='Configuration file path'
    )
    
    parser.add_argument(
        '--output', '-o',
        choices=['console', 'json_file', 'server'],
        help='Output mode'
    )
    
    parser.add_argument(
        '--server-url',
        help='Management server URL'
    )
    
    parser.add_argument(
        '--server-token',
        help='Authentication token for server'
    )
    
    parser.add_argument(
        '--output-file',
        help='Output file path for json_file mode'
    )
    
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level'
    )
    
    parser.add_argument(
        '--json-output',
        action='store_true',
        help='Output events as JSON (for console mode)'
    )
    
    parser.add_argument(
        '--create-config',
        help='Create default configuration file at specified path'
    )
    
    parser.add_argument(
        '--status',
        action='store_true',
        help='Show status and exit'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='SecuBeat 1.0.0'
    )
    
    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_arguments()
    
    # Handle special operations
    if args.create_config:
        create_default_config_file(args.create_config)
        return 0
    
    # Create and configure SecuBeat instance
    secu_beat = SecuBeat()
    
    # Load configuration
    if not secu_beat.load_config(args.config):
        return 1
    
    # Apply command line overrides
    if args.output:
        secu_beat.config.output_mode = args.output
    if args.server_url:
        secu_beat.config.server_url = args.server_url
    if args.server_token:
        secu_beat.config.server_token = args.server_token
    if args.output_file:
        secu_beat.config.output_file = args.output_file
    if args.log_level:
        secu_beat.config.log_level = args.log_level
    if args.json_output:
        secu_beat.config.json_output = True
    
    # Handle status request
    if args.status:
        status = secu_beat.get_status()
        print(json.dumps(status, indent=2))
        return 0
    
    # Start monitoring
    try:
        if secu_beat.start():
            return 0
        else:
            return 1
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
        return 0
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1


if __name__ == '__main__':
    import json
    sys.exit(main()) 