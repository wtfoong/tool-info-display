## project structure

```
app/
│
├── .streamlit/
│   └── config.toml
├── logs/
│   └── ...
├── app.py               # Streamlit UI
├── backend.py           # Business logic
├── helper.py            # Helper functions
├── config.yaml          # Custom settings
├── config_loader.py     # load_config function
├── requirements.txt
└── .env                 # Environment variables
```

## 🔧 Setup
1. Copy the template files:
```cmd
copy .env.template .env
copy config.template.yaml config.yaml
copy .streamlit\config.template.toml .streamlit\config.toml
```

2. Deployment

```
[Browser]
   ↓   (https://tool-info-display.shimano.com)
[NGINX Reverse Proxy]
   ↓   (http://localhost:8501)
[Streamlit App]
   ↑   (auto-started & kept alive by NSSM)
[NSSM Windows Service]
```

## Architecture
Start with Option 1 for MVP/testing/dev phase.
Build Option 2 as backend matures—it futureproofs the architecture, scales better, and separates concerns cleanly.

### 🧱 Streamlit App Architecture – Option 1 Caching at Streamlit Level


```text
       👤 Client (Browser)
                │
                ▼
       ┌──────────────────┐
       │   Streamlit App  │
       └──────────────────┘
                │
     🔁 @st.cache_data(ttl= 60 sec)
                │
                ▼
       ┌──────────────────┐
       │    Database      │
       └──────────────────┘
```

### 🌐 API-First Architecture – Option 2 Caching at API Layer
```text
       👤 Client (Browser)
                │
                ▼
       ┌──────────────────┐
       │   Streamlit App  │  ◀──── UI
       └──────────────────┘
                │
                ▼
       ┌──────────────────────┐
       │  API Layer (FastAPI) │  ◀──── Business logic & cache
       └──────────────────────┘
                │
       🔁 Redis / Disk / RAM (TTL)
                │
                ▼
       ┌────────────┐
       │  Database  │
       └────────────┘

```