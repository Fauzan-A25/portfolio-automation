#!/usr/bin/env python3
"""
linkedin.py — Integrasi LinkedIn untuk Portfolio Pipeline.

MODE YANG DIDUKUNG (update: +pdf):
  1. MANUAL (default) — Kamu entry data sendiri, template sudah disediain
  2. PDF     ⭐ BARU!  — Download PDF LinkedIn, auto-parse & sync ke sheets
  3. API (limited)     — Buat aplikasi LinkedIn + request API access
  4. SCRAPER (risky)   — Scrape profil publik dengan BeautifulSoup

PENGATURAN:
  config.yaml → linkedin.mode = "manual" | "pdf" | "api" | "scraper"

PDF MODE (Recommended):
  1. Buka https://www.linkedin.com/in/fauzanahsanudin/
  2. Klik "More..." → "Save to PDF" (atau Print → Save as PDF)
  3. Simpan file ke: portfolio-automation/linkedin_data/
  4. Jalanin: python scripts/linkedin_pdf_parser.py --auto
  
  Atau biarin GitHub Actions detect otomatis pas ada PDF baru!
"""

import os
import sys
import json
import requests
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils import load_config, setup_logger, format_datetime, handle_errors
from linkedin_pdf_parser import LinkedInPDFParser, LinkedInPDFtoSheets


# ─── MODE: PDF (BARU) ────────────────────────────────────────────────────────

class LinkedInPDFMode:
    """Mode PDF — parse LinkedIn PDF → sheets. ⭐ Recommended."""

    def __init__(self, username, pdf_path=None, logger=None):
        self.username = username
        self.pdf_path = pdf_path
        self.logger = logger or setup_logger("LinkedInPDF")

    def find_pdf(self):
        """Cari PDF LinkedIn di folder linkedin_data/."""
        data_dir = Path(__file__).resolve().parent.parent / "linkedin_data"
        if not data_dir.exists():
            data_dir.mkdir(parents=True)
            return None
        pdfs = sorted(data_dir.glob("*.pdf"), key=os.path.getmtime, reverse=True)
        return pdfs[0] if pdfs else None

    def run(self, dry_run=False, to_sheets=False):
        """Parse PDF dan sync."""
        pdf = self.pdf_path or self.find_pdf()
        if not pdf:
            return {"error": "Tidak ada PDF ditemukan. Taruh PDF di linkedin_data/"}

        self.logger.info(f"📄 PDF ditemukan: {pdf.name}")

        pipeline = LinkedInPDFtoSheets(str(pdf), self.logger)
        if dry_run:
            data = pipeline.parser.parse()
            LinkedInPDFtoSheets._print_summary(data)
            return data
        elif to_sheets:
            return pipeline.parse_and_sync(dry_run=False)
        else:
            return pipeline.parse_and_sync(dry_run=True)


# ─── MODE: MANUAL ────────────────────────────────────────────────────────────

class LinkedInManualHelper:
    """Bantu format data LinkedIn untuk di-entry manual ke Google Sheets."""

    def __init__(self, username, logger=None):
        self.username = username
        self.logger = logger or setup_logger("LinkedInManual")
        self.target_sheets = {
            "Experiences": [
                "id", "company", "position", "start_date",
                "end_date", "description", "location", "employment_type",
            ],
            "Certifications": [
                "id", "name", "issuer", "issue_date",
                "expiry_date", "credential_id", "credential_url",
            ],
        }

    def generate_template(self, sheet_name):
        if sheet_name not in self.target_sheets:
            self.logger.warning(f"Sheet '{sheet_name}' tidak dikenal")
            return None
        headers = self.target_sheets[sheet_name]
        return f"""
╔═══ LINKEDIN → SHEETS: {sheet_name} ═══╗

Headers: {', '.join(headers)}

Row template: {', '.join(['""' for _ in headers])}

Format tanggal: YYYY-MM-DD
LinkedIn: https://www.linkedin.com/in/{self.username}/
"""

    def log_entry(self, sheet_name, data):
        log_entry = {
            "timestamp": __import__('datetime').datetime.now().isoformat(),
            "sheet": sheet_name,
            "data": data,
            "source": "linkedin_manual",
        }
        log_path = Path(__file__).resolve().parent.parent / "logs" / "linkedin_entries.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
        return log_entry


# ─── PIPELINE ────────────────────────────────────────────────────────────────

class LinkedInPipeline:
    """Pipeline LinkedIn — jalan sesuai mode dari config.

    Mode: "manual" | "pdf" | "api" | "scraper"
    """

    def __init__(self, config=None):
        self.config = config or load_config()
        self.linkedin_cfg = self.config.get("linkedin", {})
        self.mode = self.linkedin_cfg.get("mode", "manual")
        self.username = self.linkedin_cfg.get("username", "")
        self.enabled = self.linkedin_cfg.get("enabled", False)
        self.logger = setup_logger("LinkedInPipeline")

    def run(self, **kwargs):
        if not self.enabled:
            self.logger.info("🔇 LinkedIn disabled")
            return {"status": "disabled"}

        self.logger.info(f"🔗 LinkedIn Pipeline — Mode: {self.mode}")

        if self.mode == "pdf":
            return LinkedInPDFMode(self.username).run(**kwargs)
        elif self.mode == "manual":
            helper = LinkedInManualHelper(self.username)
            return {
                "mode": "manual",
                "username": self.username,
                "templates": {
                    name: helper.generate_template(name)
                    for name in ["Experiences", "Certifications"]
                },
            }
        # ... api & scraper modes abbreviated for brevity


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="LinkedIn → Sheets integration")
    parser.add_argument("--mode", choices=["manual", "pdf", "api", "scraper"])
    parser.add_argument("--pdf", help="Path ke file PDF LinkedIn")
    parser.add_argument("--auto", action="store_true", help="Auto-detect PDF")
    parser.add_argument("--to-sheets", action="store_true", help="Sync ke sheets")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--template", choices=["Experiences", "Certifications"])

    args = parser.parse_args()

    pipeline = LinkedInPipeline()
    if args.mode:
        pipeline.mode = args.mode

    result = pipeline.run(
        pdf_path=args.pdf,
        dry_run=args.dry_run or not args.to_sheets,
        to_sheets=args.to_sheets,
    )

    if args.template:
        helper = LinkedInManualHelper(pipeline.username)
        print(helper.generate_template(args.template))


if __name__ == "__main__":
    main()
