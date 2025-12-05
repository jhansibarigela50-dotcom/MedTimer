
# MedTimer – Daily Medicine Companion
# Final build:
# - Emoji rewards by default (no warnings); Turtle code kept and only used locally if explicitly enabled
# - PDF report (optional via reportlab); automatic CSV fallback
# - Index AND ID column hidden from the visible table, while ID is kept internally for actions
# - Defensive fallbacks so the UI renders cleanly in Streamlit Cloud and locally

import streamlit as st
import pandas as pd
from datetime import datetime, date, time, timedelta
import io
import random
import math
import os
import wave
import struct

# Graphics
from PIL import Image
try:
    import turtle
    HAS_TURTLE = True
except Exception:
    HAS_TURTLE = False

# Optional PDF deps (gracefully handled)
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import cm
    HAS_REPORTLAB = True
except Exception:
    HAS_REPORTLAB = False

# ------------------------- App config -------------------------
st.set_page_config(page_title="MedTimer – Daily Medicine Companion", page_icon="🕒", layout="wide")

DEFAULT_TIPS = [
    "Small steps matter—one dose at a time.",
    "Keep water nearby to make taking medicines easier.",
    "Set gentle reminders that suit your routine.",
    "Celebrate streaks—consistency builds health!",
    "Place your medicine box where you can easily see it.",
]

# Session state init
if 'schedule' not in st.session_state:
    st.session_state.schedule = []  # List[Dict]: {id, name, time_str}
if 'logs' not in st.session_state:
    st.session_state.logs = []      # List[Dict]: {id, name, date_str, scheduled_time, status, taken_at?}
if 'next_id' not in st.session_state:
    st.session_state.next_id = 1

UPCOMING_WINDOW_MIN = 60
BEEP_WINDOW_MIN = 5

# ------------------------- Helpers -------------------------
def can_use_turtle() -> bool:
    """Return True only if turtle can draw (non-headless environment)."""
    if not HAS_TURTLE:
        return False
    return os.environ.get('DISPLAY') is not None

def add_medicine(name: str, sched_time: time):
    mid = st.session_state.next_id
    st.session_state.next_id += 1
    tstr = sched_time.strftime('%H:%M')
    st.session_state.schedule.append({'id': mid, 'name': name.strip(), 'time_str': tstr})
    ensure_today_logs()

def delete_medicine(mid: int):
    st.session_state.schedule = [m for m in st.session_state.schedule if m['id'] != mid]
    today_str = date.today().isoformat()
    # Remove only today's log for that medicine (keep historical)
    st.session_state.logs = [lg for lg in st.session_state.logs
                             if not (lg['id'] == mid and lg['date_str'] == today_str)]

def edit_medicine(mid: int, new_name: str, new_time: time):
    tstr = new_time.strftime('%H:%M')
    for m in st.session_state.schedule:
        if m['id'] == mid:
            m['name'] = new_name.strip()
            m['time_str'] = tstr
            break
    ensure_today_logs()

def ensure_today_logs():
    today_str = date.today().isoformat()
    for m in st.session_state.schedule:
        if not any((lg['id'] == m['id'] and lg['date_str'] == today_str) for lg in st.session_state.logs):
            st.session_state.logs.append({
                'id': m['id'],
                'name': m['name'],
                'date_str': today_str,
                'scheduled_time': m['time_str'],
                'status': 'upcoming',
            })

def parse_time_str(tstr: str) -> time:
    return datetime.strptime(tstr, '%H:%M').time()

def compute_status(now: datetime, sched_time: time, taken: bool) -> str:
    if taken:
        return 'taken'
    sched_dt = datetime.combine(date.today(), sched_time)
    delta = sched_dt - now
    return 'upcoming' if delta.total_seconds() > 0 else 'missed'

def mark_taken(mid: int):
    today_str = date.today().isoformat()
    now = datetime.now()
    for lg in st.session_state.logs:
        if lg['id'] == mid and lg['date_str'] == today_str:
            lg['status'] = 'taken'
            lg['taken_at'] = now.strftime('%H:%M')
            break

def weekly_adherence() -> float:
    cutoff = date.today() - timedelta(days=6)
    scheduled = 0
    taken = 0
    for lg in st.session_state.logs:
        d = datetime.fromisoformat(lg['date_str']).date()
        if d >= cutoff:
            scheduled += 1
            if lg.get('status') == 'taken':
                taken += 1
    return 0.0 if scheduled == 0 else (taken / scheduled) * 100.0

def doses_due_soon(now: datetime):
    due = []
    today_str = date.today().isoformat()
    for m in st.session_state.schedule:
        lg = next((x for x in st.session_state.logs if x['id'] == m['id'] and x['date_str'] == today_str), None)
        if lg and lg['status'] != 'taken':
            sched_dt = datetime.combine(date.today(), parse_time_str(m['time_str']))
            mins = (sched_dt - now).total_seconds() / 60.0
            if 0 <= mins <= BEEP_WINDOW_MIN:
                due.append((m['name'], int(mins)))
    return due

def generate_beep_wav(seconds: float = 0.6, freq: float = 880.0, volume: float = 0.5) -> bytes:
    rate = 44100
    n_samples = int(seconds * rate)
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        for i in range(n_samples):
            t = i / rate
            sample = volume * math.sin(2 * math.pi * freq * t)
            wf.writeframes(struct.pack('<h', int(sample * 32767)))
    return buf.getvalue()

# ------------------------- Rewards (Turtle kept; Emoji default) -------------------------
def draw_reward_image(kind: str = 'smiley', prefer_turtle: bool = False) -> Image.Image:
    """Turtle/PIL drawing kept in code; used only when explicitly enabled locally."""
    if prefer_turtle and can_use_turtle():
        try:
            screen = turtle.Screen()
            screen.setup(width=300, height=300)
            t = turtle.Turtle(); t.hideturtle(); t.speed(0); t.width(4)
            if kind == 'smiley':
                t.penup(); t.goto(0, -80); t.pendown(); t.color('gold'); t.begin_fill(); t.circle(100); t.end_fill()
                t.penup(); t.color('black'); t.goto(-40, 30); t.pendown(); t.begin_fill(); t.circle(10); t.end_fill()
                t.penup(); t.goto(40, 30); t.pendown(); t.begin_fill(); t.circle(10); t.end_fill()
                t.penup(); t.goto(-50, -10); t.pendown(); t.setheading(-60)
                for _ in range(60): t.forward(2); t.left(2)
            else:
                t.penup(); t.goto(-50, -50); t.pendown(); t.color('gold'); t.begin_fill()
                for _ in range(2): t.forward(100); t.left(90); t.forward(80); t.left(90)
                t.end_fill()
                t.penup(); t.goto(-70, 10); t.pendown(); t.circle(20)
                t.penup(); t.goto(70, 10); t.pendown(); t.circle(20)
                t.penup(); t.goto(-30, -70); t.pendown(); t.color('sienna'); t.begin_fill()
                for _ in range(2): t.forward(60); t.left(90); t.forward(20); t.left(90)
                t.end_fill()
            cv = screen.getcanvas()
            ps = cv.postscript(colormode='color')
            turtle.bye()
            img = Image.open(io.BytesIO(ps.encode('utf-8')))
            return img
        except Exception:
            pass
    # PIL fallback drawing (kept, though default display uses emoji)
    img = Image.new('RGBA', (300, 300), (255, 255, 255, 0))
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    if kind == 'smiley':
        d.ellipse([50, 50, 250, 250], fill=(255, 215, 0), outline=(240, 180, 0), width=4)
        d.ellipse([100, 120, 120, 140], fill='black')
        d.ellipse([180, 120, 200, 140], fill='black')
        d.arc([100, 150, 200, 220], start=200, end=340, fill='black', width=4)
    else:
        d.rectangle([80, 120, 220, 200], fill=(255, 215, 0), outline='gold', width=4)
        d.ellipse([60, 130, 100, 170], outline='gold', width=4)
        d.ellipse([200, 130, 240, 170], outline='gold', width=4)
        d.rectangle([130, 200, 170, 220], fill=(160, 82, 45))
    return img

def render_reward_emoji(score: float) -> None:
    """Show big emojis instead of turtle graphics by default."""
    if score >= 92:  emoji, msg = "🏆", "Fantastic adherence!"
    elif score >= 80: emoji, msg = "😊", "Great job! Keep it up."
    elif score >= 60: emoji, msg = "👍", "Nice progress—keep going!"
    else:            emoji, msg = "🌱", "Build your streak and unlock rewards."
    st.markdown("<div style='font-size:72px; line-height:1'>{}</div>".format(emoji), unsafe_allow_html=True)
    st.caption(msg)

# ------------------------- Reports -------------------------
def build_weekly_report_pdf() -> bytes:
    if not HAS_REPORTLAB:
        return None
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    c.setFont("Helvetica-Bold", 18)
    c.drawString(2*cm, h - 2*cm, "MedTimer – Weekly Adherence Report")
    c.setFont("Helvetica", 12)
    c.drawString(2*cm, h - 3*cm, "Generated: {}".format(datetime.now().strftime('%Y-%m-%d %H:%M')))
    score = weekly_adherence()
    c.drawString(2*cm, h - 4*cm, "Adherence Score (last 7 days): {:.1f}%".format(score))
    c.setFont("Helvetica-Bold", 12)
    c.drawString(2*cm, h - 5*cm, "Date")
    c.drawString(6*cm, h - 5*cm, "Medicine")
    c.drawString(12*cm, h - 5*cm, "Time")
    c.drawString(16*cm, h - 5*cm, "Status")
    c.setFont("Helvetica", 11)
    y = h - 5.7*cm
    cutoff = date.today() - timedelta(days=6)
    rows = [lg for lg in st.session_state.logs if datetime.fromisoformat(lg['date_str']).date() >= cutoff]
    rows.sort(key=lambda x: (x['date_str'], x['scheduled_time'], x['name']))
    for lg in rows:
        c.drawString(2*cm, y, lg['date_str'])
        c.drawString(6*cm, y, lg['name'])
        c.drawString(12*cm, y, lg['scheduled_time'])
        c.drawString(16*cm, y, lg['status'].title())
        y -= 0.7*cm
        if y < 2*cm:
            c.showPage(); y = h - 2*cm
    c.showPage(); c.save()
    return buf.getvalue()

def build_weekly_report_csv() -> str:
    cutoff = date.today() - timedelta(days=6)
    rows = [lg for lg in st.session_state.logs if datetime.fromisoformat(lg['date_str']).date() >= cutoff]
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=['date_str','name','scheduled_time','status','taken_at'])
    adherence = weekly_adherence()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    header = "# MedTimer Weekly Report (generated " + ts + "); Adherence: " + "{:.1f}".format(adherence) + "%\n"
    return header + df.to_csv(index=False)

# ------------------------- UI -------------------------
st.title("🕒 MedTimer – Daily Medicine Companion")

# Right panel (tips + emoji banner + optional turtle toggle)
colL, colR = st.columns([3, 2])
with colR:
    st.subheader("Tips & Motivation")
    st.write(random.choice(DEFAULT_TIPS))
    st.markdown("<div style='font-size:28px'>🏆  😊  👍  🌱</div>", unsafe_allow_html=True)
    st.write("\n")
    prefer_turtle = False
    if can_use_turtle():
        prefer_turtle = st.checkbox("Prefer Turtle rewards (advanced, local only)", value=False)

# Left panel (add medicine form)
with colL:
    st.subheader("Add a daily medicine")
    with st.form("add_form", clear_on_submit=True):
        name = st.text_input("Medicine name", placeholder="e.g., Metformin 500mg")
        sched = st.time_input("Scheduled time", value=time(9, 0))
        submitted = st.form_submit_button("Add medicine")
    if submitted and name.strip():
        add_medicine(name, sched)
        st.success("Added: {} at {}".format(name, sched.strftime('%H:%M')))

st.divider()
st.subheader("Manage medicines")
ensure_today_logs()

if st.session_state.schedule:
    df = pd.DataFrame(st.session_state.schedule)

    # Drop the ID column for display (but keep it in session_state for actions)
    df_display = df[['name', 'time_str']].rename(columns={'name': 'Medicine', 'time_str': 'Time'})

    # Hide the index safely (fallback for older Streamlit)
    try:
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    except TypeError:
        st.dataframe(df_display.style.hide_index(), use_container_width=True)

    # Per-row controls with clean labels (keys still use ID internally)
    for m in st.session_state.schedule:
        c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
        with c1:
            st.markdown("**{}** at {}".format(m['name'], m['time_str']))
        with c2:
            new_name = st.text_input("Rename", value=m['name'], key="rename_{}".format(m['id']))
        with c3:
            new_time = st.time_input("Time", value=parse_time_str(m['time_str']), key="retime_{}".format(m['id']))
        with c4:
            colA, colB = st.columns(2)
            with colA:
                if st.button("Save", key="save_{}".format(m['id'])):
                    edit_medicine(m['id'], new_name, new_time)
                    st.toast("Saved changes", icon='✅')
            with colB:
                if st.button("Delete", key="del_{}".format(m['id'])):
                    delete_medicine(m['id'])
                    st.toast("Deleted", icon='🗑️')
else:
    st.info("No medicines yet—add your first dose above.")

# ------------------------- Daily checklist -------------------------
st.divider()
st.subheader("Today's checklist")
now = datetime.now()

# Update today's log statuses
for m in st.session_state.schedule:
    today_str = date.today().isoformat()
    lg = next((x for x in st.session_state.logs if x['id'] == m['id'] and x['date_str'] == today_str), None)
    taken = (lg and lg['status'] == 'taken')
    status = compute_status(now, parse_time_str(m['time_str']), taken)
    if lg:
        lg['status'] = status

# Render checklist rows (no ID shown)
for m in st.session_state.schedule:
    today_str = date.today().isoformat()
    lg = next((x for x in st.session_state.logs if x['id'] == m['id'] and x['date_str'] == today_str), None)
    taken = (lg and lg['status'] == 'taken')
    status = lg['status'] if lg else 'upcoming'
    c1, c2, c3 = st.columns([3, 2, 2])
    with c1:
        st.markdown("**{}** at {}".format(m['name'], m['time_str']))
    with c2:
        badge_color = '#3CB371' if status == 'taken' else ('#FFC107' if status == 'upcoming' else '#E74C3C')
        st.markdown("<span style='background:{}; color:white; padding:4px 8px; border-radius:12px; font-weight:600;'>{}</span>"
                    .format(badge_color, status.title()), unsafe_allow_html=True)
    with c3:
        if not taken:
            if st.button("Mark taken", key="taken_{}".format(m['id'])):
                mark_taken(m['id'])
                st.success("Marked taken: {}".format(m['name']))
        else:
            st.button("Taken ✅", key="taken_done_{}".format(m['id']), disabled=True)

# ------------------------- Alerts -------------------------
due = doses_due_soon(now)
if len(due) > 0:
    st.warning("Upcoming dose soon: {}".format(', '.join(["{} ({} min)".format(n, mins) for n, mins in due])))
    st.audio(generate_beep_wav(), format='audio/wav')

# ------------------------- Weekly adherence + rewards -------------------------
st.divider()
st.subheader("Weekly adherence")
score = weekly_adherence()
st.progress(min(score/100.0, 1.0), text="Adherence: {:.1f}% (last 7 days)".format(score))

if can_use_turtle() and prefer_turtle:
    reward_kind = 'trophy' if score >= 92 else ('smiley' if score >= 80 else None)
    if reward_kind:
        img = draw_reward_image(reward_kind, prefer_turtle=True)
        st.image(img, caption="Reward unlocked!")
    else:
        st.caption("Build your streak to unlock turtle rewards.")
else:
    render_reward_emoji(score)

# ------------------------- Reports -------------------------
st.divider()
st.subheader("Download weekly report")
if HAS_REPORTLAB:
    pdf_bytes = build_weekly_report_pdf()
    if pdf_bytes:
        st.download_button("Download PDF", data=pdf_bytes,
                           file_name="MedTimer_Weekly_Report.pdf", mime="application/pdf")
else:
    csv_str = build_weekly_report_csv()
    st.download_button("Download CSV", data=csv_str,
                       file_name="MedTimer_Weekly_Report.csv", mime="text/csv")

# ------------------------- Testing tools -------------------------
with st.expander("Testing tools"):
    if st.button("Generate sample week data"):
        base_ids = [m['id'] for m in st.session_state.schedule]
        names_map = {m['id']: m['name'] for m in st.session_state.schedule}
        times_map = {m['id']: m['time_str'] for m in st.session_state.schedule}
        for d_off in range(1, 7):
            d = date.today() - timedelta(days=d_off)
            d_str = d.isoformat()
            for mid in base_ids:
                st.session_state.logs.append({
                    'id': mid,
                    'name': names_map[mid],
                    'date_str': d_str,
                    'scheduled_time': times_map[mid],
                    'status': 'taken' if random.random() < 0.75 else 'missed',
                    'taken_at': times_map[mid] if random.random() < 0.75 else None,
                })
        st.success("Sample week data generated.")

st.caption("Designed for clarity, comfort, and gentle motivation—MedTimer helps turn routines into healthy habits.")
