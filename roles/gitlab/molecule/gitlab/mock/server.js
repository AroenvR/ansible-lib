// The stand-in's GitLab (see Containerfile): reads its settings as GitLab does,
// records what it found in /var/opt/gitlab/mock-start.json, creates
// /etc/gitlab/gitlab-secrets.json once, answers every request with a redirect to
// the sign-in page, as GitLab answers /, and, once it listens, writes the health
// check's settings, as GitLab's setup does at the end of every start.
const fs = require('fs');
const http = require('http');

const config = process.env.GITLAB_OMNIBUS_CONFIG || '';
const file = (config.match(/^from_file\('([^']+)'\)$/) || [])[1];
const settings = file ? fs.readFileSync(file, 'utf8') : '';
const url = new URL((settings.match(/^external_url '([^']+)'$/m) || [])[1]);

if (!fs.existsSync('/etc/gitlab/gitlab-secrets.json')) {
  fs.writeFileSync('/etc/gitlab/gitlab-secrets.json', '{}\n', { mode: 0o600 });
}
fs.writeFileSync('/var/opt/gitlab/mock-start.json', `${JSON.stringify({ uid: process.getuid(), config, url: url.href })}\n`);

process.on('SIGTERM', () => process.exit(0));
http.createServer((request, response) => {
  response.writeHead(302, { Location: `${url.origin}/users/sign_in` });
  response.end();
}).listen(Number(url.port), () => {
  fs.writeFileSync('/opt/gitlab/etc/gitlab-healthcheck-rc', `url='${url.origin}/help'\nflags='--silent'\n`);
});
