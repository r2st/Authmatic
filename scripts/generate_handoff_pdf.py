#!/usr/bin/env python3
"""Generate Authmatic team handoff PDF for backend teammate."""

from fpdf import FPDF
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "authmatic-team-handoff.pdf"


class HandoffPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, "Authmatic - Team Handoff Report", align="R")
        self.ln(4)
        self.set_draw_color(200, 200, 200)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}  |  Applied Intelligence Hackathon  |  May 31, 2026", align="C")

    def section(self, title: str):
        self.ln(4)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(12, 45, 74)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(26, 95, 138)
        self.line(10, self.get_y(), 80, self.get_y())
        self.ln(4)

    def body(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5.5, text)
        self.ln(2)

    def bullet(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        x = self.get_x()
        self.cell(5, 5.5, "-")
        self.multi_cell(0, 5.5, text)
        self.set_x(x)

    def code_block(self, text: str):
        self.set_font("Courier", "", 8.5)
        self.set_fill_color(245, 247, 250)
        self.set_text_color(20, 20, 20)
        for line in text.split("\n"):
            self.cell(0, 4.8, "  " + line, new_x="LMARGIN", new_y="NEXT", fill=True)
        self.ln(3)

    def table_row(self, cols: list[str], widths: list[int], header: bool = False):
        if header:
            self.set_font("Helvetica", "B", 9)
            self.set_fill_color(232, 242, 248)
        else:
            self.set_font("Helvetica", "", 9)
            self.set_fill_color(255, 255, 255)
        self.set_text_color(30, 30, 30)
        h = 7
        for col, w in zip(cols, widths):
            self.cell(w, h, col, border=1, fill=True)
        self.ln(h)


def build():
    pdf = HandoffPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(12, 45, 74)
    pdf.cell(0, 12, "Authmatic Team Handoff", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 7, "Prior-Auth Killer  |  For backend / agent integration", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.body(
        "This report summarizes what is built, what the mock HealthFirst payer portal "
        "expects from the agent, and what still needs to be wired (FastAPI agent, sponsor APIs). "
        "Demo patient: Sarah Martinez  |  Ozempic  |  HealthFirst PPO."
    )

    # --- DONE ---
    pdf.section("1. What we have (built)")
    pdf.bullet("Demo PDFs: assets/demo/patient_chart_sarah_martinez.pdf + prescription_ozempic_martinez.pdf")
    pdf.bullet("Mock data: fixtures/healthfirst-case.json (all extractable fields + workflow API paths)")
    pdf.bullet("Next.js app: apps/web (runs on port 3000)")
    pdf.bullet("Mock HealthFirst prior-auth form: /portal/healthfirst/prior-auth")
    pdf.bullet("Realistic PA workflow - submit does NOT auto-approve:")
    pdf.bullet("  Submit -> status pending_review -> agent calls adjudicate -> under_review -> approved/denied")
    pdf.bullet("Status page (polls live): /portal/healthfirst/submission/{reference_id}")
    pdf.bullet("Portal APIs (in apps/web, ready for agent to call):")
    pdf.code_block(
        "POST /api/pa/submit          -> creates PA, returns reference_id (pending)\n"
        "GET  /api/pa/{ref}           -> current status + form payload\n"
        "POST /api/pa/{ref}/adjudicate -> runs payer medical review (~8s) -> approved/denied"
    )
    pdf.bullet("Planning docs: spec.md, architecture.md, implementation.md, demo.md, risks.md")
    pdf.bullet("Pitch deck: presentation.html (Opsera / Daytona / Insforge / Rtrvr 4-verb story)")

    pdf.section("2. Mock portal - form fields (Rtrvr must use these IDs)")
    widths = [45, 145]
    pdf.table_row(["Field ID", "Sarah Martinez demo value"], widths, header=True)
    rows = [
        ("patient_name", "Sarah Martinez"),
        ("dob", "03/14/1986"),
        ("member_id", "HF45821973"),
        ("diagnosis", "Type 2 Diabetes (E11.9)"),
        ("medication", "Ozempic"),
        ("dosage", "0.25mg weekly"),
        ("provider_name", "Emily Chen, MD"),
        ("justification", "Poor glycemic control despite first-line therapy"),
    ]
    for a, b in rows:
        pdf.table_row([a, b], widths)
    pdf.ln(2)
    pdf.body("Submit button id: submit-prior-auth  |  Form action: POST /api/pa/submit")
    pdf.body("PORTAL_URL (set in .env): http://localhost:3000/portal/healthfirst/prior-auth")

    pdf.add_page()
    pdf.section("3. Agent loop - what backend must implement")
    pdf.body(
        "apps/agent (FastAPI) does not exist yet - only README. Teammate builds this. "
        "Suggested steps aligned with pitch deck + mock portal:"
    )
    widths2 = [28, 22, 30, 110]
    pdf.table_row(["Step", "Verb", "Sponsor", "Action"], widths2, header=True)
    steps = [
        ("1", "READ-WEB", "Rtrvr", "Optional: fetch payer rules (or skip - we host mock portal)"),
        ("2", "EXECUTE", "Daytona", "Parse PDFs in sandbox (pdfplumber); fallback: healthfirst-case.json"),
        ("3", "VERIFY", "Opsera", "MCP scan_pii on outgoing packet before submit"),
        ("4", "READ-WEB", "Rtrvr", "Fill mock portal form + click Submit; capture reference_id from URL"),
        ("5", "API call", "Web app", "POST /api/pa/{ref}/adjudicate - triggers payer review"),
        ("6", "PERSIST", "Insforge", "Store run, agent_events, receipt_url, reference_id"),
    ]
    for row in steps:
        pdf.table_row(list(row), widths2)
    pdf.ln(3)

    pdf.body("Required FastAPI endpoints (apps/agent):")
    pdf.code_block(
        "POST /api/run              <- dropzone uploads chart + rx PDFs, returns run_id\n"
        "GET  /api/stream/{run_id}  <- SSE: stream each agent step to UI\n"
        "GET  /api/run/{run_id}     <- full audit payload for /run/{id} page\n"
        "GET  /health               <- smoke test"
    )

    pdf.section("4. Rtrvr task (copy-paste shape)")
    pdf.code_block(
        'task = (\n'
        '  f"Open {PORTAL_URL}. Fill the prior authorization form: "\n'
        '  f"patient_name={fields[\'patient_name\']}, "\n'
        '  f"dob={fields[\'dob\']}, member_id={fields[\'member_id\']}, "\n'
        '  f"diagnosis={fields[\'diagnosis\']}, medication={fields[\'medication\']}, "\n'
        '  f"dosage={fields[\'dosage\']}, provider_name={fields[\'provider_name\']}, "\n'
        '  f"justification={fields[\'justification\']}. "\n'
        '  "Click Submit Prior Authorization. "\n'
        '  "Return the reference_id from the submission page URL."\n'
        ')\n'
        '# After Rtrvr returns reference_id:\n'
        '# POST {WEB_URL}/api/pa/{reference_id}/adjudicate  body: {"review_delay_ms": 8000}'
    )

    pdf.section("5. What still needs to be built")
    pdf.body("YOU (frontend) - remaining:")
    pdf.bullet("Dropzone UI on / (upload chart + prescription)")
    pdf.bullet("/run/[id] audit page with SSE step cards + receipt banner")
    pdf.bullet("Deploy apps/web to Render; set PORTAL_URL to public URL")
    pdf.ln(1)
    pdf.body("TEAMMATE (backend) - primary:")
    pdf.bullet("Scaffold apps/agent FastAPI service")
    pdf.bullet("Wire Opsera MCP (VERIFY), Daytona (EXECUTE), Insforge (PERSIST)")
    pdf.bullet("Wire Rtrvr (SUBMIT to mock portal)")
    pdf.bullet("After Rtrvr submit: call POST /api/pa/{ref}/adjudicate on web app")
    pdf.bullet("SSE stream + Insforge schema (prior_auths, agent_events)")
    pdf.bullet("Deploy agent to Render; connect WEB_URL + AGENT_URL")
    pdf.ln(1)
    pdf.bullet("OPTIONAL: Tigris for PDF/receipt storage (stretch - Insforge storage also OK)")

    pdf.add_page()
    pdf.section("6. Sponsor API credentials")
    pdf.body("Copy to project root .env (from teammate). Fill in actual keys at hackathon:")
    pdf.code_block(
        "OPSERA_MCP_URL=https://mcp.opsera.io/mcp\n"
        "OPSERA_API_TOKEN=\n"
        "\n"
        "DAYTONA_API_KEY=\n"
        "DAYTONA_API_URL=https://api.daytona.io\n"
        "\n"
        "INSFORGE_API_KEY=\n"
        "INSFORGE_PROJECT_URL=\n"
        "\n"
        "RTRVR_API_KEY=\n"
        "\n"
        "# App URLs (add these)\n"
        "WEB_URL=http://localhost:3000\n"
        "AGENT_URL=http://localhost:8000\n"
        "PORTAL_URL=http://localhost:3000/portal/healthfirst/prior-auth\n"
        "DEMO_FIXTURE_MODE=true"
    )

    pdf.section("7. Sponsor roles (pitch deck alignment)")
    widths3 = [35, 155]
    pdf.table_row(["Sponsor", "Demo role"], widths3, header=True)
    sponsors = [
        ("Rtrvr.ai", "READ-WEB - drives browser, fills + submits mock HealthFirst form"),
        ("Daytona", "EXECUTE - sandbox PDF parse (pdfplumber, ICD-10 normalize)"),
        ("Opsera", "VERIFY - MCP scan_pii on outgoing packet (no PHI over-disclosure)"),
        ("Insforge", "PERSIST - Postgres workflow, agent_events, audit log"),
        ("Render", "Host web + agent publicly (live demo URL for judges)"),
    ]
    for a, b in sponsors:
        pdf.table_row([a, b], widths3)

    pdf.section("8. End-to-end demo flow (judge view)")
    pdf.bullet("1. Upload Sarah chart + Ozempic prescription PDFs")
    pdf.bullet("2. Agent EXTRACTs fields (Daytona / LLM)")
    pdf.bullet("3. Opsera VERIFY green check on packet")
    pdf.bullet("4. Rtrvr fills HealthFirst form live (browser visible)")
    pdf.bullet("5. Submit -> Pending Review (NOT instant approve)")
    pdf.bullet("6. Agent adjudicates -> Under Review -> Approved")
    pdf.bullet("7. Audit page /run/{id}: receipt + full chain + sponsor logos")

    pdf.section("9. Repo map")
    pdf.code_block(
        "authmatic/\n"
        "  apps/web/          <- Next.js + mock portal\n"
        "  apps/agent/        <- FastAPI agent\n"
        "  packages/          <- shared TS types\n"
        "  db/migrations/     <- schema + incremental migrations\n"
        "  fixtures/          <- healthfirst-case.json + portal spec\n"
        "  assets/demo/       <- Sarah PDFs\n"
        "  infra/             <- docker-compose.local.yml\n"
        "  docs/              <- architecture, handoff, sponsor notes"
    )

    pdf.section("10. Critical coordination")
    pdf.bullet("PORTAL_URL must be the PUBLIC Render URL in prod - not localhost - or Rtrvr fails")
    pdf.bullet("Field IDs on form must match exactly (see section 2)")
    pdf.bullet("Submit != Approved. Agent must call /adjudicate after Rtrvr submit")
    pdf.bullet("Member ID must be HF45821973 format or mock payer denies the PA")
    pdf.bullet("Fallback: DEMO_FIXTURE_MODE=true + pre-recorded form-fill clip")

    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, "Questions? Check architecture.md and apps/web/README.md in the repo.", align="C")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUT))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build()
