# Gleam Bot

Automation bot untuk Gleam.io giveaway menggunakan CloakBrowser + Playwright (Python).

## Features
- Login via X (Twitter) OAuth
- Auto follow @kucoincom & @MezoNetwork
- Quote tweet otomatis dengan tag 3 akun random
- Submit repost link
- Submit KuCoin UID
- Multi-account sequential

## Structure
```
gleam-bot/
├── config.py              # Semua konstanta & settings
├── helpers.py             # Helper functions (browser, oauth, angular)
├── run.py                 # Main runner
├── data/
│   ├── accounts.json      # ← JANGAN DI-COMMIT (lihat .gitignore)
│   ├── accounts.json.template
│   └── tag-handles.json   # List Twitter handles untuk tag
├── logs/                  # Auto-generated
└── screenshots/           # Auto-generated saat error
```

## Setup

### 1. Install dependencies
```bash
pip install playwright
playwright install chromium
```

### 2. Isi accounts.json
```bash
cp data/accounts.json.template data/accounts.json
# Edit data/accounts.json dengan data akun lo
```

### 3. Isi tag-handles.json
```bash
# Edit data/tag-handles.json dengan list handle Twitter
```

### 4. Edit config.py
```python
QUOTE_TWEET_URL = "https://x.com/kucoincom/status/XXXXXXXXX"  # ganti ini
```

### 5. Jalanin
```bash
python run.py 1   # akun 1
python run.py 2   # akun 2
```

## accounts.json format
```json
{
  "accounts": [
    {
      "id": 1,
      "handle": "twitter_username",
      "kucoin_uid": "12345678",
      "proxy": "",
      "cookies": {
        "auth_token": "...",
        "ct0": "..."
      }
    }
  ]
}
```

## Cara ambil auth_token & ct0
1. Login ke x.com di CloakBrowser
2. F12 → Application → Cookies → x.com
3. Copy nilai `auth_token` dan `ct0`
