#!/usr/bin/env python3
"""Простой HTTP прокси для запросов к ЮKassa. Запускается на хосте."""
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request, json, sys

class ProxyHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers['Content-Length'])
        body = self.rfile.read(length)
        auth = self.headers.get('Authorization', '')
        idem = self.headers.get('Idempotence-Key', '')
        
        req = urllib.request.Request(
            f'https://api.yookassa.ru{self.path}',
            data=body,
            headers={
                'Content-Type': 'application/json',
                'Authorization': auth,
                'Idempotence-Key': idem,
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                resp_body = r.read()
                self.send_response(r.status)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(resp_body)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())
    
    def log_message(self, format, *args):
        pass

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 9999), ProxyHandler)
    print('YuKassa proxy started on port 9999')
    server.serve_forever()
