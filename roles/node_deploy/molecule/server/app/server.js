// Test app for node_deploy. GET / answers with its version, the GREETING from
// container.env, a value from its config file (config/app.json, where the deploy
// puts config/production/), the TUNED variable that the test adds to the project's
// Quadlet template, and how often the app has started, which it counts in /data:
// a count that grows across restarts and updates proves the data directory is kept.
const fs = require('node:fs');
const http = require('node:http');
const { version } = require('./package.json');

const config = JSON.parse(fs.readFileSync('config/app.json', 'utf8'));
const countFile = '/data/starts';
const starts = (fs.existsSync(countFile) ? Number(fs.readFileSync(countFile, 'utf8')) : 0) + 1;
fs.writeFileSync(countFile, String(starts));

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
      }),
    );
  })
  .listen(process.env.PORT || 3000);
