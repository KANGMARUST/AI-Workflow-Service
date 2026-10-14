"""Temporary browser QA API with fictional quotes. Never connects to stored data."""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def send_json(self, payload):
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == '/api/health':
            self.send_json({'ok': True})
        elif self.path == '/api/quotes':
            self.send_json([])
        elif self.path == '/api/stats':
            self.send_json({'quote_count': 0, 'pending_count': 0, 'customer_count': 0, 'item_count': 0})
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != '/api/natural-search':
            self.send_error(404)
            return
        request = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
        trend = '추이' in request.get('question', '')
        answer = ('가상 견적의 원본 단가 추이야.\n\n'
                  '| 작성일 | 원본 단가 | 근거 |\n| --- | ---: | --- |\n'
                  '| 2026-09-01 | 12,000원 | [1] |\n| 2026-10-02 | 13,000원 | [2] |\n\n'
                  '날짜별 원본 값만 표시했어.' if trend else
                  '가상 견적 세 건에서 확인된 값이야.\n\n'
                  '| 품목 | 원본 단가 | 근거 |\n| --- | ---: | --- |\n'
                  '| 브라켓 | 12,000원 | [1] |\n| 모터 | 15,000원 | [2] |\n'
                  '| 센서 | 미기재 | [3] |\n\n'
                  '센서 단가는 원본에 적혀 있지 않아.')
        self.send_json({
            'answer': answer,
            'quotes': [{'id': 'test-1', 'project_name': '가상 견적 A'},
                       {'id': 'test-2', 'project_name': '가상 견적 B'},
                       {'id': 'test-3', 'project_name': '가상 견적 C'}],
            'method': 'upstage-solar', 'model': 'solar-pro4',
            'usage': {'prompt_tokens': 120, 'completion_tokens': 30, 'total_tokens': 150},
            'scope_note': '가상 견적 3건의 저장 정보를 검토했습니다.',
        })

    def log_message(self, *_args):
        pass


if __name__ == '__main__':
    HTTPServer(('127.0.0.1', 8001), Handler).serve_forever()
