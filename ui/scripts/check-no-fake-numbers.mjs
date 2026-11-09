import fs from 'fs';
import path from 'path';

// 1. Specific forbidden mock numbers / strings from historical regressions
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

function checkFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf-8');
  const errors = [];
  const lines = content.split('\n');

  // Check 1: Forbidden legacy mock literals
  for (const forbidden of FORBIDDEN_STRINGS) {
    if (content.includes(forbidden)) {
      errors.push(`Forbidden mock literal "${forbidden}"`);
    }
  }

  // Check 2: Math.random() usage
  if (content.includes('Math.random')) {
    errors.push('Forbidden Math.random() detected');
  }

  // Check 3: Static array of "Passed" statuses
  if (/\[\s*["'](?:passed|Passed)["']\s*,\s*["'](?:passed|Passed)["']/.test(content)) {
    errors.push('Forbidden static array of "Passed" statuses detected');
  }

  // Line-by-line checks for fallback values and hardcoded currency
  lines.forEach((line, idx) => {
    const lineNum = idx + 1;
    // Strip comments
    const codeLine = line.replace(/\/\/.*$/, '').replace(/\/\*.*?\*\//g, '');

    // Check 4: Fallback after logical OR with numeric value: || [0-9]
    // Allow || false, || true, || null, || undefined, || '', || []
    // Exclude FailureInjectorModal's parseInt/min input floor e.g. parseInt(...) || 1
    if (!filePath.endsWith('FailureInjectorModal.tsx')) {
      const fallbackNumMatch = codeLine.match(/\|\|\s*([0-9]+(?:\.[0-9]+)?)/);
      if (fallbackNumMatch) {
        errors.push(`Line ${lineNum}: Forbidden numeric fallback "${fallbackNumMatch[0]}"`);
      }
    }

    // Check 5: Hardcoded currency in component templates (e.g. $100, $500, $50k)
    // Matches $ followed by digit, excluding template string expressions `${...}`
    const currencyMatch = codeLine.match(/(?<!\\)(?<!\{)\$([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?|[0-9]+k?)(?!\w)/i);
    if (currencyMatch && !codeLine.includes('${')) {
      errors.push(`Line ${lineNum}: Hardcoded currency figure "${currencyMatch[0]}"`);
    }
  });

  return errors;
}

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
      const fileErrors = checkFile(fullPath);
      if (fileErrors.length > 0) {
        hasErrors = true;
        for (const err of fileErrors) {
          console.error(`[ERROR] in ${fullPath}: ${err}`);
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
    console.error('Validation failed: UI contains forbidden hardcoded mock numbers, fallbacks, or statuses.');
    process.exit(1);
  } else {
    console.log('UI validation passed: No forbidden hardcoded mock numbers found.');
  }
} else {
  console.log('Target src directory does not exist. Skipping check.');
}
