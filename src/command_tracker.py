#!/usr/bin/env python3
"""
Command tracker for SecuBeat
Tracks command execution and captures results
"""

import os
import subprocess
import psutil
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from threading import Thread, Lock
import pwd

logger = logging.getLogger(__name__)


class CommandTracker:
    """Tracks command execution and captures output/results"""
    
    def __init__(self):
        self.active_processes = {}
        self.process_lock = Lock()
        self.monitoring = False
        
    def start_tracking(self):
        """Start command tracking"""
        self.monitoring = True
        logger.info("Command tracking started")
        
        # Start background thread to monitor processes
        monitor_thread = Thread(target=self._monitor_processes, daemon=True)
        monitor_thread.start()
    
    def stop_tracking(self):
        """Stop command tracking"""
        self.monitoring = False
        logger.info("Command tracking stopped")
    
    def _monitor_processes(self):
        """Monitor running processes for SSH sessions"""
        while self.monitoring:
            try:
                self._scan_ssh_processes()
                time.sleep(1)  # Check every second
            except Exception as e:
                logger.error(f"Error monitoring processes: {e}")
                time.sleep(5)  # Wait longer on error
    
    def _scan_ssh_processes(self):
        """Scan for SSH-related processes"""
        for proc in psutil.process_iter(['pid', 'ppid', 'name', 'cmdline', 'username', 'terminal']):
            try:
                pinfo = proc.info
                
                # Skip if not SSH related
                if not self._is_ssh_related(pinfo):
                    continue
                
                pid = pinfo['pid']
                
                # Track new processes
                if pid not in self.active_processes:
                    self._track_new_process(proc, pinfo)
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    
    def _is_ssh_related(self, pinfo: Dict) -> bool:
        """Check if process is related to SSH session"""
        # Check for SSH daemon children or terminal processes
        if pinfo['name'] in ['bash', 'sh', 'zsh', 'csh', 'tcsh', 'fish']:
            return pinfo['terminal'] and pinfo['terminal'].startswith('pts/')
        
        # Check for direct SSH processes
        if pinfo['name'] == 'sshd':
            return True
            
        # Check for commands run in SSH sessions
        if pinfo['terminal'] and pinfo['terminal'].startswith('pts/'):
            return True
            
        return False
    
    def _track_new_process(self, proc: psutil.Process, pinfo: Dict):
        """Track a new process"""
        pid = pinfo['pid']
        
        try:
            # Get additional process information
            process_info = {
                'pid': pid,
                'ppid': pinfo['ppid'],
                'name': pinfo['name'],
                'cmdline': ' '.join(pinfo['cmdline']) if pinfo['cmdline'] else '',
                'username': pinfo['username'],
                'terminal': pinfo['terminal'],
                'start_time': datetime.now().isoformat(),
                'status': 'running'
            }
            
            # Get connection info for SSH sessions
            conn_info = self._get_connection_info(proc)
            if conn_info:
                process_info.update(conn_info)
            
            with self.process_lock:
                self.active_processes[pid] = process_info
                
            logger.debug(f"Tracking new process: {pid} - {process_info['cmdline']}")
            
        except Exception as e:
            logger.error(f"Error tracking process {pid}: {e}")
    
    def _get_connection_info(self, proc: psutil.Process) -> Optional[Dict]:
        """Get connection information for SSH processes"""
        try:
            connections = proc.connections()
            for conn in connections:
                if conn.status == 'ESTABLISHED' and conn.raddr:
                    return {
                        'source_ip': conn.raddr.ip,
                        'source_port': conn.raddr.port,
                        'local_port': conn.laddr.port
                    }
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass
        return None
    
    def get_command_result(self, pid: int, command: str) -> Dict:
        """Get command execution result"""
        try:
            proc = psutil.Process(pid)
            
            # Wait for process to complete
            start_time = time.time()
            timeout = 30  # 30 second timeout
            
            while proc.is_running() and time.time() - start_time < timeout:
                time.sleep(0.1)
            
            # Get exit code
            exit_code = None
            if not proc.is_running():
                try:
                    exit_code = proc.wait(timeout=1)
                except psutil.TimeoutExpired:
                    exit_code = -1
            
            # Try to capture output from various sources
            output = self._capture_command_output(pid, command)
            
            result = {
                'pid': pid,
                'command': command,
                'exit_code': exit_code,
                'output': output,
                'execution_time': time.time() - start_time,
                'completed_at': datetime.now().isoformat()
            }
            
            return result
            
        except psutil.NoSuchProcess:
            return {
                'pid': pid,
                'command': command,
                'exit_code': 0,
                'output': '',
                'execution_time': 0,
                'completed_at': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting command result for PID {pid}: {e}")
            return {
                'pid': pid,
                'command': command,
                'exit_code': -1,
                'output': f"Error: {str(e)}",
                'execution_time': 0,
                'completed_at': datetime.now().isoformat()
            }
    
    def _capture_command_output(self, pid: int, command: str) -> str:
        """Attempt to capture command output"""
        # For security and simplicity, we'll return a placeholder
        # In a production environment, you might want to implement
        # more sophisticated output capture mechanisms
        return f"[Command executed: {command}]"
    
    def get_process_info(self, pid: int) -> Optional[Dict]:
        """Get information about a tracked process"""
        with self.process_lock:
            return self.active_processes.get(pid)
    
    def cleanup_finished_processes(self):
        """Clean up information for finished processes"""
        with self.process_lock:
            finished_pids = []
            for pid, info in self.active_processes.items():
                try:
                    proc = psutil.Process(pid)
                    if not proc.is_running():
                        finished_pids.append(pid)
                except psutil.NoSuchProcess:
                    finished_pids.append(pid)
            
            for pid in finished_pids:
                del self.active_processes[pid]
                logger.debug(f"Cleaned up process {pid}")


class EnhancedCommandTracker:
    """Enhanced command tracker with better output capture"""
    
    def __init__(self):
        self.base_tracker = CommandTracker()
        self.command_history = []
        
    def track_command_with_audit(self, audit_event: Dict) -> Dict:
        """Track command using audit event information"""
        enhanced_event = audit_event.copy()
        
        # Add process information if available
        pid = audit_event.get('pid')
        if pid:
            process_info = self.base_tracker.get_process_info(pid)
            if process_info:
                enhanced_event.update(process_info)
        
        # Add command result
        command = audit_event.get('command', '')
        if command and pid:
            result = self.base_tracker.get_command_result(pid, command)
            enhanced_event['result'] = result
        
        # Store in history
        self.command_history.append(enhanced_event)
        
        # Keep only last 1000 commands in memory
        if len(self.command_history) > 1000:
            self.command_history = self.command_history[-1000:]
        
        return enhanced_event
    
    def start_tracking(self):
        """Start enhanced command tracking"""
        self.base_tracker.start_tracking()
    
    def stop_tracking(self):
        """Stop enhanced command tracking"""
        self.base_tracker.stop_tracking()
    
    def get_recent_commands(self, count: int = 10) -> List[Dict]:
        """Get recent command history"""
        return self.command_history[-count:] if self.command_history else [] 