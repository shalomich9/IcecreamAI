import streamlit as st
import asyncio
import re
from config import config
from agents import generate_response

st.set_page_config(page_title="AI Council Simulator", layout="wide", initial_sidebar_state="collapsed")

# --- CSS INJECTION (Aggressive Dark Mode & Animations) ---
css = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif !important;
    }
    
    /* Force dark mode and full-page gradient */
    .stApp, .main {
        background: linear-gradient(180deg, #020617 0%, #0f172a 100%) !important;
        background-attachment: fixed !important;
        color: #e2e8f0 !important;
    }
    
    /* Gradients for headers */
    h1, h2, h3 {
        background: linear-gradient(135deg, #38bdf8, #a78bfa, #3fb950) !important;
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        font-weight: 700 !important;
    }

    /* Fix white-on-white Chat Input */
    [data-testid="stChatInput"] {
        background-color: #1e293b !important;
        border: 1px solid rgba(56, 189, 248, 0.4) !important;
        border-radius: 20px !important;
        box-shadow: 0 4px 20px rgba(0,0,0,0.5) !important;
    }
    /* Extremely aggressive text color override for light mode */
    [data-testid="stChatInput"] textarea, div[data-baseweb="textarea"] textarea {
        color: #f8fafc !important;
        -webkit-text-fill-color: #f8fafc !important;
        background-color: transparent !important;
    }
    div[data-baseweb="base-input"] {
        background-color: transparent !important;
    }
    [data-testid="stChatInput"] button {
        color: #38bdf8 !important;
    }
    [data-testid="stChatInput"] button:hover {
        color: #a78bfa !important;
        transform: scale(1.1);
    }
    
    /* User chat message styling */
    [data-testid="stChatMessage"] {
        background-color: transparent !important;
    }
    div[data-testid="chatAvatarIcon-user"] {
        background-color: #38bdf8 !important;
    }
    div[data-testid="chatAvatarIcon-assistant"] {
        background: linear-gradient(135deg, #a78bfa, #38bdf8) !important;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #050811 !important;
        border-right: 1px solid rgba(148, 163, 184, 0.1) !important;
    }
    [data-testid="stSidebar"] * {
        color: #cbd5e1 !important;
    }
    .streamlit-expanderHeader {
        font-weight: 600 !important;
        color: #a78bfa !important;
    }
    
    /* Pulse Animation */
    .thinking-box {
        display: flex;
        align-items: center;
        gap: 12px;
        color: #a78bfa;
        font-style: italic;
        padding: 10px;
        background: rgba(167, 139, 250, 0.1);
        border-radius: 8px;
        border: 1px solid rgba(167, 139, 250, 0.2);
        margin-bottom: 10px;
    }
    .pulse-dot {
        width: 10px;
        height: 10px;
        background-color: #38bdf8;
        border-radius: 50%;
        animation: pulse 1s infinite alternate;
    }
    @keyframes pulse {
        0% { transform: scale(0.8); opacity: 0.4; }
        100% { transform: scale(1.3); opacity: 1; }
    }
</style>
"""
st.markdown(css, unsafe_allow_html=True)

# Initialize session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "agent_outputs" not in st.session_state:
    st.session_state.agent_outputs = {"DeepSeek": "", "GLM": "", "Qwen": "", "Evaluator": ""}
if "agent_status" not in st.session_state:
    st.session_state.agent_status = {"DeepSeek": "Ожидание", "GLM": "Ожидание", "Qwen": "Ожидание", "Evaluator": "Ожидание"}
if "is_running" not in st.session_state:
    st.session_state.is_running = False
if "current_prompt" not in st.session_state:
    st.session_state.current_prompt = ""

def extract_final_answer(text: str) -> str:
    match = re.search(r'\[ФИНАЛ\](.*)', text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else text.strip()

async def run_agent(agent_name: str, task: str, role_prompt: str, placeholder, status_placeholder):
    st.session_state.agent_status[agent_name] = "Думает..."
    status_placeholder.markdown(f"<div class='thinking-box'><div class='pulse-dot'></div> {agent_name} собирает данные...</div>", unsafe_allow_html=True)
    messages = [
        {"role": "system", "content": f"{config.SYSTEM_PROMPT}\n\n{role_prompt}"},
        {"role": "user", "content": task}
    ]
    st.session_state.agent_outputs[agent_name] = ""
    async for item in generate_response(agent_name, messages, use_tools=True, stream=True):
        if isinstance(item, dict):
            if item["type"] == "content":
                st.session_state.agent_outputs[agent_name] += item["data"]
                placeholder.markdown(st.session_state.agent_outputs[agent_name])
            elif item["type"] == "status":
                st.session_state.agent_status[agent_name] = item["data"]
                status_placeholder.markdown(f"<div class='thinking-box'><div class='pulse-dot'></div> {agent_name}: {item['data']}</div>", unsafe_allow_html=True)
            elif item["type"] == "error":
                st.session_state.agent_outputs[agent_name] += f"\n\n**Error:** {item['data']}"
                placeholder.markdown(st.session_state.agent_outputs[agent_name])
        else:
            st.session_state.agent_outputs[agent_name] += str(item)
            placeholder.markdown(st.session_state.agent_outputs[agent_name])

    st.session_state.agent_status[agent_name] = "Завершил Этап 1"
    status_placeholder.success(f"✓ {agent_name} завершил анализ")
    return st.session_state.agent_outputs[agent_name]

async def run_debate(agent_name: str, own_text: str, other_answers: dict, placeholder, status_placeholder):
    st.session_state.agent_status[agent_name] = "Критикует..."
    status_placeholder.markdown(f"<div class='thinking-box'><div class='pulse-dot'></div> {agent_name} критикует коллег...</div>", unsafe_allow_html=True)
    
    critique_prompt = "Проанализируй ответы других нейросетей на ту же задачу. В чем они ошибаются? В чем их сильные стороны? Согласен ли ты с ними? Ответь кратко (1-2 абзаца).\n\n"
    for name, answer in other_answers.items():
        if name != agent_name:
            critique_prompt += f"--- Ответ {name} ---\n{extract_final_answer(answer)}\n\n"
            
    st.session_state.agent_outputs[agent_name] += "\n\n---\n**[ЭТАП 2: ДЕБАТЫ]**\n\n"
    placeholder.markdown(st.session_state.agent_outputs[agent_name])
    
    messages = [
        {"role": "system", "content": f"Твоя задача критиковать решения коллег. Ты - {agent_name}. Твоя логика: {config.SYSTEM_PROMPT}"},
        {"role": "user", "content": f"Твой изначальный ответ: {extract_final_answer(own_text)}"},
        {"role": "user", "content": critique_prompt}
    ]
    
    async for item in generate_response(agent_name, messages, use_tools=False, stream=True):
        if isinstance(item, dict) and item["type"] == "content":
            st.session_state.agent_outputs[agent_name] += item["data"]
            placeholder.markdown(st.session_state.agent_outputs[agent_name])
        elif isinstance(item, dict) and item["type"] == "error":
            st.session_state.agent_outputs[agent_name] += f"\n\n**Error:** {item['data']}"
            placeholder.markdown(st.session_state.agent_outputs[agent_name])

    st.session_state.agent_status[agent_name] = "Завершил Этап 2"
    status_placeholder.success(f"✓ {agent_name} завершил дебаты")

async def run_evaluator(task: str, all_outputs: dict, placeholder, status_placeholder):
    st.session_state.agent_status["Evaluator"] = "Анализирует..."
    status_placeholder.markdown("<div class='thinking-box'><div class='pulse-dot'></div> Оценщик формирует финальный вердикт...</div>", unsafe_allow_html=True)
    
    context = f"ЗАДАЧА: {task}\n\nОТВЕТЫ АГЕНТОВ И ИХ ДЕБАТЫ:\n"
    for name, text in all_outputs.items():
        if name != "Evaluator":
            context += f"=== {name} ===\n{text}\n\n"
            
    messages = [
        {"role": "system", "content": config.EVALUATOR_PROMPT},
        {"role": "user", "content": context}
    ]
    
    st.session_state.agent_outputs["Evaluator"] = ""
    async for item in generate_response("Evaluator", messages, use_tools=False, stream=True):
         if isinstance(item, dict) and item["type"] == "content":
            st.session_state.agent_outputs["Evaluator"] += item["data"]
            placeholder.markdown(st.session_state.agent_outputs["Evaluator"])
            
    st.session_state.agent_status["Evaluator"] = "Готово"
    status_placeholder.empty() # Remove the thinking box when done

async def main_pipeline(task: str, placeholders_dict, status_placeholders_dict, global_status_placeholder):
    # Stage 1
    global_status_placeholder.markdown("<div class='thinking-box'><div class='pulse-dot'></div> <i>Агенты собирают информацию и готовят анализ...</i></div>", unsafe_allow_html=True)
    t1 = run_agent("DeepSeek", task, config.DEEPSEEK_PROMPT, placeholders_dict["DeepSeek"], status_placeholders_dict["DeepSeek"])
    t2 = run_agent("GLM", task, config.GLM_PROMPT, placeholders_dict["GLM"], status_placeholders_dict["GLM"])
    t3 = run_agent("Qwen", task, config.QWEN_PROMPT, placeholders_dict["Qwen"], status_placeholders_dict["Qwen"])
    
    res1, res2, res3 = await asyncio.gather(t1, t2, t3, return_exceptions=True)
    
    # Handle possible exceptions returned by gather
    if isinstance(res1, Exception): res1 = f"Error: {res1}"
    if isinstance(res2, Exception): res2 = f"Error: {res2}"
    if isinstance(res3, Exception): res3 = f"Error: {res3}"
    
    # Stage 2
    global_status_placeholder.markdown("<div class='thinking-box'><div class='pulse-dot'></div> <i>Консилиум проводит дебаты и критикует решения...</i></div>", unsafe_allow_html=True)
    answers = {"DeepSeek": res1, "GLM": res2, "Qwen": res3}
    d1 = run_debate("DeepSeek", res1, answers, placeholders_dict["DeepSeek"], status_placeholders_dict["DeepSeek"])
    d2 = run_debate("GLM", res2, answers, placeholders_dict["GLM"], status_placeholders_dict["GLM"])
    d3 = run_debate("Qwen", res3, answers, placeholders_dict["Qwen"], status_placeholders_dict["Qwen"])
    
    await asyncio.gather(d1, d2, d3, return_exceptions=True)
    
    # Stage 3
    global_status_placeholder.markdown("<div class='thinking-box'><div class='pulse-dot'></div> <i>Главный Оценщик формирует финальный вердикт...</i></div>", unsafe_allow_html=True)
    await run_evaluator(task, st.session_state.agent_outputs, placeholders_dict["Evaluator"], status_placeholders_dict["Evaluator"])


# --- SIDEBAR (For Background Agents) ---
with st.sidebar:
    st.markdown("<h2>🧠 AI Council</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #64748b; font-size: 0.9rem;'>Здесь работают скрытые агенты</p>", unsafe_allow_html=True)
    
    sidebar_placeholders = {}
    for agent in ["DeepSeek", "GLM", "Qwen"]:
        with st.expander(f"Процесс: {agent}", expanded=False):
            status_pl = st.empty()
            content_pl = st.empty()
            sidebar_placeholders[agent] = {"status": status_pl, "content": content_pl}
            
            # Show historical output if not running
            if not st.session_state.is_running and st.session_state.agent_outputs.get(agent):
                content_pl.markdown(st.session_state.agent_outputs[agent])


# --- MAIN SCREEN ---
landing_placeholder = st.empty()

# 1. Show the landing page only if there is no chat history and no current task
if not st.session_state.chat_history and not st.session_state.is_running:
    landing_placeholder.markdown("<h1 style='text-align: center; margin-top: 25vh; font-size: 4rem;'>Чем я могу помочь?</h1>", unsafe_allow_html=True)

# 2. Main Chat Container
chat_container = st.container()
with chat_container:
    # Render previous history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# 3. Chat Input
prompt = st.chat_input("Спросить консилиум ИИ (Level 5 Reasoning)...")

if prompt and not st.session_state.is_running:
    landing_placeholder.empty() # Immediately clear the big text
    
    # Add user prompt to history
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    
    st.session_state.is_running = True
    st.session_state.current_prompt = prompt
    
    # Reset agent outputs
    st.session_state.agent_outputs = {k: "" for k in st.session_state.agent_outputs}
    st.rerun()

# 4. Pipeline Execution Trigger
if st.session_state.is_running and st.session_state.current_prompt:
    prompt = st.session_state.current_prompt
    
    with chat_container:
         with st.chat_message("assistant"):
             eval_status_pl = st.empty()
             eval_content_pl = st.empty()
             
             eval_status_pl.markdown("<div class='thinking-box'><div class='pulse-dot'></div> <i>Инициализация ИИ-консилиума...</i></div>", unsafe_allow_html=True)
             
    placeholders = {
        "Evaluator": eval_content_pl,
        "DeepSeek": sidebar_placeholders["DeepSeek"]["content"],
        "GLM": sidebar_placeholders["GLM"]["content"],
        "Qwen": sidebar_placeholders["Qwen"]["content"]
    }
    status_placeholders = {
        "Evaluator": eval_status_pl,
        "DeepSeek": sidebar_placeholders["DeepSeek"]["status"],
        "GLM": sidebar_placeholders["GLM"]["status"],
        "Qwen": sidebar_placeholders["Qwen"]["status"]
    }
    
    asyncio.run(main_pipeline(prompt, placeholders, status_placeholders, eval_status_pl))
    
    # Finalize
    st.session_state.chat_history.append({"role": "assistant", "content": st.session_state.agent_outputs["Evaluator"]})
    st.session_state.is_running = False
    st.session_state.current_prompt = ""
    st.rerun()
