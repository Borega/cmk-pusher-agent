#!/usr/bin/env python3
# This file is part of CMK Pusher.

import os
import json
import base64
import zlib
import re
import hashlib
import datetime
from flask import Flask, request, jsonify

# Read configuration from environment variables
spool_path = os.getenv('CMK_SPOOL_PATH', '/var/www/tmp')
secret = os.getenv('CMK_SECRET', 'secret')
debug = os.getenv('CMK_DEBUG', 'False').lower() in ('true', '1', 't')

app = Flask(__name__)

def debug_log(message):
    if debug:
        with open('logs/json.log', 'a') as log_file:
            log_file.write(f"Line: {message}\n")

def clean_client(client_name):
    return re.sub(r'[^A-Za-z0-9.-]+', '', client_name)

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "config": {"spool_path": spool_path, "debug": debug}})

@app.route('/api/json.php', methods=['POST'])
def handle_json():
    clean_data = False
    jsondata = request.get_data().decode('utf-8')
    data = json.loads(jsondata)
    
    # Authenticate the request
    if data.get('auth', {}).get('secret') != secret:
        debug_log("Authentication failed - invalid secret")
        return jsonify({"error": "Authentication failed"}), 403
    
    if data.get('transaction', {}).get('action', '').strip() == "push":
        output_b64 = data['transaction']['values']['agentoutput']
        output = base64.b64decode(output_b64)
        
        # Check if compression is enabled
        if data['transaction'].get('compress', False):
            output = zlib.decompress(output)
        
        client_name = clean_client(data['transaction']['values']['client_name'])
        debug_log(f"Processing client: {client_name}")
        
        # Check for md5sum, if not existing it's legacy (old Client)
        md5sum = data['transaction']['values'].get('md5sum', '')
        if md5sum:
            if hashlib.md5(output).hexdigest() == md5sum.strip():
                debug_log("Checked MD5 Sum - OK")
                clean_data = True
            else:
                debug_log("Checked MD5 Sum - ERROR")
                clean_data = False
        else:
            # Set Clean Data for old clients
            clean_data = True
            debug_log(f"Checked MD5 Sum - Old Client - {data['transaction']['values']['client_name'].strip()}")
        
        if clean_data:
            # Ensure the directory exists
            os.makedirs(spool_path, exist_ok=True)
            
            # Write data to file
            file_path = f"{spool_path}/{client_name}.dump"
            debug_log(f"Writing to file: {file_path}")
            
            try:
                with open(file_path, 'w+') as openfile:
                    content = output.decode('utf-8')
                    # Add freshness check to file
                    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    remote_ip = request.remote_addr
                    content += f"<<<cmk_pusher>>>\nlast_connect {current_time} remote_ip {remote_ip}\n"
                    openfile.write(content)
                debug_log("File written successfully")
            except Exception as e:
                debug_log(f"Error writing file: {str(e)}")
                return jsonify({"error": str(e)}), 500
    
    return jsonify({"status": "success"})

if __name__ == "__main__":
    # Print configuration on startup
    print(f"Starting CMK Pusher API on port 5000 with:")
    print(f"- Spool path: {spool_path}")
    print(f"- Debug mode: {debug}")
    
    # Ensure the spool directory exists
    os.makedirs(spool_path, exist_ok=True)
    
    app.run(host='0.0.0.0', port=5000)