import streamlit as st
import asyncio
import re
from config import config
from agents import generate_response

st.set_page_config(page_title="AI Council Simulator", layout="wide", initial_sidebar_state="expanded")

# Inject Custom CSS for UI
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');

    /* Global Background and Fonts */
    html, body, [class*="css"]  {
        font-family: 'Outfit', sans-serif !important;
    }
    
    .stApp {
        background-color: #030712; /* Deep dark blue/black */
        color: #f8fafc; /* Very bright white/blue text */
    }
    
    /* Hide top padding */
    .stApp > header {
        background-color: transparent !important;
    }
    .block-container {
        padding-top: 2rem !important;
    }

    /* Gradients for headers */
    h1, h2, h3 {
        background: linear-gradient(135deg, #38bdf8, #a78bfa, #2dd4bf);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 700 !important;
        letter-spacing: -0.5px;
    }
    
    /* Central big text */
    .big-center-text {
        text-align: center;
        font-size: 3.5rem;
        margin-top: 20vh;
        margin-bottom: 2rem;
        background: linear-gradient(135deg, #f8fafc, #94a3b8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 500;
        animation: fadeIn 1.5s ease-in-out;
    }

    @keyframes fadeIn {
        0% { opacity: 0; transform: translateY(20px); }
        100% { opacity: 1; transform: translateY(0); }
    }

    /* Chat Input Styling */
    .stChatInputContainer {
        background-color: rgba(15, 23, 42, 0.7) !important;
        border: 1px solid rgba(56, 189, 248, 0.2) !important;
        border-radius: 24px !important;
        padding: 4px 10px !important;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.5) !important;
        backdrop-filter: blur(12px) !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        margin-bottom: 20px !important;
    }
    .stChatInputContainer:focus-within {
        border: 1px solid rgba(56, 189, 248, 0.6) !important;
        box-shadow: 0 0 30px rgba(167, 139, 250, 0.3) !important;
        transform: translateY(-2px);
    }
    .stChatInputContainer textarea {
        color: #f8fafc !important;
        font-size: 1.1rem !important;
    }
    /* Chat input send button coloring */
    .stChatInputContainer button {
        color: #38bdf8 !important;
        transition: transform 0.2s;
    }
    .stChatInputContainer button:hover {
        transform: scale(1.1) rotate(5deg);
        color: #a78bfa !important;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        background-color: transparent;
        border-bottom: 1px solid rgba(255,255,255,0.05);
    }
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        border-radius: 0;
        border: none;
        color: #64748b;
        padding: 12px 16px;
        font-weight: 500;
        font-size: 1.05rem;
        transition: color 0.3s ease;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #94a3b8;
    }
    .stTabs [aria-selected="true"] {
        background-color: transparent !important;
        color: #38bdf8 !important;
        border-bottom: 2px solid #38bdf8 !important;
    }

    /* Sidebars */
    section[data-testid="stSidebar"] {
        background-color: #020617;
        border-right: 1px solid rgba(255,255,255,0.05);
        min-width: 240px !important;
        max-width: 280px !important;
    }
    /* Adjust sidebar text */
    .css-17lntkn {
        color: #94a3b8;
    }
    
    /* Information boxes (statuses) */
    .stAlert {
        background: linear-gradient(90deg, rgba(15, 23, 42, 0.8), rgba(2, 6, 23, 0.8)) !important;
        border: 1px solid rgba(255,255,255,0.05) !important;
        border-left: 4px solid #a78bfa !important;
        color: #e2e8f0 !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* Markdown Text */
    .stMarkdown p, .stMarkdown li {
        font-size: 1.08rem;
        line-height: 1.7;
        color: #cbd5e1;
    }
    
    /* Expanders in sidebar */
    .streamlit-expanderHeader {
        color: #94a3b8 !important;
        font-weight: 500 !important;
    }
</style>
""", unsafe_allow_html=True)

# Helper function for SVG Icons
def svg_icon(path_d, color1="#38bdf8", color2="#a78bfa", size=24):
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="url(#grad_{color1[1:]})" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block; vertical-align:middle; margin-right:8px;">
        <defs>
            <linearGradient id="grad_{color1[1:]}" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:{color1};stop-opacity:1" />
                <stop offset="100%" style="stop-color:{color2};stop-opacity:1" />
            </linearGradient>
        </defs>
        <path d="{path_d}"></path>
    </svg>
    """

# Icons definitions
ICON_COUNCIL = "M12 2a10 10 0 1 0 10 10H12V2z M12 12 2.1 7.1 M12 12l9.9 4.9"
ICON_DEEPSEEK = "M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z M3.27 6.96L12 12.01l8.73-5.05 M12 22.08V12"
ICON_GLM = "M12 2v20 M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"
ICON_QWEN = "M2 12h4l3-9 5 18 3-9h5"
ICON_EVALUATOR = "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"
ICON_HISTORY = "M3 3v5h5 M3.05 13A9 9 0 1 0 6 5.3L3 8"
ICON_STATUS = "M22 11.08V12a10 10 0 1 1-5.93-9.14 M22 4L12 14.01l-3-3"

# Initialize session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "agent_outputs" not in st.session_state:
    st.session_state.agent_outputs = {"DeepSeek": "", "GLM": "", "Qwen": "", "Evaluator": ""}
if "agent_status" not in st.session_state:
    st.session_state.agent_status = {"DeepSeek": "Ожидание", "GLM": "Ожидание", "Qwen": "Ожидание", "Evaluator": "Ожидание"}
if "is_running" not in st.session_state:
    st.session_state.is_running = False
if "current_task" not in st.session_state:
    st.session_state.current_task = ""

def extract_final_answer(text: str) -> str:
    match = re.search(r'\[ФИНАЛ\](.*)', text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else text.strip()

async def run_agent(agent_name: str, task: str, role_prompt: str, placeholder, status_placeholder):
    st.session_state.agent_status[agent_name] = "Думает..."
    status_placeholder.info(f"**{agent_name}**: Думает...")
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
                status_placeholder.info(f"**{agent_name}**: {item['data']}")
            elif item["type"] == "error":
                st.session_state.agent_outputs[agent_name] += f"\n\n**Error:** {item['data']}"
                placeholder.markdown(st.session_state.agent_outputs[agent_name])
        else:
            st.session_state.agent_outputs[agent_name] += str(item)
            placeholder.markdown(st.session_state.agent_outputs[agent_name])

    st.session_state.agent_status[agent_name] = "Завершил Этап 1"
    status_placeholder.success(f"**{agent_name}**: Завершил Этап 1")
    return st.session_state.agent_outputs[agent_name]

async def run_debate(agent_name: str, own_text: str, other_answers: dict, placeholder, status_placeholder):
    st.session_state.agent_status[agent_name] = "Критикует..."
    status_placeholder.info(f"**{agent_name}**: Критикует...")
    
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
    status_placeholder.success(f"**{agent_name}**: Завершил Этап 2")

async def run_evaluator(task: str, all_outputs: dict, placeholder, status_placeholder):
    st.session_state.agent_status["Evaluator"] = "Анализирует..."
    status_placeholder.info(f"**Evaluator**: Анализирует...")
    
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
    status_placeholder.success(f"**Evaluator**: Готово")

async def main_pipeline(task: str, placeholders_dict, status_placeholders_dict):
    st.session_state.is_running = True
    
    # Stage 1
    t1 = run_agent("DeepSeek", task, config.DEEPSEEK_PROMPT, placeholders_dict["DeepSeek"], status_placeholders_dict["DeepSeek"])
    t2 = run_agent("GLM", task, config.GLM_PROMPT, placeholders_dict["GLM"], status_placeholders_dict["GLM"])
    t3 = run_agent("Qwen", task, config.QWEN_PROMPT, placeholders_dict["Qwen"], status_placeholders_dict["Qwen"])
    
    res1, res2, res3 = await asyncio.gather(t1, t2, t3)
    
    # Stage 2
    answers = {"DeepSeek": res1, "GLM": res2, "Qwen": res3}
    d1 = run_debate("DeepSeek", res1, answers, placeholders_dict["DeepSeek"], status_placeholders_dict["DeepSeek"])
    d2 = run_debate("GLM", res2, answers, placeholders_dict["GLM"], status_placeholders_dict["GLM"])
    d3 = run_debate("Qwen", res3, answers, placeholders_dict["Qwen"], status_placeholders_dict["Qwen"])
    
    await asyncio.gather(d1, d2, d3)
    
    # Stage 3
    await run_evaluator(task, st.session_state.agent_outputs, placeholders_dict["Evaluator"], status_placeholders_dict["Evaluator"])
    
    st.session_state.is_running = False
    
    # Save to history
    st.session_state.chat_history.append({
        "task": task,
        "evaluator": st.session_state.agent_outputs["Evaluator"]
    })

# --- UI Sidebar ---
st.sidebar.markdown(f"{svg_icon(ICON_COUNCIL, '#38bdf8', '#2dd4bf', 28)} <span style='font-size:1.5rem; font-weight:700; color:#e2e8f0; vertical-align:middle;'>AI Council</span>", unsafe_allow_html=True)
st.sidebar.markdown("<br>", unsafe_allow_html=True)

st.sidebar.markdown(f"{svg_icon(ICON_STATUS, '#a78bfa', '#f472b6', 20)} **Текущие Статусы**", unsafe_allow_html=True)
for agent in ["DeepSeek", "GLM", "Qwen", "Evaluator"]:
    status = st.session_state.agent_status.get(agent, "Ожидание")
    st.sidebar.caption(f"**{agent}**: {status}")

st.sidebar.markdown("<br>", unsafe_allow_html=True)
st.sidebar.markdown(f"{svg_icon(ICON_HISTORY, '#3fb950', '#2dd4bf', 20)} **История сессий**", unsafe_allow_html=True)
if not st.session_state.chat_history:
    st.sidebar.caption("Пусто")
for i, h in enumerate(st.session_state.chat_history):
    with st.sidebar.expander(f"Сессия {i+1}"):
        st.caption(h["task"][:60] + "...")
        st.markdown(h["evaluator"][:100] + "...")

# --- Main Content ---
if not st.session_state.current_task and not st.session_state.is_running and not any(st.session_state.agent_outputs.values()):
    # Landing Page
    st.markdown("<div class='big-center-text'>Чем я могу помочь?</div>", unsafe_allow_html=True)

# Chat Input at the bottom
task_input = st.chat_input("Спросить консилиум ИИ (Level 5 Reasoning)...")

if task_input:
    if not st.session_state.is_running:
        st.session_state.current_task = task_input
        # Clear previous outputs
        st.session_state.agent_outputs = {k: "" for k in st.session_state.agent_outputs}
        st.session_state.agent_status = {k: "Подготовка..." for k in st.session_state.agent_status}

if st.session_state.current_task:
    # Render the tabs
    tab_eval, tab_ds, tab_glm, tab_qwen = st.tabs(["Главный чат", "DeepSeek", "GLM", "Qwen"])
    
    with tab_eval:
        st.markdown(f"<h2>{svg_icon(ICON_EVALUATOR)} Главный Оценщик</h2>", unsafe_allow_html=True)
        status_eval = st.empty()
        content_eval = st.empty()
        
    with tab_ds:
        st.markdown(f"<h2>{svg_icon(ICON_DEEPSEEK, '#f43f5e', '#fb923c')} DeepSeek - Анализ</h2>", unsafe_allow_html=True)
        status_ds = st.empty()
        content_ds = st.empty()
        
    with tab_glm:
        st.markdown(f"<h2>{svg_icon(ICON_GLM, '#8b5cf6', '#d946ef')} GLM - Визионер</h2>", unsafe_allow_html=True)
        status_glm = st.empty()
        content_glm = st.empty()
        
    with tab_qwen:
        st.markdown(f"<h2>{svg_icon(ICON_QWEN, '#10b981', '#3b82f6')} Qwen - Архитектор</h2>", unsafe_allow_html=True)
        status_qwen = st.empty()
        content_qwen = st.empty()

    placeholders = {
        "Evaluator": content_eval,
        "DeepSeek": content_ds,
        "GLM": content_glm,
        "Qwen": content_qwen
    }
    
    status_placeholders = {
        "Evaluator": status_eval,
        "DeepSeek": status_ds,
        "GLM": status_glm,
        "Qwen": status_qwen
    }

    if st.session_state.is_running:
        # Already running, just show current output 
        pass
    else:
        # Not running yet, start it now
        if not any(st.session_state.agent_outputs.values()):
            asyncio.run(main_pipeline(st.session_state.current_task, placeholders, status_placeholders))
            st.rerun()
        else:
            # Finished, show the outputs
            content_eval.markdown(st.session_state.agent_outputs["Evaluator"])
            content_ds.markdown(st.session_state.agent_outputs["DeepSeek"])
            content_glm.markdown(st.session_state.agent_outputs["GLM"])
            content_qwen.markdown(st.session_state.agent_outputs["Qwen"])
