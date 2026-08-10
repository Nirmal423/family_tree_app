import streamlit as st
import streamlit.components.v1 as components
import sqlite3
import os
import base64
import json
from datetime import datetime

DB_PATH = "family_tree.db"
PHOTO_DIR = "photos"
os.makedirs(PHOTO_DIR, exist_ok=True)

st.set_page_config(page_title="Family Tree", layout="wide", page_icon="🌳", initial_sidebar_state="collapsed")

# =========================================================
# DATA LAYER
# =========================================================

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

def update_person(person_id, first_name, last_name, birth_date, location, bio, interests, photo_path):
    conn = get_conn()
    c = conn.cursor()
    if photo_path:
        c.execute("""
            UPDATE persons SET first_name=?, last_name=?, birth_date=?, location=?, bio=?, interests=?, photo_path=?
            WHERE id=?
        """, (first_name, last_name, birth_date, location, bio, interests, photo_path, person_id))
    else:
        c.execute("""
            UPDATE persons SET first_name=?, last_name=?, birth_date=?, location=?, bio=?, interests=?
            WHERE id=?
        """, (first_name, last_name, birth_date, location, bio, interests, person_id))
    conn.commit()
    conn.close()

def get_all_persons():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, first_name, last_name, birth_date, location, bio, interests, photo_path FROM persons ORDER BY first_name")
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
    c.execute("INSERT INTO relationships (person1_id, person2_id, relationship_type) VALUES (?, ?, ?)",
               (person1_id, person2_id, rel_type))
    conn.commit()
    conn.close()

def get_all_relationships():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT person1_id, person2_id, relationship_type FROM relationships")
    rows = c.fetchall()
    conn.close()
    return rows

def get_relationships_for(person_id):
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

def get_avatar_src(photo_path, first_name, last_name):
    if photo_path and os.path.exists(photo_path):
        ext = os.path.splitext(photo_path)[1].replace(".", "") or "png"
        with open(photo_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f"data:image/{ext};base64,{b64}"
    name = f"{first_name}+{(last_name or '')}".strip()
    return f"https://ui-avatars.com/api/?name={name}&background=FF8C69&color=fff&size=160&font-size=0.38&bold=true"

def save_uploaded_photo(photo_file):
    if not photo_file:
        return None
    from PIL import Image
    path = os.path.join(PHOTO_DIR, f"{datetime.now().timestamp()}_{photo_file.name}")
    img = Image.open(photo_file)
    img.thumbnail((800, 800))
    img.save(path)
    return path

def infer_role_label(pid, rels):
    for rt, p1, p2 in rels:
        if rt == "spouse-of" and (p1 == pid or p2 == pid):
            return "Partner"
    return ""

BRANCH_PALETTE = [
    ("#FF8C69", "#FFE3D6"),
    ("#7EC8E3", "#DCF0F8"),
    ("#B8A6E0", "#EAE3F7"),
    ("#8FD9C4", "#DFF5EE"),
    ("#FFD166", "#FFF3D6"),
]

def compute_branch_colors(people, rels):
    parent_children = {}
    has_parent = set()
    for p1, p2, t in rels:
        if t == "parent-of":
            parent_children.setdefault(p1, []).append(p2)
            has_parent.add(p2)
        elif t == "child-of":
            parent_children.setdefault(p2, []).append(p1)
            has_parent.add(p1)
    roots = [p[0] for p in people if p[0] not in has_parent]
    color_map = {}
    for i, root in enumerate(roots):
        accent, soft = BRANCH_PALETTE[i % len(BRANCH_PALETTE)]
        stack = [root]
        seen = set()
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            color_map[node] = (accent, soft)
            stack.extend(parent_children.get(node, []))
    for p in people:
        if p[0] not in color_map:
            color_map[p[0]] = BRANCH_PALETTE[0]
    return color_map

def compute_stats(people, rels):
    total = len(people)
    parent_children = {}
    has_parent = set()
    for p1, p2, t in rels:
        if t == "parent-of":
            parent_children.setdefault(p1, []).append(p2)
            has_parent.add(p2)
        elif t == "child-of":
            parent_children.setdefault(p2, []).append(p1)
            has_parent.add(p1)
    roots = [p[0] for p in people if p[0] not in has_parent]
    max_depth = 0
    for r in roots:
        stack = [(r, 1)]
        seen = set()
        while stack:
            node, depth = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            max_depth = max(max_depth, depth)
            for child in parent_children.get(node, []):
                stack.append((child, depth + 1))
    stories = sum(1 for p in people if p[5])
    return total, max_depth, len(roots), stories

# =========================================================
# QUERY PARAM STATE
# =========================================================

qp = st.query_params
selected_id = qp.get("selected")
action = qp.get("action")
rel_param = qp.get("rel")
for_param = qp.get("for")
selected_id = int(selected_id) if selected_id else None
for_param = int(for_param) if for_param else None

if "just_added" not in st.session_state:
    st.session_state.just_added = None

# =========================================================
# GLOBAL STYLE — every color explicit, nothing inherited
# =========================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

:root {
    --ivory:#FFFBF5; --navy:#1B2A4A; --navy-soft:#4A5670; --coral:#FF8C69; --coral-deep:#F2704A;
    --lavender:#B8A6E0; --sky:#7EC8E3; --mint:#8FD9C4; --yellow:#FFD166; --border:#EFE7DA;
}
html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif !important; color: var(--navy) !important; }
.stApp { background: linear-gradient(160deg, #FFFBF5 0%, #FFF3E9 100%); }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 0.5rem !important; padding-bottom: 5rem !important; max-width: 100% !important; }
section[data-testid="stSidebar"] { display: none; }

label, .stTextInput label, .stTextArea label, .stSelectbox label, .stFileUploader label {
    color: var(--navy) !important; font-weight: 600 !important; font-size: 0.88rem !important;
}
.stTextInput input, .stTextArea textarea {
    color: var(--navy) !important; background-color: #FFFFFF !important;
    border: 1.5px solid var(--border) !important; border-radius: 12px !important;
}
.stTextInput input::placeholder, .stTextArea textarea::placeholder { color: #A8A2B8 !important; }
.stSelectbox > div > div { background-color: #FFFFFF !important; color: var(--navy) !important; border-radius: 12px !important; }
div[data-baseweb="select"] * { color: var(--navy) !important; }
.stFileUploader section { background-color: #FFFFFF !important; border: 1.5px dashed var(--border) !important; border-radius:14px !important; }
.stFileUploader section * { color: var(--navy-soft) !important; }
.stMarkdown, .stMarkdown p, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 { color: var(--navy) !important; }

.top-bar {
    display:flex; align-items:center; justify-content:space-between; padding: 10px 14px;
    background:white; border-radius:16px; margin: 0 4px 6px 4px; box-shadow:0 2px 10px rgba(27,42,74,0.06);
}
.top-bar .brand { font-size:1.05rem; font-weight:800; color:var(--navy); display:flex; align-items:center; gap:8px; }
.top-bar .search-icon { font-size:1.15rem; opacity:0.55; }

.fab {
    position:fixed; right:22px; bottom:88px; width:56px; height:56px; border-radius:50%;
    background:linear-gradient(135deg, var(--coral), var(--coral-deep)); color:white !important;
    display:flex; align-items:center; justify-content:center; font-size:26px; text-decoration:none;
    box-shadow:0 8px 20px rgba(242,112,74,0.45); z-index:9999; transition: transform 0.15s ease;
}
.fab:hover { transform: scale(1.08); }
.fab:active { transform: scale(0.94); }

.bottom-nav {
    position:fixed; left:0; right:0; bottom:0; height:60px; background:white;
    display:flex; align-items:center; justify-content:space-around; box-shadow:0 -4px 16px rgba(27,42,74,0.08);
    z-index:9998; padding-bottom: env(safe-area-inset-bottom);
}
.bottom-nav a { color:var(--navy) !important; text-decoration:none; font-size:21px; opacity:0.5; min-width:44px; min-height:44px; display:flex; align-items:center; justify-content:center; }
.bottom-nav a.active { opacity:1; color:var(--coral-deep) !important; }
@media (min-width: 900px) { .bottom-nav { display:none; } .fab { bottom:32px; } }

.choice-grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(120px,1fr)); gap:14px; margin: 18px 0 6px 0; }
.choice-card {
    background:linear-gradient(155deg, #ffffff, #FFF6EE); border-radius:20px; padding:24px 10px; text-align:center;
    box-shadow:0 4px 14px rgba(27,42,74,0.08); border:2px solid transparent; transition: all 0.18s ease;
    cursor:pointer; color:var(--navy) !important; text-decoration:none; display:block;
}
.choice-card:hover { border-color: var(--coral); transform: translateY(-4px); box-shadow:0 10px 22px rgba(242,112,74,0.18); }
.choice-card:active { transform: scale(0.97); }
.choice-emoji { font-size:2rem; display:block; margin-bottom:8px; }
.choice-label { font-weight:700; font-size:0.92rem; color:var(--navy) !important; }

div[data-testid="stForm"] {
    background:white; border-radius:22px; padding:28px; box-shadow:0 8px 24px rgba(27,42,74,0.1);
    max-width:520px; margin: 0 auto; border: 1px solid var(--border);
}
div.stButton > button {
    background: linear-gradient(135deg, var(--coral), var(--coral-deep)) !important;
    color:white !important; border:none !important; border-radius:14px !important; padding:0.6em 1.4em !important; font-weight:700 !important;
    box-shadow:0 4px 12px rgba(242,112,74,0.3); transition: transform 0.12s ease;
}
div.stButton > button:hover { transform: translateY(-2px); }
div.stButton > button:active { transform: scale(0.97); }
div.stButton > button p { color: white !important; }

.success-banner {
    background: linear-gradient(135deg, var(--mint), #6FCBA8); color:white !important; border-radius:18px;
    padding:20px 24px; text-align:center; font-weight:700; font-size:1.05rem; max-width:520px; margin:16px auto;
    box-shadow:0 8px 20px rgba(143,217,196,0.4); animation: pop 0.4s cubic-bezier(.34,1.56,.64,1);
}
@keyframes pop { 0%{transform:scale(0.7);opacity:0;} 100%{transform:scale(1);opacity:1;} }

.onboarding { text-align:center; padding: 60px 20px; }
.onboarding h2 { color:var(--navy) !important; font-size:1.8rem; font-weight:800; }
.onboarding p { color:var(--navy-soft) !important; font-size:1rem; max-width:420px; margin:8px auto 20px auto; }

.wizard-heading { color:var(--navy) !important; font-weight:800; font-size:1.3rem; margin-top:4px; }
.wizard-sub { color:var(--navy-soft) !important; font-size:0.9rem; margin-top:-6px; margin-bottom:4px; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# DATA
# =========================================================

people = get_all_persons()
rels = get_all_relationships()
total, generations, branches, stories = compute_stats(people, rels)

# =========================================================
# MINIMAL HEADER
# =========================================================

st.markdown("""
<div class="top-bar">
  <div class="brand">🌳 Our Family</div>
  <div class="search-icon">⋯</div>
</div>
""", unsafe_allow_html=True)

# =========================================================
# ADD / EDIT WIZARD
# =========================================================

def render_wizard():
    editing = action == "edit" and for_param
    edit_person = get_person(for_param) if editing else None

    if not editing and not for_param and rel_param is None and len(people) > 0:
        st.markdown('<div class="wizard-heading">Who would you like to add?</div>', unsafe_allow_html=True)
        st.markdown('<div class="wizard-sub">Choose how they connect to someone already in the tree</div>', unsafe_allow_html=True)

        target_options = {f"{f} {l or ''}".strip(): pid for pid, f, l, *_ in people}
        target_name = st.selectbox("Relative to whom?", list(target_options.keys()))
        target_id = target_options[target_name]

        choices = [("Parent", "parent", "🧓"), ("Child", "child", "👶"), ("Partner", "partner", "💍"),
                   ("Sibling", "sibling", "🧑‍🤝‍🧑"), ("Other", "other", "👤")]
        cards_html = '<div class="choice-grid">'
        for label, key, emoji in choices:
            cards_html += f'<a class="choice-card" href="?action=add&rel={key}&for={target_id}"><span class="choice-emoji">{emoji}</span><span class="choice-label">{label}</span></a>'
        cards_html += '</div>'
        st.markdown(cards_html, unsafe_allow_html=True)

        if st.button("← Cancel"):
            st.query_params.clear()
            st.rerun()
        return

    label_map = {"parent": "Add a Parent", "child": "Add a Child", "partner": "Add a Partner",
                 "sibling": "Add a Sibling", "other": "Add a Family Member", None: "Add Yourself"}
    st.markdown(f'<div class="wizard-heading">{"Edit Details" if editing else label_map.get(rel_param, "Add a Family Member")}</div>', unsafe_allow_html=True)
    st.markdown('<div class="wizard-sub">Tell us about them</div>', unsafe_allow_html=True)

    with st.form("person_form"):
        p = edit_person
        first_name = st.text_input("First Name *", value=p[1] if p else "")
        last_name = st.text_input("Last Name", value=p[2] if p else "")
        birth_date = st.text_input("Birth Date (e.g. 1985-04-12)", value=p[3] if p and p[3] else "")
        location = st.text_input("Current Location", value=p[4] if p else "")
        bio = st.text_area("Their story (childhood, memories, anything worth keeping)", value=p[5] if p else "")
        interests = st.text_input("Interests (comma separated)", value=p[6] if p else "")
        photo_file = st.file_uploader("Photo", type=["jpg", "jpeg", "png"])
        submitted = st.form_submit_button("💾 Save" if editing else "✨ Add to the tree", use_container_width=True)

        if submitted:
            if not first_name:
                st.error("First name is required")
            else:
                photo_path = save_uploaded_photo(photo_file)
                if editing:
                    update_person(for_param, first_name, last_name, birth_date, location, bio, interests, photo_path)
                    st.query_params.clear()
                    st.query_params["selected"] = str(for_param)
                    st.rerun()
                else:
                    new_id = add_person(first_name, last_name, birth_date, location, bio, interests, photo_path)
                    if for_param and rel_param:
                        if rel_param == "parent":
                            add_relationship(new_id, for_param, "parent-of")
                        elif rel_param == "child":
                            add_relationship(for_param, new_id, "parent-of")
                        elif rel_param == "partner":
                            add_relationship(for_param, new_id, "spouse-of")
                        elif rel_param == "sibling":
                            add_relationship(for_param, new_id, "sibling-of")
                    st.session_state.just_added = new_id
                    st.query_params.clear()
                    st.query_params["selected"] = str(new_id)
                    st.markdown(f'<div class="success-banner">✨ {first_name} joined your family</div>', unsafe_allow_html=True)
                    st.balloons()
                    st.rerun()

    if st.button("← Cancel"):
        st.query_params.clear()
        st.rerun()

# =========================================================
# TREE CANVAS
# =========================================================

def build_tree_html(people, rels, selected_id, just_added, stats):
    branch_colors = compute_branch_colors(people, rels)
    nodes = []
    for pid, first, last, birth, loc, bio, interests, photo in people:
        accent, soft = branch_colors.get(pid, BRANCH_PALETTE[0])
        nodes.append({
            "id": pid, "name": f"{first} {last or ''}".strip(),
            "role": infer_role_label(pid, rels),
            "img": get_avatar_src(photo, first, last),
            "born": birth or "", "accent": accent, "soft": soft,
        })

    edges = []
    for p1, p2, t in rels:
        if t == "parent-of":
            edges.append({"source": p1, "target": p2, "type": "parent"})
        elif t == "child-of":
            edges.append({"source": p2, "target": p1, "type": "parent"})
        elif t == "spouse-of":
            edges.append({"source": p1, "target": p2, "type": "spouse"})
        elif t == "sibling-of":
            edges.append({"source": p1, "target": p2, "type": "sibling"})

    total, gen, branch_count, story_count = stats

    html = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  html, body { margin:0; padding:0; width:100%; height:100%; overflow:hidden; background:transparent; font-family:'Plus Jakarta Sans', sans-serif; }
  svg { width:100%; height:100%; cursor:grab; display:block; }
  svg:active { cursor:grabbing; }
  .link-parent { stroke-width:2.5px; fill:none; }
  .link-spouse { stroke:#7EC8E3; stroke-width:2px; stroke-dasharray:5,4; fill:none; }
  .link-sibling { stroke:#FFD166; stroke-width:2px; stroke-dasharray:2,4; fill:none; }
  .node-card { cursor:pointer; transition: opacity 0.25s ease; touch-action: manipulation; }
  .node-card .card-bg { filter:drop-shadow(0 4px 10px rgba(27,42,74,0.16)); transition: all 0.18s ease; }
  .node-card:hover .card-bg { transform: translateY(-3px); }
  .node-card.selected .card-bg { filter:drop-shadow(0 6px 16px rgba(242,112,74,0.35)); }
  .node-card.faded { opacity:0.22; }
  .node-name { font-size:13px; font-weight:800; fill:#1B2A4A; text-anchor:middle; }
  .node-role { font-size:10.5px; font-weight:600; fill:#8A94A6; text-anchor:middle; }
  .stat-strip { font-size:11px; fill:#8A94A6; font-weight:600; }
  .controls { position:fixed; right:14px; top:14px; display:flex; flex-direction:column; gap:8px; }
  .ctrl-btn {
    width:38px; height:38px; border-radius:50%; background:white; border:none;
    box-shadow:0 3px 10px rgba(27,42,74,0.15); font-size:17px; color:#1B2A4A; cursor:pointer;
  }
  .stats-badge {
    position:fixed; left:14px; top:14px; background:rgba(255,255,255,0.9); backdrop-filter:blur(4px);
    border-radius:14px; padding:8px 14px; font-size:11.5px; font-weight:600; color:#4A5670;
    box-shadow:0 3px 10px rgba(27,42,74,0.08); display:flex; gap:12px;
  }
</style>
</head>
<body>
<div class="stats-badge">
  <span>""" + f"{total} members · {gen} generations · {branch_count} branches" + """</span>
</div>
<div class="controls">
  <button class="ctrl-btn" onclick="zoomBy(1.25)">+</button>
  <button class="ctrl-btn" onclick="zoomBy(0.8)">−</button>
  <button class="ctrl-btn" onclick="centerTree()">⤢</button>
</div>
<svg id="canvas"></svg>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
<script>
const nodesData = __NODES__;
const edgesData = __EDGES__;
const selectedId = __SELECTED__;
const justAdded = __JUSTADDED__;

const nodeById = {};
nodesData.forEach(n => nodeById[n.id] = n);

const childrenMap = {};
const hasParent = new Set();
edgesData.filter(e => e.type === "parent").forEach(e => {
  childrenMap[e.source] = childrenMap[e.source] || [];
  childrenMap[e.source].push(e.target);
  hasParent.add(e.target);
});
const roots = nodesData.filter(n => !hasParent.has(n.id));

const svg = d3.select("#canvas");
const width = window.innerWidth, height = window.innerHeight;
svg.attr("viewBox", [0,0,width,height]);
const g = svg.append("g");

const zoom = d3.zoom().scaleExtent([0.3,3]).clickDistance(12)
  .filter((event) => !(event.target && event.target.closest && event.target.closest(".node-card")))
  .on("zoom", (event) => { g.attr("transform", event.transform); });
svg.call(zoom);
function zoomBy(factor) { svg.transition().duration(250).call(zoom.scaleBy, factor); }

let allLaidOut = [];
let offsetX = 50;
const NODE_W = 160, NODE_H = 190;

function buildHierarchy(id, visited) {
  visited = visited || new Set();
  if (visited.has(id)) return { id: id, children: [] };
  visited.add(id);
  return { id: id, children: (childrenMap[id] || []).map(c => buildHierarchy(c, visited)) };
}

roots.forEach(root => {
  const hierarchyData = buildHierarchy(root.id);
  const rootH = d3.hierarchy(hierarchyData);
  const treeLayout = d3.tree().nodeSize([NODE_W, NODE_H]);
  treeLayout(rootH);
  let minX = Infinity, maxX = -Infinity;
  rootH.each(d => { minX = Math.min(minX, d.x); maxX = Math.max(maxX, d.x); });
  rootH.each(d => { allLaidOut.push({ id: d.data.id, x: d.x - minX + offsetX, y: d.depth * 200 + 70 }); });
  offsetX += (maxX - minX) + 240;
});

const posById = {};
allLaidOut.forEach(d => posById[d.id] = d);

const connected = new Set();
if (selectedId) {
  connected.add(selectedId);
  edgesData.forEach(e => {
    if (e.source === selectedId) connected.add(e.target);
    if (e.target === selectedId) connected.add(e.source);
  });
}

const linkGroup = g.append("g");
edgesData.forEach(e => {
  const s = posById[e.source], t = posById[e.target];
  if (!s || !t) return;
  const person = nodeById[e.source];
  const path = d3.path();
  path.moveTo(s.x, s.y);
  path.bezierCurveTo(s.x, (s.y+t.y)/2, t.x, (s.y+t.y)/2, t.x, t.y);
  const cls = e.type === "parent" ? "link-parent" : (e.type === "spouse" ? "link-spouse" : "link-sibling");
  const el = linkGroup.append("path").attr("d", path.toString()).attr("class", cls);
  if (e.type === "parent") el.attr("stroke", person.accent || "#D8CDEA");
});

const nodeGroup = g.append("g");
allLaidOut.forEach(d => {
  const person = nodeById[d.id];
  if (!person) return;
  const isSelected = selectedId === d.id;
  const isFaded = selectedId && !connected.has(d.id);
  const isNew = justAdded === d.id;

  const grp = nodeGroup.append("g")
    .attr("class", "node-card" + (isSelected ? " selected" : "") + (isFaded ? " faded" : ""))
    .attr("transform", `translate(${d.x - 65}, ${d.y - 90}) scale(${isNew ? 0.2 : 1})`)
    .style("opacity", isNew ? 0 : 1)
    .on("click", () => selectPerson(d.id));

  const g2 = grp.append("g").attr("class", "card-bg");
  g2.append("rect").attr("width", 130).attr("height", 172).attr("rx", 20).attr("fill", "white")
    .attr("stroke", isSelected ? person.accent : "rgba(27,42,74,0.06)").attr("stroke-width", isSelected ? 3 : 1);
  g2.append("rect").attr("width", 130).attr("height", 6).attr("rx", 3).attr("fill", person.accent);
  g2.append("clipPath").attr("id", "clip"+d.id).append("rect").attr("x", 15).attr("y", 16).attr("width", 100).attr("height", 100).attr("rx", 16);
  g2.append("image").attr("href", person.img).attr("x", 15).attr("y", 16).attr("width", 100).attr("height", 100).attr("clip-path", `url(#clip${d.id})`);
  g2.append("text").attr("class", "node-name").attr("x", 65).attr("y", 138).text(person.name.length > 15 ? person.name.slice(0,14)+"…" : person.name);
  const roleOrBorn = person.role || person.born;
  if (roleOrBorn) g2.append("text").attr("class", "node-role").attr("x", 65).attr("y", 155).text(roleOrBorn);

  if (isNew) {
    grp.transition().duration(550).ease(d3.easeBackOut)
      .attr("transform", `translate(${d.x - 65}, ${d.y - 90}) scale(1)`).style("opacity", 1);
  }
});

function selectPerson(id) {
  const url = new URL(window.parent.location.href);
  url.searchParams.set("action", "edit");
  url.searchParams.set("for", id);
  url.searchParams.delete("selected");
  window.parent.location.href = url.toString();
}

function centerTree() {
  const target = justAdded || selectedId;
  const pos = target ? posById[target] : null;
  const cx = pos ? pos.x : (offsetX/2);
  const cy = pos ? pos.y : 200;
  svg.transition().duration(400).call(zoom.transform, d3.zoomIdentity.translate(width/2 - cx, height/2 - cy).scale(1));
}
centerTree();
</script>
</body>
</html>
"""
    html = html.replace("__NODES__", json.dumps(nodes))
    html = html.replace("__EDGES__", json.dumps(edges))
    html = html.replace("__SELECTED__", json.dumps(selected_id))
    html = html.replace("__JUSTADDED__", json.dumps(just_added))
    return html

# =========================================================
# PROFILE DRAWER / BOTTOM SHEET
# =========================================================

def render_profile_drawer(person_id):
    p = get_person(person_id)
    if not p:
        return
    pid, first, last, birth, loc, bio, interests, photo, created = p
    img = get_avatar_src(photo, first, last)
    relationships = get_relationships_for(pid)
    rel_html = "".join(
        f"<div class='rel-row'>🔗 <b>{rt.replace('-', ' ')}</b> {of} {ol or ''}</div>"
        for rt, oid, of, ol in relationships
    ) or "<div class='rel-row' style='opacity:0.6'>No connections yet</div>"

    details = ""
    if birth: details += f"<div class='drawer-detail'>🎂 {birth}</div>"
    if loc: details += f"<div class='drawer-detail'>📍 {loc}</div>"
    if interests: details += f"<div class='drawer-detail'>❤️ {interests}</div>"
    bio_html = f"<p class='drawer-bio'>{bio}</p>" if bio else ""

    html = f"""
    <style>
    .drawer {{
        position:fixed; top:0; right:0; height:100vh; width:340px; background:white;
        box-shadow:-8px 0 30px rgba(27,42,74,0.15); z-index:10000; padding:24px;
        overflow-y:auto; animation: slideIn 0.28s ease;
    }}
    @keyframes slideIn {{ from {{ transform:translateX(100%); }} to {{ transform:translateX(0); }} }}
    @media (max-width: 899px) {{
        .drawer {{ top:auto; bottom:0; left:0; right:0; width:100%; height:auto; max-height:72vh;
            border-radius:24px 24px 0 0; animation: slideUp 0.28s ease; }}
        @keyframes slideUp {{ from {{ transform:translateY(100%); }} to {{ transform:translateY(0); }} }}
    }}
    .drawer img.avatar {{ width:88px; height:88px; border-radius:22px; object-fit:cover; box-shadow:0 4px 14px rgba(27,42,74,0.2); }}
    .drawer h2 {{ color:#1B2A4A !important; margin:12px 0 4px 0; }}
    .drawer-detail {{ color:#4A5670 !important; font-size:0.86rem; margin-bottom:3px; }}
    .drawer-bio {{ color:#4A5670 !important; font-size:0.9rem; line-height:1.5; margin-top:10px; }}
    .rel-row {{ font-size:0.85rem; color:#1B2A4A !important; padding:6px 0; border-bottom:1px solid #F3F0EA; }}
    .drawer-actions {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:16px; }}
    .drawer-actions a {{
        text-decoration:none; font-size:0.8rem; font-weight:700; padding:8px 12px; border-radius:12px;
        background:#FFF3E9; color:#F2704A !important;
    }}
    .close-x {{ position:absolute; top:18px; right:18px; text-decoration:none; color:#8A94A6 !important; font-size:20px; }}
    .drawer h4 {{ color:#1B2A4A !important; margin-top:20px; }}
    </style>
    <div class="drawer">
      <a class="close-x" href="?">✕</a>
      <img class="avatar" src="{img}"/>
      <h2>{first} {last or ''}</h2>
      {details}
      {bio_html}
      <div class="drawer-actions">
        <a href="?action=edit&for={pid}">✏️ Edit</a>
        <a href="?action=add&rel=parent&for={pid}">+ Parent</a>
        <a href="?action=add&rel=child&for={pid}">+ Child</a>
        <a href="?action=add&rel=partner&for={pid}">+ Partner</a>
        <a href="?action=add&rel=sibling&for={pid}">+ Sibling</a>
      </div>
      <h4>Family Connections</h4>
      {rel_html}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

# =========================================================
# MAIN ROUTING
# =========================================================

if action == "add" or action == "edit":
    render_wizard()
elif len(people) == 0:
    st.markdown("""
    <div class="onboarding">
      <h2>Let's build your family story 🌱</h2>
      <p>Every tree starts with one person. Add yourself first, then invite your family to grow it branch by branch.</p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("🌱 Add Yourself"):
        st.query_params["action"] = "add"
        st.rerun()
else:
    tree_html = build_tree_html(people, rels, selected_id, st.session_state.just_added, (total, generations, branches, stories))
    components.html(tree_html, height=640, scrolling=False)
    st.session_state.just_added = None
    if selected_id:
        render_profile_drawer(selected_id)

    st.markdown("""
    <a class="fab" href="?action=add">+</a>
    <div class="bottom-nav">
      <a class="active" href="?">🌳</a>
      <a href="?action=add">➕</a>
    </div>
    """, unsafe_allow_html=True)
