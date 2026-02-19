/**
 * Test Reporter
 * Generates test reports with screenshots, timing stats, and verification results
 */

class TestReporter {
  constructor(testName) {
    this.testName = testName;
    this.startTime = Date.now();
    this.checkpoints = [];
    this.errors = [];
    this.screenshots = [];
    this.verifications = [];
  }

  /**
   * Record a checkpoint with optional screenshot
   * @param {string} name - Checkpoint name
   * @param {Page} page - Optional page for screenshot
   * @param {boolean} takeScreenshot - Whether to take screenshot
   */
  async checkpoint(name, page = null, takeScreenshot = false) {
    const checkpoint = {
      name,
      timestamp: Date.now(),
      elapsed: Date.now() - this.startTime,
      screenshot: null
    };

    if (takeScreenshot && page) {
      const filename = `checkpoint_${this.checkpoints.length + 1}_${name.replace(/\s+/g, '_')}.png`;
      try {
        await page.screenshot({ path: filename });
        checkpoint.screenshot = filename;
        this.screenshots.push(filename);
      } catch (e) {
        this.error(`Screenshot failed for ${name}: ${e.message}`);
      }
    }

    this.checkpoints.push(checkpoint);
    console.log(`[${this.formatTime(checkpoint.elapsed)}] ✓ ${name}`);
  }

  /**
   * Record an error
   * @param {string} message - Error message
   * @param {Error} error - Optional error object
   */
  error(message, error = null) {
    const errorRecord = {
      message,
      timestamp: Date.now(),
      elapsed: Date.now() - this.startTime,
      stack: error?.stack || null
    };
    this.errors.push(errorRecord);
    console.log(`[${this.formatTime(errorRecord.elapsed)}] ✗ ERROR: ${message}`);
  }

  /**
   * Record a verification result
   * @param {string} name - Verification name
   * @param {boolean} passed - Whether verification passed
   * @param {string} details - Optional details
   */
  verify(name, passed, details = '') {
    const verification = {
      name,
      passed,
      details,
      timestamp: Date.now()
    };
    this.verifications.push(verification);
    const status = passed ? '✓ PASS' : '✗ FAIL';
    console.log(`[VERIFY] ${status}: ${name}${details ? ` (${details})` : ''}`);
  }

  /**
   * Format milliseconds as MM:SS
   * @param {number} ms - Milliseconds
   * @returns {string} - Formatted time
   */
  formatTime(ms) {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }

  /**
   * Generate final report
   * @returns {object} - Report object
   */
  generateReport() {
    const endTime = Date.now();
    const totalTime = endTime - this.startTime;
    const passedVerifications = this.verifications.filter(v => v.passed).length;
    const totalVerifications = this.verifications.length;

    const report = {
      testName: this.testName,
      startTime: new Date(this.startTime).toISOString(),
      endTime: new Date(endTime).toISOString(),
      totalTimeMs: totalTime,
      totalTimeFormatted: this.formatTime(totalTime),
      status: this.errors.length === 0 && passedVerifications === totalVerifications ? 'PASSED' : 'FAILED',
      summary: {
        checkpoints: this.checkpoints.length,
        errors: this.errors.length,
        verifications: {
          passed: passedVerifications,
          failed: totalVerifications - passedVerifications,
          total: totalVerifications
        },
        screenshots: this.screenshots.length
      },
      checkpoints: this.checkpoints,
      errors: this.errors,
      verifications: this.verifications,
      screenshots: this.screenshots
    };

    return report;
  }

  /**
   * Print report summary to console
   */
  printSummary() {
    const report = this.generateReport();

    console.log('\n' + '='.repeat(60));
    console.log(`TEST REPORT: ${report.testName}`);
    console.log('='.repeat(60));
    console.log(`Status: ${report.status}`);
    console.log(`Duration: ${report.totalTimeFormatted}`);
    console.log(`Checkpoints: ${report.summary.checkpoints}`);
    console.log(`Verifications: ${report.summary.verifications.passed}/${report.summary.verifications.total} passed`);
    console.log(`Errors: ${report.summary.errors}`);
    console.log(`Screenshots: ${report.summary.screenshots}`);

    if (report.errors.length > 0) {
      console.log('\nErrors:');
      report.errors.forEach((e, i) => {
        console.log(`  ${i + 1}. ${e.message}`);
      });
    }

    if (report.summary.verifications.failed > 0) {
      console.log('\nFailed Verifications:');
      report.verifications.filter(v => !v.passed).forEach((v, i) => {
        console.log(`  ${i + 1}. ${v.name}${v.details ? `: ${v.details}` : ''}`);
      });
    }

    console.log('='.repeat(60) + '\n');

    return report;
  }

  /**
   * Generate markdown report
   * @returns {string} - Markdown formatted report
   */
  toMarkdown() {
    const report = this.generateReport();

    let md = `# Test Report: ${report.testName}\n\n`;
    md += `**Status:** ${report.status}\n`;
    md += `**Duration:** ${report.totalTimeFormatted}\n`;
    md += `**Date:** ${report.startTime}\n\n`;

    md += `## Summary\n\n`;
    md += `| Metric | Value |\n`;
    md += `|--------|-------|\n`;
    md += `| Checkpoints | ${report.summary.checkpoints} |\n`;
    md += `| Verifications | ${report.summary.verifications.passed}/${report.summary.verifications.total} passed |\n`;
    md += `| Errors | ${report.summary.errors} |\n`;
    md += `| Screenshots | ${report.summary.screenshots} |\n\n`;

    md += `## Checkpoints\n\n`;
    md += `| # | Name | Time | Screenshot |\n`;
    md += `|---|------|------|------------|\n`;
    report.checkpoints.forEach((c, i) => {
      md += `| ${i + 1} | ${c.name} | ${this.formatTime(c.elapsed)} | ${c.screenshot || '-'} |\n`;
    });
    md += '\n';

    if (report.verifications.length > 0) {
      md += `## Verifications\n\n`;
      md += `| Name | Status | Details |\n`;
      md += `|------|--------|--------|\n`;
      report.verifications.forEach(v => {
        md += `| ${v.name} | ${v.passed ? '✓' : '✗'} | ${v.details || '-'} |\n`;
      });
      md += '\n';
    }

    if (report.errors.length > 0) {
      md += `## Errors\n\n`;
      report.errors.forEach((e, i) => {
        md += `${i + 1}. **${e.message}**\n`;
        if (e.stack) {
          md += `   \`\`\`\n   ${e.stack}\n   \`\`\`\n`;
        }
      });
    }

    return md;
  }
}

module.exports = { TestReporter };
