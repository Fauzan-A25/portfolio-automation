# Prerequisites Setup Guide

## 1. GitHub Personal Access Token

1. Buka https://github.com/settings/tokens
2. Klik **"Generate new token (fine-grained)"**
3. Atur:
   - **Repository access**: "Public Repositories (read-only)"
   - **Permissions**: `Contents: Read` (default buat public repo)
4. Copy token → simpan di `.env` sebagai `GITHUB_TOKEN=ghp_...`

**Catatan**: Token ini hanya read-only, akses terbatas ke repo publik.

## 2. Google Cloud Console — Service Account

### 2.1. Enable Google Sheets API

1. Buka https://console.cloud.google.com/
2. Buat project baru (atau pilih "My First Project")
3. Pergi ke **APIs & Services > Library**
4. Cari "Google Sheets API" → Enable

### 2.2. Buat Service Account

1. **APIs & Services > Credentials**
2. Klik **"Create Credentials" > "Service Account"**
3. Isi nama: "portfolio-automation"
4. Klik **Done** (skip Grant access)

### 2.3. Download JSON Key

1. Di halaman Service Accounts, klik email service account yang baru
2. Tab **Keys** → **Add Key** → **Create New Key**
3. Pilih **JSON** → **Create**
4. File akan terdownload otomatis
5. Pindahkan ke `~/portfolio-automation/secrets/google-service-account.json`

### 2.4. Share Spreadsheet

1. Buka Google Sheet-mu: https://docs.google.com/spreadsheets/d/1SjfncmLV-Xarqir6ur0G3YvJD0m5RogjBxOkTSoEgdU/
2. Klik **Share** (pojok kanan atas)
3. Paste **client_email** dari file JSON service account
4. Role: **Editor**
5. Uncheck "Notify people" → **Share**

## 3. Environment File

```bash
cp .env.example .env
```

Edit `.env` dan isi:
- `GITHUB_TOKEN=ghp_your_token_here`
- `GOOGLE_CREDENTIALS_PATH=./secrets/google-service-account.json`

## 4. Verifikasi

```bash
python scripts/github_to_sheets.py --dry-run --verbose
```

Harusnya muncul:
- ✅ GitHub authenticated as: Fauzan-A25
- ✅ 23 repositori fetched
- All 23 repos listed
- (Tidak nulis ke sheet karena dry-run)
