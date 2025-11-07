
from aiohttp import web
import logging
from collections import deque
import asyncio

class ConsoleHandler(logging.Handler):
    def __init__(self, maxlen=1000):
        super().__init__()
        self.logs = deque(maxlen=maxlen)
        self.clients = set()
        
    def emit(self, record):
        log_entry = self.format(record)
        self.logs.append(log_entry)
        
        for client in self.clients.copy():
            try:
                client.put_nowait(log_entry)
            except:
                self.clients.discard(client)
    
    def get_all_logs(self):
        return list(self.logs)

console_handler = ConsoleHandler()

async def console_page(request):
    html = """
    <!DOCTYPE html>
    <html dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Web Console - لوحة التحكم</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                font-family: 'Courier New', monospace;
                background: #1e1e1e;
                color: #d4d4d4;
                padding: 20px;
            }
            .header {
                background: #2d2d30;
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 20px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            h1 {
                color: #4ec9b0;
                font-size: 24px;
            }
            .clear-btn {
                background: #c5351f;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                cursor: pointer;
                font-size: 14px;
            }
            .clear-btn:hover {
                background: #e04433;
            }
            .console {
                background: #1e1e1e;
                border: 2px solid #3c3c3c;
                border-radius: 5px;
                padding: 15px;
                min-height: 500px;
                max-height: 70vh;
                overflow-y: auto;
                font-size: 14px;
                line-height: 1.6;
            }
            .log-entry {
                padding: 5px 0;
                border-bottom: 1px solid #2d2d30;
            }
            .log-entry:last-child {
                border-bottom: none;
            }
            .log-info {
                color: #4ec9b0;
            }
            .log-warning {
                color: #ce9178;
            }
            .log-error {
                color: #f48771;
            }
            .log-debug {
                color: #9cdcfe;
            }
            .status {
                display: inline-block;
                width: 10px;
                height: 10px;
                border-radius: 50%;
                background: #4ec9b0;
                margin-left: 10px;
                animation: pulse 2s infinite;
            }
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🖥️ لوحة عرض Console</h1>
            <div>
                <span class="status"></span>
                <button class="clear-btn" onclick="clearConsole()">مسح السجل</button>
            </div>
        </div>
        <div class="console" id="console"></div>
        
        <script>
            const consoleDiv = document.getElementById('console');
            
            function addLog(text) {
                const entry = document.createElement('div');
                entry.className = 'log-entry';
                
                if (text.includes('ERROR') || text.includes('CRITICAL')) {
                    entry.classList.add('log-error');
                } else if (text.includes('WARNING')) {
                    entry.classList.add('log-warning');
                } else if (text.includes('DEBUG')) {
                    entry.classList.add('log-debug');
                } else {
                    entry.classList.add('log-info');
                }
                
                entry.textContent = text;
                consoleDiv.appendChild(entry);
                consoleDiv.scrollTop = consoleDiv.scrollHeight;
            }
            
            function clearConsole() {
                consoleDiv.innerHTML = '';
            }
            
            async function connectSSE() {
                try {
                    const response = await fetch('/console/stream');
                    const reader = response.body.getReader();
                    const decoder = new TextDecoder();
                    
                    while (true) {
                        const {value, done} = await reader.read();
                        if (done) break;
                        
                        const text = decoder.decode(value);
                        const lines = text.split('\\n\\n');
                        
                        for (let line of lines) {
                            if (line.startsWith('data: ')) {
                                const log = line.substring(6);
                                if (log.trim()) {
                                    addLog(log);
                                }
                            }
                        }
                    }
                } catch (error) {
                    console.error('Connection error:', error);
                    setTimeout(connectSSE, 3000);
                }
            }
            
            fetch('/console/history')
                .then(response => response.json())
                .then(logs => {
                    logs.forEach(log => addLog(log));
                    connectSSE();
                });
        </script>
    </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')

async def console_history(request):
    logs = console_handler.get_all_logs()
    return web.json_response(logs)

async def console_stream(request):
    response = web.StreamResponse()
    response.headers['Content-Type'] = 'text/event-stream'
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    await response.prepare(request)
    
    queue = asyncio.Queue()
    console_handler.clients.add(queue)
    
    try:
        while True:
            log_entry = await queue.get()
            await response.write(f'data: {log_entry}\n\n'.encode('utf-8'))
    except Exception:
        pass
    finally:
        console_handler.clients.discard(queue)
    
    return response

def setup_console_routes(app):
    app.router.add_get('/console', console_page)
    app.router.add_get('/console/history', console_history)
    app.router.add_get('/console/stream', console_stream)
