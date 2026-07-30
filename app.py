import os
import asyncio
import httpx
import streamlit as st

# ============================================================
# КЛЮЧИ
# Локально можно задать через переменные окружения.
# На Streamlit Community Cloud задаются в Settings -> Secrets
# в формате: KEY = "значение" (по одной строке на ключ).
# ============================================================
def get_secret(key: str) -> str:
    val = os.environ.get(key, "")
    if val:
        return val
    try:
        return st.secrets.get(key, "")
    except Exception:
        return ""


OPENROUTER_API_KEY = get_secret("OPENROUTER_API_KEY")
GOOGLE_API_KEY = get_secret("GOOGLE_API_KEY")
TAVILY_API_KEY = get_secret("TAVILY_API_KEY")  # tavily.com, 1000 бесплатных запросов/месяц

# ============================================================
# АВТОПОДБОР МОДЕЛЕЙ
# Бесплатные модели у OpenRouter и Google меняются очень часто
# (список может обновляться раз в несколько дней). Вместо того
# чтобы вручную вписывать ID, код сам спрашивает у обоих сервисов,
# что доступно ПРЯМО СЕЙЧАС, и подставляет рабочие варианты.
# Обновляется раз в час (кэш), чтобы не дёргать API на каждый запрос.
# ============================================================
async def fetch_openrouter_free_models() -> list:
    """Живой список бесплатных моделей OpenRouter (id вида provider/model:free)."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get("https://openrouter.ai/api/v1/models")
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    free_ids = []
    for m in data.get("data", []):
        model_id = m.get("id", "")
        pricing = m.get("pricing", {})
        try:
            prompt_price = float(pricing.get("prompt") or 1)
            completion_price = float(pricing.get("completion") or 1)
        except (TypeError, ValueError):
            continue
        if prompt_price == 0 and completion_price == 0 and model_id.endswith(":free"):
            free_ids.append(model_id)
    return free_ids


async def fetch_gemini_flash_model() -> str:
    """Спрашивает у Google, какая Flash-модель сейчас доступна для generateContent."""
    if not GOOGLE_API_KEY:
        return "gemini-2.0-flash"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"https://generativelanguage.googleapis.com/v1beta/models?key={GOOGLE_API_KEY}"
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return "gemini-2.0-flash"

    candidates = []
    for m in data.get("models", []):
        name = m.get("name", "").replace("models/", "")
        methods = m.get("supportedGenerationMethods", [])
        if "generateContent" in methods and "flash" in name.lower():
            candidates.append(name)

    stable = [c for c in candidates if "exp" not in c and "preview" not in c and "8b" not in c]
    pool = stable or candidates
    return pool[0] if pool else "gemini-2.0-flash"


def pretty_model_name(model_id: str) -> str:
    if model_id == "openrouter/free":
        return "OpenRouter (авто)"
    base = model_id.split("/")[-1].replace(":free", "")
    return base.replace("-", " ").title()


@st.cache_data(ttl=3600, show_spinner=False)
def resolve_models():
    free_models = asyncio.run(fetch_openrouter_free_models())
    gemini_model_id = asyncio.run(fetch_gemini_flash_model())

    # предпочитаем разные "семейства" моделей для разнообразия мнений
    pref_a = [m for m in free_models if any(k in m.lower() for k in ["deepseek", "qwen", "nemotron", "gpt-oss", "hermes", "kimi"])]
    pref_b = [m for m in free_models if "glm" in m.lower()]

    model_a = pref_a[0] if pref_a else (free_models[0] if free_models else "openrouter/free")
    model_b = pref_b[0] if pref_b else next((m for m in free_models if m != model_a), "openrouter/free")

    return [
        {"name": pretty_model_name(model_a), "provider": "openrouter", "model_id": model_a},
        {"name": pretty_model_name(model_b), "provider": "openrouter", "model_id": model_b},
        {"name": pretty_model_name(gemini_model_id), "provider": "google", "model_id": gemini_model_id},
    ]


MODELS = resolve_models()

# ============================================================
# LEVEL 5 — разбит на 4 последовательных шага с разной температурой.
# Температуру каждого шага можно смело менять здесь.
# ============================================================
BASE_SYSTEM_PROMPT = """Ты работаешь в режиме глубокого критического анализа, разбитого на шаги. Без приветствий, без вежливых вступлений, без воды — сразу к сути. Отвечай только на текущий шаг, не забегай вперёд и не повторяй то, что уже сказал на предыдущих шагах."""

TEMP_IDEAL = 1.1      # шаг 1: идеальный вариант — высокая креативность
TEMP_BLOCKS = 0.2     # шаг 2: разбивка на блоки — минимум, нужна точность
TEMP_VARIANTS = 1.0   # шаг 3: варианты по блокам — выше среднего, нужен разброс
TEMP_FINAL = 0.3      # шаг 4: итоговая оценка — низкая, чтобы не галлюцинировал

STAGE_1_IDEAL = """Тебе может быть передан блок "ДАННЫЕ ИЗ ПОИСКА" — свежая информация из интернета. Обязательно учти её, если она есть; если её нет или она не по теме — работай на своих знаниях и явно укажи это.

{search_block}ЗАДАЧА:
{user_message}

Шаг 1.
1) Сформулируй одним предложением ЦЕЛЬ — конечную точку, которую нужно получить.
2) Опиши ИДЕАЛЬНЫЙ ВАРИАНТ решения без ограничений — как будто время, ресурсы и технические барьеры не важны. Будь смелым и нестандартным, это ориентир для дальнейшей работы, а не финальный ответ."""

STAGE_2_BLOCKS = """Шаг 2. Основываясь на цели и идеальном варианте из шага 1, раздели задачу на чёткие логические блоки (составные части решения). Пока не предлагай варианты решения — только сама структура блоков, по одному предложению на блок (что за блок и зачем он нужен). Будь точным и лаконичным."""

STAGE_3_VARIANTS = """Шаг 3. Для каждого блока из шага 2 предложи 2-3 конкретных варианта решения. На этом шаге ценится широта: не бойся нестандартных и даже почти нереализуемых вариантов. По каждому варианту коротко укажи реализуемость (высокая/средняя/низкая) и главный риск."""

STAGE_4_FINAL = """Шаг 4. Трезво оцени всё предложенное выше. Собери из вариантов по блокам одну итоговую реалистичную комбинацию — ближе всего к идеальному варианту, но реально осуществимую. Будь максимально объективным: не приукрашивай, не выдумывай факты, отбрось нереалистичные варианты. Заверши одним абзацем, почему выбрана именно эта комбинация."""


# ============================================================
# ВЫЗОВ OPENROUTER (DeepSeek, GLM)
# ============================================================
async def call_openrouter_model(model_id: str, messages: list, temperature: float) -> str:
    if not OPENROUTER_API_KEY:
        return "[Ошибка: не задан OPENROUTER_API_KEY в Secrets]"
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model_id,
                    "messages": messages,
                    "temperature": temperature,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            return "[Недоступно: превышен бесплатный лимит запросов. Попробуйте через пару минут.]"
        detail = e.response.text[:150]
        return f"[Ошибка запроса: {e.response.status_code} — {detail}]"
    except Exception as e:
        return f"[Ошибка: {str(e)[:200]}]"


# ============================================================
# ВЫЗОВ GOOGLE AI STUDIO (Gemini)
# ============================================================
async def call_gemini_model(model_id: str, system_prompt: str, contents: list, temperature: float) -> str:
    if not GOOGLE_API_KEY:
        return "[Ошибка: не задан GOOGLE_API_KEY в Secrets]"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={GOOGLE_API_KEY}"
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {"temperature": temperature},
    }
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            return "[Недоступно: превышен бесплатный лимит запросов. Попробуйте через пару минут.]"
        detail = e.response.text[:150]
        return f"[Ошибка запроса: {e.response.status_code} — {detail}]"
    except Exception as e:
        return f"[Ошибка: {str(e)[:200]}]"


def is_error_text(text: str) -> bool:
    return text.startswith("[Ошибка") or text.startswith("[Недоступно")


# ============================================================
# ПОЛНЫЙ ПРОХОД ПО 4 ШАГАМ ДЛЯ ОДНОЙ МОДЕЛИ
# ============================================================
async def run_level5_pipeline(model_cfg: dict, user_message: str, search_context: str):
    search_block = f"ДАННЫЕ ИЗ ПОИСКА:\n{search_context}\n\n" if search_context else ""

    stages = [
        (STAGE_1_IDEAL.format(search_block=search_block, user_message=user_message), TEMP_IDEAL, "ЦЕЛЬ и ИДЕАЛЬНЫЙ ВАРИАНТ"),
        (STAGE_2_BLOCKS, TEMP_BLOCKS, "БЛОКИ"),
        (STAGE_3_VARIANTS, TEMP_VARIANTS, "ВАРИАНТЫ ПО БЛОКАМ"),
        (STAGE_4_FINAL, TEMP_FINAL, "ИТОГОВАЯ КОМБИНАЦИЯ"),
    ]

    output_parts = []

    if model_cfg["provider"] == "openrouter":
        messages = [{"role": "system", "content": BASE_SYSTEM_PROMPT}]
        for prompt_text, temperature, label in stages:
            messages.append({"role": "user", "content": prompt_text})
            reply = await call_openrouter_model(model_cfg["model_id"], messages, temperature)
            if is_error_text(reply):
                output_parts.append(f"**{label}:** {reply}")
                break
            messages.append({"role": "assistant", "content": reply})
            output_parts.append(f"**{label}:**\n{reply}")
    else:
        contents = []
        for prompt_text, temperature, label in stages:
            contents.append({"role": "user", "parts": [{"text": prompt_text}]})
            reply = await call_gemini_model(model_cfg["model_id"], BASE_SYSTEM_PROMPT, contents, temperature)
            if is_error_text(reply):
                output_parts.append(f"**{label}:** {reply}")
                break
            contents.append({"role": "model", "parts": [{"text": reply}]})
            output_parts.append(f"**{label}:**\n{reply}")

    return model_cfg["name"], "\n\n".join(output_parts)


# ============================================================
# ВЕБ-ПОИСК (Tavily) — один запрос на всю задачу
# ============================================================
async def search_web(query: str) -> str:
    if not TAVILY_API_KEY:
        return ""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": TAVILY_API_KEY,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": 5,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            if not results:
                return ""
            parts = []
            for r in results:
                title = r.get("title", "")
                content = r.get("content", "")[:500]
                url = r.get("url", "")
                parts.append(f"- {title}\n  {content}\n  Источник: {url}")
            return "\n\n".join(parts)
    except Exception:
        return ""


# ============================================================
# ИНТЕРФЕЙС (Streamlit)
# ============================================================
st.set_page_config(page_title="AI Council", page_icon="🧠", layout="centered")
st.title("🧠 Мульти-ИИ консилиум")
st.caption("Этап 1: каждая модель прорабатывает задачу независимо (Level 5, 4 шага).")
st.caption("Сейчас работают: " + ", ".join(m["name"] for m in MODELS))

if "history" not in st.session_state:
    st.session_state.history = []  # список {"role": "user"/"assistant", "content": str}

# показать уже накопленную историю
for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if st.button("Очистить чат"):
    st.session_state.history = []
    st.rerun()

user_message = st.chat_input("Опишите задачу или проблему...")

if user_message:
    st.session_state.history.append({"role": "user", "content": user_message})
    with st.chat_message("user"):
        st.markdown(user_message)

    search_context = ""
    if TAVILY_API_KEY:
        with st.chat_message("assistant"):
            search_box = st.empty()
            search_box.markdown("_🔍 Ищу информацию по теме..._")
            search_context = asyncio.run(search_web(user_message))
            if search_context:
                search_text = f"**🔍 Найдено в интернете:**\n\n{search_context}"
                search_box.markdown(search_text)
                st.session_state.history.append({"role": "assistant", "content": search_text})
            else:
                search_box.empty()

    # создаём placeholder на каждую модель заранее, заполняем по готовности
    placeholders = {}
    for m in MODELS:
        with st.chat_message("assistant"):
            box = st.empty()
            box.markdown(f"_{m['name']} думает..._")
            placeholders[m["name"]] = box

    async def run_all():
        tasks = [
            asyncio.create_task(run_level5_pipeline(m, user_message, search_context))
            for m in MODELS
        ]
        for coro in asyncio.as_completed(tasks):
            name, text = await coro
            content = f"**{name}:**\n\n{text}"
            placeholders[name].markdown(content)
            st.session_state.history.append({"role": "assistant", "content": content})

    asyncio.run(run_all())
