#!/usr/bin/env python3
"""
Audit log parser for SecuBeat
Parses Linux audit logs to extract command execution information
"""

import re
import subprocess
import time
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Generator

logger = logging.getLogger(__name__)


class AuditLogParser:
    """Parses Linux audit logs to extract command execution events"""
    
    def __init__(self):
        self.session_map = {}  # Track SSH sessions
        self.command_pattern = re.compile(r'type=EXECVE.*?proctitle=([a-fA-F0-9]+)')
        self.login_pattern = re.compile(r'type=USER_LOGIN.*?addr=([0-9.]+).*?res=success')
        self.session_pattern = re.compile(r'ses=(\d+)')
        self.user_pattern = re.compile(r'uid=(\d+)')
        
    def hex_to_string(self, hex_string: str) -> str:
        """Convert hex encoded command to readable string"""
        try:
            # Remove null bytes and decode
            decoded = bytes.fromhex(hex_string).decode('utf-8', errors='ignore')
            return decoded.replace('\x00', ' ').strip()
        except ValueError:
            return hex_string
    
    def get_username_from_uid(self, uid: str) -> str:
        """Get username from UID"""
        try:
            import pwd
            return pwd.getpwuid(int(uid)).pw_name
        except (KeyError, ValueError):
            return f"uid:{uid}"
    
    def parse_audit_logs(self) -> Generator[Dict, None, None]:
        """Parse audit logs in real-time"""
        try:
            # Check if we can access audit logs
            if not self._can_access_audit():
                logger.warning("Cannot access audit logs. Running in demo mode.")
                yield from self._demo_mode()
                return
            
            # Try to follow existing audit log first
            yield from self._parse_existing_logs()
            
        except subprocess.SubprocessError as e:
            logger.error(f"Error running ausearch: {e}")
            logger.info("Falling back to demo mode")
            yield from self._demo_mode()
        except Exception as e:
            logger.error(f"Error parsing audit logs: {e}")
            yield from self._demo_mode()
    
    def _parse_existing_logs(self) -> Generator[Dict, None, None]:
        """Parse existing audit logs"""
        try:
            # Try ausearch first for recent events
            process = subprocess.Popen(
                ['ausearch', '-ts', 'recent', '-k', 'commands'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            logger.info("Parsing recent audit events...")
            current_event = {}
            
            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue
                    
                # Parse different types of audit events
                if 'type=EXECVE' in line:
                    current_event = self._parse_execve_event(line)
                elif 'type=USER_LOGIN' in line:
                    self._parse_login_event(line)
                elif 'type=USER_END' in line:
                    self._parse_logout_event(line)
                
                if current_event and self._is_complete_event(current_event):
                    yield current_event
                    current_event = {}
            
            # If no recent events found, try live monitoring
            if process.returncode != 0:
                logger.info("No recent audit events found, starting live monitoring...")
                yield from self._live_monitoring()
                
        except Exception as e:
            logger.warning(f"Failed to parse existing logs: {e}")
            yield from self._live_monitoring()
    
    def _live_monitoring(self) -> Generator[Dict, None, None]:
        """Live monitoring of audit logs"""
        try:
            # Try to tail audit log file directly
            audit_files = [
                '/var/log/audit/audit.log',
                '/var/log/audit.log'
            ]
            
            audit_file = None
            for file_path in audit_files:
                if os.path.exists(file_path) and os.access(file_path, os.R_OK):
                    audit_file = file_path
                    break
            
            if audit_file:
                logger.info(f"Monitoring audit log: {audit_file}")
                process = subprocess.Popen(
                    ['tail', '-f', audit_file],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True
                )
                
                for line in process.stdout:
                    line = line.strip()
                    if 'type=EXECVE' in line:
                        event = self._parse_execve_event(line)
                        if event and self._is_complete_event(event):
                            yield event
            else:
                logger.warning("No accessible audit log files found")
                yield from self._demo_mode()
                
        except Exception as e:
            logger.warning(f"Live monitoring failed: {e}")
            yield from self._demo_mode()
    
    def _can_access_audit(self) -> bool:
        """Check if we can access audit logs"""
        # Check if running as root
        if os.geteuid() == 0:
            return True
            
        # Check if audit log files are readable
        audit_paths = [
            '/var/log/audit/audit.log',
            '/var/log/audit.log'
        ]
        
        for path in audit_paths:
            if os.path.exists(path) and os.access(path, os.R_OK):
                return True
        
        # Check if ausearch is available and accessible
        try:
            result = subprocess.run(['ausearch', '--help'], 
                                  capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def _demo_mode(self) -> Generator[Dict, None, None]:
        """Generate demo events when audit access is not available"""
        import random
        import time
        
        demo_users = ['john', 'admin', 'developer', 'ops']
        demo_ips = ['192.168.1.100', '192.168.1.101', '10.0.0.50', '172.16.0.10']
        demo_commands = [
            'ls -la',
            'cat /etc/passwd',
            'sudo systemctl status nginx',
            'ps aux | grep python',
            'df -h',
            'netstat -tulpn',
            'tail -f /var/log/syslog',
            'vim config.conf',
            'git status',
            'docker ps'
        ]
        
        logger.info("Running in demo mode - generating sample events")
        
        session_id = 1
        while True:
            # Generate a demo event
            event = {
                'timestamp': datetime.now().isoformat(),
                'event_type': 'command_execution',
                'user': random.choice(demo_users),
                'source_ip': random.choice(demo_ips),
                'command': random.choice(demo_commands),
                'session_id': str(session_id),
                'pid': random.randint(1000, 9999),
                'exit_code': random.choice([0, 0, 0, 0, 1]),  # Mostly successful
                'demo_mode': True
            }
            
            yield event
            session_id += 1
            
            # Wait between demo events
            time.sleep(random.uniform(2, 8))
    
    def _parse_execve_event(self, line: str) -> Dict:
        """Parse EXECVE event from audit log"""
        event = {
            'timestamp': datetime.now().isoformat(),
            'event_type': 'command_execution'
        }
        
        # Extract session ID
        session_match = self.session_pattern.search(line)
        if session_match:
            event['session_id'] = session_match.group(1)
        
        # Extract user ID
        uid_match = self.user_pattern.search(line)
        if uid_match:
            uid = uid_match.group(1)
            event['user'] = self.get_username_from_uid(uid)
            event['uid'] = uid
        
        # Extract command
        proctitle_match = self.command_pattern.search(line)
        if proctitle_match:
            hex_command = proctitle_match.group(1)
            event['command'] = self.hex_to_string(hex_command)
        
        # Add IP address from session map
        session_id = event.get('session_id')
        if session_id and session_id in self.session_map:
            event['source_ip'] = self.session_map[session_id]
        
        return event
    
    def _parse_login_event(self, line: str) -> None:
        """Parse login event to track IP addresses"""
        ip_match = self.login_pattern.search(line)
        session_match = self.session_pattern.search(line)
        
        if ip_match and session_match:
            ip_addr = ip_match.group(1)
            session_id = session_match.group(1)
            self.session_map[session_id] = ip_addr
            logger.debug(f"Mapped session {session_id} to IP {ip_addr}")
    
    def _parse_logout_event(self, line: str) -> None:
        """Parse logout event to clean up session map"""
        session_match = self.session_pattern.search(line)
        if session_match:
            session_id = session_match.group(1)
            if session_id in self.session_map:
                del self.session_map[session_id]
                logger.debug(f"Removed session {session_id} from map")
    
    def _is_complete_event(self, event: Dict) -> bool:
        """Check if event has all required fields"""
        required_fields = ['timestamp', 'user', 'command']
        return all(field in event for field in required_fields)


class LiveAuditParser:
    """Real-time audit log parser using auditd"""
    
    def __init__(self):
        self.parser = AuditLogParser()
        self.running = False
        
    def start_monitoring(self) -> Generator[Dict, None, None]:
        """Start real-time monitoring of audit logs"""
        self.running = True
        logger.info("Starting audit log monitoring...")
        
        try:
            # Configure auditd rules for command tracking (only if root)
            if os.geteuid() == 0:
                self._setup_audit_rules()
            else:
                logger.warning("Not running as root - audit rules cannot be configured")
            
            # Start parsing logs
            for event in self.parser.parse_audit_logs():
                if not self.running:
                    break
                yield event
                
        except KeyboardInterrupt:
            logger.info("Stopping audit log monitoring...")
            self.stop_monitoring()
        except Exception as e:
            logger.error(f"Error in audit monitoring: {e}")
            raise
    
    def stop_monitoring(self):
        """Stop audit log monitoring"""
        self.running = False
        logger.info("Audit log monitoring stopped")
    
    def _setup_audit_rules(self):
        """Setup audit rules for command tracking"""
        # Check if auditctl is available
        auditctl_paths = ['/sbin/auditctl', '/usr/sbin/auditctl']
        auditctl_cmd = None
        
        for path in auditctl_paths:
            if os.path.exists(path):
                auditctl_cmd = path
                break
        
        if not auditctl_cmd:
            logger.warning("auditctl command not found - audit rules cannot be configured")
            return
        
        rules = [
            [auditctl_cmd, '-a', 'always,exit', '-F', 'arch=b64', '-S', 'execve', '-k', 'commands'],
            [auditctl_cmd, '-a', 'always,exit', '-F', 'arch=b32', '-S', 'execve', '-k', 'commands'],
        ]
        
        for rule in rules:
            try:
                result = subprocess.run(rule, check=True, capture_output=True, text=True)
                logger.debug(f"Added audit rule: {' '.join(rule[1:])}")
            except subprocess.CalledProcessError as e:
                # Check if rule already exists
                if "exists" in e.stderr.lower() or "duplicate" in e.stderr.lower():
                    logger.debug(f"Audit rule already exists: {' '.join(rule[1:])}")
                else:
                    logger.warning(f"Failed to add audit rule {' '.join(rule[1:])}: {e.stderr.strip()}")
            except FileNotFoundError:
                logger.warning("auditctl command not found - audit rules cannot be configured")
                break
        
        # Verify rules were added
        try:
            result = subprocess.run([auditctl_cmd, '-l'], capture_output=True, text=True)
            if 'execve' in result.stdout:
                logger.info("Audit rules for command tracking are active")
            else:
                logger.warning("No audit rules found for command tracking")
        except Exception as e:
            logger.debug(f"Could not verify audit rules: {e}") 