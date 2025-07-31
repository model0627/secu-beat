#!/usr/bin/env python3
"""
Network sender for SecuBeat
Handles sending data to management servers
"""

import json
import requests
import logging
import time
from typing import Dict, List, Optional
from datetime import datetime
from threading import Thread, Queue, Lock
import urllib3

# Disable SSL warnings for self-signed certificates (optional)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class NetworkSender:
    """Handles sending data to remote management servers"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.server_url = config.get('server_url')
        self.auth_token = config.get('server_token')
        self.batch_size = config.get('batch_size', 10)
        self.timeout = config.get('timeout', 30)
        self.verify_ssl = config.get('verify_ssl', True)
        self.retry_attempts = config.get('retry_attempts', 3)
        self.retry_delay = config.get('retry_delay', 5)
        
        # Queue for buffering events
        self.event_queue = Queue()
        self.sending = False
        self.sender_thread = None
        
        # Statistics
        self.stats = {
            'sent_events': 0,
            'failed_events': 0,
            'last_sent': None,
            'last_error': None
        }
        self.stats_lock = Lock()
    
    def start_sending(self):
        """Start the background sender thread"""
        if self.sending:
            return
            
        self.sending = True
        self.sender_thread = Thread(target=self._sender_worker, daemon=True)
        self.sender_thread.start()
        logger.info("Network sender started")
    
    def stop_sending(self):
        """Stop the background sender thread"""
        self.sending = False
        if self.sender_thread:
            self.sender_thread.join(timeout=5)
        logger.info("Network sender stopped")
    
    def send_event(self, event: Dict):
        """Queue an event for sending"""
        if not self.server_url:
            logger.warning("No server URL configured, skipping event")
            return
            
        self.event_queue.put(event)
    
    def send_events(self, events: List[Dict]):
        """Queue multiple events for sending"""
        for event in events:
            self.send_event(event)
    
    def _sender_worker(self):
        """Background worker that sends queued events"""
        batch = []
        
        while self.sending:
            try:
                # Collect events for batch sending
                while len(batch) < self.batch_size and self.sending:
                    try:
                        event = self.event_queue.get(timeout=1.0)
                        batch.append(event)
                    except:
                        break
                
                # Send batch if we have events
                if batch:
                    self._send_batch(batch)
                    batch = []
                    
            except Exception as e:
                logger.error(f"Error in sender worker: {e}")
                time.sleep(self.retry_delay)
    
    def _send_batch(self, events: List[Dict]):
        """Send a batch of events to the server"""
        if not events:
            return
            
        payload = {
            'timestamp': datetime.now().isoformat(),
            'source': 'secu-beat',
            'events': events,
            'count': len(events)
        }
        
        for attempt in range(self.retry_attempts):
            try:
                response = self._make_request(payload)
                
                if response.status_code == 200:
                    with self.stats_lock:
                        self.stats['sent_events'] += len(events)
                        self.stats['last_sent'] = datetime.now().isoformat()
                    
                    logger.debug(f"Successfully sent batch of {len(events)} events")
                    return
                else:
                    logger.warning(f"Server returned status {response.status_code}: {response.text}")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Network error (attempt {attempt + 1}/{self.retry_attempts}): {e}")
                
                with self.stats_lock:
                    self.stats['last_error'] = str(e)
                
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
            except Exception as e:
                logger.error(f"Unexpected error sending batch: {e}")
                break
        
        # If we get here, all attempts failed
        with self.stats_lock:
            self.stats['failed_events'] += len(events)
        
        logger.error(f"Failed to send batch of {len(events)} events after {self.retry_attempts} attempts")
    
    def _make_request(self, payload: Dict) -> requests.Response:
        """Make HTTP request to the server"""
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'SecuBeat/1.0'
        }
        
        # Add authentication if configured
        if self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'
        
        response = requests.post(
            self.server_url,
            json=payload,
            headers=headers,
            timeout=self.timeout,
            verify=self.verify_ssl
        )
        
        return response
    
    def get_stats(self) -> Dict:
        """Get sender statistics"""
        with self.stats_lock:
            return self.stats.copy()
    
    def flush_queue(self):
        """Flush remaining events in queue"""
        batch = []
        
        # Collect all remaining events
        while not self.event_queue.empty():
            try:
                event = self.event_queue.get_nowait()
                batch.append(event)
            except:
                break
        
        # Send final batch
        if batch:
            self._send_batch(batch)


class WebhookSender:
    """Simple webhook sender for basic integrations"""
    
    def __init__(self, webhook_url: str, secret: Optional[str] = None):
        self.webhook_url = webhook_url
        self.secret = secret
    
    def send_event(self, event: Dict):
        """Send single event via webhook"""
        try:
            headers = {'Content-Type': 'application/json'}
            
            # Add signature if secret is provided
            if self.secret:
                import hmac
                import hashlib
                
                payload = json.dumps(event)
                signature = hmac.new(
                    self.secret.encode(),
                    payload.encode(),
                    hashlib.sha256
                ).hexdigest()
                headers['X-Signature'] = f'sha256={signature}'
            
            response = requests.post(
                self.webhook_url,
                json=event,
                headers=headers,
                timeout=10
            )
            
            if response.status_code != 200:
                logger.warning(f"Webhook returned status {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error sending webhook: {e}")


class SyslogSender:
    """Send events via syslog protocol"""
    
    def __init__(self, syslog_server: str, syslog_port: int = 514):
        self.syslog_server = syslog_server
        self.syslog_port = syslog_port
        
    def send_event(self, event: Dict):
        """Send event via syslog"""
        try:
            import socket
            
            # Format as syslog message
            timestamp = event.get('timestamp', datetime.now().isoformat())
            user = event.get('user', 'unknown')
            command = event.get('command', '')
            source_ip = event.get('source_ip', 'unknown')
            
            message = f"SecuBeat: {user}@{source_ip} executed: {command}"
            
            # Send UDP syslog message
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(message.encode(), (self.syslog_server, self.syslog_port))
            sock.close()
            
        except Exception as e:
            logger.error(f"Error sending syslog: {e}")


class MultiSender:
    """Manages multiple sending methods"""
    
    def __init__(self, config: Dict):
        self.senders = []
        self.config = config
        
        # Setup configured senders
        self._setup_senders()
    
    def _setup_senders(self):
        """Setup senders based on configuration"""
        # HTTP/HTTPS sender
        if self.config.get('server_url'):
            network_sender = NetworkSender(self.config)
            network_sender.start_sending()
            self.senders.append(network_sender)
        
        # Webhook sender
        webhook_url = self.config.get('webhook_url')
        if webhook_url:
            webhook_secret = self.config.get('webhook_secret')
            webhook_sender = WebhookSender(webhook_url, webhook_secret)
            self.senders.append(webhook_sender)
        
        # Syslog sender
        syslog_server = self.config.get('syslog_server')
        if syslog_server:
            syslog_port = self.config.get('syslog_port', 514)
            syslog_sender = SyslogSender(syslog_server, syslog_port)
            self.senders.append(syslog_sender)
    
    def send_event(self, event: Dict):
        """Send event using all configured senders"""
        for sender in self.senders:
            try:
                sender.send_event(event)
            except Exception as e:
                logger.error(f"Error in sender {type(sender).__name__}: {e}")
    
    def send_events(self, events: List[Dict]):
        """Send multiple events"""
        for event in events:
            self.send_event(event)
    
    def stop_all(self):
        """Stop all senders"""
        for sender in self.senders:
            if hasattr(sender, 'stop_sending'):
                sender.stop_sending()
            elif hasattr(sender, 'flush_queue'):
                sender.flush_queue()
    
    def get_stats(self) -> Dict:
        """Get statistics from all senders"""
        stats = {}
        for sender in self.senders:
            sender_name = type(sender).__name__
            if hasattr(sender, 'get_stats'):
                stats[sender_name] = sender.get_stats()
            else:
                stats[sender_name] = {'status': 'active'}
        return stats 