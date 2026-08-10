import streamlit as st
import sqlite3
from PIL import Image
import os
import base64
from datetime import datetime
from streamlit_agraph import agraph, Node, Edge, Config

DB_PATH = "family_tree.db"
PHOTO_DIR = "photos"
os.makedirs(PHOTO_DIR, exist_ok=True)

st.set_page_config(page_title="Our Family Tree", layout="wide", page_icon="🌳")

# ---------- STYLING ----------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@400;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Quicksand', sans-serif;
    }
    .stApp {
        background: linear-gradient(135deg, #FFF8F0 0%, #FFE8D6 100%);
    }
    h1, h2, h3 {
        color: #3D3D3D !important;
        font-weight: 700 !important;
    }
    div.stButton > button {
        background-color: #E07A5F;
        color: white;
        border-radius: 12px;
        border: none;
        padding: 0.5em 1.2em;
        font-weight: 600;
        transition: 0.2s;
    }
    div.stButton > button:hover {
        background-color: #C9603F;
        transform: scale(1.03);
    }
    div[data-testid="stForm"] {
        background-color: white;
        padding: 25px;
        border-radius: 16px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.06);
    }
    .person-card {
        background-color: white;
        border-radius: 16px;
        padding: 16px;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.06);
        margin-bottom: 16px;
    }
    section[data-testid="stSidebar"] {
        background-color: #FDEEDC;
    }
</style>
""", unsafe_allow_html=True)

# ---------- DATABASE ----------

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS persons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT,
            birth_date TEXT,
            location TEXT,
            bio TEXT,
            interests TEXT,
            photo_path TEXT,
            created_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person1_id INTEGER NOT NULL,
            person2_id INTEGER NOT NULL,
            relationship_type TEXT NOT NULL,
            FOREIGN KEY (person1_id) REFERENCES persons(id),
            FOREIGN KEY (person2_id) REFERENCES persons(id)
        )
    """)
    conn.commit()
    conn.close()

def add_person(first_name, last_name, birth_date, location, bio, interests, photo_path):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO persons (first_name, last_name, birth_date, location, bio, interests, photo_path, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (first_name, last_name, birth_date, location, bio, interests, photo_path, datetime.now().isoformat()))
    conn.commit()
    person_id = c.lastrowid
    conn.close()
    return person_id

def get_all_persons(search_term=None):
    conn = get_conn()
    c = conn.cursor()
    if search_term:
        c.execute("""
            SELECT id, first_name, last_name, photo_path FROM persons
            WHERE first_name LIKE ? OR last_name LIKE ?
            ORDER BY first_name
        """, (f"%{search_term}%", f"%{search_term}%"))
    else:
        c.execute("SELECT id, first_name, last_name, photo_path FROM persons ORDER BY first_name")
    rows = c.fetchall()
    conn.close()
    return rows

def get_person(person_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM persons WHERE id = ?", (person_id,))
    row = c.fetchone()
    conn.close()
    return row

def add_relationship(person1_id, person2_id, rel_type):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO relationships (person1_id, person2_id, relationship_type)
        VALUES (?, ?, ?)
    """, (person1_id, person2_id, rel_type))
    conn.commit()
    conn.close()

def get_relationships(person_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT r.relationship_type, p.id, p.first_name, p.last_name
        FROM relationships r
        JOIN persons p ON (p.id = CASE WHEN r.person1_id = ? THEN r.person2_id ELSE r.person1_id END)
        WHERE r.person1_id = ? OR r.person2_id = ?
    """, (person_id, person_id, person_id))
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_relationships():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT person1_id, person2_id, relationship_type FROM relationships")
    rows = c.fetchall()
    conn.close()
    return rows

init_db()

# ---------- AVATAR HELPER ----------
def get_avatar_src(photo_path, first_name, last_name):
    if photo_path and os.path.exists(photo_path):
        ext = os.path.splitext(photo_path)[1].replace(".", "") or "png"
        with open(photo_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f"data:image/{ext};base64,{b64}"
    # Nice colored placeholder avatar with initials, no local file needed
    name = f"{first_name}+{last_name or ''}".strip()
    return f"https://ui-avatars.com/api/?name={name}&background=E07A5F&color=fff&size=128&font-size=0.45&bold=true"

# ---------- SESSION STATE ----------
if "page" not in st.session_state:
    st.session_state.page = "tree"
if "selected_person" not in st.session_state:
    st.session_state.selected_person = None

def go_to_profile(person_id):
    st.session_state.selected_person = int(person_id)
    st.session_state.page = "profile"

# ---------- SIDEBAR ----------
st.sidebar.title("🌳 Our Family Tree")
if st.sidebar.button("🌳 Tree View"):
    st.session_state.page = "tree"
if st.sidebar.button("🔲 Grid View"):
    st.session_state.page = "grid"
if st.sidebar.button("➕ Add Person"):
    st.session_state.page = "add"

search_term = st.sidebar.text_input("🔍 Search by name")
if search_term:
    st.session_state.page = "grid"

# ---------- ADD PERSON PAGE ----------
if st.session_state.page == "add":
    st.header("Add a Family Member")
    with st.form("add_person_form"):
        first_name = st.text_input("First Name *")
        last_name = st.text_input("Last Name")
        birth_date = st.date_input("Birth Date", value=None)
        location = st.text_input("Current Location")
        bio = st.text_area("About them (childhood, story, etc.)")
        interests = st.text_input("Interests (comma separated)")
        photo_file = st.file_uploader("Photo", type=["jpg", "jpeg", "png"])
        submitted = st.form_submit_button("Save")

        if submitted:
            if not first_name:
                st.error("First name is required")
            else:
                photo_path = None
                if photo_file:
                    photo_path = os.path.join(PHOTO_DIR, f"{datetime.now().timestamp()}_{photo_file.name}")
                    img = Image.open(photo_file)
                    img.thumbnail((800, 800))
                    img.save(photo_path)
                new_id = add_person(
                    first_name, last_name,
                    str(birth_date) if birth_date else None,
                    location, bio, interests, photo_path
                )
                st.success(f"{first_name} added! 🎉")
                go_to_profile(new_id)
                st.rerun()

# ---------- TREE PAGE ----------
elif st.session_state.page == "tree":
    st.header("🌳 Family Tree")
    st.caption("Scroll to zoom, drag to pan, click a photo to open their profile.")

    people = get_all_persons()
    rels = get_all_relationships()

    if not people:
        st.info("No family members yet. Click 'Add Person' to start building the tree.")
    else:
        nodes = []
        for pid, first, last, photo_path in people:
            nodes.append(Node(
                id=str(pid),
                label=f"{first} {last or ''}".strip(),
                size=30,
                shape="circularImage",
                image=get_avatar_src(photo_path, first, last)
            ))

        edges = []
        for p1, p2, rel_type in rels:
            if rel_type == "parent-of":
                edges.append(Edge(source=str(p1), target=str(p2), color="#E07A5F"))
            elif rel_type == "child-of":
                edges.append(Edge(source=str(p2), target=str(p1), color="#E07A5F"))
            elif rel_type == "spouse-of":
                edges.append(Edge(source=str(p1), target=str(p2), color="#81B29A", dashes=True))
            elif rel_type == "sibling-of":
                edges.append(Edge(source=str(p1),