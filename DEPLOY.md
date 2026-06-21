# CareerAI Hub — Render.com-ға жариялау (қадам-қадам)

## Алдын ала дайындық

Жоба Render-ге дайын:
- `gunicorn` — production сервер
- `wsgi.py` — Render кіру нүктесі
- `render.yaml` — автоматты баптау (опционал)
- SQLite + PostgreSQL қолдауы

---

## 1-ҚАДАМ: GitHub репозиторий жасау

1. [github.com](https://github.com) сайтына кіріңіз
2. **New repository** басыңыз
3. Repository name: `career-ai-hub` (немесе өз атыңыз)
4. **Public** таңдаңыз
5. **Create repository** басыңыз

---

## 2-ҚАДАМ: Кодты GitHub-қа жүктеу

PowerShell-де (компьютеріңізде):

```powershell
cd c:\Users\SenetUser\Desktop\GameDevelop\career-ai-hub

git init
git add .
git commit -m "CareerAI Hub — Flask + Gemini AI + Render deploy"

git branch -M main
git remote add origin https://github.com/SIZIN_USERNAME/career-ai-hub.git
git push -u origin main
```

> `SIZIN_USERNAME` орнына өз GitHub логиніңізді жазыңыз.
> GitHub логин/пароль сұраса — **Personal Access Token** қолданыңыз.

**⚠️ МАҢЫЗДЫ:** `.env` файлы GitHub-қа кірмейді (`.gitignore`-та). API кілттер Render Dashboard-та қойылады.

---

## 3-ҚАДАМ: Render.com аккаунт

1. [render.com](https://render.com) сайтына кіріңіз
2. **Sign Up** → **GitHub** арқылы тіркеліңіз
3. GitHub-қа Render-ге рұқсат беріңіз

---

## 4-ҚАДАМ: Web Service жасау

1. Render Dashboard → **New +** → **Web Service**
2. GitHub репозиторийіңізді таңдаңыз: `career-ai-hub`
3. Баптаулар:

| Өріс | Мән |
|------|-----|
| **Name** | `career-ai-hub` |
| **Region** | Frankfurt (EU) немесе жақын регион |
| **Branch** | `main` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120` |
| **Plan** | **Free** |

4. **Advanced** → Environment Variables:

| Key | Value |
|-----|-------|
| `SECRET_KEY` | Кез келген ұзын құпия сөз (мыс: `my-super-secret-key-2024-xyz`) |
| `GEMINI_API_KEY` | Сіздің Google Gemini API кілтіңіз |
| `GEMINI_MODEL` | `gemini-2.5-flash` |
| `PYTHON_VERSION` | `3.11.9` |

5. **Create Web Service** басыңыз

---

## 5-ҚАДАМ: Deploy күту

- Render кодты жинайды (Build) — 2–5 минут
- Содан кейін сайт іске қосылады
- Сілтеме: `https://career-ai-hub.onrender.com` (немесе өз name-іңіз)

**Deploy сәтті болса:** ✅ Live көрінеді

---

## 6-ҚАДАМ: Сайтты тексеру

1. Сайт URL-ін ашыңыз
2. Demo аккаунтпен кіріңіз:
   - `user@careerhub.kz` / `user123`
   - `admin@careerhub.kz` / `admin123`
3. AI чат және ұсыныстарды тексеріңіз

---

## SQLite туралы (МАҢЫЗДЫ)

Render **Free** жоспарында файл жүйесі **уақытша**:

| Мәселе | Шешім |
|--------|-------|
| Redeploy кейін деректер жоғалуы | Demo seed автоматты қайта жасалады |
| Тіркелген user-дер сақталмайды | PostgreSQL қосу (төменде) |
| SQLite жұмыс істейді | Иә, demo/бағалау үшін жеткілікті |

### Деректерді тұрақты сақтау (қосымша):

**Render PostgreSQL (Free 90 күн):**
1. Render → **New +** → **PostgreSQL**
2. PostgreSQL жасалғаннан кейін **Internal Database URL** көшіріңіз
3. Web Service → **Environment** → `DATABASE_URL` қосыңыз
4. **Manual Deploy** → Redeploy

---

## Код жаңартқанда

```powershell
git add .
git commit -m "Жаңарту"
git push
```

Render автоматты redeploy жасайды.

---

## Жиі қателер

| Қате | Шешім |
|------|-------|
| Build failed | `requirements.txt` бар екенін тексеріңіз |
| Application failed to respond | Start Command дұрыс екенін тексеріңіз |
| AI жұмыс істемейді | `GEMINI_API_KEY` Environment-та бар ма |
| 502 / timeout | Free plan cold start — 30–60 сек күтіңіз |
| Internal Server Error | Render Logs қараңыз (Dashboard → Logs) |

---

## Demo аккаунттар

| Рөл | Email | Пароль |
|-----|-------|--------|
| Admin | admin@careerhub.kz | admin123 |
| Manager | manager@careerhub.kz | manager123 |
| Employee | employee@careerhub.kz | employee123 |
| Moderator | moderator@careerhub.kz | moderator123 |
| User | user@careerhub.kz | user123 |
