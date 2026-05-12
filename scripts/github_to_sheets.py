#!/usr/bin/env python3
"""
github_to_sheets.py — Sync GitHub repositories ke Google Sheets.

Flow:
  1. Ambil semua repositori dari GitHub (via PyGithub)
  2. Filter & transform data sesuai konfigurasi
  3. Connect ke Google Sheets (via gspread)
  4. Upsert data ke sheet "GitHubRepos"
  5. (Optional) Update sheet "Projects" untuk portfolio

Usage:
  python scripts/github_to_sheets.py
  python scripts/github_to_sheets.py --dry-run   # Preview tanpa nulis
  python scripts/github_to_sheets.py --verbose   # Debug log
"""

import os
import sys
import logging
import argparse
from pathlib import Path

# ─── Setup path ──────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from utils import load_config, setup_logger, format_datetime, now_str, handle_errors

load_dotenv()

# ─── Constants ────────────────────────────────────────────────────────────────

REQUIRED_ENV_VARS = ["GITHUB_TOKEN", "GITHUB_USERNAME"]
SPREADSHEET_ID_ENV = "SPREADSHEET_ID"
SHEET_NAME_ENV = "GITHUB_REPOS_SHEET_NAME"

# ─── GitHub Client ───────────────────────────────────────────────────────────

class GitHubClient:
    """Wrapper untuk PyGithub — fetch repositori."""

    def __init__(self, token, username, config=None, logger=None):
        self.token = token
        self.username = username
        self.config = config or {}
        self.logger = logger or setup_logger("GitHubClient")
        self._client = None

    def _get_client(self):
        """Lazy init PyGithub client."""
        if self._client is None:
            from github import Github, Auth
            auth = Auth.Token(self.token)
            self._client = Github(auth=auth)
            # Verify token works
            try:
                user = self._client.get_user()
                self.logger.info(f"✅ GitHub authenticated as: {user.login}")
            except Exception as e:
                self.logger.error(f"❌ GitHub auth gagal: {e}")
                raise
        return self._client

    @handle_errors()
    def fetch_repos(self):
        """
        Fetch semua public repositori milik user.

        Returns:
            list of dict: data repositori yang sudah difilter & diformat
        """
        client = self._get_client()
        user = client.get_user(self.username)

        repos = user.get_repos(type="public", sort="pushed_at", direction="desc")
        exclude = self.config.get("github", {}).get("exclude_repos", [])
        fields = self.config.get("github", {}).get("fields", [])

        self.logger.info(f"Fetching repos for user: {self.username}")
        results = []

        for repo in repos:
            if repo.name in exclude:
                self.logger.debug(f"  ⏭ Skipping excluded: {repo.name}")
                continue

            repo_data = self._extract_repo_data(repo, fields)
            results.append(repo_data)
            self.logger.debug(f"  ✅ {repo.name} (⭐ {repo.stargazers_count})")

        # Sorting sesuai config
        sort_by = self.config.get("github", {}).get("sort_by", "pushed_at")
        sort_reverse = self.config.get("github", {}).get("sort_reverse", True)

        if sort_by in fields or sort_by == "repo_name":
            try:
                results.sort(
                    key=lambda r: (r.get(sort_by) or "").lower()
                    if isinstance(r.get(sort_by), str)
                    else (r.get(sort_by) or 0),
                    reverse=sort_reverse,
                )
            except Exception as e:
                self.logger.warning(f"Sorting warning: {e}")

        self.logger.info(f"✅ Total repos fetched: {len(results)}")
        return results

    def _extract_repo_data(self, repo, fields):
        """Extract data dari PyGithub Repository object ke dict."""
        data = {}
        last_synced = now_str()

        # Mapping field → PyGithub attribute
        field_map = {
            "repo_name": lambda r: r.name,
            "description": lambda r: (r.description or "").strip(),
            "primary_language": lambda r: r.language or "",
            "stars": lambda r: r.stargazers_count,
            "forks": lambda r: r.forks_count,
            "topics": lambda r: ", ".join(r.get_topics()) if r.get_topics() else "",
            "last_commit": self._get_last_commit_date,
            "created_at": lambda r: format_datetime(r.created_at, "%Y-%m-%d"),
            "repo_url": lambda r: r.html_url,
            "is_archived": lambda r: "Yes" if r.archived else "No",
            "license": lambda r: r.license.spdx_id if r.license else "No License",
            "last_synced": lambda _: last_synced,
        }

        for field in fields:
            extractor = field_map.get(field)
            if extractor:
                try:
                    data[field] = extractor(repo)
                except Exception as e:
                    self.logger.warning(f"Field '{field}' error untuk {repo.name}: {e}")
                    data[field] = ""

        return data

    @staticmethod
    def _get_last_commit_date(repo):
        """Get last commit date — fallback ke updated_at."""
        try:
            commits = repo.get_commits()
            if commits.totalCount > 0:
                return format_datetime(commits[0].commit.committer.date, "%Y-%m-%d")
        except Exception:
            pass
        return format_datetime(repo.updated_at, "%Y-%m-%d")


# ─── Sheets Client ───────────────────────────────────────────────────────────

class SheetsClient:
    """Wrapper untuk gspread — tulis data ke Google Sheets."""

    def __init__(self, credentials_path, spreadsheet_id, logger=None):
        self.credentials_path = credentials_path
        self.spreadsheet_id = spreadsheet_id
        self.logger = logger or setup_logger("SheetsClient")
        self._client = None
        self._spreadsheet = None

    def _get_client(self):
        """Lazy init gspread client dengan service account."""
        if self._client is None:
            import gspread
            from gspread import exceptions as gs_exc

            try:
                gc = gspread.service_account(filename=self.credentials_path)
                self._client = gc
                self.logger.info(f"✅ Google Sheets auth OK")
            except Exception as e:
                self.logger.error(f"❌ Google Sheets auth gagal: {e}")
                self.logger.error(
                    "Pastikan: (1) Service Account JSON benar, "
                    "(2) Spreadsheet sudah di-share ke client_email"
                )
                raise
        return self._client

    def _get_spreadsheet(self):
        """Lazy open spreadsheet."""
        if self._spreadsheet is None:
            client = self._get_client()
            try:
                self._spreadsheet = client.open_by_key(self.spreadsheet_id)
                self.logger.info(
                    f"📊 Spreadsheet opened: {self._spreadsheet.title}"
                )
            except Exception as e:
                self.logger.error(f"Gagal buka spreadsheet: {e}")
                raise
        return self._spreadsheet

    def get_or_create_worksheet(self, title, cols):
        """
        Dapatkan worksheet berdasarkan title. Buat baru kalau belum ada.

        Args:
            title: Nama sheet
            cols: Jumlah kolom (untuk create)

        Returns:
            gspread Worksheet object
        """
        sh = self._get_spreadsheet()

        try:
            ws = sh.worksheet(title)
            self.logger.info(f"📄 Sheet '{title}' ditemukan ({ws.row_count} baris)")
        except Exception:
            self.logger.info(f"🆕 Sheet '{title}' belum ada, membuat baru...")
            ws = sh.add_worksheet(title=title, rows=100, cols=cols)
            self.logger.info(f"✅ Sheet '{title}' dibuat")

        return ws

    @handle_errors()
    def upsert_data(self, sheet_name, data, key_column="repo_name"):
        """
        Upsert data ke sheet. Update baris existing berdasarkan key_column,
        tambah baris baru kalau belum ada.

        Args:
            sheet_name: Nama sheet tujuan
            data: List of dict — data repositori
            key_column: Nama kolom kunci untuk matching

        Returns:
            dict: status hasil sync
        """
        if not data:
            return {"success": True, "rows_written": 0, "message": "No data"}

        ws = self.get_or_create_worksheet(sheet_name, len(data[0]))
        headers = list(data[0].keys())

        # Baca existing data
        existing_rows = ws.get_all_values()
        existing_headers = existing_rows[0] if existing_rows else []
        existing_data = existing_rows[1:] if len(existing_rows) > 1 else []

        # Cari index kolom kunci
        if existing_headers:
            key_idx = existing_headers.index(key_column) if key_column in existing_headers else -1
        else:
            key_idx = -1

        # Build lookup dari existing data
        lookup = {}
        if key_idx >= 0:
            for i, row in enumerate(existing_data):
                if row and len(row) > key_idx:
                    lookup[row[key_idx].strip().lower()] = i + 2  # +2 karena header + 1-indexed

        # Siapkan data untuk di-write
        new_headers = headers
        rows_to_write = []
        rows_updated = 0
        rows_added = 0

        for item in data:
            row = [str(item.get(h, "")) for h in headers]
            repo_key = str(item.get(key_column, "")).strip().lower()

            if repo_key in lookup:
                # Update existing row
                row_num = lookup[repo_key]
                cell_range = f"A{row_num}:{chr(64 + len(headers))}{row_num}"
                ws.update(cell_range, [row])
                rows_updated += 1
            else:
                rows_to_write.append(row)
                rows_added += 1

        # Append new rows
        if rows_to_write:
            if existing_headers:
                # Ada data existing — append setelah baris terakhir
                start_row = len(existing_data) + 2  # +1 header + 1 index
                # Hati-hati: kalau ada update juga, start_row perlu disesuaikan
                # Pakai append_rows aja lebih aman
                ws.append_rows(rows_to_write)

        # Kalau sheet masih kosong, tulis header dulu + data
        if not existing_headers:
            all_rows = [new_headers] + rows_to_write
            ws.update(range_name=f"A1:{chr(64 + len(headers))}{len(all_rows)}", values=all_rows)
            rows_added = len(rows_to_write)

        # Format header (bold)
        ws.format("1:1", {"textFormat": {"bold": True}})

        self.logger.info(
            f"📊 Sync selesai — {rows_updated} updated, {rows_added} added, "
            f"{len(data)} total repos"
        )

        return {
            "success": True,
            "rows_updated": rows_updated,
            "rows_added": rows_added,
            "total_rows": len(data),
            "sheet": sheet_name,
        }

    @handle_errors()
    def clear_and_write(self, sheet_name, data):
        """
        Clear sheet lalu tulis ulang semua data.
        Alternatif untuk upsert — lebih sederhana.

        Args:
            sheet_name: Nama sheet tujuan
            data: List of dict
        """
        if not data:
            return {"success": True, "rows_written": 0}

        ws = self.get_or_create_worksheet(sheet_name, len(data[0]))
        headers = list(data[0].keys())
        all_rows = [headers] + [
            [str(item.get(h, "")) for h in headers] for item in data
        ]

        ws.clear()
        ws.update(
            range_name=f"A1:{chr(64 + len(headers))}{len(all_rows)}",
            values=all_rows,
        )
        ws.format("1:1", {"textFormat": {"bold": True}})

        self.logger.info(
            f"✅ {sheet_name}: {len(data)} repos written (clear + rewrite)"
        )

        return {"success": True, "rows_written": len(data)}


# ─── Main Pipeline ──────────────────────────────────────────────────────────

class Pipeline:
    """Orkestrator — menjalankan GitHub → Sheets sync."""

    def __init__(self, dry_run=False, verbose=False):
        self.dry_run = dry_run
        self.config = load_config()
        level = "DEBUG" if verbose else self.config.get("logging", {}).get("level", "INFO")
        self.logger = setup_logger("Pipeline", level=getattr(logging, level))
        self.results = []

    def run(self):
        """Jalankan pipeline lengkap."""
        self.logger.info("=" * 60)
        self.logger.info("🚀 Portfolio Automation Pipeline — Starting")
        self.logger.info("=" * 60)

        # ── Step 1: Validasi Environment ──
        self.logger.info("\n📋 Step 1: Validasi environment")
        missing = [v for v in REQUIRED_ENV_VARS if not os.getenv(v)]
        missing_sheet = [v for v in [SPREADSHEET_ID_ENV] if not os.getenv(v)]
        if missing:
            self.logger.error(f"❌ Missing env vars: {missing}")
            self.logger.error("   Copy .env.example ke .env dan isi nilainya.")
            return False
        if missing_sheet:
            self.logger.warning(f"⚠️ {SPREADSHEET_ID_ENV} tidak di set, pakai dari config")
        self.logger.info("✅ Environment OK")

        # ── Step 2: Fetch GitHub Data ──
        self.logger.info("\n📋 Step 2: Fetch GitHub repositories")
        gh = GitHubClient(
            token=os.getenv("GITHUB_TOKEN"),
            username=os.getenv("GITHUB_USERNAME"),
            config=self.config,
            logger=self.logger,
        )
        repos = gh.fetch_repos()

        if isinstance(repos, dict) and not repos.get("success", True):
            self.logger.error(f"❌ GitHub fetch gagal: {repos.get('error')}")
            return False

        if not repos:
            self.logger.warning("⚠️ Tidak ada repositori yang ditemukan")
            return False

        self.logger.info(f"✅ {len(repos)} repositori berhasil diambil")

        # Print summary
        for r in repos:
            stars_str = f"⭐ {r.get('stars', 0)}" if r.get('stars', 0) > 0 else "   "
            self.logger.info(f"   {r.get('repo_name', '?'):40s} {stars_str} | {r.get('primary_language', ''):15s} | {r.get('last_commit', '')}")

        # ── Step 3: Write to Google Sheets ──
        self.logger.info("\n📋 Step 3: Sync ke Google Sheets")

        if self.dry_run:
            self.logger.info("🔍 DRY RUN — tidak ada data yang ditulis")
            self.logger.info(f"   Akan menulis {len(repos)} baris ke sheet")
            return True

        creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "./secrets/google-service-account.json")
        sheet_name = os.getenv(SHEET_NAME_ENV, self.config.get("spreadsheet", {}).get("sheets", {}).get("github_repos", "GitHubRepos"))
        spreadsheet_id = os.getenv(SPREADSHEET_ID_ENV, self.config.get("spreadsheet", {}).get("id", ""))

        sheets = SheetsClient(
            credentials_path=creds_path,
            spreadsheet_id=spreadsheet_id,
            logger=self.logger,
        )

        strategy = self.config.get("sync", {}).get("strategy", "upsert")
        key_column = self.config.get("sync", {}).get("key_column", "repo_name")

        if strategy == "upsert":
            result = sheets.upsert_data(sheet_name, repos, key_column=key_column)
        else:
            result = sheets.clear_and_write(sheet_name, repos)

        if isinstance(result, dict) and not result.get("success", True):
            self.logger.error(f"❌ Sheets write gagal: {result.get('error')}")
            return False

        self.results.append(result)

        # ── Step 4: Summary ──
        self.logger.info("\n" + "=" * 60)
        self.logger.info("📊 SYNC SUMMARY")
        self.logger.info("=" * 60)
        for r in self.results:
            if isinstance(r, dict) and r.get("success"):
                self.logger.info(f"   Sheet: {r.get('sheet', '?')}")
                self.logger.info(f"   Updated: {r.get('rows_updated', 0)} rows")
                self.logger.info(f"   Added:   {r.get('rows_added', 0)} rows")
                self.logger.info(f"   Total:   {r.get('total_rows', 0)} repos")

        self.logger.info("✅ Pipeline completed successfully!")
        return True


# ─── Entry Point ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Sync GitHub repositori ke Google Sheets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/github_to_sheets.py              # Full sync
  python scripts/github_to_sheets.py --dry-run    # Preview only
  python scripts/github_to_sheets.py --verbose    # Debug mode
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview perubahan tanpa menulis ke sheets",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Log level DEBUG untuk troubleshooting",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="portfolio-automation v1.0.0",
    )

    args = parser.parse_args()

    pipeline = Pipeline(dry_run=args.dry_run, verbose=args.verbose)
    success = pipeline.run()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
