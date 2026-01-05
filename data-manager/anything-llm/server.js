const http = require('http');
const port = process.env.PORT || 8000;

const server = http.createServer((req, res) => {
  if (req.method === 'POST' && req.url.startsWith('/api/ingest')) {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ingested', received: body ? JSON.parse(body) : null }));
    });
    return;
  }
  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ status: 'anythingllm stub', ok: true }));
});

server.listen(port, () => console.log(`AnythingLLM stub listening on ${port}`));
