---
title: Instareplier
emoji: ⚡
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
---

# InstaReply — Instagram Comment-to-DM Automation

A self-hosted ManyChat-style tool. When someone comments a keyword on a tracked Instagram post, InstaReply automatically **replies to the comment** AND **sends them a private DM** — all via the official Instagram Graph API.

---

## Table of Contents

1. [Quick Start (Local)](#1-quick-start-local)
2. [Instagram API Setup](#2-instagram-api-setup) ← **Read this first**
3. [Environment Variables](#3-environment-variables)
4. [Deploy to Railway / Render](#4-deploy)
5. [Configure Webhook in Facebook](#5-configure-webhook)
6. [Using the Dashboard](#6-using-the-dashboard)
7. [DM Permissions Notice](#7-dm-permissions-notice)
8. [Token Refresh](#8-token-refresh)
9. [Project Structure](#9-project-structure)

---

## 1. Quick Start (Local)

```bash
git clone <your-repo>
cd instareplier

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your credentials (see Section 2 first)

uvicorn main:app --reload
# → Open http://localhost:8000
```

---

## 2. Instagram API Setup

### Step 1 — Convert your Instagram account

Your Instagram account must be a **Business** or **Creator** account, linked to a Facebook Page.

- Instagram app → Profile → Settings → Account → Switch to Professional Account
- Link to a Facebook Page (create one if needed)

---

### Step 2 — Create a Facebook Developer App

1. Go to [developers.facebook.com](https://developers.facebook.com)
2. Click **My Apps → Create App**
3. Choose **Business** type
4. Fill in app name and contact email → **Create App**

---

### Step 3 — Add Instagram Graph API

1. Inside your app → **Add a Product** → find **Instagram Graph API** → **Set Up**
2. Under **Instagram Graph API** → **Settings**, add your Instagram account as a test user

---

### Step 4 — Add Required Permissions

Go to **App Review → Permissions and Features** and request:

| Permission | Why |
|---|---|
| `instagram_manage_comments` | Read comments, post replies |
| `instagram_manage_messages` | Send DMs (requires App Review) |
| `pages_show_list` | Access linked pages |
| `pages_read_engagement` | Read page data |

> **Note**: `instagram_manage_messages` requires formal App Review and an approved messaging use case. See [Section 7](#7-dm-permissions-notice).

---

### Step 5 — Generate a Long-Lived Access Token

1. Go to [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
2. Select your app in the top-right dropdown
3. Click **Generate Access Token** → grant permissions
4. Copy the short-lived token
5. Exchange for a long-lived token (valid 60 days):

```
GET https://graph.facebook.com/v19.0/oauth/access_token
  ?grant_type=fb_exchange_token
  &client_id={app-id}
  &client_secret={app-secret}
  &fb_exchange_token={short-lived-token}
```

Save the `access_token` value in your `.env` as `INSTAGRAM_ACCESS_TOKEN`.

---

### Step 6 — Get Your IDs

**Facebook Page ID:**
```
GET https://graph.facebook.com/v19.0/me/accounts?access_token={token}
```
Find `id` for your page in the response.

**Instagram Business Account ID:**
```
GET https://graph.facebook.com/v19.0/{page-id}?fields=instagram_business_account&access_token={token}
```
The `id` inside `instagram_business_account` is your IG Account ID.

**Post ID** (for a specific video/photo):
```
GET https://graph.facebook.com/v19.0/{ig-account-id}/media?fields=id,caption,permalink&access_token={token}
```

---

## 3. Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Description |
|---|---|
| `INSTAGRAM_ACCESS_TOKEN` | Long-lived token (60-day expiry) |
| `INSTAGRAM_PAGE_ID` | Facebook Page ID |
| `INSTAGRAM_BUSINESS_ACCOUNT_ID` | Instagram Business/Creator account ID |
| `FACEBOOK_APP_SECRET` | From Facebook App → Settings → Basic |
| `WEBHOOK_VERIFY_TOKEN` | Any secret string — must match Facebook webhook config |
| `DATABASE_URL` | SQLite by default. Use `postgresql://...` for Postgres |

---

## 4. Deploy

### Railway

```bash
railway login
railway init
railway up
```

Set environment variables in the Railway dashboard under **Variables**.

### Render

1. Push to GitHub
2. New Web Service → connect your repo
3. Render auto-detects `render.yaml`
4. Add env vars in Render dashboard

### Docker

```bash
docker build -t instareplier .
docker run -p 8000:8000 --env-file .env -v $(pwd)/data:/data instareplier
```

---

## 5. Configure Webhook in Facebook

After deploying (your app must be publicly accessible):

1. Facebook Developer App → **Instagram Graph API → Webhooks** (or **Products → Webhooks**)
2. **Subscribe to object:** `instagram`
3. **Callback URL:** `https://your-domain.com/webhook/instagram`
4. **Verify Token:** same value as `WEBHOOK_VERIFY_TOKEN` in your `.env`
5. Click **Verify and Save**
6. Subscribe to the **`comments`** field

To test locally, use [ngrok](https://ngrok.com):
```bash
ngrok http 8000
# Use the https ngrok URL as your callback URL
```

---

## 6. Using the Dashboard

Open `https://your-domain.com` in your browser.

### Settings Tab
- Enter your Access Token, Page ID, and Instagram Account ID
- Save — credentials are stored in the database

### Campaigns Tab
- **New Campaign** → enter Post ID, keywords, reply text, DM text
- The Post ID field auto-fetches a preview thumbnail when you blur out of it
- Toggle campaigns Active/Inactive without deleting them

### How it works
1. Someone comments "info" on your tracked post
2. Facebook sends a webhook to `/webhook/instagram`
3. InstaReply matches the keyword to your campaign
4. It replies to the comment publicly + sends a private DM
5. The comment ID is stored so it's never processed twice

---

## 7. DM Permissions Notice

The Instagram Graph API restricts who businesses can DM:

- ✅ Users who have **previously sent a message to the business**
- ✅ Businesses with an **approved `instagram_manage_messages` use case** via App Review
- ❌ Cold DMs to arbitrary users are **not allowed**

To apply for `instagram_manage_messages`:
1. Facebook Developer App → **App Review → Permissions and Features**
2. Request `instagram_manage_messages`
3. Provide a screencast showing the user interaction flow and how DMs benefit users
4. Submit for review (can take 1–5 business days)

Until approved, the comment reply will still work. Only DMs to users who have previously initiated a conversation will succeed.

---

## 8. Token Refresh

Long-lived tokens expire after **60 days**. To refresh before expiry:

```
GET https://graph.facebook.com/v19.0/oauth/access_token
  ?grant_type=fb_exchange_token
  &client_id={app-id}
  &client_secret={app-secret}
  &fb_exchange_token={current-long-lived-token}
```

Update `INSTAGRAM_ACCESS_TOKEN` in your `.env` / hosting platform, or paste the new token in the Settings tab of the dashboard.

> **Tip**: Set a calendar reminder 2 weeks before expiry.

---

## 9. Project Structure

```
/
├── main.py               # FastAPI app + startup
├── instagram.py          # Instagram Graph API client (with retry/backoff)
├── models.py             # SQLAlchemy models (Config, Campaign, ProcessedComment)
├── database.py           # DB session + init
├── routes/
│   ├── webhook.py        # POST/GET /webhook/instagram
│   ├── dashboard.py      # Serves HTML
│   └── api.py            # REST API for campaigns/config
├── templates/
│   └── dashboard.html    # Full single-page dashboard
├── static/               # (reserved for CSS/JS assets)
├── .env.example
├── Dockerfile
├── railway.toml
├── render.yaml
├── requirements.txt
└── README.md
```

---

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Dashboard |
| `GET` | `/health` | Health check (returns `{"status":"ok"}`) |
| `GET` | `/webhook/instagram` | Webhook challenge verification |
| `POST` | `/webhook/instagram` | Incoming comment events |
| `GET` | `/api/config` | Get saved config |
| `POST` | `/api/config` | Save credentials |
| `GET` | `/api/campaigns` | List campaigns |
| `POST` | `/api/campaigns` | Create campaign |
| `PUT` | `/api/campaigns/{id}` | Update campaign |
| `DELETE` | `/api/campaigns/{id}` | Delete campaign |
| `PATCH` | `/api/campaigns/{id}/toggle` | Toggle active/inactive |
| `GET` | `/api/post-preview/{post_id}` | Fetch post thumbnail + caption |
