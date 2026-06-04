/**
 * NPI (National Provider Identifier) validation (ticket 0031).
 *
 * An NPI is 10 digits whose last digit is a Luhn check digit computed over
 * the constant prefix "80840" + the first 9 digits (CMS spec). We reject
 * anything that doesn't validate rather than substituting a literal — a wrong
 * NPI on a real payer submission is at best an instant denial, at worst fraud.
 */

/** Luhn checksum: true if the all-digit string passes mod-10. */
function luhnValid(digits: string): boolean {
  let sum = 0;
  let double = false;
  for (let i = digits.length - 1; i >= 0; i--) {
    let d = digits.charCodeAt(i) - 48;
    if (d < 0 || d > 9) return false;
    if (double) {
      d *= 2;
      if (d > 9) d -= 9;
    }
    sum += d;
    double = !double;
  }
  return sum % 10 === 0;
}

/** True if `npi` is a syntactically valid NPI with a correct check digit. */
export function isValidNpi(npi: string | null | undefined): boolean {
  if (!npi || !/^\d{10}$/.test(npi)) return false;
  // Luhn over "80840" + the full 10-digit NPI (prefix makes it a 15-digit
  // ISO-7812 number whose check digit is the NPI's 10th digit).
  return luhnValid("80840" + npi);
}
