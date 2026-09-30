// Manual integration check: node tests/verify_ai_parser.cjs <parser.js> <category-ai-!cn.list>
// Inputs are downloaded separately; the normal unit suite remains offline.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const [parserPath, rulesPath] = process.argv.slice(2);
assert(parserPath && rulesPath, 'Provide the KOP-XIAO parser and the MetaCubeX AI list');
const config = fs.readFileSync(path.join(__dirname, '../src/quanx/50-filter-remote.conf'), 'utf8');
const resource = config.split('\n').find(line => line.includes('force-policy=🤖 AI'));
assert(resource.includes('opt-parser=true'));
const input = fs.readFileSync(rulesPath, 'utf8');
let output;
vm.runInNewContext(fs.readFileSync(parserPath, 'utf8'), {
  $resource: {link: resource.split(',')[0], content: input, type: 'filter', tag: 'AI'},
  $environment: {version: 'v1.8.0 build9999'},
  $notify() {},
  $done(result) { output = result.content; },
  console,
}, {timeout: 10000});
const domains = input.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
assert(domains.length > 0);
const actual = output.trim().split('\n').map(line => line.split(',').map(part => part.trim()));
assert.equal(actual.length, domains.length, 'Every upstream domain must survive conversion');
domains.forEach((domain, index) => {
  const suffix = domain.startsWith('+.');
  assert.equal(actual[index][0], suffix ? 'host-suffix' : 'host');
  assert.equal(actual[index][1], suffix ? domain.slice(2) : domain);
  assert.equal(actual[index][3], 'via-interface=%TUN%');
});
// QX applies force-policy=🤖 AI after the parser returns its rules.
function matches(domain) {
  return actual.some(([type, value]) => domain === value ||
    (type === 'host-suffix' && domain.endsWith('.' + value)));
}
for (const domain of ['api.openai.com', 'claude.ai', 'clau.de', 'platform.claude.com',
  'bridge.claudeusercontent.com', 'gemini.google.com', 'generativelanguage.googleapis.com',
  'perplexity.ai', 'pplx.ai', 'poecdn.net', 'copilot.microsoft.com', 'api.githubcopilot.com',
  'cursor.com', 'grok.com']) {
  assert(matches(domain), `Missing AI service: ${domain}`);
}
for (const domain of ['claude.example.com', 'openai.example.com', 'www.google.com', 'github.com']) {
  assert(!matches(domain), `Unrelated domain matched: ${domain}`);
}
console.log(`PASS: ${domains.length} rules preserve matching semantics and TUN; service checks passed`);
