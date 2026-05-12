#!/usr/bin/env python3
"""
github_to_projects_ai.py — Transform GitHub repos → Projects sheet with AI ✨

Flow:
  1. Baca data dari sheet GitHubRepos (raw)
  2. Kirim ke DeepSeek API → generate konten portfolio
  3. Tulis hasilnya ke sheet Projects

Cara pakai:
  # Set DEEPSEEK_API_KEY di .env dulu
  python scripts/github_to_projects_ai.py                    # Generate semua repo baru
  python scripts/github_to_projects_ai.py --dry-run           # Preview aja
  python scripts/github_to_projects_ai.py --check-only        # Cek aja (gak pake AI)
  python scripts/github_to_projects_ai.py --repo coppa-risk   # 1 repo spesifik
  python scripts/github_to_projects_ai.py --batch 5           # Proses 5 per batch

OPTIMASI BIAYA:
  ✅ Hanya generate untuk repo BARU (cek githubUrl duplikat)
  ✅ --check-only: cek jumlah repo baru TANPA manggil API
  ✅ Dry-run gratis (gak pake AI, gak nulis ke sheet)
  ✅ Batch processing + rate limiting otomatis
"""

import os
import sys
import json
import re
import argparse
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
from utils import load_config, setup_logger, now_str, handle_errors

load_dotenv()

# ─── DeepSeek API ────────────────────────────────────────────────────────────

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"  # deepseek-v4

# Urutan kolom di sheet Projects
PROJECTS_HEADERS = [
    "id", "title", "slug", "shortDescription", "description", "image",
    "tags", "technologies", "features", "category", "status", "year",
    "duration", "role", "teamSize", "githubUrl", "demoUrl", "videoUrl",
    "featured", "highlights",
]


def call_deepseek(api_key, messages, temperature=0.7, max_retries=3):
    """Call DeepSeek API dengan retry logic."""
    import requests

    for attempt in range(max_retries):
        try:
            resp = requests.post(
                DEEPSEEK_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": DEEPSEEK_MODEL,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": 4000,
                },
                timeout=120,
            )
            resp.raise_for_status()
            result = resp.json()
            content = result["choices"][0]["message"]["content"]
            return content
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                print(f"  ⚠️ Retry {attempt+1}/{max_retries} after {wait}s: {e}")
                time.sleep(wait)
            else:
                raise
    return None


# ─── System Prompt ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a Senior Data Science Portfolio Curator. Your job is to transform raw GitHub repository data into polished, portfolio-ready project entries for a data scientist's portfolio website.

For each repository, you will receive:
- repo_name: The GitHub repository name
- description: The raw GitHub description (may be empty or technical)
- primary_language: Main programming language
- topics: Comma-separated list of topics (may be empty)
- stars, forks: Social metrics
- last_commit: Date of last commit

You must return a VALID JSON object (no markdown, no code blocks, pure JSON only) with these exact fields:

{
  "title": "Clean project title (e.g., 'Fossil - Water Potability Prediction')",
  "slug": "url-friendly-slug (lowercase, hyphens)",
  "shortDescription": "One compelling sentence describing the project (max 120 chars)",
  "description": "2-3 paragraph detailed description. First paragraph: problem statement. Second: solution/approach. Third: results/impact. Professional tone, 150-250 words total.",
  "tags": ["Array of 3-6 relevant tags as strings, based on topics and language"],
  "technologies": ["Array of 5-8 technologies used, based on language and topics. Include versions where known"],
  "features": ["Array of 3-5 key features as string bullets"],
  "category": "Best category: 'Machine Learning' | 'Data Science' | 'Computer Vision' | 'Web Development' | 'Mobile Development' | 'Tools' | 'Academic' | 'DevOps' | 'Backend' | 'Other'",
  "status": "'Completed' | 'In Progress' | 'Maintained' | 'Archived'",
  "year": "4-digit year from repo creation or last_commit",
  "duration": "Estimated duration like '2 months', '1 semester', '1 week' (be realistic for a student project)",
  "role": "Role: 'Data Scientist' | 'ML Engineer' | 'Full Stack Developer' | 'Researcher' | 'Solo Developer' | 'Team Lead'",
  "teamSize": "Estimated team size as number or string like '1', '2-3', '4+'",
  "highlights": ["Array of 3 specific, measurable achievements. Use numbers/percentages if possible. Example: 'Achieved 89% accuracy on test set'"]
}

RULES:
1. Be HONEST — don't invent metrics you don't know. Use realistic estimates.
2. If description is empty, infer the project purpose from repo_name and topics.
3. Use professional but engaging language.
4. For student/academic projects, be clear it's a course project.
5. Tags should be a mix of: technical (Python, PyTorch) and domain (NLP, Classification).
6. Return ONLY the JSON object, no other text.
7. If the repo looks like a simple exercise/assignment, keep description brief but professional.
8. For "highlights", infer from repo context what achievements make sense."""


def build_repo_prompt(repo):
    """Build user prompt untuk satu repositori."""
    return f"""Transform this GitHub repository into a portfolio project entry:

repo_name: {repo.get('repo_name', 'N/A')}
description: {repo.get('description', 'N/A')}
primary_language: {repo.get('primary_language', 'N/A')}
topics: {repo.get('topics', 'N/A')}
stars: {repo.get('stars', 0)}
forks: {repo.get('forks', 0)}
last_commit: {repo.get('last_commit', 'N/A')}
created_at: {repo.get('created_at', 'N/A')}
repo_url: {repo.get('repo_url', 'N/A')}
is_archived: {repo.get('is_archived', 'N/A')}
license: {repo.get('license', 'N/A')}

Return ONLY the JSON object."""


def parse_ai_response(content):
    """Parse AI response — handle markdown code blocks, extra text, etc."""
    if not content:
        return None

    # Strip markdown code blocks
    content = re.sub(r'```json\s*', '', content)
    content = re.sub(r'```\s*', '', content)
    content = content.strip()

    # Try parsing JSON
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Try to find JSON object in the response
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return None
    return None


# ─── AI Pipeline ────────────────────────────────────────────────────────────

class GitHubToProjectsAI:
    """Transform GitHub repos → Projects sheet via DeepSeek AI."""

    def __init__(self, api_key=None, dry_run=False, logger=None):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.dry_run = dry_run
        self.logger = logger or setup_logger("GitHubToProjectsAI")
        self.repos_data = []
        self.existing_projects = {}  # key: githubUrl

        if not self.api_key:
            self.logger.error("❌ DEEPSEEK_API_KEY tidak ditemukan! Set di .env dulu.")

    def load_repos_from_sheets(self):
        """Baca data repositori dari sheet GitHubRepos."""
        import gspread

        creds = os.getenv("GOOGLE_CREDENTIALS_PATH", "./secrets/google-service-account.json")
        spreadsheet_id = os.getenv("SPREADSHEET_ID", "")
        if not spreadsheet_id:
            cfg = load_config()
            spreadsheet_id = cfg.get("spreadsheet", {}).get("id", "")

        gc = gspread.service_account(filename=creds)
        sh = gc.open_by_key(spreadsheet_id)

        # Baca GitHubRepos
        ws = sh.worksheet(os.getenv("GITHUB_REPOS_SHEET_NAME", "GitHubRepos"))
        headers = ws.row_values(1)
        rows = ws.get_all_values()[1:]

        self.repos_data = []
        for row in rows:
            if not row or not row[0]:
                continue
            repo = dict(zip(headers, row))
            self.repos_data.append(repo)

        # Baca Projects existing (untuk deteksi duplikat)
        try:
            ws_proj = sh.worksheet("Projects")
            proj_headers = ws_proj.row_values(1)
            proj_rows = ws_proj.get_all_values()[1:]

            for row in proj_rows:
                if len(row) >= 16:
                    proj = dict(zip(proj_headers, row))
                    if proj.get("githubUrl"):
                        self.existing_projects[proj["githubUrl"].strip().lower()] = proj
        except Exception:
            pass

        self.logger.info(f"📖 Loaded {len(self.repos_data)} repos from GitHubRepos sheet")
        self.logger.info(f"📖 Existing projects: {len(self.existing_projects)}")
        return self.repos_data

    def get_new_repos(self):
        """Dapatkan repos yang belum ada di Projects sheet."""
        new_repos = []
        existing_repos = []

        for repo in self.repos_data:
            repo_url = repo.get("repo_url", "").strip().lower()
            if repo_url in self.existing_projects:
                existing_repos.append(repo)
            else:
                new_repos.append(repo)

        self.logger.info(f"✅ Already in Projects: {len(existing_repos)}")
        self.logger.info(f"🆕 New to generate: {len(new_repos)}")
        return new_repos, existing_repos

    def generate_project_entry(self, repo):
        """Generate satu project entry via DeepSeek."""
        if not self.api_key:
            return None

        prompt = build_repo_prompt(repo)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        repo_name = repo.get("repo_name", "?")
        self.logger.info(f"  🤖 Generating for: {repo_name}")

        try:
            content = call_deepseek(self.api_key, messages)
            parsed = parse_ai_response(content)

            if not parsed:
                self.logger.warning(f"  ⚠️ Gagal parse response untuk {repo_name}")
                self.logger.debug(f"     Raw: {content[:200] if content else 'None'}")
                return None

            # Tambahkan id dan githubUrl dari data asli
            parsed["githubUrl"] = repo.get("repo_url", "")
            parsed["id"] = ""  # Akan di-set saat nulis ke sheet

            self.logger.info(f"  ✅ {parsed.get('title', repo_name)} — {parsed.get('category', '?')}")
            return parsed

        except Exception as e:
            self.logger.error(f"  ❌ Error generating {repo_name}: {e}")
            return None

    def generate_all(self, repo_filter=None, batch_size=5):
        """Generate project entries untuk semua repo baru."""
        if not self.repos_data:
            self.load_repos_from_sheets()

        new_repos, existing = self.get_new_repos()

        # Filter specific repo
        if repo_filter:
            new_repos = [
                r for r in new_repos
                if repo_filter.lower() in r.get("repo_name", "").lower()
            ]
            self.logger.info(f"🔍 Filtered to: {len(new_repos)} repos matching '{repo_filter}'")

        if not new_repos:
            self.logger.info("🎉 Semua repos sudah ada di Projects! Tidak ada yang perlu di-generate.")
            return []

        results = []
        total = len(new_repos)
        cost_estimate = total * 0.002  # ~$0.002 per repo

        self.logger.info(f"\n📊 Akan generate {total} project entries (estimated ~${cost_estimate:.3f})")

        for i in range(0, total, batch_size):
            batch = new_repos[i:i + batch_size]
            self.logger.info(f"\n--- Batch {i//batch_size + 1}/{(total-1)//batch_size + 1} ({len(batch)} repos) ---")

            for repo in batch:
                entry = self.generate_project_entry(repo)
                if entry:
                    results.append(entry)

                # Rate limiting
                time.sleep(1.5)

        self.logger.info(f"\n✅ Generated {len(results)}/{total} project entries")
        return results

    def write_to_sheets(self, entries):
        """Tulis generated entries ke sheet Projects."""
        if not entries:
            self.logger.info("Tidak ada data untuk ditulis.")
            return

        if self.dry_run:
            self._print_preview(entries)
            return

        import gspread
        from gspread import exceptions as gs_exc

        creds = os.getenv("GOOGLE_CREDENTIALS_PATH", "./secrets/google-service-account.json")
        spreadsheet_id = os.getenv("SPREADSHEET_ID", "")

        gc = gspread.service_account(filename=creds)
        sh = gc.open_by_key(spreadsheet_id)
        ws = sh.worksheet("Projects")

        # Dapatkan ID terakhir
        existing = ws.get_all_values()
        next_id = len(existing)  # Baris terakhir = ID terakhir

        # Siapkan rows
        rows = []
        for entry in entries:
            next_id += 1
            row = []
            for h in PROJECTS_HEADERS:
                val = entry.get(h, "")
                if isinstance(val, list):
                    val = json.dumps(val, ensure_ascii=False)
                if h == "id":
                    val = str(next_id)
                row.append(val)
            rows.append(row)

        # Append ke sheet
        ws.append_rows(rows)
        self.logger.info(f"✅ {len(rows)} project entries written to Projects sheet (ID {next_id - len(rows) + 1} - {next_id})")

    def _print_preview(self, entries):
        """Print preview hasil generate."""
        print("\n" + "=" * 70)
        print(f"📋 PREVIEW — {len(entries)} generated project entries")
        print("=" * 70)

        for i, entry in enumerate(entries, 1):
            print(f"\n--- {i}. {entry.get('title', '?')} ---")
            print(f"   Slug:        {entry.get('slug', '')}")
            print(f"   Short Desc:  {entry.get('shortDescription', '')[:80]}...")
            print(f"   Description: {entry.get('description', '')[:150]}...")
            print(f"   Category:    {entry.get('category', '')}")
            print(f"   Tags:        {', '.join(entry.get('tags', [])[:4])}")
            print(f"   Technologies:{', '.join(entry.get('technologies', [])[:4])}")
            print(f"   Features:    {' | '.join(entry.get('features', [])[:3])}")
            print(f"   Highlights:  {' | '.join(entry.get('highlights', [])[:3])}")
            print(f"   GitHub:      {entry.get('githubUrl', '')}")
            print(f"   Status:      {entry.get('status', '')} | Year: {entry.get('year', '')}")
            print(f"   Role:        {entry.get('role', '')} | Team: {entry.get('teamSize', '')}")

        print("\n" + "=" * 70)
        print(f"Total: {len(entries)} entries ready to write")
        print("=" * 70)


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="AI-powered GitHub → Projects sheet transformer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/github_to_projects_ai.py                          # Generate semua repo baru
  python scripts/github_to_projects_ai.py --dry-run                 # Preview aja
  python scripts/github_to_projects_ai.py --repo coppa             # 1 repo spesifik
  python scripts/github_to_projects_ai.py --batch 3                # 3 per batch
  python scripts/github_to_projects_ai.py --repo coppa --dry-run   # Preview 1 repo
        """,
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview tanpa nulis")
    parser.add_argument("--check-only", action="store_true", help="Cek jumlah repo baru tanpa panggil AI")
    parser.add_argument("--repo", help="Generate spesifik repo (filter by name)")
    parser.add_argument("--batch", type=int, default=5, help="Jumlah per batch (default: 5)")
    parser.add_argument("--verbose", action="store_true", help="Debug log")

    args = parser.parse_args()

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("❌ DEEPSEEK_API_KEY belum di-set!")
        print("   Tambahkan ke .env: DEEPSEEK_API_KEY=sk-xxx")
        sys.exit(1)

    pipeline = GitHubToProjectsAI(api_key=api_key, dry_run=args.dry_run or args.check_only)
    pipeline.load_repos_from_sheets()

    # --check-only: cek aja tanpa AI
    if args.check_only:
        new_repos, existing = pipeline.get_new_repos()
        total_sheets = len(pipeline.repos_data)
        print(f"\n📊 CEK OPTIMASI BIAYA")
        print(f"{'='*50}")
        print(f"  Total repos di GitHubRepos: {total_sheets}")
        print(f"  Sudah di Projects sheet:    {len(existing)}")
        print(f"  Belum di Projects sheet:    {len(new_repos)}")
        print(f"{'='*50}")
        if new_repos:
            print(f"\n🆕 {len(new_repos)} repo baru — butuh generate:")
            for r in new_repos:
                print(f"  • {r.get('repo_name', '?')}")
            print(f"\n💰 Estimasi biaya AI: ~${len(new_repos) * 0.002:.3f}")
            print(f"   Jalankan: python scripts/github_to_projects_ai.py")
        else:
            print(f"\n✅ SEMUA SUDAH TERCOVER! Gak perlu AI.")
        sys.exit(0)

    if args.repo:
        # Generate 1 spesifik repo
        new_repos, _ = pipeline.get_new_repos()
        filtered = [r for r in new_repos if args.repo.lower() in r.get("repo_name", "").lower()]
        if not filtered:
            # Coba cari di semua repos
            filtered = [r for r in pipeline.repos_data if args.repo.lower() in r.get("repo_name", "").lower()]
        if filtered:
            pipeline.repos_data = filtered
        else:
            print(f"❌ Repo '{args.repo}' tidak ditemukan")
            sys.exit(1)

    entries = pipeline.generate_all(batch_size=args.batch)
    pipeline.write_to_sheets(entries)

    # Save backup ke file JSON
    if entries and not args.dry_run:
        backup_path = Path(__file__).resolve().parent.parent / "logs" / f"projects_ai_{now_str()[:10]}.json"
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        with open(backup_path, "w") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Backup saved: {backup_path}")


if __name__ == "__main__":
    main()
