#!/usr/bin/env python3
"""
Example Management Server for SecuBeat
Simple Flask server to receive and store SecuBeat events
"""

from flask import Flask, request, jsonify
import json
import sqlite3
import logging
from datetime import datetime
import os

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Database setup
DB_FILE = 'secu_beat_events.db'

def init_database():
    """Initialize SQLite database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            user TEXT,
            source_ip TEXT,
            command TEXT,
            session_id TEXT,
            pid INTEGER,
            exit_code INTEGER,
            execution_time REAL,
            terminal TEXT,
            raw_data TEXT,
            received_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def store_event(event_data):
    """Store event in database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO events (
            timestamp, event_type, user, source_ip, command,
            session_id, pid, exit_code, execution_time, terminal, raw_data
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        event_data.get('timestamp'),
        event_data.get('event_type'),
        event_data.get('user'),
        event_data.get('source_ip'),
        event_data.get('command'),
        event_data.get('session_id'),
        event_data.get('pid'),
        event_data.get('exit_code'),
        event_data.get('execution_time'),
        event_data.get('terminal'),
        json.dumps(event_data)
    ))
    
    conn.commit()
    conn.close()

@app.route('/api/secu-beat/logs', methods=['POST'])
def receive_logs():
    """Receive logs from SecuBeat clients"""
    try:
        # Validate content type
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        
        data = request.get_json()
        
        # Log received data
        logger.info(f"Received batch from {request.remote_addr}: {data.get('count', 0)} events")
        
        # Validate required fields
        if 'events' not in data:
            return jsonify({'error': 'Missing events field'}), 400
        
        # Store each event
        events = data['events']
        for event in events:
            store_event(event)
            logger.debug(f"Stored event: {event.get('user')}@{event.get('source_ip')} - {event.get('command')}")
        
        return jsonify({
            'status': 'success',
            'received': len(events),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/secu-beat/events', methods=['GET'])
def get_events():
    """Get stored events (for debugging/viewing)"""
    try:
        limit = request.args.get('limit', 100, type=int)
        user = request.args.get('user')
        command = request.args.get('command')
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        query = 'SELECT * FROM events WHERE 1=1'
        params = []
        
        if user:
            query += ' AND user = ?'
            params.append(user)
        
        if command:
            query += ' AND command LIKE ?'
            params.append(f'%{command}%')
        
        query += ' ORDER BY received_at DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        # Convert to list of dictionaries
        columns = [description[0] for description in cursor.description]
        events = [dict(zip(columns, row)) for row in rows]
        
        conn.close()
        
        return jsonify({
            'events': events,
            'count': len(events)
        })
        
    except Exception as e:
        logger.error(f"Error fetching events: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/secu-beat/stats', methods=['GET'])
def get_stats():
    """Get statistics"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Total events
        cursor.execute('SELECT COUNT(*) FROM events')
        total_events = cursor.fetchone()[0]
        
        # Unique users
        cursor.execute('SELECT COUNT(DISTINCT user) FROM events WHERE user IS NOT NULL')
        unique_users = cursor.fetchone()[0]
        
        # Unique IPs
        cursor.execute('SELECT COUNT(DISTINCT source_ip) FROM events WHERE source_ip IS NOT NULL')
        unique_ips = cursor.fetchone()[0]
        
        # Recent activity (last hour)
        cursor.execute('''
            SELECT COUNT(*) FROM events 
            WHERE datetime(received_at) > datetime('now', '-1 hour')
        ''')
        recent_events = cursor.fetchone()[0]
        
        # Top users
        cursor.execute('''
            SELECT user, COUNT(*) as count 
            FROM events 
            WHERE user IS NOT NULL 
            GROUP BY user 
            ORDER BY count DESC 
            LIMIT 10
        ''')
        top_users = [{'user': row[0], 'count': row[1]} for row in cursor.fetchall()]
        
        # Top commands
        cursor.execute('''
            SELECT command, COUNT(*) as count 
            FROM events 
            WHERE command IS NOT NULL 
            GROUP BY command 
            ORDER BY count DESC 
            LIMIT 10
        ''')
        top_commands = [{'command': row[0], 'count': row[1]} for row in cursor.fetchall()]
        
        conn.close()
        
        return jsonify({
            'total_events': total_events,
            'unique_users': unique_users,
            'unique_ips': unique_ips,
            'recent_events_1h': recent_events,
            'top_users': top_users,
            'top_commands': top_commands
        })
        
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'database': os.path.exists(DB_FILE)
    })

if __name__ == '__main__':
    # Initialize database
    init_database()
    logger.info("Management server starting...")
    
    # Run server
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False
    ) 