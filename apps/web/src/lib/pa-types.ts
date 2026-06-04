/**
 * Re-export of the clinic-form subdomain types from @authmatic/shared.
 *
 * Kept as a local module so existing consumers' `@/lib/pa-types` imports
 * stay valid; new code should import from @authmatic/shared directly.
 */
export type {
  PaStatus,
  PaFormPayload,
  PaSubmission,
  PaSubmissionRow,
  AdjudicationResult,
} from "@authmatic/shared";
export { FORM_FIELDS, STATUS_LABELS } from "@authmatic/shared";
