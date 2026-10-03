// Test app for node_deploy, built to dist/main.js like a NestJS app. It runs in the
// service's directory on the server and uses paths relative to it, as apps do:
// it reads config/app.json, counts its starts in data/starts and writes app.state
// next to config/. GET / answers with its version, the GREETING from container.env,
// a value from the config file, the TUNED variable the test adds to the project's
// Quadlet template, the start count, its working directory and the size of /tmp.
const fs = require('node:fs');
const http = require('node:http');
const os = require('node:os');
const { version } = require('../package.json');

const config = JSON.parse(fs.readFileSync('config/app.json', 'utf8'));
const countFile = 'data/starts';
const starts = (fs.existsSync(countFile) ? Number(fs.readFileSync(countFile, 'utf8')) : 0) + 1;
fs.writeFileSync(countFile, String(starts));
fs.writeFileSync('app.state', `started ${starts} times\n`);
const tmp = fs.statfsSync(os.tmpdir());

http
  .createServer((request, response) => {
    response.setHeader('content-type', 'application/json');
    response.end(
      JSON.stringify({
        version,
        greeting: process.env.GREETING,
        config: config.source,
        tuned: process.env.TUNED,
        starts,
        cwd: process.cwd(),
        tmpBytes: tmp.blocks * tmp.bsize,
      }),
    );
  })
  .listen(process.env.PORT || 3000);
