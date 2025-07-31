#!/usr/bin/env python3
"""
Audit log parser for SecuBeat
Parses Linux audit logs to extract command execution information
"""

import re
import subprocess
import time
import logging
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
            # Start following audit log
            process = subprocess.Popen(
                ['ausearch', '-i', '-k', 'commands', '--format', 'text'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
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
                    
        except subprocess.SubprocessError as e:
            logger.error(f"Error running ausearch: {e}")
        except Exception as e:
            logger.error(f"Error parsing audit logs: {e}")
    
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
            # Configure auditd rules for command tracking
            self._setup_audit_rules()
            
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
        rules = [
            '-a always,exit -F arch=b64 -S execve -k commands',
            '-a always,exit -F arch=b32 -S execve -k commands',
        ]
        
        for rule in rules:
            try:
                subprocess.run(['auditctl'] + rule.split()[1:], 
                             check=True, capture_output=True)
                logger.debug(f"Added audit rule: {rule}")
            except subprocess.CalledProcessError as e:
                logger.warning(f"Failed to add audit rule {rule}: {e}") 