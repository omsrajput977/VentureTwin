import fs from 'fs';
import path from 'path';

const FORBIDDEN_STRINGS = [
  '157200',
  '144500',
  '172800',
  '18.8',
  '59.6',
  '20.9',
  '1.16',
  '145 + i',
  'GDP Growth',
  'getDemoResponse'
];

function checkDirectory(dir) {
  let hasErrors = false;
  const entries = fs.readdirSync(dir, { withFileTypes: true });

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name !== 'node_modules' && entry.name !== 'dist' && entry.name !== '.git') {
        if (checkDirectory(fullPath)) hasErrors = true;
      }
    } else if (entry.isFile() && /\.(tsx?|jsx?|html)$/.test(entry.name)) {
      const content = fs.readFileSync(fullPath, 'utf-8');
      for (const forbidden of FORBIDDEN_STRINGS) {
        if (content.includes(forbidden)) {
          console.error(`[ERROR] Forbidden mock literal "${forbidden}" found in ${fullPath}`);
          hasErrors = true;
        }
      }
    }
  }
  return hasErrors;
}

const targetDir = fs.existsSync(path.resolve(process.cwd(), 'src'))
  ? path.resolve(process.cwd(), 'src')
  : path.resolve(process.cwd(), 'ui/src');

if (fs.existsSync(targetDir)) {
  const failed = checkDirectory(targetDir);
  if (failed) {
    console.error('Validation failed: UI contains forbidden hardcoded mock numbers.');
    process.exit(1);
  } else {
    console.log('UI validation passed: No forbidden hardcoded mock numbers found.');
  }
} else {
  console.log('Target src directory does not exist. Skipping check.');
}
