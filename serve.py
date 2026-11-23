"""唯讀本機儀表板。預設僅綁定 127.0.0.1，不啟用外部部署。"""
import argparse
import json
import mimetypes
import sqlite3
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from src.pipeline import execute
from src.storage import snapshot, list_runs, db_path
from src.report import claims_csv
from src.public_content import catalogue, ask

ROOT = Path(__file__).resolve().parent


def make_handler(root, local_only=True, research=False):
    root = Path(root)

    class Handler(BaseHTTPRequestHandler):
        def respond(self, status, payload, mime='application/json; charset=utf-8', download=None):
            body = payload if isinstance(payload, bytes) else payload.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'self'")
            if download:
                self.send_header('Content-Disposition', f'attachment; filename="{download}"')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if local_only and self.headers.get('Host', '').split(':')[0] not in ('localhost', '127.0.0.1'):
                self.respond(403, '{"error":"僅接受本機存取"}')
                return
            parsed = urlsplit(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)
            try:
                if path == '/api/health':
                    self.respond(200, '{"ok":true,"mode":"read-only"}')
                elif path == '/api/public':
                    self.respond(200, json.dumps(catalogue(root), ensure_ascii=False))
                elif research and path == '/api/snapshot':
                    self.respond(200, json.dumps(snapshot(root, query.get('run', [None])[0]), ensure_ascii=False))
                elif research and path == '/api/runs':
                    self.respond(200, json.dumps(list_runs(root), ensure_ascii=False))
                elif research and path == '/api/export.csv':
                    self.respond(200, claims_csv(snapshot(root, query.get('run', [None])[0])), 'text/csv; charset=utf-8', 'claims.csv')
                elif path in ('/', '/index.html', '/app.js', '/style.css', '/favicon.svg'):
                    base = root / 'web/research' if research and path in ('/', '/index.html') else root / 'web'
                    file = base / ('index.html' if path == '/' else path[1:])
                    mime = mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
                    self.respond(200, file.read_bytes(), mime + '; charset=utf-8')
                elif research and path in ('/research/app.js', '/research/style.css'):
                    file = root / 'web' / path[1:]
                    mime = mimetypes.guess_type(file.name)[0]
                    self.respond(200, file.read_bytes(), mime + '; charset=utf-8')
                else:
                    self.respond(404, '{"error":"找不到此資源"}')
            except ValueError as exc:
                self.respond(404, json.dumps({'error': str(exc)}, ensure_ascii=False))
            except (OSError, sqlite3.Error):
                self.respond(503, '{"error":"讀取失敗；請檢查資料檔案或重新執行 run.py"}')

        def do_POST(self):
            if local_only and self.headers.get('Host', '').split(':')[0] not in ('localhost', '127.0.0.1'):
                self.respond(403, '{"error":"僅接受本機存取"}')
                return
            if urlsplit(self.path).path != '/api/ask':
                self.respond(405, '{"error":"網站僅接受問答查詢，請使用命令列維護與審閱"}')
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 8192:
                    raise ValueError('問題內容大小錯誤')
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ValueError('問題格式錯誤')
                result = ask(root, payload.get('question'))
                self.respond(200, json.dumps(result, ensure_ascii=False))
            except (ValueError, UnicodeDecodeError) as error:
                self.respond(400, json.dumps({'error': str(error)}, ensure_ascii=False))
            except OSError:
                self.respond(503, '{"error":"目前無法讀取審閱內容，請稍後再試"}')

    return Handler


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=8501)
    p.add_argument('--strictPort', action='store_true', help=argparse.SUPPRESS)
    p.add_argument('--research', action='store_true', help='僅供研究人員的本機儀表板，含原始測試資料')
    args = p.parse_args()
    if args.research and not db_path(ROOT).exists():
        execute(ROOT, 'mock')
    if not args.research:
        catalogue(ROOT)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(ROOT, args.host == '127.0.0.1', args.research))
    print(f'油品風向標：http://{args.host}:{server.server_port}（唯讀；Ctrl+C 停止）', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
