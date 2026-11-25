# CloudBox — Cloud-Based File Storage System (Mini Dropbox)

**Submitted by:** Saar Ravindra Singh, Rohan Tiwari, Saksham Garg  
**Submitted to:** Mr. Mradul Jain (CSE Deptt.)

---

## Overview

CloudBox (Mini Dropbox) is a responsive web-based file storage and sharing application built with **React.js**, **Django + Django REST Framework**, **MySQL / SQLite**, and **AWS S3** (with a local S3-compatible bucket fallback for development).

### Implemented Features
- **Authentication & User Quotas**: Registration, login (username or email), token-based session auth, one-click demo presenter login, and per-user storage quota enforcement.
- **File & Folder Operations**: Upload (direct + chunked upload with 3x automatic retry for large files up to 100 MB), in-app file preview (images/SVG, PDF, text/CSV), download, rename, delete, folder hierarchy, breadcrumbs, and search.
- **Storage Dashboard**: Visual breakdown of used vs. available storage, file category breakdown (Documents, Images, Audio/Video, Archives, Other), and recent files.
- **Shareable Links**: Generate secure cryptographic links for individual files or entire folders (with `.zip` folder download), optional expiration in hours, download counters, and instant link revocation.
- **System Architecture & Specs View**: Interactive in-app architecture diagram, tech stack summary, and NFR overview for live walkthroughs.
- **Admin Dashboard**: Staff interface to inspect all users' storage usage and adjust per-user storage quotas.
- **Security**: Owner-scoped API access control, server-side encryption (`AES256` in S3 mode), SHA-256 object integrity checksums, and path-traversal protection.

---

## Quick Presentation Launch (One Command)

Run the included launcher script to migrate, seed demo users/files, and start both servers:

```bash
./start_demo.sh
```

Then open **http://localhost:5173** and use the **Quick Presentation Demo Login** buttons on the login screen:
- **Demo Admin**: `saar` / `demo1234` (includes seeded folders, sample architecture SVG, summary notes, active share links, and Admin Dashboard access)
- **Demo User**: `rohan` / `demo1234`

---

## Project Structure

```text
Mini Project/
├── start_demo.sh           # One-command presentation launcher
├── backend/
│   ├── cloudbox/           # Django project config, MySQL/SQLite & S3 settings
│   ├── accounts/           # Auth endpoints, UserProfile, Admin quota APIs
│   ├── storage/            # Files, folders, chunked uploads, share links, seed_demo
│   ├── .env.example        # Environment config template (MySQL + AWS S3)
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── components/     # AuthScreen, DashboardView, FilesView, SharesView, PublicShareView, ArchitectureView, AdminView
    │   ├── api.js          # REST client + chunked upload with retry
    │   ├── App.jsx
    │   └── styles.css      # Responsive desktop & mobile UI
    ├── vite.config.js
    └── package.json
```

---

## Production Configuration (AWS S3 Free Tier + MySQL)

CloudBox supports **direct-to-S3 presigned uploads and downloads** (so 100 MB+ files bypass Vercel's 4.5 MB serverless body limit) and includes an automatic **AWS S3 Free Tier Guard** (`S3_FREE_TIER_MAX_GB=4.5` out of the 5 GB monthly Free Tier allowance).

### 1. Create an AWS IAM User & Configure S3 Free Tier Bucket
1. In the **AWS IAM Console**, create a user (e.g. `cloudbox-s3-user`) with programmatic access keys and attach a minimal bucket-scoped policy:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": ["s3:CreateBucket", "s3:HeadBucket", "s3:PutBucketCORS", "s3:PutBucketPublicAccessBlock", "s3:PutEncryptionConfiguration", "s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
         "Resource": [
           "arn:aws:s3:::YOUR-UNIQUE-BUCKET-NAME",
           "arn:aws:s3:::YOUR-UNIQUE-BUCKET-NAME/*"
         ]
       }
     ]
   }
   ```
2. Run the one-time bucket setup command locally (creates the private bucket, enables AES-256 encryption, blocks all public access, and sets CORS for Vercel + localhost):
   ```bash
   cd backend
   USE_S3=true AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_STORAGE_BUCKET_NAME=... AWS_S3_REGION_NAME=ap-south-1 ./.venv/bin/python manage.py setup_s3_bucket
   ```

### 2. Set Production Environment Variables in Vercel
In **Vercel → Project Settings → Environment Variables**, configure:
- `USE_S3=true`
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME`
- `S3_FREE_TIER_GUARD=true`, `S3_FREE_TIER_MAX_GB=4.5`
- `DATABASE_URL=mysql://user:pass@host:port/db` (or `DB_ENGINE=mysql` with `MYSQL_*` vars)
- `DJANGO_SECRET_KEY=<random-64-char-secret>`
- `DJANGO_DEBUG=false`

---

## Deploying to Vercel

This repository is pre-configured for full-stack Vercel deployment via `vercel.json` (React SPA static build + Django Python serverless function at `api/index.py`):

1. Install/run Vercel CLI and log in:
   ```bash
   npx vercel login
   npx vercel --prod
   ```
2. *(Optional for persistent production storage)* In Vercel Project Settings → **Environment Variables**, add your `DB_ENGINE=mysql` (`MYSQL_*`) and `USE_S3=true` (`AWS_*`) credentials. Without external DB/S3 env vars, `api/index.py` runs in ephemeral `/tmp` demo mode and auto-seeds `saar` / `rohan` (`demo1234`) on cold start.

