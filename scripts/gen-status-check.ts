#!/usr/bin/env npx tsx
/**
 * Generates the SQL CHECK constraint for pa_submissions.status
 * from the shared PA_STATUSES array. Run after adding a new status
 * to packages/shared/src/pa-submission.ts.
 *
 * Usage: npx tsx scripts/gen-status-check.ts
 */
import { PA_STATUSES } from "@authmatic/shared";

const values = PA_STATUSES.map((s) => `'${s}'`).join(",\n    ");
console.log(`-- Auto-generated from PA_STATUSES (packages/shared/src/pa-submission.ts)`);
console.log(`ALTER TABLE pa_submissions DROP CONSTRAINT IF EXISTS pa_submissions_status_check;`);
console.log(`ALTER TABLE pa_submissions`);
console.log(`  ADD CONSTRAINT pa_submissions_status_check`);
console.log(`  CHECK (status IN (`);
console.log(`    ${values}`);
console.log(`  ));`);
