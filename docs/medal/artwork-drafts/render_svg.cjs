// Local review rasterization only. No production dependencies or assets changed.
const fs = require('node:fs');
const path = require('node:path');
const sharp = require(process.argv[2] || 'sharp');
const inputDir = process.argv[3];
const outputDir = process.argv[4];
const sizes = [32, 40, 48, 64, 72, 128, 160];
(async () => {
  for (const file of fs.readdirSync(inputDir).filter(f => f.endsWith('.svg'))) {
    const svg = fs.readFileSync(path.join(inputDir, file), 'utf8');
    const slug = path.basename(file, '.svg');
    for (const [theme, ink] of [['light', '#475569'], ['dark', '#CBD5E1']]) {
      const buffer = Buffer.from(svg.replace('color="#475569"', `color="${ink}"`));
      for (const size of sizes) {
        await sharp(buffer, { density: 300 }).resize(size, size).png().toFile(path.join(outputDir, `${slug}-${theme}-${size}.png`));
      }
    }
  }
})().catch(err => { console.error(err); process.exitCode = 1; });
