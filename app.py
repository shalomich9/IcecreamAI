import streamlit as st
import asyncio
import re
from config import config
from agents import generate_response

st.set_page_config(page_title="AI Council Simulator", layout="wide", initial_sidebar_state="expanded")

# Inject Custom CSS for UI
st.markdown("""
<style>
    /* Global Background and Colors */
    .stApp {
        background-color: #0d1117;
        color: #c9d1d9;
    }
    
    /* Text Inputs and Text Areas */
    .stTextArea textarea {
        background-color: #161b22 !important;
        color: #c9d1d9 !important;
        border: 1px solid #30363d !important;
        border-radius: 12px !important;
        padding: 16px !important;
        box-shadow: inset 0 1px 2px rgba(0,0,0,0.075) !important;
        transition: all 0.3s ease !important;
    }
    .stTextArea textarea:focus {
        border-color: #58a6ff !important;
        box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.3) !important;
    }

    /* Buttons */
    .stButton>button {
        background: linear-gradient(135deg, #1f6feb, #8957e5, #3fb950);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 10px 24px;
        font-weight: 600;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(137, 87, 229, 0.4);
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #21262d;
        border-radius: 8px 8px 0 0;
        border: none;
        color: #8b949e;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(31, 111, 235, 0.1), rgba(137, 87, 229, 0.1));
        color: #58a6ff;
        border-bottom: 2px solid #58a6ff;
    }

    /* Sidebars */
    section[data-testid="stSidebar"] {
        background-color: #161b22;
        border-right: 1px solid #30363d;
    }
    
    /* Headers and Gradients */
    h1, h2, h3 {
        background: -webkit-linear-gradient(45deg, #58a6ff, #a371f7, #3fb950);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800 !important;
    }

    /* Information boxes (statuses) */
    .stAlert {
        background-color: rgba(33, 38, 45, 0.8) !important;
        border: 1px solid #30363d !important;
        border-left: 4px solid #8957e5 !important;
        color: #c9d1d9 !important;
        border-radius: 8px !important;
    }
    
    /* Markdown Text */
    .stMarkdown p {
        font-size: 1.05rem;
        line-height: 1.6;
    }
</style>
""", unsafe_allow_html=True)


# Initialize session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "agent_outputs" not in st.session_state:
    st.session_state.agent_outputs = {"DeepSeek": "", "GLM": "", "Qwen": "", "Evaluator": ""}
if "agent_status" not in st.session_state:
    st.session_state.agent_status = {"DeepSeek": "Ожидание", "GLM": "Ожидание", "Qwen": "Ожидание", "Evaluator": "Ожидание"}
if "is_running" not in st.session_state:
    st.session_state.is_running = False

def extract_final_answer(text: str) -> str:
    """Extracts the [ФИНАЛ] block from an agent's response."""
    match = re.search(r'\[ФИНАЛ\](.*)', text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else text.strip()

async def run_agent(agent_name: str, task: str, role_prompt: str, placeholder, status_placeholder):
    """Stage 1: Generate initial response from an agent."""
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
    """Stage 2: Cross debate."""
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
    """Stage 3: Evaluator."""
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

# --- UI ---

st.sidebar.title("🧠 AI Council")

st.sidebar.markdown("---")
st.sidebar.subheader("Статусы")
for agent in ["DeepSeek", "GLM", "Qwen", "Evaluator"]:
    status = st.session_state.agent_status.get(agent, "Ожидание")
    st.sidebar.caption(f"**{agent}**: {status}")

st.sidebar.markdown("---")
st.sidebar.subheader("История сессий")
for i, h in enumerate(st.session_state.chat_history):
    with st.sidebar.expander(f"Сессия {i+1}"):
        st.write(h["task"][:50] + "...")
        st.markdown(h["evaluator"])

# Main Content
st.title("🏛 Мультиагентный Консилиум")
st.markdown("Задайте сложную задачу, и консилиум из 3 нейросетей разберет ее, проведет дебаты, а главный оценщик выдаст финальный вердикт.")

task_input = st.text_area("Введите задачу (Level 5 Reasoning):", height=100)

if st.button("Запустить симуляцию", disabled=st.session_state.is_running):
    if task_input:
        # Clear previous outputs
        st.session_state.agent_outputs = {k: "" for k in st.session_state.agent_outputs}
        st.session_state.agent_status = {k: "Подготовка..." for k in st.session_state.agent_status}
        
        # UI containers for tabs
        tab_eval, tab_ds, tab_glm, tab_qwen = st.tabs(["Главный чат (Оценщик)", "DeepSeek", "GLM", "Qwen"])
        
        with tab_eval:
            st.subheader("Главный чат")
            status_eval = st.empty()
            content_eval = st.empty()
            
        with tab_ds:
            st.subheader("🧠 DeepSeek - Личный чат")
            status_ds = st.empty()
            content_ds = st.empty()
            
        with tab_glm:
            st.subheader("💡 GLM - Личный чат")
            status_glm = st.empty()
            content_glm = st.empty()
            
        with tab_qwen:
            st.subheader("🏗️ Qwen - Личный чат")
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

        # Run asyncio event loop for pipeline
        asyncio.run(main_pipeline(task_input, placeholders, status_placeholders))
        st.rerun()

# If not running and there is output, show it (so it persists after rerun)
elif not st.session_state.is_running and any(st.session_state.agent_outputs.values()):
    tab_eval, tab_ds, tab_glm, tab_qwen = st.tabs(["Главный чат (Оценщик)", "DeepSeek", "GLM", "Qwen"])
    
    with tab_eval:
        st.subheader("Главный чат")
        st.markdown(st.session_state.agent_outputs["Evaluator"])
        
    with tab_ds:
        st.subheader("🧠 DeepSeek - Личный чат")
        st.markdown(st.session_state.agent_outputs["DeepSeek"])
        
    with tab_glm:
        st.subheader("💡 GLM - Личный чат")
        st.markdown(st.session_state.agent_outputs["GLM"])
        
    with tab_qwen:
        st.subheader("🏗️ Qwen - Личный чат")
        st.markdown(st.session_state.agent_outputs["Qwen"])
