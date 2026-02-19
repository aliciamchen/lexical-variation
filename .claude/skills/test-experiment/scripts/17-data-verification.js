/**
 * Data Verification Script
 * Verifies that exported data contains all required fields and correct values
 *
 * Run after: empirica export (generates a zip file)
 * Unzip first, then run verification on the extracted directory
 * Checks: game.csv, player.csv, round.csv, playerRound.csv
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// Required fields for each CSV file
const REQUIRED_FIELDS = {
  'game.csv': [
    'condition',
    'tangram_set'
  ],
  'player.csv': [
    'participantID',  // Note: capital ID
    'original_group',
    'avatar',
    'name'
  ],
  'round.csv': [
    'phase_num',
    'block_num',
    'target'
  ],
  'playerRound.csv': [
    'role',
    'original_group',
    'current_group',
    'chat',
    'clicked',
    'clicked_correct'
  ]
};

// Additional fields for social_mixed condition
const SOCIAL_MIXED_FIELDS = {
  'playerRound.csv': [
    'social_guess',
    'social_guess_correct'
  ]
};

/**
 * Find the latest export zip file in the experiment directory
 * @param {string} experimentDir - Path to experiment directory
 * @returns {string|null} - Path to latest zip file or null
 */
function findLatestExportZip(experimentDir) {
  const files = fs.readdirSync(experimentDir);
  const zipFiles = files
    .filter(f => f.startsWith('export-') && f.endsWith('.zip'))
    .sort()
    .reverse();

  if (zipFiles.length === 0) return null;
  return path.join(experimentDir, zipFiles[0]);
}

/**
 * Extract a zip file to a directory
 * @param {string} zipPath - Path to zip file
 * @param {string} outputDir - Directory to extract to
 * @returns {string} - Path to extracted directory
 */
function extractZip(zipPath, outputDir) {
  // Create output directory if it doesn't exist
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  // Extract using unzip command
  execSync(`unzip -o "${zipPath}" -d "${outputDir}"`, { stdio: 'pipe' });

  return outputDir;
}

/**
 * Export and extract data, returning the path to CSV files
 * @param {string} experimentDir - Path to experiment directory
 * @returns {string} - Path to extracted CSV directory
 */
function exportAndExtract(experimentDir) {
  // Run empirica export
  console.log('Running empirica export...');
  execSync('empirica export', { cwd: experimentDir, stdio: 'pipe' });

  // Find the latest zip
  const zipPath = findLatestExportZip(experimentDir);
  if (!zipPath) {
    throw new Error('No export zip file found');
  }
  console.log(`Found export: ${zipPath}`);

  // Extract to a temporary directory
  const extractDir = path.join(experimentDir, 'export-extracted');
  console.log(`Extracting to: ${extractDir}`);
  extractZip(zipPath, extractDir);

  return extractDir;
}

/**
 * Parse CSV file into array of objects
 * Uses a proper CSV parser to handle embedded commas and quotes
 * @param {string} filePath - Path to CSV file
 * @returns {object[]} - Array of row objects
 */
function parseCSV(filePath) {
  const content = fs.readFileSync(filePath, 'utf-8');
  const lines = content.trim().split('\n');
  if (lines.length === 0) return [];

  // Parse header line
  const headers = parseCSVLine(lines[0]);
  const rows = [];

  for (let i = 1; i < lines.length; i++) {
    const values = parseCSVLine(lines[i]);
    const row = {};
    headers.forEach((h, idx) => {
      row[h] = values[idx] || '';
    });
    rows.push(row);
  }

  return rows;
}

/**
 * Parse a single CSV line handling quoted fields with embedded commas
 * @param {string} line - CSV line
 * @returns {string[]} - Array of field values
 */
function parseCSVLine(line) {
  const fields = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];

    if (char === '"') {
      if (inQuotes && line[i + 1] === '"') {
        // Escaped quote
        current += '"';
        i++;
      } else {
        // Toggle quote mode
        inQuotes = !inQuotes;
      }
    } else if (char === ',' && !inQuotes) {
      fields.push(current.trim());
      current = '';
    } else {
      current += char;
    }
  }

  fields.push(current.trim());
  return fields;
}

/**
 * Verify data export contains required fields
 * @param {string} exportDir - Path to export directory
 * @param {string} condition - Expected condition (for social_mixed checks)
 * @returns {object} - Verification results
 */
function verifyDataExport(exportDir, condition = null) {
  const results = {
    passed: true,
    checks: [],
    errors: [],
    warnings: []
  };

  // Check each required file
  for (const [filename, fields] of Object.entries(REQUIRED_FIELDS)) {
    const filePath = path.join(exportDir, filename);

    // Check file exists
    if (!fs.existsSync(filePath)) {
      results.passed = false;
      results.errors.push(`Missing file: ${filename}`);
      results.checks.push({ name: `File exists: ${filename}`, passed: false });
      continue;
    }
    results.checks.push({ name: `File exists: ${filename}`, passed: true });

    // Parse file
    const rows = parseCSV(filePath);
    if (rows.length === 0) {
      results.warnings.push(`Empty file: ${filename}`);
      continue;
    }

    // Check required fields exist
    const firstRow = rows[0];
    for (const field of fields) {
      const hasField = field in firstRow;
      results.checks.push({
        name: `${filename} has field: ${field}`,
        passed: hasField
      });
      if (!hasField) {
        results.passed = false;
        results.errors.push(`Missing field '${field}' in ${filename}`);
      }
    }

    // Check social_mixed specific fields
    if (condition === 'social_mixed' && SOCIAL_MIXED_FIELDS[filename]) {
      for (const field of SOCIAL_MIXED_FIELDS[filename]) {
        const hasField = field in firstRow;
        results.checks.push({
          name: `${filename} has social field: ${field}`,
          passed: hasField
        });
        if (!hasField) {
          results.passed = false;
          results.errors.push(`Missing social field '${field}' in ${filename}`);
        }
      }
    }
  }

  return results;
}

/**
 * Verify chat messages have timestamps
 * @param {string} exportDir - Path to export directory
 * @returns {object} - Verification results
 */
function verifyChatTimestamps(exportDir) {
  const results = {
    passed: true,
    messagesChecked: 0,
    messagesWithTimestamp: 0,
    errors: []
  };

  const playerRoundPath = path.join(exportDir, 'playerRound.csv');
  if (!fs.existsSync(playerRoundPath)) {
    results.passed = false;
    results.errors.push('playerRound.csv not found');
    return results;
  }

  const rows = parseCSV(playerRoundPath);
  for (const row of rows) {
    if (row.chat && row.chat.length > 2) {
      results.messagesChecked++;
      try {
        // Chat is JSON - check for timestamp field
        const chatData = JSON.parse(row.chat);
        if (Array.isArray(chatData)) {
          for (const msg of chatData) {
            if (msg.timestamp) {
              results.messagesWithTimestamp++;
            }
          }
        } else if (chatData.timestamp) {
          results.messagesWithTimestamp++;
        }
      } catch (e) {
        // Not JSON, might be empty or different format
      }
    }
  }

  if (results.messagesChecked > 0 && results.messagesWithTimestamp === 0) {
    results.passed = false;
    results.errors.push('No chat messages have timestamps');
  }

  return results;
}

/**
 * Verify group assignments are correct
 * @param {string} exportDir - Path to export directory
 * @param {number} expectedPlayers - Expected number of players
 * @returns {object} - Verification results
 */
function verifyGroupAssignments(exportDir, expectedPlayers = 3) {
  const results = {
    passed: true,
    players: 0,
    groups: new Set(),
    errors: []
  };

  const playerPath = path.join(exportDir, 'player.csv');
  if (!fs.existsSync(playerPath)) {
    results.passed = false;
    results.errors.push('player.csv not found');
    return results;
  }

  const rows = parseCSV(playerPath);
  results.players = rows.length;

  for (const row of rows) {
    if (row.original_group) {
      results.groups.add(row.original_group);
    }
  }

  if (results.players !== expectedPlayers) {
    results.passed = false;
    results.errors.push(`Expected ${expectedPlayers} players, found ${results.players}`);
  }

  const expectedGroups = Math.floor(expectedPlayers / 3);
  if (results.groups.size !== expectedGroups) {
    results.passed = false;
    results.errors.push(`Expected ${expectedGroups} groups, found ${results.groups.size}`);
  }

  return results;
}

/**
 * Verify speaker rotation is balanced
 * @param {string} exportDir - Path to export directory
 * @returns {object} - Verification results
 */
function verifySpeakerRotation(exportDir) {
  const results = {
    passed: true,
    speakerCounts: {},
    errors: []
  };

  const playerRoundPath = path.join(exportDir, 'playerRound.csv');
  if (!fs.existsSync(playerRoundPath)) {
    results.passed = false;
    results.errors.push('playerRound.csv not found');
    return results;
  }

  const rows = parseCSV(playerRoundPath);
  for (const row of rows) {
    if (row.role === 'speaker') {
      const playerKey = row.participantId || row.playerId || 'unknown';
      results.speakerCounts[playerKey] = (results.speakerCounts[playerKey] || 0) + 1;
    }
  }

  // Check if speaker counts are roughly balanced
  const counts = Object.values(results.speakerCounts);
  if (counts.length > 0) {
    const min = Math.min(...counts);
    const max = Math.max(...counts);
    if (max - min > 2) {
      results.warnings = [`Speaker rotation may be unbalanced: min=${min}, max=${max}`];
    }
  }

  return results;
}

/**
 * Run all verifications
 * @param {string} exportDir - Path to export directory
 * @param {object} options - Verification options
 * @returns {object} - All verification results
 */
function runAllVerifications(exportDir, options = {}) {
  const { condition = null, expectedPlayers = 3 } = options;

  console.log(`\nRunning data verification on: ${exportDir}\n`);

  const results = {
    dataExport: verifyDataExport(exportDir, condition),
    chatTimestamps: verifyChatTimestamps(exportDir),
    groupAssignments: verifyGroupAssignments(exportDir, expectedPlayers),
    speakerRotation: verifySpeakerRotation(exportDir)
  };

  // Print summary
  console.log('='.repeat(50));
  console.log('DATA VERIFICATION RESULTS');
  console.log('='.repeat(50));

  let allPassed = true;
  for (const [name, result] of Object.entries(results)) {
    const status = result.passed ? '✓ PASS' : '✗ FAIL';
    console.log(`${name}: ${status}`);
    if (!result.passed) allPassed = false;
    if (result.errors && result.errors.length > 0) {
      result.errors.forEach(e => console.log(`  - ${e}`));
    }
  }

  console.log('='.repeat(50));
  console.log(`Overall: ${allPassed ? 'PASSED' : 'FAILED'}`);
  console.log('='.repeat(50) + '\n');

  return { allPassed, results };
}

module.exports = {
  parseCSV,
  parseCSVLine,
  verifyDataExport,
  verifyChatTimestamps,
  verifyGroupAssignments,
  verifySpeakerRotation,
  runAllVerifications,
  findLatestExportZip,
  extractZip,
  exportAndExtract,
  REQUIRED_FIELDS,
  SOCIAL_MIXED_FIELDS
};

/**
 * MCP Usage:
 *
 * This verification works for ALL conditions:
 * - refer_separated: Checks core fields only
 * - refer_mixed: Checks core fields only
 * - social_mixed: Checks core fields + social_guess fields
 *
 * Steps to verify data after a test:
 *
 * 1. Export data (generates a zip file):
 *    Bash: cd experiment && empirica export
 *
 * 2. Unzip the export:
 *    Bash: unzip -o $(ls -t export-*.zip | head -1) -d export-extracted
 *
 * 3. Run verification:
 *    Bash: node -e "
 *      const { runAllVerifications } = require('./.claude/skills/test-experiment/scripts/17-data-verification.js');
 *      runAllVerifications('./export-extracted', {
 *        condition: 'refer_separated',  // or 'refer_mixed' or 'social_mixed' or null
 *        expectedPlayers: 3             // or 9 for full tests
 *      });
 *    "
 *
 * The 'condition' parameter is OPTIONAL:
 * - If null/undefined: Only checks core required fields
 * - If 'social_mixed': Also checks social_guess and social_guess_correct fields
 */
