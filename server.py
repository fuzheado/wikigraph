#!/usr/bin/env python3
"""HTTP server that serves the wikigraph web app and provides graph APIs.

Serves static files (index.html, etc.) from the current directory, and
intercepts /api/graph and /api/graph-from-list for NDJSON streaming.

Endpoints:
  GET /                                                     → index.html
  GET /api/graph?year=&month=&day=&refresh=1                → NDJSON stream with progress (date mode)
  POST /api/graph-from-list                                 → NDJSON stream with progress (custom list)

Query params (GET /api/graph):
  year, month, day   — date to build (default: latest available)
  min_entity         — entity helper threshold (default: 3)
  ignore             — comma-separated articles to exclude
  user_agent         — custom User-Agent string
  refresh            — set to 1 to clear cache before building

POST body (POST /api/graph-from-list):
  {"titles": ["Article A", "Article B", ...]}
"""
import json
import os
import shutil
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from wikigraph import build_graph, build_graph_from_list, latest_available_date
from wikigraph.config import CACHE_DIR


class GraphAPIHandler(SimpleHTTPRequestHandler):

    def _write_json(self, obj):
        self.wfile.write((json.dumps(obj) + "\n").encode())
        self.wfile.flush()

    def _stream_graph(self, build_fn, *args, **kwargs):
        """Stream NDJSON progress + graph data for any build function."""
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        try:
            self._write_json({"type": "progress", "message": "Starting..."})
            graph_data = build_fn(
                *args,
                progress_callback=lambda m: self._write_json(
                    {"type": "progress", "message": m}
                ),
                **kwargs,
            )
            self._write_json({"type": "graph", "data": graph_data})
        except Exception as e:
            try:
                self._write_json({"type": "error", "message": str(e)})
            except BrokenPipeError:
                pass

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/graph":
            params = parse_qs(parsed.query)
            try:
                year = params.get("year", [None])[0]
                month = params.get("month", [None])[0]
                day = params.get("day", [None])[0]
                if not (year and month and day):
                    ly, lm, ld = latest_available_date()
                    year = year or ly
                    month = month or lm
                    day = day or ld
                min_entity = int(params.get("min_entity", ["3"])[0])
                ignore_raw = params.get("ignore", [None])[0]
                ignore_list = ignore_raw.split(",") if ignore_raw else None
                user_agent = params.get("user_agent", [None])[0]
                wiki = params.get("wiki", ["en"])[0]
                refresh = params.get("refresh", ["0"])[0] == "1"
            except (ValueError, KeyError):
                self.send_error(400, "Invalid parameters")
                return

            if refresh and os.path.exists(CACHE_DIR):
                shutil.rmtree(CACHE_DIR)
                print("  Cache cleared on refresh request")

            self._stream_graph(
                build_graph,
                year, month, day,
                min_entity_share=min_entity,
                ignore_articles=ignore_list,
                user_agent=user_agent,
                wiki=wiki,
            )
            return

        if parsed.path == "/api/pagepile":
            params = parse_qs(parsed.query)
            pile_id = params.get("id", [None])[0]
            if not pile_id:
                self.send_error(400, "Missing 'id' parameter")
                return
            try:
                from wikigraph.sources.pagepile import fetch_pagepile
                result = fetch_pagepile(int(pile_id))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            except ValueError as e:
                self.send_error(404, str(e))
            except Exception as e:
                self.send_error(500, str(e))
            return

        if parsed.path == "/api/category":
            params = parse_qs(parsed.query)
            name = params.get("name", [None])[0]
            depth = int(params.get("depth", ["0"])[0])
            if not name:
                self.send_error(400, "Missing 'name' parameter")
                return
            try:
                from wikigraph.sources.category import fetch_category
                result = fetch_category(name, depth)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            except ValueError as e:
                self.send_error(404, str(e))
            except Exception as e:
                self.send_error(500, str(e))
            return

        # Serve static files (index.html, etc.)
        return super().do_GET()

    def do_POST(self):
        import json
        parsed = urlparse(self.path)

        if parsed.path == "/api/graph-from-cytoscape":
            # Expect multipart/form-data with a file field named "file"
            try:
                import cgi
            except ImportError:
                self.send_error(501, "Cytoscape upload requires Python < 3.13")
                return
            ctype, pdict = cgi.parse_header(self.headers.get('content-type'))
            if ctype != 'multipart/form-data':
                self.send_error(400, "Expected multipart/form-data")
                return
            pdict['boundary'] = bytes(pdict['boundary'], "utf-8")
            fields = cgi.parse_multipart(self.rfile, pdict)
            if "file" not in fields:
                self.send_error(400, "No file uploaded")
                return
            try:
                cyt_data = json.loads(fields["file"][0])
            except Exception as e:
                self.send_error(400, f"Invalid JSON: {e}")
                return

            # Convert to internal format then stream it back as NDJSON (like other builds)
            from wikigraph.graph.serializers import convert_from_cytoscape
            output = convert_from_cytoscape(cyt_data)
            # Bypass callbacks – just stream the result
            self._stream_graph(lambda *a, **k: output, {})
            return

        if parsed.path == "/api/graph-from-list":
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                data = json.loads(body)
                titles = data.get("titles", [])
                wiki = data.get("wiki", "en")
                if not titles or not isinstance(titles, list):
                    self.send_error(400, "Expected JSON with 'titles' array")
                    return
            except (ValueError, KeyError, json.JSONDecodeError):
                self.send_error(400, "Invalid JSON body")
                return

            self._stream_graph(build_graph_from_list, titles, wiki=wiki)
            return

        self.send_error(404)

    def log_message(self, format, *args):
        """Quiet logs; show errors and API requests."""
        if args and "404" in str(args[0]):
            super().log_message(format, *args)


def main():
    port = int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) >= 2 else "8000"))
    server = HTTPServer(("0.0.0.0", port), GraphAPIHandler)
    print(f"wikigraph server at http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
