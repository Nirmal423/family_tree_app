import streamlit as st
import sqlite3
from PIL import Image
import os
from datetime import datetime

DB_PATH = "family_tree.db"
PHOTO_DIR = "photos"
os.makedirs(PHOTO_DIR, exist_ok=True)

st.set_page_config(page_title="Family Tree", layout="wide")

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

init_db()

# ---------- SESSION STATE ----------
if "page" not in st.session_state:
    st.session_state.page = "grid"
if "selected_person" not in st.session_state:
    st.session_state.selected_person = None

def go_to_profile(person_id):
    st.session_state.selected_person = person_id
    st.session_state.page = "profile"

# ---------- SIDEBAR ----------
st.sidebar.title("🌳 Family Tree")
if st.sidebar.button("All Family Members"):
    st.session_state.page = "grid"
if st.sidebar.button("Add Person"):
    st.session_state.page = "add"

search_term = st.sidebar.text_input("Search by name")
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
                    img.thumbnail((800, 800))  # keep storage light
                    img.save(photo_path)
                new_id = add_person(
                    first_name, last_name,
                    str(birth_date) if birth_date else None,
                    location, bio, interests, photo_path
                )
                st.success(f"{first_name} added!")
                go_to_profile(new_id)
                st.rerun()

# ---------- GRID PAGE ----------
elif st.session_state.page == "grid":
    st.header("Family Members")
    people = get_all_persons(search_term if search_term else None)

    if not people:
        st.info("No family members yet. Click 'Add Person' to start building the tree.")
    else:
        cols = st.columns(4)
        for i, (pid, first, last, photo_path) in enumerate(people):
            with cols[i % 4]:
                if photo_path and os.path.exists(photo_path):
                    st.image(photo_path, use_container_width=True)
                else:
                    st.markdown("📷 *No photo*")
                st.markdown(f"**{first} {last or ''}**")
                if st.button("View Profile", key=f"btn_{pid}"):
                    go_to_profile(pid)
                    st.rerun()

# ---------- PROFILE PAGE ----------
elif st.session_state.page == "profile":
    person = get_person(st.session_state.selected_person)
    if person:
        pid, first, last, birth_date, location, bio, interests, photo_path, created_at = person
        st.header(f"{first} {last or ''}")
        col1, col2 = st.columns([1, 2])
        with col1:
            if photo_path and os.path.exists(photo_path):
                st.image(photo_path, use_container_width=True)
        with col2:
            if birth_date:
                st.write(f"**Born:** {birth_date}")
            if location:
                st.write(f"**Lives in:** {location}")
            if interests:
                st.write(f"**Interests:** {interests}")
            if bio:
                st.write("**About:**")
                st.write(bio)

        st.divider()
        st.subheader("Connect a Relative")
        other_people = [p for p in get_all_persons() if p[0] != pid]
        if other_people:
            options = {f"{f} {l or ''}": pid2 for pid2, f, l, _ in other_people}
            selected_name = st.selectbox("Select relative", list(options.keys()))
            rel_type = st.selectbox("Relationship", ["parent-of", "child-of", "spouse-of", "sibling-of"])
            if st.button("Add Relationship"):
                add_relationship(pid, options[selected_name], rel_type)
                st.success("Relationship added")
                st.rerun()

        st.divider()
        st.subheader("Relationships")
        rels = get_relationships(pid)
        if rels:
            for rel_type, other_id, other_first, other_last in rels:
                st.write(f"- **{rel_type}** {other_first} {other_last or ''}")
        else:
            st.write("No relationships added yet.")