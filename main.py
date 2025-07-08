import http.server
import socketserver
import os

PORT = 3000

os.chdir("frontend")

Handler = http.server.SimpleHTTPRequestHandler

with socketserver.TCPServer(("", PORT), Handler) as httpd:
  print("Serving at port", PORT)
  httpd.serve_forever()
  