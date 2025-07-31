#!/usr/bin/env python3
"""
JSON formatter and output manager for SecuBeat
Handles formatting and outputting of tracking data
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


class OutputMode(Enum):
    """Output modes for the system"""
    CONSOLE = "console"
    JSON_FILE = "json_file"
    SERVER = "server"


class JSONFormatter:
    """Formats tracking data into JSON format"""
    
    def __init__(self):
        self.version = "1.0"
    
    def format_command_event(self, event: Dict) -> Dict:
        """Format a command execution event"""
        formatted_event = {
            "version": self.version,
            "timestamp": event.get('timestamp', datetime.now().isoformat()),
            "event_type": "command_execution",
            "user": event.get('user', 'unknown'),
            "source_ip": event.get('source_ip', 'unknown'),
            "command": event.get('command', ''),
            "session_id": event.get('session_id'),
            "pid": event.get('pid'),
            "exit_code": event.get('exit_code'),
            "execution_time": event.get('execution_time'),
            "terminal": event.get('terminal'),
            "result": event.get('result', {})
        }
        
        # Remove None values
        formatted_event = {k: v for k, v in formatted_event.items() if v is not None}
        
        return formatted_event
    
    def format_login_event(self, event: Dict) -> Dict:
        """Format a login event"""
        formatted_event = {
            "version": self.version,
            "timestamp": event.get('timestamp', datetime.now().isoformat()),
            "event_type": "user_login",
            "user": event.get('user', 'unknown'),
            "source_ip": event.get('source_ip', 'unknown'),
            "session_id": event.get('session_id'),
            "terminal": event.get('terminal')
        }
        
        # Remove None values
        formatted_event = {k: v for k, v in formatted_event.items() if v is not None}
        
        return formatted_event
    
    def format_logout_event(self, event: Dict) -> Dict:
        """Format a logout event"""
        formatted_event = {
            "version": self.version,
            "timestamp": event.get('timestamp', datetime.now().isoformat()),
            "event_type": "user_logout",
            "user": event.get('user', 'unknown'),
            "session_id": event.get('session_id'),
            "session_duration": event.get('session_duration')
        }
        
        # Remove None values
        formatted_event = {k: v for k, v in formatted_event.items() if v is not None}
        
        return formatted_event
    
    def format_summary(self, events: List[Dict]) -> Dict:
        """Format a summary of events"""
        if not events:
            return {
                "version": self.version,
                "timestamp": datetime.now().isoformat(),
                "summary": {
                    "total_events": 0,
                    "unique_users": 0,
                    "unique_ips": 0,
                    "commands_executed": 0
                }
            }
        
        users = set()
        ips = set()
        commands = 0
        
        for event in events:
            if event.get('user'):
                users.add(event['user'])
            if event.get('source_ip'):
                ips.add(event['source_ip'])
            if event.get('event_type') == 'command_execution':
                commands += 1
        
        return {
            "version": self.version,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_events": len(events),
                "unique_users": len(users),
                "unique_ips": len(ips),
                "commands_executed": commands,
                "time_range": {
                    "start": events[0].get('timestamp') if events else None,
                    "end": events[-1].get('timestamp') if events else None
                }
            }
        }


class ConsoleOutput:
    """Handles console output formatting"""
    
    def __init__(self, use_colors: bool = True):
        self.use_colors = use_colors
        self.formatter = JSONFormatter()
        
    def print_event(self, event: Dict):
        """Print event to console"""
        formatted = self.formatter.format_command_event(event)
        
        if self.use_colors:
            self._print_colored_event(formatted)
        else:
            self._print_plain_event(formatted)
    
    def _print_colored_event(self, event: Dict):
        """Print colored event to console"""
        # ANSI color codes
        GREEN = '\033[92m'
        YELLOW = '\033[93m'
        RED = '\033[91m'
        BLUE = '\033[94m'
        CYAN = '\033[96m'
        RESET = '\033[0m'
        BOLD = '\033[1m'
        
        timestamp = event.get('timestamp', '')
        user = event.get('user', 'unknown')
        source_ip = event.get('source_ip', 'unknown')
        command = event.get('command', '')
        exit_code = event.get('exit_code', 'N/A')
        
        # Color code based on exit status
        status_color = GREEN if exit_code == 0 else RED if exit_code else YELLOW
        
        print(f"{CYAN}[{timestamp}]{RESET} "
              f"{BLUE}{user}@{source_ip}{RESET} "
              f"{BOLD}${RESET} {command} "
              f"{status_color}(exit: {exit_code}){RESET}")
    
    def _print_plain_event(self, event: Dict):
        """Print plain event to console"""
        timestamp = event.get('timestamp', '')
        user = event.get('user', 'unknown')
        source_ip = event.get('source_ip', 'unknown')
        command = event.get('command', '')
        exit_code = event.get('exit_code', 'N/A')
        
        print(f"[{timestamp}] {user}@{source_ip} $ {command} (exit: {exit_code})")
    
    def print_json(self, event: Dict):
        """Print event as JSON"""
        formatted = self.formatter.format_command_event(event)
        print(json.dumps(formatted, indent=2, ensure_ascii=False))


class FileOutput:
    """Handles file output"""
    
    def __init__(self, filename: str):
        self.filename = filename
        self.formatter = JSONFormatter()
    
    def write_event(self, event: Dict):
        """Write event to file"""
        try:
            formatted = self.formatter.format_command_event(event)
            
            with open(self.filename, 'a', encoding='utf-8') as f:
                json.dump(formatted, f, ensure_ascii=False)
                f.write('\n')
                
        except Exception as e:
            logger.error(f"Error writing to file {self.filename}: {e}")
    
    def write_events(self, events: List[Dict]):
        """Write multiple events to file"""
        try:
            with open(self.filename, 'a', encoding='utf-8') as f:
                for event in events:
                    formatted = self.formatter.format_command_event(event)
                    json.dump(formatted, f, ensure_ascii=False)
                    f.write('\n')
                    
        except Exception as e:
            logger.error(f"Error writing events to file {self.filename}: {e}")


class OutputManager:
    """Manages different output methods"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.formatter = JSONFormatter()
        self.outputs = []
        
        self._setup_outputs()
    
    def _setup_outputs(self):
        """Setup output methods based on configuration"""
        output_mode = self.config.get('output_mode', OutputMode.CONSOLE.value)
        
        if output_mode == OutputMode.CONSOLE.value:
            use_colors = self.config.get('use_colors', True)
            self.outputs.append(ConsoleOutput(use_colors))
            
        elif output_mode == OutputMode.JSON_FILE.value:
            filename = self.config.get('output_file', 'secu-beat.log')
            self.outputs.append(FileOutput(filename))
            
        elif output_mode == OutputMode.SERVER.value:
            # Server output will be handled separately
            pass
    
    def output_event(self, event: Dict):
        """Output event using configured methods"""
        for output in self.outputs:
            try:
                if isinstance(output, ConsoleOutput):
                    if self.config.get('json_output', False):
                        output.print_json(event)
                    else:
                        output.print_event(event)
                elif isinstance(output, FileOutput):
                    output.write_event(event)
            except Exception as e:
                logger.error(f"Error outputting event: {e}")
    
    def output_events(self, events: List[Dict]):
        """Output multiple events"""
        for event in events:
            self.output_event(event)
    
    def get_formatted_event(self, event: Dict) -> Dict:
        """Get formatted event for external use"""
        return self.formatter.format_command_event(event) 