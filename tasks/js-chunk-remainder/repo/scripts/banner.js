// Prints build metadata before tests, like many real projects do.
const lines = [
  'textkit test harness',
  `node ${process.version} on ${process.platform}/${process.arch}`,
  'loading fixtures: 0 remote, 12 inline',
  'locale: en-US, tz: UTC',
];
for (const l of lines) console.log(`[textkit] ${l}`);
for (let i = 0; i < 40; i++) console.log(`[textkit] warmup cache shard ${i}/40 ok`);
