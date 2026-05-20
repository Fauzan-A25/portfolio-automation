#!/usr/bin/env python3
"""
generate_resume.py — Generate tailored resume untuk apply magang pake Gemini AI.

Usage:
  python scripts/generate_resume.py --company Grab
  python scripts/generate_resume.py --company Grab --output ~/Apply\ Magang/Resume/Grab/Resume_Grab.pdf

Flow:
  1. Baca CV data dari Google Docs / portfolio data
  2. Baca job description PDF dari folder Perusahaan/{company}/
  3. Kirim ke Gemini → generate resume tailored
  4. Simpan ke folder Resume/{company}/
"""

import os, sys, json, re, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
from utils import load_config, setup_logger, now_str

load_dotenv()

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

BASE_DIR = Path.home() / "Apply Magang"
COMPANIES_DIR = BASE_DIR / "Perusahaan"
RESUMES_DIR = BASE_DIR / "Resume"


class ResumeGenerator:
    """Generate tailored resume using Gemini AI."""

    def __init__(self, company, logger=None):
        self.company = company
        self.logger = logger or setup_logger(f"Resume-{company}")
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        
        if not self.api_key:
            self.logger.error("❌ GEMINI_API_KEY tidak ditemukan!")
            raise ValueError("Set GEMINI_API_KEY di .env")

    def load_cv_data(self):
        """Load CV data from Google Docs export or portfolio fallback."""
        cv_path = Path.home() / "Apply Magang" / ".cv_data.txt"
        
        # Try Google Docs export
        doc_id = "1zm9N7lCHsZPCChdz5zjfQK4wogPMqb5g"
        import urllib.request
        try:
            url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"
            resp = urllib.request.urlopen(url, timeout=10)
            text = resp.read().decode("utf-8")
            if text.strip():
                # Save cache
                cv_path.parent.mkdir(parents=True, exist_ok=True)
                cv_path.write_text(text)
                self.logger.info(f"📄 CV loaded from Google Docs ({len(text)} chars)")
                return text
        except Exception as e:
            self.logger.warning(f"⚠️ Gagal download CV dari Google Docs: {e}")
        
        # Fallback: use cached
        if cv_path.exists():
            text = cv_path.read_text()
            self.logger.info(f"📄 CV loaded from cache ({len(text)} chars)")
            return text
        
        self.logger.error("❌ CV data tidak ditemukan!")
        return ""

    def load_job_description(self):
        """Load job description PDF from company folder."""
        company_dir = COMPANIES_DIR / self.company
        if not company_dir.exists():
            self.logger.error(f"❌ Folder {company_dir} tidak ditemukan!")
            return ""
        
        pdfs = list(company_dir.glob("*.pdf"))
        if not pdfs:
            self.logger.error(f"❌ Tidak ada PDF di {company_dir}")
            return ""
        
        # Read the SmartRecruiters / main job description PDF
        import fitz
        text = ""
        for pdf_path in pdfs:
            doc = fitz.open(str(pdf_path))
            for page in doc:
                text += page.get_text("text") + "\n"
            doc.close()
        
        self.logger.info(f"📋 Job description loaded ({len(text)} chars)")
        return text

    def call_gemini(self, system_prompt, user_prompt):
        """Call Gemini API."""
        import requests
        
        url = f"{GEMINI_API_URL}?key={self.api_key}"
        payload = {
            "contents": [{
                "role": "user",
                "parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]
            }],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 8192,
            }
        }
        
        try:
            resp = requests.post(url, json=payload, timeout=120)
            resp.raise_for_status()
            result = resp.json()
            return result["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            self.logger.error(f"❌ Gemini error: {e}")
            return None

    def generate_resume(self):
        """Generate tailored resume for the company."""
        cv_data = self.load_cv_data()
        if not cv_data:
            return None
        
        job_desc = self.load_job_description()
        if not job_desc:
            self.logger.warning("⚠️ No job description found, generating generic resume")
            job_desc = f"Intern position at {self.company}"
        
        system_prompt = """You are an Expert Resume Writer certified by CPRW (Certified Professional Resume Writer). Your task is to create a HIGH-IMPACT, ATS-OPTIMIZED resume that passes the 7-second HR scan test.

=== CRITICAL FORMATTING RULES ===
1. ONE PAGE MAXIMUM — no exceptions for <10 years experience
2. REVERSE CHRONOLOGICAL order (most recent first)
3. SINGLE COLUMN layout (NO tables, columns, text boxes)
4. Standard section headers: "Professional Summary", "Education", "Skills", "Experience", "Projects"
5. Plain text only — NO graphics, images, icons, or special characters
6. Font-compatible: use clean ASCII formatting

=== THE 7-SECOND SCAN STRATEGY ===
Recruiters scan in F-pattern:
- 0-2s: Name + title → must show relevance immediately
- 2-4s: First 3 bullets of most recent role → MUST have QUANTIFIED RESULTS
- 4-5s: Skills section → MUST match job description keywords EXACTLY
- 5-6s: Company names → recognizable or impressive
- 6-7s: Education → GPA, degree, school

=== BULLET POINT RULES (XYZ Method) ===
Format: "Accomplished [X] as measured by [Y], by doing [Z]"
Examples:
- "Reduced data processing time by 40% by implementing automated Python scripts for data cleaning"
- "Increased model accuracy from 85% to 92% by engineering 15+ features and tuning hyperparameters"
- "Managed data for 10,000+ mobile app entries, ensuring 100% accuracy through systematic validation"

EVERY bullet MUST have:
1. A strong ACTION VERB (Developed, Led, Optimized, Achieved, Implemented, Reduced, Delivered)
2. A NUMBER/QUANTIFICATION (%, $, time saved, volume processed)
3. A clear business/technical IMPACT

NEVER start bullets with: "Responsible for", "Tasked with", "Duties included"

=== PROFESSIONAL SUMMARY RULES ===
- 2-3 lines maximum
- First line: Title + years of experience + key differentiator
- Second line: Technical skills relevant to THIS job
- Third line: What you bring / career goal
- Must include keywords from the job description

=== KEYWORD OPTIMIZATION ===
- Source exact phrases from the job description
- Place keywords in: Summary > Skills > Experience bullets
- Aim for 80%+ keyword match rate
- Include exact job title from the description"""

        user_prompt = f"""Create a 1-page ATS-optimized resume for this job:

=== JOB DESCRIPTION ===
{job_desc}

=== MY CV DATA ===
{cv_data}

=== COMPANY ===
{self.company}

=== TARGET ROLE ===
Research & Data Analytics Intern

=== INSTRUCTIONS ===
Generate a plain text resume following ALL the formatting rules above.

Section order for this candidate (Data Science student):
1. Contact Info (name, phone, email, LinkedIn, GitHub)
2. Professional Summary (3 lines max, keyword-optimized for Research & Data Analytics)
3. Education (Telkom University, 3.60 GPA, relevant coursework)
4. Skills (grouped by category, match JD keywords)
5. Experience (Lab Assistant, PRADA, ISLAH, GDGoC — tailor bullets to data analytics)
6. Projects (COPPA, FOSSIL, Anti-Spoofing — tailor to show data analysis + business impact)
7. Achievements (competitions only, limit to 4-5 most relevant)

IMPORTANT:
- Every bullet point MUST have a quantified result or number
- Use XYZ method: Accomplished X, measured by Y, by doing Z
- Emphasize data analysis, research, Excel, Python, SQL skills
- Keep it ONE PAGE — be concise, remove filler words
- Use "|" pipe separator between items on same line
- No markdown formatting, just clean plain text
- Do NOT include "References available upon request" — outdated"""

        self.logger.info(f"🤖 Generating resume for {self.company}...")
        resume = self.call_gemini(system_prompt, user_prompt)
        
        if resume:
            # Clean up markdown
            resume = re.sub(r'```(?:text|plain)?', '', resume)
            resume = resume.strip()
            self.logger.info(f"✅ Resume generated ({len(resume)} chars)")
        
        return resume

    def save_resume(self, resume_text):
        """Save resume to file."""
        if not resume_text:
            return None
        
        # Create output directory
        output_dir = RESUMES_DIR / self.company
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save as .txt
        txt_path = output_dir / f"Resume_{self.company}.txt"
        txt_path.write_text(resume_text)
        self.logger.info(f"💾 Resume saved: {txt_path}")
        
        # Try to create PDF if reportlab is available
        pdf_path = output_dir / f"Resume_{self.company}.pdf"
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            
            doc = SimpleDocTemplate(str(pdf_path), pagesize=A4,
                                   topMargin=20, bottomMargin=20,
                                   leftMargin=30, rightMargin=30)
            styles = getSampleStyleSheet()
            
            # Custom styles
            styles.add(ParagraphStyle('ResumeBody', parent=styles['Normal'],
                                       fontSize=10, leading=14, spaceAfter=4))
            styles.add(ParagraphStyle('ResumeTitle', parent=styles['Title'],
                                       fontSize=16, spaceAfter=6))
            
            # Build content
            flowables = []
            for line in resume_text.split('\n'):
                line = line.strip()
                if not line:
                    flowables.append(Spacer(1, 6))
                elif line.isupper() and len(line) < 40:
                    # Section header
                    flowables.append(Paragraph(f"<b>{line}</b>", styles['ResumeBody']))
                else:
                    flowables.append(Paragraph(line, styles['ResumeBody']))
            
            doc.build(flowables)
            self.logger.info(f"📄 PDF saved: {pdf_path}")
        except ImportError:
            self.logger.info("ℹ️ reportlab not installed. Saving as .txt only.")
            pdf_path = None
        
        return {"txt": str(txt_path), "pdf": str(pdf_path) if pdf_path else None}


def main():
    parser = argparse.ArgumentParser(description="Generate tailored internship resume")
    parser.add_argument("--company", required=True, help="Nama perusahaan (nama folder)")
    parser.add_argument("--output", help="Output path (optional)")
    
    args = parser.parse_args()
    
    generator = ResumeGenerator(args.company)
    resume = generator.generate_resume()
    
    if resume:
        result = generator.save_resume(resume)
        print(f"\n✅ Resume for {args.company} saved!")
        print(f"   📄 TXT: {result['txt']}")
        if result['pdf']:
            print(f"   📄 PDF: {result['pdf']}")
        print(f"\n--- PREVIEW ---\n{resume[:500]}...")
    else:
        print(f"\n❌ Failed to generate resume for {args.company}")


if __name__ == "__main__":
    main()
