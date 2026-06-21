# CareerAI Hub — AI көмегімен мамандық ұсынатын сайт

Flask + SQLite + HTML/CSS/JS + REST API + рөл жүйесі (RBAC).

## Іске қосу

```powershell
cd c:\Users\SenetUser\Desktop\GameDevelop\career-ai-hub
pip install -r requirements.txt
python app.py
```

Сайт: **http://127.0.0.1:5005**

## Render.com-ға жариялау

Толық нұсқаулық: **[DEPLOY.md](DEPLOY.md)** (қадам-қадам қазақша)

## Demo аккаунттар

| Рөл | Email | Пароль |
|-----|-------|--------|
| Әкімші (Admin) | admin@careerhub.kz | admin123 |
| Менеджер (Manager) | manager@careerhub.kz | manager123 |
| Қызметкер (Employee) | employee@careerhub.kz | employee123 |
| Модератор (Moderator) | moderator@careerhub.kz | moderator123 |
| Клиент (User) | user@careerhub.kz | user123 |

## Технологиялар

- **HTML / CSS / JavaScript** — интерфейс
- **Python Flask** — сервер
- **SQLite** — деректер қоры
- **REST API** — `/api/professions`, `/api/recommend`, `/api/stats`

## Рөлдер және құқықтар

| Рөл | Мүмкіндіктер |
|-----|--------------|
| **Admin** | Барлық пайдаланушыларды CRUD, мамандықтар, жүйелік журнал |
| **Manager** | Консультация өтінімдерін өңдеу, қызметкерге тапсырма беру |
| **Employee** | Тек өзіне бекітілген тапсырмалар |
| **Moderator** | Материалдар мен AI ұсыныстарды тексеру |
| **User/Client** | Профиль, AI ұсыныс, консультация, материал жариялау |

## AI интеграция — Google Gemini

Сайт **Google Gemini API** арқылы нақты AI ұсыныстар береді.

`.env` файлында:

```
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.0-flash
```

API кілтсіз rule-based fallback қолданылады.

API статус: `GET /api/ai/status`

## API мысалдары

```bash
GET /api/professions?q=python&category=IT
GET /api/professions/1
POST /api/recommend  {"profession_id": 1}  (login қажет)
GET /api/stats  (admin)
```

## Бағалау критерийлері

✅ Дизайн сапасы — заманауи dark UI  
✅ Код құрылымы — models, auth, ai_service, app  
✅ Flask + SQLite — толық CRUD  
✅ API интеграция — REST endpoints  
✅ Рөл жүйесі — 5 рөл + RBAC  
✅ Функционал — тіркелу, профиль, AI, модерация, менеджмент  
