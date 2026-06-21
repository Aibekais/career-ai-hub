"""
AI мамандық ұсыну сервисі.
Негізгі: Google Gemini API
Резерв: rule-based matching (API сәтсіз болса)
"""
import os
import re
import json
import urllib.request
import urllib.error

PROFESSIONS_KEYWORDS = {
    'Бағдарламашы': ['python', 'javascript', 'код', 'программ', 'web', 'it', 'логика'],
    'Дизайнер': ['дизайн', 'ui', 'ux', 'креатив', 'визуал', 'figma'],
    'Дәрігер': ['медицина', 'денсаулық', 'биология', 'адам', 'көмек'],
    'Мұғалім': ['оқыту', 'білім', 'педагог', 'бала', 'сабақ'],
    'Маркетолог': ['маркетинг', 'жарнама', 'smm', 'сату', 'клиент'],
    'Инженер': ['инженер', 'техника', 'құрылыс', 'механика', 'есептеу'],
    'Деректер аналитигі': ['дерек', 'анализ', 'статистика', 'excel', 'ai', 'ml'],
    'Әдіскер': ['құқық', 'заң', 'сот', 'шарт', 'келісім'],
}


def is_gemini_configured():
    return bool(os.environ.get('GEMINI_API_KEY', '').strip())


def _score_profession(profession_title, skills_text, interests_text):
    keywords = PROFESSIONS_KEYWORDS.get(profession_title, [])
    blob = f"{skills_text} {interests_text}".lower()
    if not keywords:
        return 50
    hits = sum(1 for kw in keywords if kw in blob)
    return min(95, 40 + hits * 12)


def _parse_ai_json(text):
    """Gemini жауабынан JSON шығару."""
    text = text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    try:
        parsed = json.loads(text)
        score = int(parsed.get('score', 75))
        score = max(0, min(100, score))
        summary = str(parsed.get('summary', '')).strip()
        if summary:
            return score, summary
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    match = re.search(r'"score"\s*:\s*(\d+)', text)
    score = int(match.group(1)) if match else 75
    summary_match = re.search(r'"summary"\s*:\s*"([^"]+)"', text, re.DOTALL)
    if summary_match:
        return max(0, min(100, score)), summary_match.group(1)
    return max(0, min(100, score)), text[:500]


def generate_recommendation_gemini(profession, profile):
    """Google Gemini API арқылы мамандық ұсынысы."""
    api_key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not api_key:
        return None

    primary = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
    fallback_models = [
        primary,
        'gemini-2.5-flash',
        'gemini-2.0-flash',
        'gemini-flash-latest',
    ]
    # Қайталанбас модельдер
    models = []
    for m in fallback_models:
        if m and m not in models:
            models.append(m)

    prompt = _build_gemini_prompt(profession, profile)

    for model in models:
        result = _call_gemini_api(api_key, model, prompt)
        if result:
            return result
    return None


def _build_gemini_prompt(profession, profile):
    return f"""Сен кәсіби мамандық кеңесшісісің. Тек қазақ тілінде жауап бер.

Пайдаланушы профилі:
- Қызығушылық салалары: {profile.interests or 'көрсетілмеген'}
- Дағдылар: {profile.skills or 'көрсетілмеген'}
- Білім: {profile.education or 'көрсетілмеген'}
- Тәжірибе (жыл): {profile.experience_years or 0}
- Қалаған сала: {profile.preferred_field or 'көрсетілмеген'}

Ұсынылған мамандық:
- Атауы: {profession.title}
- Сипаттама: {profession.description or '—'}
- Сала: {profession.category or '—'}
- Қажет дағдылар: {profession.skills_required or '—'}
- Нарық болжамы: {profession.growth_outlook or '—'}
- Жалақы: {profession.salary_min or 0} – {profession.salary_max or 0} ₸

Тапсырма: осы мамандық пайдаланушыға насканша сәйкес екенін 0–100 арасында бағала.
Негіздемені 2–4 толық сөйлеммен жаз (неге сәйкес немесе сәйкес емес).

Тек мына JSON форматында жауап бер, басқа мәтін қоспа:
{{"score": 85, "summary": "негіздеме мәтіні"}}"""


def _call_gemini_api(api_key, model, prompt):
    url = (
        f'https://generativelanguage.googleapis.com/v1beta/models/'
        f'{model}:generateContent?key={api_key}'
    )

    payload = json.dumps({
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {
            'temperature': 0.7,
            'responseMimeType': 'application/json',
        },
    }).encode('utf-8')

    req = urllib.request.Request(
        url,
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )

    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        candidates = data.get('candidates') or []
        if not candidates:
            return None
        parts = candidates[0].get('content', {}).get('parts', [])
        if not parts:
            return None
        text = parts[0].get('text', '')
        if not text:
            return None
        score, summary = _parse_ai_json(text)
        return score, summary, 'gemini'
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8', errors='replace')
        if e.code == 429:
            print(f'[Gemini {model}] quota exceeded, trying next model...')
        else:
            print(f'[Gemini {model} error {e.code}]: {err_body[:200]}')
        return None
    except Exception as e:
        print(f'[Gemini {model} error]: {e}')
        return None


def generate_recommendation_local(profession, profile):
    """Rule-based ұсыныс — API сәтсіз болса."""
    skills = profile.skills or ''
    interests = profile.interests or ''
    score = _score_profession(profession.title, skills, interests)

    reasons = []
    if profession.category and profession.category.lower() in interests.lower():
        reasons.append(f'Сіздің қызығушылықтарыңыз {profession.category} саласына сәйкес.')
    if profession.skills_required:
        matched = [s.strip() for s in profession.skills_required.split(',')
                   if s.strip().lower() in skills.lower()]
        if matched:
            reasons.append(f'Дағдыларыңыз: {", ".join(matched[:3])}.')
    if profession.growth_outlook:
        reasons.append(f'Нарық болжамы: {profession.growth_outlook}.')

    summary = (
        f'«{profession.title}» мамандығы сізге {score}% сәйкестік көрсетті. '
        + ' '.join(reasons[:3])
        if reasons else
        f'«{profession.title}» — {profession.description[:120] if profession.description else "перспективалы мамандық"}.'
    )
    return score, summary, 'local'


def get_career_recommendation(profession, profile):
    """
    Алдымен Google Gemini, сосын local fallback.
    Қайтарады: (score, summary, source) — source: 'gemini' | 'local'
    """
    gemini_result = generate_recommendation_gemini(profession, profile)
    if gemini_result:
        return gemini_result
    return generate_recommendation_local(profession, profile)


CHAT_SYSTEM_PROMPT = """Сен CareerAI Hub платформасының универсалды AI көмекшісісің.
Атың: CareerAI Assistant.
Тек қазақ тілінде жауап бер (пайдаланушы басқа тілде сұраса, сол тілде де жауап беруге болады).
Кез келген сұраққа еркін, толық және пайдалы жауап бер — мамандық, білім, технология, өмір, ғылым, тарих, денсаулық, спорт, ойын-сауық және т.б.
Ешқандай тақырыпты шектеу немесе басқа тақырыпқа бағыттау — пайдаланушы не сұраса, сол туралы жауап бер.
Достық, нақты, түсінікті стильде жаз. Қажет болса тізім, қадамдар немесе мысалдар қолдан.
Егер сұрақ мамандыққа байланысты болса, пайдаланушы профилін ескер."""


def _get_gemini_models():
    primary = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
    fallback = [primary, 'gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-flash-latest']
    models = []
    for m in fallback:
        if m and m not in models:
            models.append(m)
    return models


def _call_gemini_chat(api_key, model, system_prompt, history, user_message):
    """Gemini chat — сөйлем тарихымен."""
    contents = []
    for msg in history[-10:]:
        role = 'user' if msg['role'] == 'user' else 'model'
        contents.append({'role': role, 'parts': [{'text': msg['content']}]})
    contents.append({'role': 'user', 'parts': [{'text': user_message}]})

    url = (
        f'https://generativelanguage.googleapis.com/v1beta/models/'
        f'{model}:generateContent?key={api_key}'
    )
    payload = json.dumps({
        'systemInstruction': {'parts': [{'text': system_prompt}]},
        'contents': contents,
        'generationConfig': {'temperature': 0.9, 'maxOutputTokens': 2048},
    }).encode('utf-8')

    req = urllib.request.Request(
        url, data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        candidates = data.get('candidates') or []
        if not candidates:
            return None
        parts = candidates[0].get('content', {}).get('parts', [])
        text = parts[0].get('text', '').strip() if parts else ''
        return text or None
    except urllib.error.HTTPError as e:
        if e.code == 429:
            print(f'[Gemini chat {model}] quota exceeded')
        return None
    except Exception as e:
        print(f'[Gemini chat {model}]: {e}')
        return None


def _local_chat_response(user_message, profile):
    """Gemini қолжетімсіз болса — қарапайым жауап (шектеулі)."""
    msg = user_message.lower().strip()
    skills = (profile.skills or '') if profile else ''

    greetings = ['сәлем', 'салем', 'hello', 'hi', 'қайырлы']
    if any(g in msg for g in greetings) and len(msg) < 30:
        return (
            'Сәлем! Мен CareerAI Assistant — кез келген сұраққа жауап беремін. '
            'Gemini API quota шектеуіне байланысты қазір жергілікті режимде жұмыс істеп тұрмын.'
        )

    if any(w in msg for w in ['it', 'бағдарлам', 'python', 'web', 'программ']):
        return (
            f'IT саласы сізге жарайды! Сіздің дағдыларыңыз: {skills or "айтылмаған"}. '
            'Бағдарламашы, деректер аналитигі немесе UI/UX дизайнер мамандықтарын қарастырыңыз. '
            'Python, JavaScript және SQL үйрену перспективалы.'
        )
    if any(w in msg for w in ['дизайн', 'ui', 'ux', 'figma']):
        return 'UI/UX дизайнер мамандығы креативті әрі сұранысты саланы. Figma, Adobe XD үйреніңіз.'
    if any(w in msg for w in ['медицина', 'дәрігер', 'денсаулық']):
        return 'Медицина саласы — жауапкершілігі жüksek, бірақ маңызды мамандық. Биология мен химияны терең оқыңыз.'
    if any(w in msg for w in ['маркетинг', 'smm', 'жарнама']):
        return 'Digital маркетинг заманауи әрі тиімді сала. SMM, SEO, Analytics дағдыларын дамытыңыз.'
    if any(w in msg for w in ['мұғалім', 'оқыту', 'педагог']):
        return 'Мұғалім мамандығы — білім беру арқылы қоғамға үлес.'
    if any(w in msg for w in ['космос', 'ғарыш', 'планета']):
        return 'Ғарыш — керемет зерттеу объекты! Космос зерттеулері технология мен ғылымды дамытады.'
    if any(w in msg for w in ['футбол', 'спорт']):
        return 'Спорт — денсаулық пен командалық рухты дамытатын тамаша хобби әрі мамандық.'
    if '?' in user_message or len(msg) > 8:
        return (
            f'Сұрағыңыз қабылданды: «{user_message[:120]}». '
            'Gemini API қосулы болса, кез келген сұраққа толық жауап аласыз. '
            'Қазір жергілікті режим — нақты жауап үшін Google AI Studio-дан quota тексеріңіз.'
        )

    return 'Сұрағыңызды толығырақ жазыңыз — кез келген тақырып туралы.'


def get_chat_response(user_message, profile, history):
    """
    AI чат жауабы.
    history: [{'role': 'user'|'assistant', 'content': '...'}, ...]
    Қайтарады: (reply_text, source)
    """
    api_key = os.environ.get('GEMINI_API_KEY', '').strip()
    system = CHAT_SYSTEM_PROMPT
    if profile:
        system += f"""

Пайдаланушы профилі (есепке ал):
- Дағдылар: {profile.skills or '—'}
- Қызығушылық: {profile.interests or '—'}
- Білім: {profile.education or '—'}
- Тәжірибе: {profile.experience_years or 0} жыл
- Қалаған сала: {profile.preferred_field or '—'}"""

    if api_key:
        for model in _get_gemini_models():
            reply = _call_gemini_chat(api_key, model, system, history, user_message)
            if reply:
                return reply, 'gemini'

    return _local_chat_response(user_message, profile), 'local'
