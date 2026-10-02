// Test app for node_deploy. GET / answers with the GREETING from container.env
// and how often the app has started, which it counts in /data: a count that
// grows across restarts proves the data directory is kept.
const fs = require('node:fs');
const http = require('node:http');

const countFile = '/data/starts';
const starts = (fs.existsSync(countFile) ? Number(fs.readFileSync(countFile, 'utf8')) : 0) + 1;
fs.writeFileSync(countFile, String(starts));

http
  .createServer((request, response) => {
    response.setHeader('content-type', 'application/json');
    response.end(JSON.stringify({ greeting: process.env.GREETING, starts }));
  })
  .listen(process.env.PORT || 3000);
