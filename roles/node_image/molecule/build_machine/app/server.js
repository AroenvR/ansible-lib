// Test app: answers with the results of its native addon and its build script.
const http = require('http');
const addon = require('./build/Release/addon.node');
const buildInfo = require('./build-info.json');

http
  .createServer((request, response) => {
    response.setHeader('Content-Type', 'application/json');
    response.end(JSON.stringify({ addon: addon.hello(), build: buildInfo, nodeEnv: process.env.NODE_ENV }));
  })
  .listen(Number(process.env.PORT), '0.0.0.0');
