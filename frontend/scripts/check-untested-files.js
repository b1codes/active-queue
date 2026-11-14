#!/usr/bin/env node
/**
 * Fails when any measured source file contains code but no test ever executed a line of it.
 *
 * A global coverage threshold can still pass while a whole new screen sits at 0%. This
 * makes "nobody wrote a test for this file" a hard failure. Usage:
 *   node scripts/check-untested-files.js coverage/coverage-final.json
 */
const fs = require('fs');
const path = require('path');

const reportPath = process.argv[2] || 'coverage/coverage-final.json';
const report = JSON.parse(fs.readFileSync(reportPath, 'utf8'));

const untested = Object.entries(report)
  .filter(([, file]) => {
    const counts = Object.values(file.s);
    return counts.length > 0 && counts.every((n) => n === 0);
  })
  .map(([file]) => path.relative(process.cwd(), file));

if (untested.length > 0) {
  console.error('Source files with code that no test executes:');
  for (const file of untested) console.error(`  - ${file}`);
  process.exit(1);
}
console.log(`check-untested-files: all ${Object.keys(report).length} measured files are exercised.`);
