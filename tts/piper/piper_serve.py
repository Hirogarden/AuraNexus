#!/usr/bin/env python3
import argparse
import http.server
import socketserver
import json

parser = argparse.ArgumentParser()
parser.add_argument('--host', default='127.0.0.1')
parser.add_argument('--port', type=int, default=59125)
args = parser.parse_args()

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'piper': 'stub', 'path': self.path}).encode())

with socketserver.TCPServer((args.host, args.port), Handler) as httpd:
    print(f'piper stub listening on {args.host}:{args.port}')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
