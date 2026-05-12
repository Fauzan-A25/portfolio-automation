# Database_Fauzan_Ahsn — Sheet Schema Documentation

Dokumentasi struktur sheet di spreadsheet **Database_Fauzan_Ahsn**.
Spreadsheet ini dipakai sebagai **CMS backend** untuk portfolio website React
dan sebagai **central database** untuk pipeline automation.

---

## Sheet: GitHubRepos (NEW — akan dibuat script)

Data repositori GitHub, otomatis di-sync tiap 6 jam.

| Kolom | Tipe | Deskripsi | Sumber |
|-------|------|-----------|--------|
| repo_name | text | Nama repositori | GitHub API |
| description | text | Deskripsi repositori | GitHub API |
| primary_language | text | Bahasa utama | GitHub API |
| stars | number | Jumlah bintang | GitHub API |
| forks | number | Jumlah fork | GitHub API |
| topics | text | Topics (comma-separated) | GitHub API |
| last_commit | date | Tanggal commit terakhir (YYYY-MM-DD) | GitHub API |
| created_at | date | Tanggal dibuat | GitHub API |
| repo_url | text | URL ke GitHub | GitHub API |
| is_archived | text | "Yes" / "No" | GitHub API |
| license | text | Lisensi | GitHub API |
| last_synced | datetime | Timestamp sinkronisasi terakhir | Script |

---

## Sheet: Projects (EXISTING — untuk portfolio)

Data project portfolio. Akan diisi dari GitHubRepos + manual entry.
Kolom existing (dari analisa sheet):

| Kolom | Tipe | Contoh |
|-------|------|--------|
| id | number | 1 |
| title | text | COPPA Risk Prediction |
| description | text | ML model using XGBoost... |
| image | text | URL gambar |
| technologies | text | Python, XGBoost, Pandas |
| category | text | Data Science |
| live_url | text | URL demo |
| github_url | text | https://github.com/... |
| featured | boolean | TRUE |
| order | number | 1 |

---

## Sheet: PersonalInfo (EXISTING)

| Kolom | Tipe | Contoh |
|-------|------|--------|
| id | number | 1 |
| name | text | Fauzan Ahsanudin Alfikri |
| title | text | Data Science Undergraduate |
| email | text | fauzan@email.com |
| phone | text | +62... |
| location | text | Indonesia |
| avatar | text | URL gambar |
| resume_url | text | URL PDF |

---

## Sheet: SocialLinks (EXISTING)

| Kolom | Tipe |
|-------|------|
| id | number |
| platform | text |
| url | text |
| icon | text |
| order | number |

---

## Sheet: Skills (EXISTING)

| Kolom | Tipe |
|-------|------|
| id | number |
| name | text |
| level | number (0-100) |
| category | text |

---

## Sheet: Education (EXISTING)

| Kolom | Tipe |
|-------|------|
| id | number |
| institution | text |
| degree | text |
| field | text |
| start_year | text |
| end_year | text |
| gpa | text |
| description | text |

---

## Sheet: Experiences (EXISTING)

| Kolom | Tipe |
|-------|------|
| id | number |
| company | text |
| position | text |
| start_date | text |
| end_date | text |
| description | text |
| location | text |
| type | text |

---

## Sheet: Certifications (EXISTING)

| Kolom | Tipe |
|-------|------|
| id | number |
| name | text |
| issuer | text |
| issue_date | text |
| expiry_date | text |
| credential_id | text |
| credential_url | text |

---

## Sheet: Stats (EXISTING)

| Kolom | Tipe |
|-------|------|
| id | number |
| label | text |
| value | text |
| icon | text |

---

## Integrasi Pipeline

```
GitHub API ──▶ GitHubRepos sheet ──▶ (manual mapping) ──▶ Projects sheet ──▶ Portfolio Website
                                                              ▲
LinkedIn ──▶ (manual entry) ──▶ Experiences / Certifications ──┘
```
