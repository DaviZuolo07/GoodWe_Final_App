import streamlit as st
import sys, re, time, uuid
from pathlib import Path
from datetime import datetime, timedelta


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from ai.memory.user_profile_memory import UserProfileMemory
from database.chat_persistence_service import ChatPersistenceService

import base64
def _img64(path):
    with open(ROOT_DIR / path, "rb") as f:
        return base64.b64encode(f.read()).decode()
LOGO_B64 = _img64("assets/goodwe_logo.png")


try:
    from ai.services.chat_service import ChatService
except Exception:
    class ChatService:
        """Fallback mock — substitui pelo serviço real quando disponível."""

        def __init__(
            self,
            system_context=None,
            user_context=None
        ):
            self.system_context = system_context or ""
            self.user_context = user_context or ""

        def send_message(self, msg):
            return (
                f"(modo offline) Recebido: {msg}\n\n"
                f"Conecte o ChatService real em "
                f"ai/services/chat_service.py "
                f"para respostas completas."
            )


st.set_page_config(page_title="GoodWe ChargeOps AI", page_icon="⚡", layout="wide")


# ==================================================
# CSS — TEMA GOODWE FUTURISTA
# ==================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"]  { font-family: 'Inter', sans-serif; }

.stApp {
    background: radial-gradient(circle at 10% 0%, #1b2735 0%, #0d1520 45%, #0a0f17 100%);
    color: #E8EEF4;
}

#MainMenu, footer {visibility: hidden;}
header { visibility: visible !important; background: transparent !important; }
[data-testid="stSidebarCollapsedControl"] {
    visibility: visible !important; display:flex !important;
    color: #fff !important; z-index: 999999;
}
[data-testid="stSidebarCollapsedControl"] svg { fill:#fff !important; }

/* Sidebar */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #11181f 0%, #0c1116 100%);
    border-right: 1px solid rgba(215,25,32,0.15);
}
section[data-testid="stSidebar"] * { color: #DCE4EC; }
section[data-testid="stSidebar"] > div { height: 100vh; display:flex; flex-direction:column; }
section[data-testid="stSidebar"] > div > div[data-testid="stVerticalBlock"] { flex:1; display:flex; flex-direction:column; }

.sb-brand {
    display:flex; align-items:center; gap:12px;
    padding: 8px 4px 20px 4px; border-bottom: 1px solid rgba(255,255,255,0.06);
    margin-bottom: 16px;
}
.sb-brand .logo {
    width:42px; height:42px; border-radius:10px;
    background: linear-gradient(135deg, #D71920, #FF5A33);
    display:flex; align-items:center; justify-content:center;
    font-size:22px; box-shadow: 0 0 14px rgba(215,25,32,0.6);
}
.sb-brand .name { font-weight:700; font-size:17px; color:#fff; }
.sb-brand .sub { font-size:12px; color:#8A97A6; }

.sb-section-label {
    font-size: 12px; letter-spacing: .08em; text-transform: uppercase;
    color: #6E7A89; margin: 16px 0 8px 4px; font-weight:600;
}

section[data-testid="stSidebar"] .stButton button {
    background: rgba(255,255,255,0.05) !important;
    color: #fff !important; text-align:left; font-weight:500;
    border: 1px solid rgba(255,255,255,0.08);
    box-shadow:none; font-size:14px; padding: 10px 12px;
}
section[data-testid="stSidebar"] .stButton button:hover {
    background: rgba(215,25,32,0.18) !important;
    border-color: rgba(215,25,32,0.4); box-shadow:none;
}
section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] > div:nth-of-type(2) .stButton button {
    background: linear-gradient(135deg, #D71920, #B5151B) !important; text-align:center;
}
section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] > div:nth-of-type(n+3) .stButton button {
    background: rgba(215,25,32,0.16) !important;
    color: #fff !important; text-align:left; font-weight:500;
    border: 1px solid rgba(215,25,32,0.3);
    box-shadow:none; font-size:14px; padding: 10px 12px;
}
section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] > div:nth-of-type(n+3) .stButton button:hover {
    background: rgba(215,25,32,0.32) !important;
    border-color: rgba(215,25,32,0.6); box-shadow:none;
}

.chat-history-item {
    padding: 8px 10px; border-radius: 8px; font-size: 13px;
    color: #C2CCD8; cursor:pointer; margin-bottom:2px;
    white-space: nowrap; overflow:hidden; text-overflow:ellipsis;
    border: 1px solid transparent;
}
.chat-history-item:hover { background: rgba(215,25,32,0.10); border-color: rgba(215,25,32,0.25); }
.chat-history-active { background: rgba(215,25,32,0.18); border-color: rgba(215,25,32,0.4); color:#fff; }

.sb-profile {
    display:flex; align-items:center; gap:10px; padding:10px 8px;
    border-top: 1px solid rgba(255,255,255,0.06); margin-top: auto;
}
.sb-profile .avatar {
    width:30px; height:30px; border-radius:50%;
    background: linear-gradient(135deg,#D71920,#1E3A5F);
    display:flex; align-items:center; justify-content:center;
    font-weight:700; font-size:13px; color:#fff;
}
.sb-profile .meta .nm { font-size:13px; font-weight:600; color:#fff; }
.sb-profile .meta .role { font-size:11px; color:#8A97A6; }

/* Header principal */
.gw-header {
    background: linear-gradient(120deg, rgba(215,25,32,0.18), rgba(30,58,95,0.25));
    border: 1px solid rgba(215,25,32,0.25);
    padding: 28px 32px; border-radius: 18px; margin-bottom: 24px;
    backdrop-filter: blur(6px);
    box-shadow: 0 4px 24px rgba(0,0,0,0.25);
}
.gw-title { color:#fff; font-size:34px; font-weight:800; display:flex; align-items:center; gap:12px;}
.gw-title .bolt { color:#FF4D4D; filter: drop-shadow(0 0 8px rgba(255,77,77,.7)); }
.gw-subtitle { color:#AAB6C3; font-size:15px; margin-top:6px; letter-spacing:.03em; }

/* Chat bubbles */
[data-testid="stChatMessage"] {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    color: #fff !important;
}
[data-testid="stChatMessage"] * { color: #fff !important; }
[data-testid="stChatMessage"] table { color:#fff !important; }
[data-testid="stChatMessage"] code { color:#FFD479 !important; background: rgba(255,255,255,0.08) !important; }

/* Chat input fixo no rodapé, estilo Claude */
[data-testid="stChatInput"] {
    background: #fff !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: 16px !important;
}
[data-testid="stChatInput"] textarea {
    background: transparent !important; color:#FFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
}
[data-testid="stChatInput"] textarea::placeholder { color:#B0B0B0 !important; }
[data-testid="stBottomBlockContainer"] {
    background: #0d1520 !important;
}

/* Botões */
.stButton button {
    background: linear-gradient(135deg, #D71920, #B5151B);
    color: white; border: none; border-radius: 10px; font-weight:600;
    transition: all .15s ease;
}
.stButton button:hover {
    background: linear-gradient(135deg, #FF4D4D, #D71920);
    box-shadow: 0 0 14px rgba(215,25,32,0.5);
}

/* Inputs */
.stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] > div, .stTextArea textarea {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    color: #fff !important; border-radius: 10px !important;
}

/* welcome card */
.welcome-card {
    background: linear-gradient(135deg, rgba(215,25,32,0.15), rgba(30,58,95,0.25));
    border: 1px solid rgba(215,25,32,0.3);
    border-radius: 24px; padding: 56px; text-align:center;
    box-shadow: 0 8px 40px rgba(0,0,0,0.35);
    max-width: 900px; margin: 30px auto;
}
.welcome-card h1 { color:#fff; font-size: 42px; }
.welcome-card .accent { color:#FF4D4D; }

.feature-grid { display:grid; grid-template-columns: repeat(2,1fr); gap:18px; margin-top:28px; }
.feature-box {
    background: rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08);
    border-radius: 16px; padding: 22px; text-align:left;
}
.feature-box .ico { font-size:28px; }
.feature-box h4 { color:#fff; font-size:16px; margin:8px 0 6px; }
.feature-box p { color:#9AA7B5; font-size:13px; margin:0; }

.login-card {
    max-width: 640px; margin: 60px auto; background: rgba(255,255,255,0.05);
    border:1px solid rgba(255,255,255,0.08); border-radius:20px; padding:48px;
    box-shadow: 0 8px 40px rgba(0,0,0,0.35);
}
.login-card h2 { color:#fff; margin-bottom:6px; font-size:28px; }
.login-card .sub { color:#8A97A6; font-size:14px; margin-bottom:24px; }

.stTextInput input, .stNumberInput input, .stTextArea textarea {
    background: #fff !important; color: #111 !important;
    border: 1px solid rgba(255,255,255,0.15) !important; border-radius:10px !important;
    font-size: 15px !important; padding: 10px 12px !important;
}
.stTextInput input::placeholder, .stTextArea textarea::placeholder { color:#9aa0a6 !important; opacity:1 !important; }
.stSelectbox div[data-baseweb="select"] > div { background:#fff !important; color:#111 !important; border-radius:10px !important; }
label { color:#DCE4EC !important; font-size:14px !important; font-weight:600 !important; }
</style>
""", unsafe_allow_html=True)


# ==================================================
# HELPERS
# ==================================================
def clean_response(text: str) -> str:

    if not text:
        return text

    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)

    # remove blocos latex
    text = text.replace("\\text", "")
    text = text.replace("\\frac", "dividido por")
    text = text.replace("\\approx", "aproximadamente")
    text = text.replace("\\times", "x")

    text = re.sub(r'\\[a-zA-Z]+', '', text)

    return text.strip()


def build_system_context(profile: dict) -> str:
    return (
        f"Usuário: {profile['name']} | Persona: {profile['persona']} | "
        f"Carro: {profile['car_model']} | Bateria: {profile['battery_kwh']} kWh | "
        f"Carregador preferido: {profile['charger_kw']} kW | "
        f"Bloco/Apto: {profile['block']}/{profile['apartment']}. "
        f"Use esses dados para calcular tempo de carga, % de bateria e estimativas sem perguntar ao usuário."
    )


def generate_chat_title(first_message: str) -> str:
    title = first_message.strip().split("\n")[0]
    title = re.sub(r'\s+', ' ', title)
    return title[:40] + ("..." if len(title) > 40 else "")


def make_chat_service(
    system_context: str,
    profile_context: str
):

    return ChatService(
        system_context=system_context,
        user_context=profile_context
    )


def new_chat_id():
    return str(uuid.uuid4())[:8]


# ==================================================
# SESSION STATE INIT
# ==================================================
defaults = {
    "stage": "login",
    "profile": {},
    "chats": {},
    "active_chat": None,

    # banco
    "db_user_id": None,
    "db_chat_id": None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ==================================================
# STAGE: LOGIN
# ==================================================
if st.session_state.stage == "login":
    st.markdown(f"<div class='login-card'><img src='data:image/png;base64,{LOGO_B64}' style='width:180px;display:block;margin:0 auto 20px;'>", unsafe_allow_html=True)
    st.markdown("<h2>⚡ GoodWe ChargeOps</h2>", unsafe_allow_html=True)
    st.markdown("<div class='sub'>Acesse sua conta para continuar</div>", unsafe_allow_html=True)

    name = st.text_input("Nome", placeholder="Digite seu nome")
    pwd = st.text_input("Senha", type="password", placeholder="Digite sua senha")

    if st.button("Entrar", use_container_width=True):
        if name and pwd:
            st.session_state.profile["name"] = name
            st.session_state.stage = "register"
            st.rerun()
        else:
            st.warning("Preencha nome e senha.")
    st.markdown("</div>", unsafe_allow_html=True)


# ==================================================
# STAGE: CADASTRO
# ==================================================
elif st.session_state.stage == "register":
    st.markdown(f"<div class='login-card'><img src='data:image/png;base64,{LOGO_B64}' style='width:180px;display:block;margin:0 auto 20px;'>", unsafe_allow_html=True)
    st.markdown(f"<h2>Olá, {st.session_state.profile['name']} 👋</h2>", unsafe_allow_html=True)
    st.markdown("<div class='sub'>Complete seu cadastro para personalizarmos sua experiência</div>", unsafe_allow_html=True)

    car_model = st.text_input("Modelo do carro", placeholder="ex: BYD Dolphin")
    col1, col2 = st.columns(2)
    with col1:
        battery_kwh = st.number_input("Capacidade da bateria (kWh)", min_value=5.0, max_value=200.0, value=45.0, step=1.0, format="%.1f")
    with col2:
        charger_kw = st.number_input("Carregador preferido (kW)", min_value=1.0, max_value=350.0, value=7.0, step=0.5, format="%.1f")
    col3, col4 = st.columns(2)
    with col3:
        block = st.text_input("Bloco", placeholder="ex: A")
    with col4:
        apartment = st.text_input("Apartamento", placeholder="ex: 101")
    persona = st.selectbox("Você é:", ["Morador", "Operador", "Síndico", "Visitante"])

    if st.button("Concluir cadastro", use_container_width=True):
        if car_model and block and apartment:
            st.session_state.profile.update({
                "car_model": car_model,
                "battery_kwh": battery_kwh,
                "charger_kw": charger_kw,
                "block": block,
                "apartment": apartment,
                "persona": persona,
            })

            persistence = ChatPersistenceService()
            user_id = persistence.create_user_if_not_exists(
                st.session_state.profile
            )

            st.session_state.db_user_id = user_id
            st.session_state.stage = "welcome"
            st.rerun()
        else:
            st.warning("Preencha todos os campos.")
    st.markdown("</div>", unsafe_allow_html=True)


# ==================================================
# STAGE: WELCOME
# ==================================================
elif st.session_state.stage == "welcome":
    p = st.session_state.profile
    st.markdown(f"""
    <div class="welcome-card">
        <h1>Bem-vindo, <span class="accent">{p['name']}</span> ⚡</h1>
        <p style="color:#C2CCD8; max-width:560px; margin:10px auto;">
        Sou o <b>GoodWe ChargeOps AI</b>, seu assistente inteligente para carregamento de veículos
        elétricos em condomínios. Conectado ao seu perfil de <b>{p['persona']}</b>,
        consigo calcular tempos de carga, sugerir horários ideais e explicar o funcionamento
        dos carregadores — tudo sem que você precise repetir seus dados.
        </p>
        <div class="feature-grid">
            <div class="feature-box"><div class="ico">🔋</div><h4>Cálculo de carga</h4><p>Tempo estimado para atingir a % de bateria desejada, com seu carro e carregador.</p></div>
            <div class="feature-box"><div class="ico">🚗</div><h4>ChargeOps</h4><p>Gestão de filas, status e disponibilidade dos pontos de carga.</p></div>
            <div class="feature-box"><div class="ico">🏢</div><h4>Condomínios</h4><p>Regras de uso, alocação de vagas e relatórios de consumo.</p></div>
            <div class="feature-box"><div class="ico">📡</div><h4>Modbus & OCPP</h4><p>Dúvidas técnicas sobre protocolos e integração dos carregadores.</p></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.write("")
    if st.button("Começar a conversar →", use_container_width=True):
        st.session_state.stage = "chat"
        st.rerun()


# ==================================================
# STAGE: CHAT
# ==================================================
else:
    profile = st.session_state.profile

    system_context = build_system_context(
        profile
    )

    profile_context = (
        UserProfileMemory(profile)
        .build_context()
    )

    # Sidebar
    with st.sidebar:
        st.markdown("""
        <div class="sb-brand">
            <div class="logo">⚡</div>
            <div>
                <div class="name">GoodWe ChargeOps</div>
                <div class="sub">ChargeOps AI Assistant</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("+ Novo bate-papo", use_container_width=True):
            cid = new_chat_id()

            persistence = ChatPersistenceService()

            db_chat_id = persistence.create_chat(
                st.session_state.db_user_id,
                "Nova Conversa"
            )

            st.session_state.db_chat_id = db_chat_id
            st.session_state.chats[cid] = {
                "title": None,
                "messages": [],
                "db_chat_id": db_chat_id,
                "service": make_chat_service(
                    system_context,
                    profile_context
                ),
            }
            st.session_state.active_chat = cid
            st.rerun()

        st.markdown("<div class='sb-section-label'>Conversas</div>", unsafe_allow_html=True)

        # Apenas chats com >=1 mensagem aparecem na lista
        for cid, chat in st.session_state.chats.items():
            if chat["title"] is None:
                continue
            active_cls = "chat-history-active" if cid == st.session_state.active_chat else ""
            if st.button(chat["title"], key=f"hist_{cid}", use_container_width=True):
                st.session_state.active_chat = cid
                st.rerun()

        st.markdown("<div style='flex:1'></div>", unsafe_allow_html=True)
        st.markdown(f"""
        <div class="sb-profile">
            <div class="avatar">{profile['name'][:1].upper()}</div>
            <div class="meta">
                <div class="nm">{profile['name']}</div>
                <div class="role">{profile['persona']} · Bloco {profile['block']}/{profile['apartment']}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Header
    st.markdown("""
    <div class="gw-header">
        <div class="gw-title"><span class="bolt">⚡</span> GoodWe ChargeOps AI Assistant</div>
        <div class="gw-subtitle">EV ChargeOps • Condomínios • Eletromobilidade • Smart Energy</div>
    </div>
    """, unsafe_allow_html=True)

    # Garante chat ativo
    if st.session_state.active_chat is None or st.session_state.active_chat not in st.session_state.chats:
        cid = new_chat_id()
        persistence = ChatPersistenceService()
        db_chat_id = persistence.create_chat(
            st.session_state.db_user_id,
            "Nova Conversa"
        )

        st.session_state.db_chat_id = db_chat_id
        
        st.session_state.chats[cid] = {
            "title": None,
            "messages": [],
            "db_chat_id": db_chat_id,
            "service": make_chat_service(
                system_context,
                profile_context,
            ),
        }
        st.session_state.active_chat = cid

    chat = st.session_state.chats[
        st.session_state.active_chat
    ]

    db_chat_id = chat["db_chat_id"]

    # Histórico
    for message in chat["messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Input
    user_input = st.chat_input("Pergunte algo sobre carregamento, potência, filas ou carregadores...")

    if user_input:

        persistence = ChatPersistenceService()

        # salva usuário no banco
        persistence.save_user_message(
            db_chat_id,
            user_input
        )

        chat["messages"].append(
            {
                "role": "user",
                "content": user_input
            }
        )

        with st.chat_message("user"):
            st.markdown(user_input)

        if chat["title"] is None:
            chat["title"] = generate_chat_title(user_input)

        with st.chat_message("assistant"):

            with st.spinner(
                "Consultando ChargeOps AI..."
            ):
                
                raw = chat["service"].send_message(
                    user_input
                )

                response = clean_response(
                    raw
                )

                st.markdown(response)

        # salva resposta IA no banco
        persistence.save_assistant_message(
            db_chat_id,
            response
        )

        chat["messages"].append(
            {
                "role": "assistant",
                "content": response
            }
        )

        st.rerun()