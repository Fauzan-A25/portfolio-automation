# Portfolio Automation Pipeline

> **Otomatiskan sinkronisasi GitHub → Google Sheets + integrasi LinkedIn**
> Dibuat untuk Fauzan Ahsanudin (Fauzan-A25)

## Arsitektur Sistem

```
┌─────────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│   GitHub REST API   │────▶│  Python Script   │────▶│  Google Sheets API  │
│   (PyGithub)        │     │  (sync engine)   │     │  (gspread)          │
└─────────────────────┘     └──────────────────┘     └─────────────────────┘
                                    │
                                    ▼
                            ┌──────────────────┐
                            │  LinkedIn Data   │
                            │  (optional)      │
                            └──────────────────┘

Pemicu Eksekusi:
  ⏰ Cron Job (tiap 6 jam)      → Linux server / VPS
  🔄 GitHub Actions             → Setiap push ke repo ini
  🐳 Docker Container           → Deploy di mana aja
  📄 LinkedIn PDF (baru!)       → Download PDF → auto-parse → sheets
```

### Komponen Utama

| Komponen | Peran |
|----------|-------|
| **`github_to_sheets.py`** | Sync repositori GitHub ke sheet "GitHubRepos" |
| **`linkedin_scraper.py`** | Ambil data publik LinkedIn (profil, post) |
| **`utils.py`** | Shared helpers (logger, date formatting, error handler) |
| **`config.yaml`** | Konfigurasi — spreadsheet ID, sheet name, dll |

## Sheet Structure (Google Sheets)

Spreadsheet: **Database_Fauzan_Ahsn**
Sheet target: **GitHubRepos** (akan dibuat otomatis)

### Kolom Sheet "GitHubRepos"

| Kolom | Source | Contoh |
|-------|--------|--------|
| repo_name | GitHub | coppa-risk-prediction-findit2025-fauzan |
| description | GitHub | ML model to predict mobile app risk... |
| primary_language | GitHub | Jupyter Notebook |
| stars | GitHub | 1 |
| forks | GitHub | 0 |
| topics | GitHub | machine-learning, xgboost, coppa |
| last_commit | GitHub | 2025-09-29 |
| created_at | GitHub | 2025-08-15 |
| repo_url | GitHub | https://github.com/Fauzan-A25/... |
| is_archived | GitHub | FALSE |
| license | GitHub | MIT |
| last_synced | Script | 2026-05-12 22:30:00 |

### Sheet Lain di Database_Fauzan_Ahsn

Sheet yang sudah ada (digunakan oleh portfolio React):
- **PersonalInfo** — data diri
- **SocialLinks** — link sosial media
- **Projects** — data project untuk portfolio (bisa diisi dari GitHubRepos)
- **Skills** — skill set
- **Education** — riwayat pendidikan
- **Experiences** — pengalaman kerja
- **Certifications** — sertifikasi
- **Stats** — statistik portfolio
- **ProjectCategories** — kategori project
- **NavLinks / HeroTypingTexts / AboutContent / SkillsContent**
- **ContactContent / ProjectsContent / FooterContent**
- **EmailJSConfig** — konfigurasi email form

## Quick Start

```bash
# 1. Clone / masuk ke folder
cd ~/portfolio-automation

# 2. Install dependencies
pip install -r requirements.txt

# 3. Setup credentials
cp .env.example .env
# Edit .env — isi GOOGLE_CREDENTIALS_PATH dan GITHUB_TOKEN

# 4. Jalankan sync
python scripts/github_to_sheets.py

# 5. Auto-schedule (cron)
crontab -e
# Tambahkan: 0 */6 * * * cd ~/portfolio-automation && python scripts/github_to_sheets.py >> logs/sync.log 2>&1
```

## Prerequisites

Lihat file `docs/prerequisites.md` untuk panduan lengkap setup:
1. **GitHub Personal Access Token** (repo:public_repo scope)
2. **Google Cloud Console** — enable Google Sheets API + buat Service Account
3. **LinkedIn** (opsional) — API atau scraping approach
