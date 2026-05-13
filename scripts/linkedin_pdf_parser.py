#!/usr/bin/env python3
"""
linkedin_pdf_parser.py — Parse LinkedIn Profile PDF ke structured data.

Cara Kerja:
  1. Baca file PDF LinkedIn (hasil "Save to PDF" dari profil)
  2. Ekstrak teks per halaman
  3. Parse section-by-section: Header, About, Experience, Education, Certifications, Skills
  4. Output: JSON / langsung tulis ke Google Sheets

Cara Dapetin PDF LinkedIn:
  - Buka https://www.linkedin.com/in/fauzanahsanudin/
  - Klik "More..." → "Save to PDF" (via browser Print → Save as PDF)
  - Atau: klik tombol "..." di profil → "Save to PDF"
  - Simpan file ke: linkedin_data/fauzanahsanudin_profile.pdf

Usage:
  python scripts/linkedin_pdf_parser.py --pdf linkedin_data/profile.pdf
  python scripts/linkedin_pdf_parser.py --pdf linkedin_data/profile.pdf --to-sheets
  python scripts/linkedin_pdf_parser.py --pdf linkedin_data/profile.pdf --json
"""

import os
import re
import sys
import json
from pathlib import Path
import hashlib
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
from utils import load_config, setup_logger, now_str, handle_errors

load_dotenv()


# ─── Constants ────────────────────────────────────────────────────────────────

SECTION_KEYWORDS = {
    "HEADER": ["linkedin", "profile"],
    "ABOUT": ["about", "tentang", "summary", "ringkasan"],
    "EXPERIENCE": ["experience", "pengalaman", "employment", "work history"],
    "EDUCATION": ["education", "pendidikan"],
    "CERTIFICATIONS": [
        "licenses", "certifications", "lisensi", "sertifikasi",
        "licenses & certifications", "licenses and certifications",
    ],
    "SKILLS": ["skills", "keahlian", "top skills"],
    "VOLUNTEER": ["volunteer", "volunteering", "sukarelawan"],
    "LANGUAGES": ["languages", "bahasa"],
    "HONORS": ["honors", "awards", "penghargaan"],
    "PUBLICATIONS": ["publications", "publikasi"],
}

MONTH_MAP = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    "januari": "01", "februari": "02", "maret": "03", "april": "04",
    "mei": "05", "juni": "06", "juli": "07", "agustus": "08",
    "september": "09", "oktober": "10", "november": "11", "desember": "12",
}

PDF_DATA_DIR = Path(__file__).resolve().parent.parent / "linkedin_data"


# ─── PDF Extractor ───────────────────────────────────────────────────────────

class LinkedInPDFParser:
    """Parse LinkedIn profile PDF ke data terstruktur."""

    def __init__(self, pdf_path=None, logger=None):
        self.pdf_path = Path(pdf_path) if pdf_path else None
        self.logger = logger or setup_logger("LinkedInPDF")
        self.raw_text = ""
        self.pages = []
        self.data = {}

    def set_pdf(self, pdf_path):
        """Set PDF file path."""
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF tidak ditemukan: {pdf_path}")

    def extract_text(self):
        """
        Ekstrak teks dari PDF pake PyMuPDF (fitz).
        Clean page break artifacts dan gabung konten antar halaman.

        Returns:
            str: seluruh teks dari PDF
        """
        if not self.pdf_path or not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF tidak ditemukan: {self.pdf_path}")

        try:
            import fitz  # PyMuPDF
        except ImportError:
            self.logger.error("PyMuPDF belum terinstall. Jalankan: pip install pymupdf")
            raise

        doc = fitz.open(str(self.pdf_path))
        self.pages = []
        all_text = ""

        for page_num, page in enumerate(doc):
            text = page.get_text("text")
            # Bersihin whitespace berlebih
            text = re.sub(r'\s+\n\s+', '\n', text)
            text = text.strip()
            self.pages.append({"page": page_num + 1, "text": text})
            all_text += text + "\n"

        doc.close()

        # Clean page break artifacts: remove "Page X of Y" markers
        self.raw_text = re.sub(r'Page \d+ of \d+', '', all_text)
        self.raw_text = re.sub(r'\n{3,}', '\n\n', self.raw_text)

        self.logger.info(f"✅ PDF loaded: {len(self.pages)} pages, {len(self.raw_text)} chars")
        return self.raw_text

    def parse(self):
        """
        Parse seluruh teks PDF → data terstruktur.

        Returns:
            dict: {
                "header": {...},
                "about": "...",
                "experiences": [...],
                "education": [...],
                "certifications": [...],
                "skills": [...],
                "parsed_at": "2026-05-12 ..."
            }
        """
        if not self.raw_text:
            self.extract_text()

        self.data = {
            "header": self._parse_header(),
            "about": self._parse_about(),
            "experiences": self._parse_section("EXPERIENCE", self._parse_experience_block),
            "education": self._parse_section("EDUCATION", self._parse_education_block),
            "certifications": self._parse_section("CERTIFICATIONS", None),
            "skills": self._parse_skills(),
            "parsed_at": now_str(),
        }

        # Log summary
        for section, items in [
            ("Experience", self.data["experiences"]),
            ("Education", self.data["education"]),
            ("Certifications", self.data["certifications"]),
            ("Skills", self.data["skills"]),
        ]:
            count = len(items)
            if count > 0:
                labels = {
                    "Experience": f"di {items[0].get('company', '?')}",
                    "Education": f"di {items[0].get('institution', '?')}",
                    "Certifications": f"contoh: {items[0].get('name', '?')}",
                    "Skills": f"contoh: {items[0].get('name', '?')}",
                }
                self.logger.info(f"  📌 {section}: {count} item ({labels.get(section, '')})")
            else:
                self.logger.info(f"  📌 {section}: 0 item")

        return self.data

    def _parse_header(self):
        """Parse header profil: nama, headline, lokasi."""
        lines = self.raw_text.split("\n")
        header = {
            "name": "",
            "headline": "",
            "location": "",
            "profile_url": f"https://www.linkedin.com/in/{os.getenv('LINKEDIN_USERNAME', 'fauzanahsanudin')}/",
        }

        # Fallback dari env / known data
        known_name = "Fauzan Ahsanudin Alfikri"
        known_headline = "Data Science Undergraduate • Full Stack Enthusiast"

        # LinkedIn PDF biasanya naruh nama sebagai gambar — cari email dulu
        email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', self.raw_text)
        if email_match:
            header["email"] = email_match.group()

        # Cari lokasi (biasanya di atas email)
        for i, line in enumerate(lines):
            if '@' in line and i > 0:
                header["location"] = lines[i-1].strip() if i > 0 else ""
                break

        # LinkedIn PDF export: nama selalu sebagai gambar (gak bisa di-extract).
        # Fallback ke data yang diketahui.
        header["name"] = known_name
        header["headline"] = known_headline

        # Gak perlu cari nama dari teks — nama LinkedIn selalu gambar

        self.logger.info(f"  👤 {header['name']} — {header['headline']}")
        return header

    def _find_section_boundaries(self, section_key):
        """
        Cari start & end line dari suatu section dalam teks.

        Returns:
            (start_index, end_index) dalam list lines, atau None
        """
        keywords = SECTION_KEYWORDS.get(section_key, [])
        lines = self.raw_text.split("\n")
        start = None
        end = None

        for i, line in enumerate(lines):
            line_lower = line.strip().lower()

            # Check if this line matches section start
            if any(kw in line_lower for kw in keywords):
                # Make sure it's a section header (short, not part of longer text)
                if len(line.strip()) < 60 and not line_lower.startswith("http"):
                    start = i
                    break

        if start is None:
            return None

        # Find next section after this one
        all_sections = []
        for sec_name, sec_kws in SECTION_KEYWORDS.items():
            if sec_name == section_key:
                continue
            all_sections.extend(sec_kws)

        for j in range(start + 1, len(lines)):
            line_lower = lines[j].strip().lower()
            if any(kw in line_lower for kw in all_sections):
                if len(lines[j].strip()) < 60:
                    end = j
                    break

        return (start, end)

    def _parse_section(self, section_key, block_parser):
        """
        Generic section parser: extract raw text → split into blocks → parse each block.

        For certifications: uses custom line-by-line parser instead of block splitting.
        For other sections: uses block_parser callback for each block.
        """
        boundaries = self._find_section_boundaries(section_key)
        if not boundaries:
            self.logger.debug(f"  Section '{section_key}' tidak ditemukan di PDF")
            return []

        start, end = boundaries
        lines = self.raw_text.split("\n")
        section_lines = lines[start + 1:end] if end else lines[start + 1:]
        section_lines = [l.strip() for l in section_lines if l.strip()]

        if not section_lines:
            return []

        # ── Certifications: special parser (line-by-line, 3 lines per entry) ──
        if section_key == "CERTIFICATIONS":
            return self._parse_certs_line_by_line(section_lines)

        # ── Other sections: block splitting ──
        blocks = self._split_into_blocks(section_lines)
        results = []

        for block in blocks:
            parsed = block_parser(block)
            if parsed:
                results.append(parsed)

        return results

    @staticmethod
    def _split_into_blocks(lines):
        """
        Split lines menjadi block-block terpisah.
        Block separator: baris yang terdeteksi sebagai header baru.
        """
        blocks = []
        current_block = []

        for line in lines:
            # Check if line looks like a new block header:
            # - Company name (capitalized, short)
            # - Institution name
            # - Certification name
            if current_block and (
                line.isupper() or  # ALL CAPS = company/institution name
                (len(line) < 50 and line[0].isupper() and 
                 any(kw in line.lower() for kw in ["univ", "institut", "school", "llc", "inc", "ltd"]))
            ):
                blocks.append(current_block)
                current_block = [line]
            else:
                current_block.append(line)

        if current_block:
            blocks.append(current_block)

        return blocks

    def _parse_certs_line_by_line(self, lines):
        """
        Parse certifications line-by-line.
        LinkedIn cert entries typically follow: Name → Issuer → Date

        Handles both:
          Cert Name          Cert Name
          Issuer Name        Issuer Name
          Issued Mon YYYY    Some non-date description
                             Issued Mon YYYY
        """
        certs = []
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Skip empty or header lines
            if not line or "licenses" in line.lower() or "certifications" in line.lower():
                i += 1
                continue

            cert = {"name": line, "issuer": "", "issue_date": "",
                    "expiry_date": "", "credential_id": "", "credential_url": ""}

            # Look ahead for issuer (next 1-2 lines)
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                # If it contains a date, it's the date line, not issuer
                if re.search(r"(?:Issued|Diterbitkan|Expires|Berakhir|Jan|Feb|Mar)", next_line, re.IGNORECASE) and re.search(r"\d{4}", next_line):
                    cert = self._parse_cert_date_line(cert, next_line)
                else:
                    cert["issuer"] = next_line
                    # Check if there's a date line after issuer
                    if i + 2 < len(lines):
                        date_line = lines[i + 2]
                        if re.search(r"(?:Issued|Diterbitkan|Expires|Berakhir|Jan|Feb|Mar|Apr)", date_line, re.IGNORECASE) and re.search(r"\d{4}", date_line):
                            cert = self._parse_cert_date_line(cert, date_line)
                            i += 1  # Skip issuer-only advance

            certs.append(cert)
            i += 2 if cert["issuer"] else 1

        return certs

    def _parse_cert_date_line(self, cert, line):
        """Parse date information from a certification date line."""
        issued_match = re.search(r"(?:Issued|Diterbitkan)\s*:?\s*([A-Za-z]+\.?\s*\d{4})", line, re.IGNORECASE)
        if issued_match:
            cert["issue_date"] = self._parse_single_date(issued_match.group(1))
        expires_match = re.search(r"(?:Expires|Berakhir)\s*:?\s*([A-Za-z]+\.?\s*\d{4})", line, re.IGNORECASE)
        if expires_match:
            cert["expiry_date"] = self._parse_single_date(expires_match.group(1))
        if not cert["issue_date"]:
            date_match = re.search(r"([A-Za-z]+\.?\s*\d{4})", line)
            if date_match:
                cert["issue_date"] = self._parse_single_date(date_match.group(1))
        if "credential id" in line.lower():
            parts = line.split(":", 1)
            cert["credential_id"] = parts[1].strip() if len(parts) > 1 else line.strip()
        return cert

    def _parse_about(self):
        """Parse About/Summary section."""
        boundaries = self._find_section_boundaries("ABOUT")
        if not boundaries:
            return ""

        start, end = boundaries
        lines = self.raw_text.split("\n")
        about_lines = lines[start + 1:end] if end else lines[start + 1:]
        about_text = " ".join(l.strip() for l in about_lines if l.strip() and len(l.strip()) > 3)

        self.logger.info(f"  📝 About: {len(about_text)} chars")
        return about_text

    @staticmethod
    def _parse_date_range(text):
        """
        Parse date range dari teks LinkedIn.

        Contoh input:
          "Jan 2020 - Present · 3 yrs 6 mos"
          "2021 - 2023"
          "Aug 2019 - Dec 2022 · 3 yrs 5 mos"

        Returns:
            (start_date, end_date) dalam format YYYY-MM
        """
        # Pattern: "Mon YYYY - Mon YYYY" or "Mon YYYY - Present"
        pattern = r"([A-Za-z]+\.?\s*\d{4})\s*[-–]\s*([A-Za-z]+\.?\s*\d{4}|Present|Now|Sekarang)"
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            start_raw = match.group(1).strip()
            end_raw = match.group(2).strip()

            start_date = LinkedInPDFParser._parse_single_date(start_raw)
            end_date = LinkedInPDFParser._parse_single_date(end_raw) if end_raw.lower() not in ["present", "now", "sekarang"] else "Present"

            return start_date, end_date

        # Pattern: "YYYY - YYYY" or "YYYY - Present"
        pattern2 = r"(\d{4})\s*[-–]\s*(\d{4}|Present|Now|Sekarang)"
        match2 = re.search(pattern2, text, re.IGNORECASE)
        if match2:
            start_year = match2.group(1)
            end_year = match2.group(2)
            return f"{start_year}-01", f"{end_year}-01" if end_year.lower() not in ["present", "now", "sekarang"] else "Present"

        return "", ""

    @staticmethod
    def _parse_single_date(text):
        """Parse single date like 'Jan 2020' → '2020-01'."""
        text = text.strip().replace(".", "")  # Remove "Jan." → "Jan"

        # Try "Mon YYYY"
        pattern = r"([A-Za-z]+)\s*(\d{4})"
        match = re.search(pattern, text)
        if match:
            month_name = match.group(1).lower()[:3]
            year = match.group(2)
            month = MONTH_MAP.get(month_name, "01")
            return f"{year}-{month}"

        # Try just YYYY
        pattern2 = r"(\d{4})"
        match2 = re.search(pattern2, text)
        if match2:
            return f"{match2.group(1)}-01"

        return ""

    @staticmethod
    def _parse_experience_block(block_lines):
        """
        Parse satu block experience.

        Typical LinkedIn PDF experience block:
          Company Name
          Title
          Date range · Duration
          Location
          Description line 1
          Description line 2
        """
        if not block_lines:
            return None

        exp = {
            "company": "",
            "position": "",
            "start_date": "",
            "end_date": "",
            "location": "",
            "description": "",
            "employment_type": "",
        }

        # Line 0: Company name
        exp["company"] = block_lines[0]

        # Cari date range
        date_range = ""
        for line in block_lines:
            if re.search(r"\d{4}\s*[-–]\s*\d{4}|Present|Now|Sekarang", line, re.IGNORECASE):
                date_range = line
                exp["start_date"], exp["end_date"] = LinkedInPDFParser._parse_date_range(line)
                break

        # Position = line after company, before date
        for i, line in enumerate(block_lines):
            if i == 0:
                continue
            if re.search(r"\d{4}\s*[-–]", line):
                break
            if not exp["position"] and len(line) < 100:
                exp["position"] = line

        # Location = line containing location keywords or right after duration
        for i, line in enumerate(block_lines):
            if any(kw in line.lower() for kw in ["indonesia", "jakarta", "bandung", "area", "remote"]):
                exp["location"] = line
                break

        # Description = remaining lines
        desc_lines = []
        for line in block_lines:
            if line == exp["company"] or line == exp["position"] or line == date_range or line == exp["location"]:
                continue
            if line.strip():
                desc_lines.append(line)

        exp["description"] = " ".join(desc_lines) if desc_lines else ""

        return exp

    @staticmethod
    def _parse_education_block(block_lines):
        """Parse satu block education."""
        if not block_lines:
            return None

        edu = {
            "institution": "",
            "degree": "",
            "field": "",
            "start_date": "",
            "end_date": "",
            "gpa": "",
            "description": "",
        }

        # Line 0: Institution name
        edu["institution"] = block_lines[0]

        # Cari date range
        for line in block_lines:
            if re.search(r"\d{4}\s*[-–]\s*\d{4}", line):
                edu["start_date"], edu["end_date"] = LinkedInPDFParser._parse_date_range(line)
                break

        # Degree and field
        for i, line in enumerate(block_lines):
            if i == 0:
                continue
            if "gpa" in line.lower() or "ipk" in line.lower():
                edu["gpa"] = line
                continue
            if re.search(r"\d{4}\s*[-–]", line):
                continue
            if any(kw in line.lower() for kw in ["bachelor", "master", "sarjana", "s1", "s2", "diploma", "associate"]):
                # Format: "Bachelor's degree, Computer Science"
                parts = line.split(",")
                edu["degree"] = parts[0].strip()
                edu["field"] = parts[1].strip() if len(parts) > 1 else ""
                break
            if not edu["degree"]:
                edu["field"] = line  # fallback

        return edu

    # ─── Certifications: already handled by _parse_certs_line_by_line ───

    def _parse_skills(self):
        """Parse skills section."""
        boundaries = self._find_section_boundaries("SKILLS")
        if not boundaries:
            return []

        start, end = boundaries
        lines = self.raw_text.split("\n")
        skill_lines = lines[start + 1:end] if end else lines[start + 1:]
        skills = []

        for line in skill_lines:
            line = line.strip()
            if line and len(line) < 80 and not line.startswith("http"):
                # Remove trailing numbers (endorsement counts)
                clean = re.sub(r"\s+\d+\s*$", "", line)
                if clean and not any(
                    kw in clean.lower() for kw in ["top skills", "skill", "keahlian", "page"]
                ):
                    skills.append({"name": clean, "category": "", "level": ""})

        self.logger.info(f"  🛠️ Skills: {len(skills)} found")
        return skills


# ─── Sheets Integration ──────────────────────────────────────────────────────

class LinkedInPDFtoSheets:
    """Parse PDF → sync ke Google Sheets via DeepSeek AI.

    Flow:
      1. Hash check → skip kalo PDF gak berubah (0 token)
      2. Extract raw text dari PDF
      3. Kirim ke DeepSeek API → structured JSON (≈2000 token)
      4. Write ke sheets
      5. Cache hasil biar re-run gak perlu API lagi
    """

    GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

    # Prompt template untuk extract LinkedIn data
    EXTRACT_PROMPT = """Extract structured data from this LinkedIn profile PDF text.

PERSON: FAUZAN AHSANUDIN ALFIKRI
- Universitas Telkom (Data Science / Data Analytics)
- Location: Bandung, Indonesia
- Active in organizational activities at Telkom University

RAW TEXT FROM PDF:
{raw_text}

Return ONLY valid JSON (no markdown, no code blocks) with this EXACT structure:
{{
  "experiences": [
    {{"title": "Job title/position", "company": "Company name", "location": "Bandung, Indonesia", "period": "Mon YYYY - Mon YYYY", "duration": "X months", "type": "Internship|Organization|Part-time|Full-time", "description": "1-2 sentences in Indonesian", "responsibilities": ["responsibility 1", "responsibility 2"], "technologies": ["tech1", "tech2"], "achievements": []}}
  ],
  "certifications": [
    {{"name": "Cert name", "issuer": "Issuer", "issueDate": "YYYY", "expiryDate": "", "credentialId": "", "credentialUrl": "", "description": ""}}
  ],
  "skills": [
    {{"name": "Skill name", "category": "programming|dataScience|tools|soft", "icon": "", "color": "", "yearsOfExperience": "", "description": "", "projects": []}}
  ],
  "education": [
    {{"institution": "Univ name", "degree": "Degree name", "field": "Field of study", "startYear": "YYYY", "endYear": "YYYY", "gpa": ""}}
  ]
}}

CRITICAL RULES:
1. EXPERIENCES - group multiple roles at same org into 1 entry
2. Include ONLY: PRADA (Steering+PR), Univ Telkom (Lab Asst), Al-Fath, ISLAH, GDGoC, Bank Muamalat Intern
3. DO NOT include: SMAN 1 TALAGA, PMB 2024
4. period format: "Mon YYYY - Mon YYYY" or "Mon YYYY - Present"
5. duration: human readable like "2 years", "5 months"
6. type: "Organization" for campus orgs, "Internship" for Bank Muamalat, "Part-time" for Lab Asst
7. responsibilities: 1-3 items array
8. technologies: relevant tech stack array
9. CERTIFICATIONS - from "Certifications" section ONLY, NOT "Honors-Awards"
10. SKILLS - extract ALL skills, categorize properly
11. Return ONLY JSON, nothing else"""

    def __init__(self, pdf_path, logger=None):
        self.pdf_path = pdf_path
        self.logger = logger or setup_logger("PDFtoSheets")
        self._hash_file = Path(pdf_path).parent / ".pdf_hash"
        self._cache_file = Path(pdf_path).parent / ".pdf_cache.json"

    def has_pdf_changed(self):
        """Check if PDF file has changed since last sync (pakai SHA256)."""
        if not self.pdf_path or not Path(self.pdf_path).exists():
            return True
        current_hash = hashlib.sha256(open(self.pdf_path, "rb").read()).hexdigest()[:16]
        if self._hash_file.exists():
            prev_hash = self._hash_file.read_text().strip()
            if prev_hash == current_hash:
                self.logger.info("🔒 PDF tidak berubah sejak sync terakhir. Skip.")
                return False
        # Save new hash
        self._hash_file.write_text(current_hash)
        return True

    def _extract_raw_text(self):
        """Extract raw text dari PDF pake PyMuPDF."""
        try:
            import fitz
        except ImportError:
            self.logger.error("PyMuPDF belum terinstall. pip install pymupdf")
            raise

        doc = fitz.open(str(self.pdf_path))
        text = ""
        for page in doc:
            text += page.get_text("text") + "\n"
        doc.close()

        # Bersihin whitespace berlebih
        text = re.sub(r'\n{3,}', '\n\n', text)
        self.logger.info(f"📄 Raw text: {len(text)} chars extracted")
        return text

    def _call_gemini(self, raw_text):
        """Send raw text to Gemini API → structured JSON."""
        import requests as req

        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            self.logger.error("❌ GEMINI_API_KEY tidak ditemukan!")
            # Fallback ke DeepSeek
            ds_key = os.getenv("DEEPSEEK_API_KEY", "")
            if ds_key:
                return self._call_deepseek_fallback(raw_text, ds_key)
            return None

        prompt = self.EXTRACT_PROMPT.format(raw_text=raw_text)
        
        # Estimasi token
        input_chars = len(prompt)
        self.logger.info(f"🤖 Gemini call — estimasi input: ~{input_chars // 4} tokens")

        url = f"{self.GEMINI_API_URL}?key={api_key}"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 4000,
            }
        }

        try:
            resp = req.post(url, json=payload, timeout=120)
            resp.raise_for_status()
            result = resp.json()
            
            # Token tracking (Gemini doesn't always return usage)
            if "usageMetadata" in result:
                u = result["usageMetadata"]
                self.logger.info(
                    f"📊 Token usage: {u.get('promptTokenCount', '?')} in + "
                    f"{u.get('candidatesTokenCount', '?')} out = "
                    f"{u.get('totalTokenCount', '?')} total"
                )
            
            content = result["candidates"][0]["content"]["parts"][0]["text"]
            return content

        except Exception as e:
            self.logger.error(f"❌ Gemini API error: {e}")
            # Fallback ke DeepSeek
            ds_key = os.getenv("DEEPSEEK_API_KEY", "")
            if ds_key:
                self.logger.info("Fallback ke DeepSeek...")
                return self._call_deepseek_fallback(raw_text, ds_key)
            return None

    def _call_deepseek_fallback(self, raw_text, api_key):
        """Fallback: call DeepSeek API jika Gemini gagal."""
        import requests as req
        
        prompt = self.EXTRACT_PROMPT.format(raw_text=raw_text)
        messages = [
            {"role": "system", "content": "You are a data extraction expert."},
            {"role": "user", "content": prompt},
        ]
        
        try:
            resp = req.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": "deepseek-chat", "messages": messages, "temperature": 0.1, "max_tokens": 4000},
                timeout=120,
            )
            resp.raise_for_status()
            result = resp.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            self.logger.error(f"❌ DeepSeek fallback juga gagal: {e}")
            return None

    def _parse_ai_response(self, content):
        """Parse AI response — handle markdown, extra text, etc."""
        if not content:
            return None

        # Strip markdown code blocks
        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'```\s*', '', content)
        content = content.strip()

        try:
            data = json.loads(content)
            return data
        except json.JSONDecodeError:
            # Try to find JSON object
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            self.logger.error("❌ Gagal parse JSON dari response DeepSeek")
            return None

    def _load_cache(self):
        """Load cached AI result kalo ada."""
        if self._cache_file.exists():
            try:
                with open(self._cache_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def _save_cache(self, data):
        """Save AI result ke cache file."""
        try:
            with open(self._cache_file, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.logger.info("💾 AI result cached")
        except Exception as e:
            self.logger.warning(f"Gagal save cache: {e}")

    def parse_and_sync(self, dry_run=False):
        """Parse PDF via DeepSeek AI → sync ke sheets.

        Optimasi token:
          - Hash check: skip kalo PDF sama               (0 token) ✅
          - Cache: re-use hasil AI sebelumnya             (0 token) ✅
          - DeepSeek call: cuma kalo PDF baru             (~2000 token) ✅
          - Dry-run: parse aja, gak nulis ke sheets       (gratis) ✅
        """
        # Skip kalo PDF gak berubah (0 token)
        if not dry_run and not self.has_pdf_changed():
            cached = self._load_cache()
            if cached:
                self.logger.info("📦 Using cached AI result")
                return cached
            self.logger.info("ℹ️ Tidak ada perubahan. Selesai.")
            return {}

        # Extract raw text
        raw_text = self._extract_raw_text()

        # Dry-run: pakai regex parser (gratis, no API)
        if dry_run:
            self.logger.info("🔍 Dry-run: parsing dengan regex (gratis)")
            parser = LinkedInPDFParser(self.pdf_path, self.logger)
            data = parser.parse()
            self._print_summary(data)
            return data

        # Production: Gemini AI
        self.logger.info("🤖 Parsing dengan Gemini AI...")
        response = self._call_gemini(raw_text)

        if not response:
            self.logger.warning("⚠️ Gemini gagal, fallback ke regex parser")
            parser = LinkedInPDFParser(self.pdf_path, self.logger)
            data = parser.parse()
        else:
            data = self._parse_ai_response(response)
            if not data:
                self.logger.warning("⚠️ Parse AI gagal, fallback ke regex")
                parser = LinkedInPDFParser(self.pdf_path, self.logger)
                data = parser.parse()

        if not data:
            self.logger.error("❌ Gagal extract data dari PDF")
            return {}

        # Cache hasil AI
        self._save_cache(data)

        # Sync to sheets
        if data.get("experiences"):
            self._sync_to_sheet("Experiences", data["experiences"])
        if data.get("certifications"):
            self._sync_to_sheet("Certifications", data["certifications"])
        if data.get("skills"):
            self._sync_to_sheet("Skills", data["skills"])
        if data.get("education"):
            self._sync_to_sheet("Education", data["education"])

        self.logger.info("✅ Sync selesai!")
        return data

    def _sync_to_sheet(self, sheet_name, items):
        """Sync parsed items ke sheet tertentu."""
        from github_to_sheets import SheetsClient

        creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "./secrets/google-service-account.json")
        spreadsheet_id = os.getenv("SPREADSHEET_ID", "")
        if not spreadsheet_id:
            config = load_config()
            spreadsheet_id = config.get("spreadsheet", {}).get("id", "")

        client = SheetsClient(
            credentials_path=creds_path,
            spreadsheet_id=spreadsheet_id,
            logger=self.logger,
        )

        # Map sheet → field mapping (portfolio React format)
        field_map = {
            "Experiences": ["id", "title", "company", "location", "period", "duration", "type", "description", "responsibilities", "technologies", "achievements"],
            "Certifications": ["id", "name", "issuer", "issueDate", "expiryDate", "credentialId", "credentialUrl", "description"],
            "Skills": ["name", "category", "icon", "color", "yearsOfExperience", "description", "projects"],
            "Education": ["institution", "degree", "field", "startYear", "endYear", "gpa"],
        }

        key_map = {
            "Experiences": "title",
            "Certifications": "name",
            "Skills": "name",
            "Education": "institution",
        }

        headers = field_map.get(sheet_name, list(items[0].keys()))
        key_column = key_map.get(sheet_name, headers[0])
        rows = []
        for item in items:
            rows.append({h: item.get(h, "") for h in headers})

        result = client.upsert_data(sheet_name, rows, key_column=key_column)
        self.logger.info(f"✅ {sheet_name}: {len(rows)} rows synced")

    @staticmethod
    def _print_summary(data):
        """Print ringkasan data yang di-parse."""
        print("\n" + "=" * 60)
        print("📄 LINKEDIN PDF — PARSING RESULT (DRY RUN)")
        print("=" * 60)

        print(f"\n👤 {data['header'].get('name', '?')}")
        print(f"   {data['header'].get('headline', '?')}")
        print(f"   {data['header'].get('location', '?')}")
        print(f"   🔗 {data['header'].get('profile_url', '?')}")

        if data["about"]:
            print(f"\n📝 About: {data['about'][:200]}{'...' if len(data['about']) > 200 else ''}")

        print(f"\n💼 Experience ({len(data['experiences'])}):")
        for exp in data["experiences"]:
            print(f"   • {exp.get('company', '?')} — {exp.get('position', '?')}")
            print(f"     {exp.get('start_date', '')} → {exp.get('end_date', '')}")

        print(f"\n🎓 Education ({len(data['education'])}):")
        for edu in data["education"]:
            print(f"   • {edu.get('institution', '?')} — {edu.get('degree', '?')} {edu.get('field', '')}")

        print(f"\n📜 Certifications ({len(data['certifications'])}):")
        for cert in data["certifications"]:
            print(f"   • {cert.get('name', '?')} — {cert.get('issuer', '?')}")

        print(f"\n🛠️ Skills ({len(data['skills'])}):")
        for skill in data["skills"][:10]:
            print(f"   • {skill.get('name', '?')}")
        if len(data["skills"]) > 10:
            print(f"   ... and {len(data['skills']) - 10} more")

        print(f"\n⏱️ Parsed at: {data.get('parsed_at', '?')}")
        print("=" * 60)


# ─── CLI ─────────────────────────────────────────────────────────────────────

def find_latest_pdf():
    """Cari PDF LinkedIn terbaru di folder linkedin_data/."""
    if not PDF_DATA_DIR.exists():
        return None
    pdfs = sorted(PDF_DATA_DIR.glob("*.pdf"), key=os.path.getmtime, reverse=True)
    return pdfs[0] if pdfs else None


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Parse LinkedIn Profile PDF → Google Sheets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/linkedin_pdf_parser.py --pdf linkedin_data/fauzanahsanudin.pdf
  python scripts/linkedin_pdf_parser.py --auto              # Cari PDF terbaru
  python scripts/linkedin_pdf_parser.py --pdf profile.pdf --to-sheets  # + sync
  python scripts/linkedin_pdf_parser.py --pdf profile.pdf --json > data.json
        """,
    )
    parser.add_argument("--pdf", help="Path ke file PDF LinkedIn")
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto-detect PDF terbaru di folder linkedin_data/",
    )
    parser.add_argument(
        "--to-sheets",
        action="store_true",
        help="Sync hasil parsing langsung ke Google Sheets",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output dalam format JSON",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview hasil parsing tanpa nulis ke sheets",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Debug logging",
    )

    args = parser.parse_args()

    # Determine PDF path
    pdf_path = args.pdf
    if args.auto or not pdf_path:
        found = find_latest_pdf()
        if found:
            pdf_path = str(found)
            print(f"📁 Auto-detected PDF: {pdf_path}")
        elif not pdf_path:
            print("❌ Tidak ada PDF ditemukan.")
            print("   Taruh file PDF LinkedIn di: linkedin_data/")
            print("   Atau gunakan: --pdf /path/to/profile.pdf")
            sys.exit(1)

    # Parse
    pipeline = LinkedInPDFtoSheets(pdf_path)

    if args.json:
        data = pipeline.parser.parse()
        print(json.dumps(data, indent=2, ensure_ascii=False))
    elif args.to_sheets:
        pipeline.parse_and_sync(dry_run=False)
    else:
        pipeline.parse_and_sync(dry_run=True)


if __name__ == "__main__":
    main()
