// This helper only converts document text. It does not execute source HTML.
const fs = require('node:fs');
const { marked } = require('marked');
const texts = JSON.parse(fs.readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(texts.map(text => marked.parse(text, { gfm: true }))));
