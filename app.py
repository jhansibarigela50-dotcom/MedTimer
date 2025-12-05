
import streamlit as st
import pandas as pd
from datetime import datetime, date, time, timedelta
import io
import random
import math
import os

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

import wave
import struct

st.set_page_config(page_title="MedTimer – Daily Medicine Companion", page_icon="🕒", layout="wide")

# -------------------------
# Session state
# -------------------------
DEFAULT_TIPS = [
    "Small steps matter—one dose at a time.",
    "Keep water nearby to make taking medicines easier.",
    "Set gentle reminders that suit your routine.",
    "Celebrate streaks—consistency builds health!",
    "Place your medicine box where you can easily see it.",
]

if 'schedule' not in st.session_state:
    st.session_state.schedule = []  # List[Dict]: {id, name, time_str}
if 'logs' not in st.session_state:
    st.session_state.logs = []      # List[Dict]: {id, name, date_str, scheduled_time, status, taken_at?}
if 'next_id' not in st.session_state:
    st.session_state.next_id = 1

UPCOMING_WINDOW_MIN = 60
BEEP_WINDOW_MIN = 5

# -------------------------
# Turtle availability check
# -------------------------
def can_use_turtle() -> bool:
    """Return True only if turtle can draw (non-headless environment)."""
    if not HAS_TURTLE:
        return False
    # On most cloud deployments, DISPLAY is unset -> headless
    if os.environ.get('DISPLAY') is None:
        return False
    return True

# -------------------------
# Domain logic
# -------------------------
def add_medicine(name: str, sched_time: time):
    mid = st.session_state.next_id
    st.session_state.next_id += 1
    tstr = sched_time.strftime('%H:%M')
    st.session_state.schedule.append({'id': mid, 'name': name.strip(), 'time_str': tstr})
    ensure_today_logs()

def delete_medicine(mid: int):
    st.session_state.schedule = [m for m in st.session_state.schedule if m['id'] != mid]
    today_str = date.today().isoformat()
    # remove today's log for that medicine (keep historical ones intact)
    st.session_state.logs = [lg for lg in st.session_state.logs if not (lg['id'] == mid and lg['date_str'] == today_str)]

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

# -------------------------
# Alerts & Audio
# -------------------------
def doses_due_soon(now: datetime):
    due = []
    for m in st.session_state.schedule:
        today_str = date.today().isoformat()
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

# -------------------------
# Rewards (Turtle kept; Emoji default)
# -------------------------
def draw_reward_image(kind: str = 'smiley', prefer_turtle: bool = False) -> Image.Image:
    """Turtle/PIL drawing kept in code; used only when explicitly enabled locally."""
    if prefer_turtle and can_use_turtle():
        try:
            screen = turtle.Screen()
            screen.setup(width=300, height=300)
            t = turtle.Turtle()
            t.hideturtle()
            t.speed(0)
            t.width(4)
            if kind == 'smiley':
                t.penup(); t.goto(0, -80); t.pendown(); t.color('gold'); t.begin_fill(); t.circle(100); t.end_fill()
                t.penup(); t.color('black'); t.goto(-40, 30); t.pendown(); t.begin_fill(); t.circle(10); t.end_fill()
                t.penup(); t.goto(40, 30); t.pendown(); t.begin_fill(); t.circle(10); t.end_fill()
                t.penup(); t.goto(-50, -10); t.pendown(); t.setheading(-60)
                for _ in range(60):
                    t.forward(2); t.left(2)
            else:
                t.penup(); t.goto(-50, -50); t.pendown(); t.color('gold'); t.begin_fill()
                for _ in range(2):
