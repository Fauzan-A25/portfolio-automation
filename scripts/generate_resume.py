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
            
            # Also generate styled DOCX and PDF
            try:
                self._create_styled_docx(resume)
                self._create_styled_pdf(resume)
                self._create_template_docx(resume)  # Template 2-column format
            except Exception as e:
                self.logger.warning(f"⚠️ Styled formatting failed: {e}")
        
        return resume

    def _create_styled_docx(self, resume_text):
        """Create a styled .docx with dividers and icons."""
        from docx import Document
        from docx.shared import Pt, Cm, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
        
        output_dir = RESUMES_DIR / self.company
        output_path = output_dir / f"Resume_{self.company}.docx"
        
        doc = Document()
        section = doc.sections[0]
        section.top_margin = Cm(1.5)
        section.bottom_margin = Cm(1.5)
        section.left_margin = Cm(2)
        section.right_margin = Cm(2)
        
        style = doc.styles['Normal']
        style.font.name = 'Times New Roman'
        style.font.size = Pt(10)
        style.paragraph_format.space_after = Pt(2)
        
        def add_hr():
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            pPr = p._p.get_or_add_pPr()
            pBdr = OxmlElement('w:pBdr')
            bottom = OxmlElement('w:bottom')
            bottom.set(qn('w:val'), 'single')
            bottom.set(qn('w:sz'), '4')
            bottom.set(qn('w:space'), '1')
            bottom.set(qn('w:color'), '00D4AA')
            pBdr.append(bottom)
            pPr.append(pBdr)
        
        lines = resume_text.split('\n')
        i = 0
        in_header = True
        
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            
            if in_header and i < 4:
                p = doc.add_paragraph()
                if i == 0:
                    run = p.add_run(line.upper())
                    run.bold = True
                    run.font.size = Pt(16)
                    run.font.color.rgb = RGBColor(0, 212, 170)
                elif i >= 1:
                    parts = line.split('|')
                    for j, part in enumerate(parts):
                        part = part.strip()
                        run = p.add_run(part)
                        run.font.size = Pt(9)
                        run.font.color.rgb = RGBColor(100, 100, 100)
                        if j < len(parts) - 1:
                            run = p.add_run(' | ')
                            run.font.size = Pt(9)
                            run.font.color.rgb = RGBColor(200, 200, 200)
                if i == min(3, len(lines)-1):
                    add_hr()
                    in_header = False
                i += 1
                continue
            
            is_section = line.isupper() and len(line) < 35 and '|' not in line and not line.startswith('HTTP')
            is_org = '|' in line and len(line) < 100
            is_date = bool(re.search(r'\d{4}\s*[–-]', line)) and len(line) < 60
            
            if is_section:
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(8)
                p.paragraph_format.space_after = Pt(4)
                run = p.add_run(f'▸ {line}')
                run.bold = True
                run.font.size = Pt(11)
                run.font.color.rgb = RGBColor(0, 212, 170)
            
            elif is_org:
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(4)
                p.paragraph_format.space_after = Pt(1)
                parts = line.split('|')
                if parts:
                    run = p.add_run(parts[0].strip())
                    run.bold = True
                    run.font.size = Pt(10)
                for part in parts[1:]:
                    part = part.strip()
                    if part:
                        run = p.add_run(f' | {part}')
                        run.font.size = Pt(9)
                        run.font.color.rgb = RGBColor(100, 100, 100)
            
            elif is_date:
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(2)
                run = p.add_run(line)
                run.font.size = Pt(9)
                run.font.italic = True
                run.font.color.rgb = RGBColor(0, 212, 170)
            
            elif line.startswith(('*', '•', '-')):
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(1)
                p.paragraph_format.left_indent = Cm(0.5)
                clean = line.lstrip('* •-').strip()
                run = p.add_run(f'▸ {clean}')
                run.font.size = Pt(9.5)
            
            else:
                p = doc.add_paragraph()
                run = p.add_run(line)
                run.font.size = Pt(9.5)
            
            i += 1
        
        add_hr()
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run('▸ References available upon request')
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(150, 150, 150)
        
        doc.save(str(output_path))
        self.logger.info(f"📄 DOCX saved: {output_path}")

    def _create_styled_pdf(self, resume_text):
        """Create a styled PDF with dividers and icons."""
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.lib.colors import HexColor
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
        from reportlab.lib.enums import TA_CENTER
        
        output_dir = RESUMES_DIR / self.company
        output_path = output_dir / f"Resume_{self.company}_Styled.pdf"
        
        ACCENT = HexColor('#00D4AA')
        GREY = HexColor('#666666')
        
        doc = SimpleDocTemplate(str(output_path), pagesize=A4,
                               topMargin=1.5*cm, bottomMargin=1.5*cm,
                               leftMargin=2*cm, rightMargin=2*cm)
        
        styles = getSampleStyleSheet()
        s_name = ParagraphStyle('N', fontSize=16, textColor=ACCENT, spaceAfter=2, fontName='Times-Bold')
        s_contact = ParagraphStyle('C', fontSize=9, textColor=GREY, spaceAfter=1, fontName='Times-Roman')
        s_section = ParagraphStyle('S', fontSize=11, textColor=ACCENT, spaceBefore=8, spaceAfter=4, fontName='Times-Bold')
        s_org = ParagraphStyle('O', fontSize=10, spaceBefore=4, spaceAfter=1, fontName='Times-Bold')
        s_normal = ParagraphStyle('T', fontSize=9.5, leading=12.5, spaceAfter=1, fontName='Times-Roman')
        s_bullet = ParagraphStyle('B', fontSize=9.5, leading=12.5, leftIndent=12, spaceAfter=1, fontName='Times-Roman')
        s_date = ParagraphStyle('D', fontSize=9, textColor=ACCENT, spaceAfter=2, fontName='Times-Italic')
        
        hr = HRFlowable(width="100%", thickness=0.5, color=ACCENT, spaceBefore=2, spaceAfter=2)
        
        story = []
        lines = resume_text.split('\n')
        i = 0
        in_header = True
        
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            
            if in_header and i < 4:
                if i == 0:
                    story.append(Paragraph(line.upper(), s_name))
                elif i >= 1:
                    parts = line.split('|')
                    formatted = ''.join(
                        f'<font color="#0066CC">{p.strip()}</font>' if 'linkedin' in p.lower() or 'github' in p.lower()
                        else p.strip()
                        for p in parts
                    )
                    story.append(Paragraph(formatted, s_contact))
                if i == min(3, len(lines)-1):
                    story.append(hr)
                    in_header = False
                i += 1
                continue
            
            is_section = line.isupper() and len(line) < 35 and '|' not in line
            is_org = '|' in line and len(line) < 100
            is_date = bool(__import__('re').search(r'\d{4}\s*[–-]', line)) and len(line) < 60
            
            if is_section:
                story.append(Paragraph(f'<bullet>&#9656;</bullet> {line}', s_section))
            elif is_org:
                parts = line.split('|')
                formatted = f'<b>{parts[0].strip()}</b>'
                for p in parts[1:]:
                    p = p.strip()
                    if p:
                        formatted += f' <font color="#666666" size="9">| {p}</font>'
                story.append(Paragraph(formatted, s_org))
            elif is_date:
                story.append(Paragraph(line, s_date))
            elif line.startswith(('*', '•', '-')):
                clean = line.lstrip('* •-').strip()
                story.append(Paragraph(f'<bullet>&#9656;</bullet> {clean}', s_bullet))
            else:
                story.append(Paragraph(line, s_normal))
            
            i += 1
        
        story.append(hr)
        story.append(Paragraph('<font color="#999999" size="8">▸ References available upon request</font>',
                              ParagraphStyle('F', fontSize=8, textColor=HexColor('#999999'), spaceBefore=4, alignment=TA_CENTER)))
        
        doc.build(story)
        self.logger.info(f"📄 Styled PDF saved: {output_path}")

    def _create_template_docx(self, resume_text):
        """Create 2-column template-based DOCX from Template/Resume.docx."""
        import re as re_mod
        from docx import Document
        from docx.shared import Pt, Cm, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        
        template_path = str(RESUMES_DIR.parent / "Resume" / "Template" / "Resume.docx")
        if not os.path.exists(template_path):
            self.logger.warning(f"⚠️ Template not found: {template_path}")
            return
        
        doc = Document(template_path)
        table = doc.tables[0]
        ACC = RGBColor(0, 212, 170)
        
        def _add(p, text, **kw):
            r = p.add_run(text)
            r.bold = kw.get('bold', False)
            r.italic = kw.get('italic', False)
            r.font.size = Pt(kw.get('size', 10))
            r.font.color.rgb = kw.get('color', RGBColor(30, 30, 30))
            r.font.name = 'Times New Roman'
            return r
        
        def _spacing(p):
            pf = p.paragraph_format
            pf.space_before = Pt(0)
            pf.space_after = Pt(0)
            pf.line_spacing = 1.0
        
        # Parse sections
        KNOWN = ['PROFESSIONAL SUMMARY', 'SUMMARY', 'EDUCATION', 'SKILLS', 'EXPERIENCE', 'PROJECTS', 'ACHIEVEMENTS']
        sections = {'HEADER': []}
        cur = 'HEADER'
        for line in resume_text.split('\n'):
            s = line.strip()
            if not s: continue
            if any(s.upper() == k.upper() for k in KNOWN):
                cur = s.upper()
                sections[cur] = []
            else:
                sections.setdefault(cur, []).append(s)
        
        # Header
        hdr = sections.get('HEADER', [])
        name = next((l for l in hdr if l and not any(x in l for x in ['@', '+', 'linkedin', 'github', '|'])), 'Fauzan Ahsanudin')
        c0 = table.cell(0, 0)
        c0.paragraphs[0].clear()
        _add(c0.paragraphs[0], name.upper(), bold=True, size=14, color=ACC)
        
        summ = sections.get('PROFESSIONAL SUMMARY', sections.get('SUMMARY', []))
        if summ:
            p = c0.add_paragraph()
            _spacing(p)
            _add(p, summ[0][:150], size=8.5, color=RGBColor(100,100,100))
        
        c1 = table.cell(0, 1)
        c1.paragraphs[0].clear()
        for line in hdr:
            if '@' in line or '+' in line or 'linkedin' in line.lower() or 'github' in line.lower():
                parts = line.split('|')
                for part in parts:
                    p = c1.add_paragraph()
                    _spacing(p)
                    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                    _add(p, part.strip(), size=8.5, color=RGBColor(100,100,100))
        
        # Content
        main_cell = table.cell(1, 0)
        side_cell = table.cell(1, 1)
        for cell in [main_cell, side_cell]:
            for p in cell.paragraphs:
                p.clear()
        
        # LEFT
        for sec in ['EXPERIENCE', 'EDUCATION', 'PROJECTS']:
            items = sections.get(sec, [])
            if not items: continue
            p = main_cell.add_paragraph()
            _spacing(p)
            p.paragraph_format.space_before = Pt(6)
            _add(p, sec, bold=True, size=10, color=ACC)
            pu = main_cell.add_paragraph()
            _spacing(pu)
            _add(pu, chr(9472) * 40, size=5, color=ACC)
            
            for item in items:
                if '|' in item or chr(8212) in item:
                    sep = '|' if '|' in item else chr(8212)
                    parts = item.split(sep)
                    pp = main_cell.add_paragraph()
                    _spacing(pp)
                    pp.paragraph_format.space_before = Pt(3)
                    _add(pp, parts[0].strip(), bold=True, size=9.5)
                    if len(parts) > 1:
                        _add(pp, f' {sep} {parts[1].strip()}', size=8.5, color=RGBColor(100,100,100))
                elif re_mod.search(r'\d{4}\s*[–-]', item) and len(item) < 60:
                    pp = main_cell.add_paragraph()
                    _spacing(pp)
                    _add(pp, item, size=8, color=ACC, italic=True)
                elif item.startswith(('*', chr(8226), chr(9656), '-')):
                    pp = main_cell.add_paragraph()
                    _spacing(pp)
                    pp.paragraph_format.left_indent = Cm(0.3)
                    _add(pp, f'{chr(8226)} {item.lstrip("* " + chr(8226) + chr(9656) + "-").strip()}', size=8.5)
                else:
                    pp = main_cell.add_paragraph()
                    _spacing(pp)
                    _add(pp, item, size=8.5)
        
        # RIGHT
        for sec in ['PROFESSIONAL SUMMARY', 'SKILLS', 'ACHIEVEMENTS']:
            items = sections.get(sec, [])
            if not items: continue
            
            label = 'SUMMARY' if sec == 'PROFESSIONAL SUMMARY' else sec
            p = side_cell.add_paragraph()
            _spacing(p)
            p.paragraph_format.space_before = Pt(6)
            _add(p, label, bold=True, size=10, color=ACC)
            pu = side_cell.add_paragraph()
            _spacing(pu)
            _add(pu, chr(9472) * 25, size=5, color=ACC)
            
            for item in items:
                if sec == 'SKILLS':
                    pp = side_cell.add_paragraph()
                    _spacing(pp)
                    _add(pp, item, size=8.5)
                elif sec == 'ACHIEVEMENTS':
                    pp = side_cell.add_paragraph()
                    _spacing(pp)
                    pp.paragraph_format.left_indent = Cm(0.2)
                    _add(pp, f'{chr(8226)} {item.lstrip("* " + chr(8226) + chr(9656) + "-").strip()}', size=8, color=RGBColor(100,100,100))
                else:
                    pp = side_cell.add_paragraph()
                    _spacing(pp)
                    _add(pp, item[:200], size=8, color=RGBColor(100,100,100))
        
        output_dir = RESUMES_DIR / self.company
        output_path = output_dir / f"Resume_{self.company}_Template.docx"
        doc.save(str(output_path))
        self.logger.info(f"📄 Template DOCX saved: {output_path}")

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
