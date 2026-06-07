"""
app.py  – FitBot Streamlit UI
Run:  streamlit run app.py
"""
from __future__ import annotations

import os
import sys
from datetime import date

import streamlit as st
from dotenv import load_dotenv

# ── load .env ──────────────────────────────────────────────────────────────
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import database as db

# ── page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FitBot – AI Fitness Coach",
    page_icon="🏋️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── global CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@300;400;500;600&display=swap');

/* ── base ── */
html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

/* ── dark background ── */
.stApp {
    background: #0d0f14;
    color: #e8eaf0;
}

/* ── sidebar ── */
[data-testid="stSidebar"] {
    background: #13151c !important;
    border-right: 1px solid #1e2130;
}
[data-testid="stSidebar"] * { color: #c8cad4 !important; }

/* ── headings ── */
h1, h2, h3 {
    font-family: 'Bebas Neue', sans-serif;
    letter-spacing: 2px;
    color: #e8eaf0 !important;
}

/* ── metric cards ── */
[data-testid="metric-container"] {
    background: #181b24;
    border: 1px solid #252836;
    border-radius: 12px;
    padding: 16px !important;
}

/* ── buttons ── */
.stButton > button {
    background: linear-gradient(135deg, #00e5a0, #00b8d4) !important;
    color: #0d0f14 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 10px 28px !important;
    font-size: 15px !important;
    transition: opacity 0.2s;
}
.stButton > button:hover { opacity: 0.85 !important; }

/* secondary button */
.stButton.secondary > button {
    background: #1e2130 !important;
    color: #e8eaf0 !important;
    border: 1px solid #2e3245 !important;
}

/* ── inputs ── */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stSelectbox > div > div {
    background: #181b24 !important;
    border: 1px solid #252836 !important;
    border-radius: 8px !important;
    color: #e8eaf0 !important;
}

/* ── chat bubbles ── */
.chat-user {
    background: linear-gradient(135deg, #00e5a022, #00b8d422);
    border: 1px solid #00e5a044;
    border-radius: 18px 18px 4px 18px;
    padding: 12px 18px;
    margin: 8px 0 8px 15%;
    color: #e8eaf0;
    font-size: 15px;
    line-height: 1.6;
}
.chat-bot {
    background: #181b24;
    border: 1px solid #252836;
    border-radius: 18px 18px 18px 4px;
    padding: 14px 18px;
    margin: 8px 15% 8px 0;
    color: #c8cad4;
    font-size: 15px;
    line-height: 1.6;
}
.chat-label-user { text-align:right; font-size:11px; color:#00e5a0; margin-bottom:2px; font-weight:600; letter-spacing:1px; }
.chat-label-bot  { font-size:11px; color:#00b8d4; margin-bottom:2px; font-weight:600; letter-spacing:1px; }

/* ── calorie bar container ── */
.cal-bar-wrap {
    background: #181b24;
    border: 1px solid #252836;
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 16px;
}
.cal-bar-track {
    background: #252836;
    border-radius: 99px;
    height: 10px;
    overflow: hidden;
    margin-top: 8px;
}
.cal-bar-fill {
    height: 10px;
    border-radius: 99px;
    transition: width 0.5s;
}

/* ── plan table ── */
.plan-table { width:100%; border-collapse: collapse; font-size:14px; }
.plan-table th {
    background: #1a1d28;
    color: #00e5a0;
    font-family: 'Bebas Neue', sans-serif;
    letter-spacing: 1px;
    padding: 10px 14px;
    text-align: left;
    border-bottom: 2px solid #252836;
}
.plan-table td {
    padding: 9px 14px;
    border-bottom: 1px solid #1e2130;
    vertical-align: top;
    color: #c8cad4;
}
.plan-table tr:hover td { background: #181b24; }

/* ── section header ── */
.section-header {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 22px;
    letter-spacing: 3px;
    color: #00e5a0;
    border-bottom: 2px solid #00e5a033;
    padding-bottom: 6px;
    margin: 24px 0 16px;
}

/* ── login card ── */
.login-card {
    background: #13151c;
    border: 1px solid #1e2130;
    border-radius: 20px;
    padding: 40px;
    max-width: 420px;
    margin: 0 auto;
}

/* ── hero ── */
.hero {
    text-align: center;
    padding: 40px 0 20px;
}
.hero h1 {
    font-size: 72px !important;
    background: linear-gradient(135deg, #00e5a0, #00b8d4);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 0 !important;
}
.hero p { color: #6b7280; font-size: 17px; margin-top: 6px; }

/* ── tab fix ── */
.stTabs [data-baseweb="tab"] {
    font-family: 'Bebas Neue', sans-serif;
    letter-spacing: 1.5px;
    font-size: 16px;
    color: #6b7280;
}
.stTabs [aria-selected="true"] { color: #00e5a0 !important; }
.stTabs [data-baseweb="tab-highlight"] { background: #00e5a0 !important; }

/* ── dataframe ── */
[data-testid="stDataFrame"] { background: #181b24 !important; }

/* hide streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── init DB & session ──────────────────────────────────────────────────────
db.init_db()

def _ss(key, default=None):
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]

_ss("page", "login")        # login | onboard | app
_ss("user", None)
_ss("chat_messages", [])    # list of {role, content}
_ss("login_tab", "login")   # login | signup


# ══════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════

def check_api_key():
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        st.error("❌ **GROQ_API_KEY not set.** Create a `.env` file with your key.")
        st.stop()
    if not os.environ.get("YOUTUBE_API_KEY"):
        st.warning("⚠️ **YOUTUBE_API_KEY not set.** Video search won't work. Add it to your `.env` file.")


def calorie_bar_html(consumed: float, target: float) -> str:
    pct = min(consumed / target, 1.0) if target else 0
    remaining = max(target - consumed, 0)
    color = "#00e5a0" if pct < 0.8 else ("#f59e0b" if pct < 1.0 else "#ef4444")
    return f"""
    <div class="cal-bar-wrap">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <span style="font-family:'Bebas Neue',sans-serif;letter-spacing:2px;font-size:17px;color:#e8eaf0">
          TODAY'S CALORIES
        </span>
        <span style="font-size:13px;color:#6b7280">{remaining:.0f} kcal remaining</span>
      </div>
      <div class="cal-bar-track">
        <div class="cal-bar-fill" style="width:{pct*100:.1f}%;background:{color}"></div>
      </div>
      <div style="display:flex;justify-content:space-between;margin-top:6px;font-size:13px">
        <span style="color:{color};font-weight:600">{consumed:.0f} eaten</span>
        <span style="color:#6b7280">target {target:.0f} kcal</span>
      </div>
    </div>"""


def nutrition_table_html(plan: dict) -> str:
    days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    week = plan.get("week", {})
    rows = ""
    for d in days:
        m = week.get(d, {})
        rows += f"""<tr>
          <td><b style="color:#e8eaf0">{d}</b></td>
          <td>{m.get('breakfast','–')}</td>
          <td>{m.get('lunch','–')}</td>
          <td>{m.get('dinner','–')}</td>
          <td style="color:#6b7280">{m.get('snacks','–')}</td>
        </tr>"""
    return f"""
    <table class="plan-table">
      <thead><tr>
        <th>Day</th><th>Breakfast</th><th>Lunch</th><th>Dinner</th><th>Snacks</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>"""


def exercise_table_html(plan: dict) -> str:
    days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    week = plan.get("week", {})
    rows = ""
    for d in days:
        dp = week.get(d, {})
        wtype = dp.get("type", "Rest")
        exs = dp.get("exercises", [])
        if exs:
            ex_str = "<br>".join(
                f"• {e.get('name','?')}  {e.get('sets','?')}×{e.get('reps','?')}  rest {e.get('rest_sec','?')}s"
                for e in exs
            )
        else:
            ex_str = f"<span style='color:#6b7280'>{wtype}</span>"
        rows += f"""<tr>
          <td><b style="color:#e8eaf0">{d}</b></td>
          <td style="color:#00b8d4">{wtype}</td>
          <td style="font-size:13px">{ex_str}</td>
        </tr>"""
    return f"""
    <table class="plan-table">
      <thead><tr><th>Day</th><th>Type</th><th>Exercises</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>"""


# ══════════════════════════════════════════════════════════════════════════
#  PAGE: LOGIN / SIGNUP
# ══════════════════════════════════════════════════════════════════════════

def page_login():
    check_api_key()

    st.markdown("""
    <div class="hero">
      <h1>FITBOT</h1>
      <p>Your AI-powered personal fitness & nutrition coach</p>
    </div>""", unsafe_allow_html=True)

    col = st.columns([1, 1.4, 1])[1]
    with col:
        tab_login, tab_signup = st.tabs(["LOGIN", "CREATE ACCOUNT"])

        # ── Login tab
        with tab_login:
            st.markdown("<br>", unsafe_allow_html=True)
            username = st.text_input("Username", key="li_user", placeholder="your username")
            password = st.text_input("Password", type="password", key="li_pass", placeholder="••••••••")
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Sign In →", key="btn_login", use_container_width=True):
                if not username or not password:
                    st.error("Please fill in all fields.")
                else:
                    user = db.verify_user(username, password)
                    if user:
                        st.session_state.user = user
                        st.session_state.chat_messages = db.get_chat_history(user["id"], 50)
                        st.session_state.page = "onboard" if not user.get("name") else "app"
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")

        # ── Signup tab
        with tab_signup:
            st.markdown("<br>", unsafe_allow_html=True)
            new_user = st.text_input("Choose a username", key="su_user", placeholder="fitnessfan42")
            new_pass = st.text_input("Password", type="password", key="su_pass", placeholder="••••••••")
            new_conf = st.text_input("Confirm password", type="password", key="su_conf", placeholder="••••••••")
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Create Account →", key="btn_signup", use_container_width=True):
                if not new_user or not new_pass or not new_conf:
                    st.error("Please fill in all fields.")
                elif new_pass != new_conf:
                    st.error("Passwords do not match.")
                elif db.get_user(new_user):
                    st.error("Username already taken.")
                else:
                    db.create_user(new_user, new_pass)
                    user = db.get_user(new_user)
                    st.session_state.user = user
                    st.session_state.chat_messages = []
                    st.session_state.page = "onboard"
                    st.rerun()


# ══════════════════════════════════════════════════════════════════════════
#  PAGE: ONBOARDING
# ══════════════════════════════════════════════════════════════════════════

def page_onboard():
    check_api_key()
    user = st.session_state.user

    st.markdown("""
    <div class="hero" style="padding:20px 0 10px">
      <h1 style="font-size:48px!important">LET'S GET STARTED</h1>
      <p>Tell us about yourself so we can build your personalised plan</p>
    </div>""", unsafe_allow_html=True)

    col = st.columns([1, 2, 1])[1]
    with col:
        st.markdown("<br>", unsafe_allow_html=True)

        name   = st.text_input("Full name", placeholder="John Smith")
        c1, c2 = st.columns(2)
        age    = c1.number_input("Age", min_value=13, max_value=100, value=25)
        sex    = c2.selectbox("Sex", ["Male", "Female"])
        weight = c1.number_input("Weight (kg)", min_value=30.0, max_value=300.0, value=75.0, step=0.5)
        height = c2.number_input("Height (cm)", min_value=100.0, max_value=250.0, value=175.0, step=0.5)

        goal = st.selectbox("Your goal", [
            "fat_loss — Lose fat (-500 kcal/day)",
            "muscle_gain — Build muscle (+300 kcal/day)",
            "maintain — Maintain weight",
        ])
        goal_key = goal.split(" — ")[0]

        activity = st.selectbox("Activity level", [
            "sedentary — Little or no exercise",
            "light — Light exercise 1-3 days/week",
            "moderate — Moderate exercise 3-5 days/week",
            "active — Hard exercise 6-7 days/week",
        ])
        activity_key = activity.split(" — ")[0]

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Generate My Plans 🚀", use_container_width=True):
            if not name:
                st.error("Please enter your name.")
            else:
                profile = {
                    **user,
                    "name": name,
                    "age": int(age),
                    "weight_kg": float(weight),
                    "height_cm": float(height),
                    "goal": goal_key,
                    "sex": sex.lower(),
                    "activity_level": activity_key,
                }
                with st.spinner("🤖 AI is building your personalised nutrition & workout plans… (30–60s)"):
                    from agents import generate_plans_for_user
                    nutrition_plan, exercise_plan, tdee = generate_plans_for_user(profile)

                db.update_user_profile(
                    user["id"], name, int(age), float(weight),
                    float(height), goal_key, tdee, activity_key
                )
                db.save_plan(user["id"], nutrition_plan, exercise_plan)

                st.session_state.user = db.get_user(user["username"])
                st.session_state.page = "app"
                st.success(f"✅ Plans ready! Your daily target: **{tdee:.0f} kcal**")
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════
#  PAGE: MAIN APP
# ══════════════════════════════════════════════════════════════════════════

def page_app():
    check_api_key()
    user = st.session_state.user

    # ── Sidebar ────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(f"""
        <div style="padding:8px 0 24px">
          <div style="font-family:'Bebas Neue',sans-serif;font-size:28px;
               background:linear-gradient(135deg,#00e5a0,#00b8d4);
               -webkit-background-clip:text;-webkit-text-fill-color:transparent;
               background-clip:text;letter-spacing:3px">FITBOT</div>
          <div style="font-size:13px;color:#6b7280;margin-top:2px">AI Fitness Coach</div>
        </div>

        <div style="background:#1a1d28;border-radius:12px;padding:14px 16px;margin-bottom:20px">
          <div style="font-size:13px;color:#6b7280">Logged in as</div>
          <div style="font-size:16px;font-weight:600;color:#e8eaf0;margin-top:2px">{user['name']}</div>
          <div style="font-size:12px;color:#00e5a0;margin-top:4px">
            {user['goal'].replace('_',' ').title()} · {user['tdee']:.0f} kcal/day
          </div>
        </div>
        """, unsafe_allow_html=True)

        # Nav
        pages = {
            "💬  Chat": "chat",
            "📋  My Plans": "plans",
            "📊  Today's Log": "log",
        }
        if "nav" not in st.session_state:
            st.session_state.nav = "chat"
        for label, key in pages.items():
            active = st.session_state.nav == key
            if st.button(label, key=f"nav_{key}",
                         use_container_width=True):
                st.session_state.nav = key
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚪  Logout", use_container_width=True):
            for k in ["user","page","chat_messages","nav"]:
                st.session_state.pop(k, None)
            st.rerun()

    # ── Route to sub-page ──────────────────────────────────────────────────
    nav = st.session_state.get("nav", "chat")
    if nav == "chat":
        subpage_chat(user)
    elif nav == "plans":
        subpage_plans(user)
    elif nav == "log":
        subpage_log(user)


# ── Sub-page: Chat ─────────────────────────────────────────────────────────

def subpage_chat(user: dict):
    from agents import chat as agent_chat

    st.markdown('<div class="section-header">CHAT WITH FITBOT</div>', unsafe_allow_html=True)

    # Calorie bar
    consumed = db.get_today_calories(user["id"])
    target   = user.get("tdee") or 2000
    st.markdown(calorie_bar_html(consumed, target), unsafe_allow_html=True)

    # Chat history display
    chat_container = st.container()
    with chat_container:
        msgs = st.session_state.chat_messages
        if not msgs:
            st.markdown(f"""
            <div class="chat-bot">
              <b>Hey {user['name']}! 👋</b><br>
              I'm FitBot, your AI fitness coach. You can:<br>
              • Tell me what you ate — I'll track the calories automatically<br>
              • Ask me anything about fitness, workouts, or nutrition<br>
              • Type <b>/today</b> to see your food log<br><br>
              What's on your mind?
            </div>""", unsafe_allow_html=True)
        else:
            for m in msgs:
                if m["role"] == "user":
                    st.markdown(f'<div class="chat-label-user">YOU</div><div class="chat-user">{m["content"]}</div>', unsafe_allow_html=True)
                else:
                    content = m["content"]
                    # Check if this is a YouTube result message
                    if content.startswith("YOUTUBE_RESULTS:"):
                        try:
                            import json
                            videos = json.loads(content[len("YOUTUBE_RESULTS:"):])
                            st.markdown('<div class="chat-label-bot">🤖 FITBOT</div>', unsafe_allow_html=True)
                            st.markdown('<div class="chat-bot">Here are some tutorial videos for you! 🎬</div>', unsafe_allow_html=True)
                            for v in videos:
                                vid_id = v["video_id"]
                                title  = v["title"]
                                link   = v["url"]
                                st.markdown(f'<div style="margin:8px 0 4px;color:#00e5a0;font-weight:600">▶ <a href="{link}" target="_blank" style="color:#00e5a0">{title}</a></div>', unsafe_allow_html=True)
                                st.video(f"https://www.youtube.com/watch?v={vid_id}")
                        except Exception:
                            st.markdown(f'<div class="chat-label-bot">🤖 FITBOT</div><div class="chat-bot">{content}</div>', unsafe_allow_html=True)
                    else:
                        content_html = content.replace("\n", "<br>")
                        st.markdown(f'<div class="chat-label-bot">🤖 FITBOT</div><div class="chat-bot">{content_html}</div>', unsafe_allow_html=True)

    # Input
    st.markdown("<br>", unsafe_allow_html=True)
    with st.form("chat_form", clear_on_submit=True):
        c1, c2 = st.columns([5, 1])
        user_input = c1.text_input(
            "Message", label_visibility="collapsed",
            placeholder="Ask me anything or tell me what you ate…"
        )
        send = c2.form_submit_button("Send →", use_container_width=True)

    if send and user_input.strip():
        msg = user_input.strip()
        # Handle /today command
        if msg.lower() == "/today":
            logs = db.get_today_logs(user["id"])
            if logs:
                lines = "\n".join(f"• {l['meal'].title()}: {l['description']} ({l['calories']:.0f} kcal)" for l in logs)
                reply = f"**Today's food log:**\n{lines}\n\n**Total:** {consumed:.0f} / {target:.0f} kcal"
            else:
                reply = "No food logged today yet. Tell me what you've eaten!"
            st.session_state.chat_messages.append({"role": "user", "content": msg})
            st.session_state.chat_messages.append({"role": "assistant", "content": reply})
            st.rerun()

        st.session_state.chat_messages.append({"role": "user", "content": msg})

        with st.spinner("FitBot is thinking…"):
            reply = agent_chat(user, msg)

        st.session_state.chat_messages.append({"role": "assistant", "content": reply})
        st.rerun()


# ── Sub-page: Plans ────────────────────────────────────────────────────────

def subpage_plans(user: dict):
    plan = db.get_latest_plan(user["id"])
    if not plan:
        st.warning("No plan found. Please complete onboarding.")
        return

    nutrition = plan["nutrition_plan"]
    exercise  = plan["exercise_plan"]
    m = nutrition.get("macros", {})

    # Summary metrics
    st.markdown('<div class="section-header">YOUR WEEKLY PLANS</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Daily Calories", f"{user['tdee']:.0f} kcal")
    c2.metric("Protein", f"{m.get('protein_g','?')} g")
    c3.metric("Carbs",   f"{m.get('carbs_g','?')} g")
    c4.metric("Fat",     f"{m.get('fat_g','?')} g")

    st.markdown("<br>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["🥗  NUTRITION PLAN", "🏋️  EXERCISE PLAN"])

    with tab1:
        st.markdown(nutrition_table_html(nutrition), unsafe_allow_html=True)

    with tab2:
        st.markdown(exercise_table_html(exercise), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("♻️  Regenerate Plans"):
        profile = {**user}
        with st.spinner("Regenerating your plans with AI…"):
            from agents import generate_plans_for_user
            nutrition_plan, exercise_plan, tdee = generate_plans_for_user(profile)
        db.save_plan(user["id"], nutrition_plan, exercise_plan)
        st.success("Plans regenerated!")
        st.rerun()


# ── Sub-page: Today's Log ──────────────────────────────────────────────────

def subpage_log(user: dict):
    st.markdown('<div class="section-header">TODAY\'S FOOD LOG</div>', unsafe_allow_html=True)

    consumed = db.get_today_calories(user["id"])
    target   = user.get("tdee") or 2000
    st.markdown(calorie_bar_html(consumed, target), unsafe_allow_html=True)

    logs = db.get_today_logs(user["id"])
    if not logs:
        st.info("Nothing logged today yet. Head to Chat and tell FitBot what you've eaten!")
    else:
        # Group by meal
        meals = {}
        for l in logs:
            meals.setdefault(l["meal"], []).append(l)

        for meal_name, items in meals.items():
            meal_total = sum(i["calories"] for i in items)
            st.markdown(f"""
            <div style="margin:16px 0 8px;font-family:'Bebas Neue',sans-serif;
                 letter-spacing:2px;font-size:16px;color:#00e5a0">
              {meal_name.upper()}  <span style="color:#6b7280;font-size:14px">{meal_total:.0f} kcal</span>
            </div>""", unsafe_allow_html=True)
            for item in items:
                st.markdown(f"""
                <div style="background:#181b24;border-radius:8px;padding:10px 16px;
                     margin-bottom:6px;display:flex;justify-content:space-between;
                     border:1px solid #1e2130">
                  <span style="color:#c8cad4">{item['description']}</span>
                  <span style="color:#00b8d4;font-weight:600">{item['calories']:.0f} kcal</span>
                </div>""", unsafe_allow_html=True)

    # Manual add
    st.markdown('<div class="section-header" style="font-size:16px">ADD FOOD MANUALLY</div>', unsafe_allow_html=True)
    with st.form("manual_log"):
        c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
        meal_type = c1.selectbox("Meal", ["breakfast","lunch","dinner","snack"])
        desc      = c2.text_input("Food description", placeholder="e.g. 200g grilled chicken")
        cals      = c3.number_input("Calories", min_value=0, max_value=5000, value=0)
        submitted = c4.form_submit_button("Add", use_container_width=True)
        if submitted:
            if desc and cals > 0:
                db.log_food(user["id"], meal_type, desc, float(cals))
                st.success("Logged!")
                st.rerun()
            else:
                st.error("Fill in description and calories.")


# ══════════════════════════════════════════════════════════════════════════
#  ROUTER
# ══════════════════════════════════════════════════════════════════════════

def main():
    page = st.session_state.get("page", "login")
    if page == "login":
        page_login()
    elif page == "onboard":
        page_onboard()
    elif page == "app":
        page_app()


main()