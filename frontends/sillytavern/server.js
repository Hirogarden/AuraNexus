const http = require('http');
const port = process.env.PORT || 3000;

const server = http.createServer((req, res) => {
  res.writeHead(200, { 'Content-Type': 'text/html' });
  res.end('<h1>SillyTavern Stub</h1><p>This is a placeholder UI.</p>');
});

server.listen(port, () => console.log(`SillyTavern stub listening on ${port}`));
