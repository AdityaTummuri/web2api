/**
 * build.js - Web2API Firefox / Zen Extension Packager
 * Generates web2api-firefox.xpi and prepares dist/firefox/
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const EXT_DIR = __dirname;
const DIST_DIR = path.join(EXT_DIR, 'dist', 'firefox');
const XPI_OUT = path.join(EXT_DIR, 'web2api-firefox.xpi');

console.log('🚀 Building Web2API Firefox / Zen Extension...');

// 1. Validate manifest
const manifestPath = path.join(EXT_DIR, 'manifest.json');
const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
console.log(`✓ Validated manifest.json (v${manifest.version})`);

// 2. Prepare dist/firefox directory
if (fs.existsSync(DIST_DIR)) {
  fs.rmSync(DIST_DIR, { recursive: true, force: true });
}
fs.mkdirSync(DIST_DIR, { recursive: true });

const filesToCopy = [
  'manifest.json',
  'background.js',
  'content.js',
  'parser.js',
  'popup.html',
  'popup.js',
  'popup.css'
];

for (const file of filesToCopy) {
  const src = path.join(EXT_DIR, file);
  const dest = path.join(DIST_DIR, file);
  fs.copyFileSync(src, dest);
}

// Copy icons
const iconsSrcDir = path.join(EXT_DIR, 'icons');
const iconsDestDir = path.join(DIST_DIR, 'icons');
fs.mkdirSync(iconsDestDir, { recursive: true });

for (const icon of fs.readdirSync(iconsSrcDir)) {
  fs.copyFileSync(path.join(iconsSrcDir, icon), path.join(iconsDestDir, icon));
}
console.log(`✓ Copied extension assets to dist/firefox/`);

// 3. Create .xpi (zip) file
if (fs.existsSync(XPI_OUT)) {
  fs.unlinkSync(XPI_OUT);
}

try {
  // Zip inside DIST_DIR
  execSync(`zip -r -q "${XPI_OUT}" *`, { cwd: DIST_DIR });
  console.log(`✓ Packaged extension into: ${XPI_OUT}`);
} catch (err) {
  console.error('Failed to create .xpi using zip:', err.message);
  process.exit(1);
}

console.log('\n🎉 Web2API Firefox / Zen extension build complete!');
console.log('\nTo use in Zen Browser:');
console.log('  1. Navigate to: about:debugging#/runtime/this-firefox');
console.log('  2. Click "Load Temporary Add-on..."');
console.log(`  3. Select: ${path.join(EXT_DIR, 'manifest.json')}`);
console.log(`     (or install the packaged file: ${XPI_OUT})`);
