# LinkedIn Integration Strategy

## The Problem — dan Solusi PDF 🎯

LinkedIn API v2 **sangat terbatas** untuk individual developers.
Tapi ada celah: **LinkedIn punya fitur "Save to PDF" resmi** yang:

- ✅ 100% Terms of Service compliant
- ✅ Data lebih lengkap daripada API (experience, education, certs, skills)
- ✅ Bisa di-parse otomatis dengan Python (PyMuPDF)
- ✅ tinggal commit file PDF → GitHub Actions auto-detect & sync

### Flow PDF (Recommended)

```
Your Browser                         GitHub
    │                                   │
    ├── Buka linkedin.com/in/...        │
    ├── Klik "More..."                  │
    ├── "Save to PDF"                   │
    │   (Print → Save as PDF)           │
    │                                   │
    └── Simpan PDF ──────────────────▶  portfolio-automation/linkedin_data/
                                        │
                                        ▼
                                GitHub Actions detect perubahan
                                        │
                                        ▼
                                linkedin_pdf_parser.py --auto --to-sheets
                                        │
                                        ▼
                                Google Sheets terupdate!
                                (Experiences, Education, Certifications, Skills)
```

## Cara Download PDF dari LinkedIn

1. Buka https://www.linkedin.com/in/fauzanahsanudin/
2. Klik tombol **"More..."** (di sebelah kanan "Message")
3. Pilih **"Save to PDF"**
   - Kalau gak ada opsi itu, alternatifnya:
   - **Ctrl+P** (Print) → Destination: **Save as PDF**
4. Simpan file dengan nama: `fauzanahsanudin_profile_2026-05.pdf`
5. Taruh di folder: `portfolio-automation/linkedin_data/`
6. Commit & push ke GitHub, atau langsung jalankan:

```bash
python scripts/linkedin_pdf_parser.py --auto --dry-run    # Preview
python scripts/linkedin_pdf_parser.py --auto --to-sheets  # Sync ke sheets
```

## Yang Bisa Di-Parse dari PDF

| Section | Sheet Target | Contoh Data |
|---------|-------------|-------------|
| Header (nama, headline) | PersonalInfo | Fauzan Ahsanudin Alfikri |
| About | - (buat referensi) | Data science student... |
| Experience | Experiences | Telkom University |
| Education | Education | Telkom University, S1 Informatics |
| Certifications | Certifications | FIND IT 2025 Finalist |
| Skills | Skills | Python, Machine Learning, Go |

| Fitur | Developer Individu | Company Page |
|-------|-------------------|--------------|
| Baca profil sendiri | ✅ (r_liteprofile) | ✅ |
| Baca email | ✅ (r_emailaddress) | ✅ |
| Posting konten | ❌ | ✅ (butuh approval) |
| Baca feed | ❌ | ❌ |
| Search orang | ❌ | ❌ |
| Manage halaman | ❌ | ✅ (rw_organization_admin) |

**Sumber**: https://learn.microsoft.com/en-us/linkedin/

Sejak Maret 2023, LinkedIn juga **menutup API untuk "Share on LinkedIn"**
untuk aplikasi non-enterprise. Permintaan akses baru biasanya ditolak
kecuali untuk Company Pages yang terverifikasi.

---

## Recommended Strategy: Hybrid

### Approach 1: `manual` — Paling Praktis ✅ (Default)

**Cara kerja:**
1. Kamu entry data LinkedIn (experience, certification) langsung ke sheet
2. Script `linkedin.py` bantu generate template yang rapi
3. Data dari sheet bisa dipakai untuk portfolio, resume generator, dll

**Pros:**
- 100% reliable — no API, no scraping
- Kamu kontrol penuh data yang masuk
- Bisa format sesuai kebutuhan sheet yang sudah ada

**Cons:**
- Manual entry — tapi sekali setup, update jarang (tiap ganti kerja/sertif baru)

**Implementation:**
```bash
# Generate template untuk diisi
python scripts/linkedin.py --template Experiences
python scripts/linkedin.py --template Certifications
```

Output-nya berupa tabel yang tinggal di-copy ke Google Sheet.

---

### Approach 2: `scraper` — One-Time Data Gathering

**Cara kerja:**
- Scrape profil LinkedIn publik dengan requests + BeautifulSoup
- Ambil data experience, education, certifications

**⚠️ Risiko:**
- Melanggar LinkedIn Terms of Service
- IP bisa di-rate limit / block
- Data terbatas karena LinkedIn pake banyak JS rendering
- Struktur HTML sering berubah (maintenance tinggi)

**Rekomendasi:** Hanya untuk satu kali ambil data awal, bukan automation rutin.

---

### Approach 3: `api` — Jika Akses Disetujui

Kalau suatu saat LinkedIn approve aplikasi-mu:

1. Buat aplikasi di https://www.linkedin.com/developers/
2. Minta scope: `r_liteprofile`, `r_emailaddress`, `w_member_social`
3. Setup OAuth 2.0 dengan PKCE
4. Dapetin access token → simpan sebagai `LINKEDIN_ACCESS_TOKEN`

Tapi realistisnya, ini **sulit** untuk individual dev.

---

## Alternative: Push Update ke LinkedIn (Outbound)

Daripada ambil data DARI LinkedIn, gimana kalau kita push update KE LinkedIn?

### Workflow: GitHub → LinkedIn Auto-Post

```
Push ke GitHub (star/topic baru)
        │
        ▼
GitHub Actions detect perubahan
        │
        ▼
Generate postingan LinkedIn (format teks)
        │
        ▼
Kirim via ... (sini masalahnya)
```

**Masalah:** LinkedIn gak kasih API buat posting ke personal profile.

**Solusi kreatif:**

### A. LinkedIn Mobile Notification PWA
Bikin sistem yang ngirim notifikasi ke HP kamu:
```
GitHub activity → scripts detect → push notification
                      ↓
            Kamu buka LinkedIn → copy-paste postingan
```

Ini pake Telegram Bot / ntfy.sh buat notifikasi, bukan otomatis posting.

### B. Buffer / Hootsuite (Third-Party)
Platform seperti Buffer, Hootsuite, Later punya akses LinkedIn API.
Workflow:
```
Script → generate posting → API Buffer → Jadwalkan ke LinkedIn
```

Kelemahan: butuh akun berbayar untuk fitur API.

### C. Semi-Manual: Email Reminder
```
Cron job tiap minggu → kirim email ke kamu:
  "This week's GitHub activity:
   - coppa-risk-prediction: ⭐ +1 star
   - New repo: awesome-project
  
  Post to LinkedIn? Copy this text:
  🚀 Just shipped [project] — [description]"
```

Ini yang paling realistis: **notifikasi untuk posting manual**.

---

## Recommended Setup for Fauzan

```
1. Entry manual data LinkedIn (sekali)
   ↓
2. Sync GitHub → Sheets otomatis (tiap 6 jam)
   ↓
3. Weekly email reminder untuk posting update ke LinkedIn
   ↓
4. Portfolio website baca dari Google Sheets
```

Dengan setup ini:
- GitHub activity **otomatis masuk** ke spreadsheet 📊
- LinkedIn data **manual tapi rapi** dengan template ✍️
- Portfolio website **real-time** dari sheet 🚀
- Kamu tetap bisa posting ke LinkedIn **tiap minggu** 🎯

## Template untuk Manual Entry

### Experiences
```
id, company, position, start_date, end_date, description, location, employment_type
1, "Telkom University", "Data Science Student", "2022-08", "2026-07", "Studying Informatics Engineering", "Bandung", "Full-time"
```

### Certifications
```
id, name, issuer, issue_date, expiry_date, credential_id, credential_url
1, "FIND IT 2025 Finalist", "Universitas Gadjah Mada", "2025-09", "", "FINDIT-2025-XXX", ""
```
