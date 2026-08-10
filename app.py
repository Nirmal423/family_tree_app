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
# DATA LAYER (unchanged model, one addition: update_person)
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
    return f"https://ui-avatars.com/api/?name={name}&background=FF8C69&color=fff&size=128&font-size=0.4&bold=true"

def save_uploaded_photo(photo_file):
    if not photo_file:
        return None
    from PIL import Image
    path = os.path.join(PHOTO_DIR, f"{datetime.now().timestamp()}_{photo_file.name}")
    img = Image.open(photo_file)
    img.thumbnail((800, 800))
    img.save(path)
    return path

# =========================================================
# QUERY PARAM STATE (navigation without a custom JS bridge)
# =========================================================

qp = st.query_params
selected_id = qp.get("selected")
action = qp.get("action")
rel_param = qp.get("rel")
for_param = qp.get("for")
selected_id = int(selected_id) if selected_id else None
for_param = int(for_param) if for_param else None

if "wizard_step" not in st.session_state:
    st.session_state.wizard_step = 1
if "just_added" not in st.session_state:
    st.session_state.just_added = None

# =========================================================
# GLOBAL STYLE
# =========================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

:root {
    --ivory:#FFFBF5; --navy:#1B2A4A; --coral:#FF8C69; --coral-deep:#F2704A;
    --lavender:#B8A6E0; --sky:#7EC8E3; --mint:#8FD9C4; --yellow:#FFD166;
}
html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }
.stApp { background: linear-gradient(160deg, #FFFBF5 0%, #FFF3E9 100%); }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1rem !important; padding-bottom: 5rem !important; max-width: 100% !important; }
section[data-testid="stSidebar"] { display: none; }

.app-header { display:flex; align-items:center; justify-content:space-between; padding: 4px 8px 12px 8px; }
.app-header h1 { font-size: 1.4rem; font-weight: 800; color: var(--navy); margin:0; }
.stat-pills { display:flex; gap:8px; flex-wrap:wrap; margin-top:4px; }
.stat-pill {
    background:white; border-radius:999px; padding:5px 14px; font-size:0.78rem;
    font-weight:600; color:var(--navy); box-shadow:0 2px 8px rgba(27,42,74,0.08);
}

.fab {
    position:fixed; right:24px; bottom:84px; width:58px; height:58px; border-radius:50%;
    background:linear-gradient(135deg, var(--coral), var(--coral-deep)); color:white;
    display:flex; align-items:center; justify-content:center; font-size:28px; text-decoration:none;
    box-shadow:0 8px 20px rgba(242,112,74,0.45); z-index:9999; transition: transform 0.15s ease;
}
.fab:hover { transform: scale(1.08); }
.fab:active { transform: scale(0.94); }

.bottom-nav {
    position:fixed; left:0; right:0; bottom:0; height:64px; background:white;
    display:flex; align-items:center; justify-content:space-around; box-shadow:0 -4px 16px rgba(27,42,74,0.08);
    z-index:9998; padding-bottom: env(safe-area-inset-bottom);
}
.bottom-nav a { color:var(--navy); text-decoration:none; font-size:22px; opacity:0.55; min-width:44px; min-height:44px; display:flex; align-items:center; justify-content:center; }
.bottom-nav a.active { opacity:1; color:var(--coral-deep); }

@media (min-width: 900px) { .bottom-nav { display:none; } .fab { bottom:32px; } }

.choice-grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(130px,1fr)); gap:14px; margin-top:18px; }
.choice-card {
    background:white; border-radius:20px; padding:22px 12px; text-align:center; box-shadow:0 4px 14px rgba(27,42,74,0.08);
    border:2px solid transparent; transition: all 0.18s ease;
}
.choice-card:hover { border-color: var(--coral); transform: translateY(-3px); }

div.stButton > button {
    background: linear-gradient(135deg, var(--coral), var(--coral-deep));
    color:white; border:none; border-radius:14px; padding:0.6em 1.4em; font-weight:700;
    box-shadow:0 4px 12px rgba(242,112,74,0.3); transition: transform 0.12s ease;
}
div.stButton > button:hover { transform: translateY(-2px); }
div.stButton > button:active { transform: scale(0.97); }

div[data-testid="stForm"] {
    background:white; border-radius:22px; padding:28px; box-shadow:0 8px 24px rgba(27,42,74,0.1);
    max-width:520px; margin: 0 auto;
}

.success-banner {
    background: linear-gradient(135deg, var(--mint), #6FCBA8); color:white; border-radius:18px;
    padding:20px 24px; text-align:center; font-weight:700; font-size:1.05rem; max-width:520px; margin:20px auto;
    box-shadow:0 8px 20px rgba(143,217,196,0.4);
    animation: pop 0.4s cubic-bezier(.34,1.56,.64,1);
}
@keyframes pop { 0%{transform:scale(0.7);opacity:0;} 100%{transform:scale(1);opacity:1;} }

.onboarding { text-align:center; padding: 60px 20px; }
.onboarding h2 { color:var(--navy); font-size:1.8rem; font-weight:800; }
.onboarding p { color:#6b7280; font-size:1rem; max-width:420px; margin:8px auto 20px auto; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# HEADER + STATS
# =========================================================

people = get_all_persons()
rels = get_all_relationships()

def compute_stats(people, rels):
    total = len(people)
    parent_children = {}
    for p1, p2, t in rels:
        if t == "parent-of":
            parent_children.setdefault(p1, []).append(p2)
        elif t == "child-of":
            parent_children.setdefault(p2, []).append(p1)
    has_parent = set()
    for p1, p2, t in rels:
        if t == "parent-of": has_parent.add(p2)
        if t == "child-of": has_parent.add(p1)
    roots = [p[0] for p in people if p[0] not in has_parent]
    max_depth = 0
    for r in roots:
        stack = [(r, 1)]
        seen = set()
        while stack:
            node, depth = stack.pop()
            if node in seen: continue
            seen.add(node)
            max_depth = max(max_depth, depth)
            for child in parent_children.get(node, []):
                stack.append((child, depth + 1))
    stories = sum(1 for p in people if p[5])
    return total, max_depth, len(roots), stories

total, generations, branches, stories = compute_stats(people, rels)

st.markdown(f"""
<div class="app-header">
  <div>
    <h1>🌳 Our Family</h1>
    <div class="stat-pills">
      <span class="stat-pill">👨‍👩‍👧 {total} members</span>
      <span class="stat-pill">🌿 {generations} generations</span>
      <span class="stat-pill">🌳 {branches} branches</span>
      <span class="stat-pill">📖 {stories} stories</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# =========================================================
# ADD / EDIT WIZARD
# =========================================================

def render_wizard():
    editing = action == "edit" and for_param
    edit_person = get_person(for_param) if editing else None

    if not editing and not for_param and rel_param is None and st.session_state.wizard_step == 1 and len(people) > 0:
        st.markdown("### Who would you like to add?")
        cols = st.columns(5)
        choices = [("Parent", "parent", "🧓"), ("Child", "child", "👶"), ("Partner", "partner", "💍"),
                   ("Sibling", "sibling", "🧑‍🤝‍🧑"), ("Other", "other", "👤")]
        target_options = {f"{f} {l or ''}".strip(): pid for pid, f, l, *_ in people}
        target_name = st.selectbox("Relative to whom?", list(target_options.keys()))
        for i, (label, key, emoji) in enumerate(choices):
            with cols[i]:
                if st.button(f"{emoji}\n{label}", key=f"rel_{key}", use_container_width=True):
                    st.query_params["action"] = "add"
                    st.query_params["rel"] = key
                    st.query_params["for"] = str(target_options[target_name])
                    st.rerun()
        if st.button("← Cancel"):
            st.query_params.clear()
            st.rerun()
        return

    # Step 2: details form
    label_map = {"parent": "Add a Parent", "child": "Add a Child", "partner": "Add a Partner",
                 "sibling": "Add a Sibling", "other": "Add a Family Member", None: "Add Yourself"}
    st.markdown(f"### {'Edit' if editing else label_map.get(rel_param, 'Add a Family Member')}")

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
                    st.markdown(f'<div class="success-banner">🎉 {first_name} has joined your family tree!</div>', unsafe_allow_html=True)
                    st.balloons()
                    st.rerun()

    if st.button("← Cancel"):
        st.query_params.clear()
        st.rerun()

# =========================================================
# TREE CANVAS (D3, pan/zoom/hover fully client-side)
# =========================================================

def build_tree_html(people, rels, selected_id, just_added):
    nodes = []
    for pid, first, last, birth, loc, bio, interests, photo in people:
        nodes.append({
            "id": pid,
            "name": f"{first} {last or ''}".strip(),
            "img": get_avatar_src(photo, first, last),
            "born": birth or "",
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

    nodes_json = json.dumps(nodes)
    edges_json = json.dumps(edges)
    selected_json = json.dumps(selected_id)
    just_added_json = json.dumps(just_added)

    html = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  html, body { margin:0; padding:0; overflow:hidden; background:transparent; font-family:'Plus Jakarta Sans', sans-serif; }
  svg { width:100%; height:100%; cursor:grab; }
  svg:active { cursor:grabbing; }
  .link-parent { stroke:#D8CDEA; stroke-width:2.5px; fill:none; }
  .link-spouse { stroke:#7EC8E3; stroke-width:2px; stroke-dasharray:5,4; fill:none; }
  .link-sibling { stroke:#FFD166; stroke-width:2px; stroke-dasharray:2,4; fill:none; }
  .node-card { cursor:pointer; }
  .node-card rect { fill:white; stroke:rgba(27,42,74,0.06); stroke-width:1px; filter:drop-shadow(0 3px 8px rgba(27,42,74,0.15)); transition: all 0.18s ease; }
  .node-card:hover rect { stroke:#FF8C69; stroke-width:2px; transform: translateY(-2px); }
  .node-card.selected rect { stroke:#F2704A; stroke-width:3px; }
  .node-card.faded { opacity:0.25; }
  .node-name { font-size:13px; font-weight:700; fill:#1B2A4A; text-anchor:middle; }
  .node-sub { font-size:10px; fill:#8A94A6; text-anchor:middle; }
  .controls { position:fixed; right:14px; top:14px; display:flex; flex-direction:column; gap:8px; }
  .ctrl-btn {
    width:38px; height:38px; border-radius:50%; background:white; border:none;
    box-shadow:0 3px 10px rgba(27,42,74,0.15); font-size:17px; color:#1B2A4A; cursor:pointer;
  }
</style>
</head>
<body>
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

const zoom = d3.zoom().scaleExtent([0.3,3]).on("zoom", (event) => {
  g.attr("transform", event.transform);
});
svg.call(zoom);

function zoomBy(factor) {
  svg.transition().duration(250).call(zoom.scaleBy, factor);
}

let allLaidOut = [];
let offsetX = 40;
const NODE_W = 150, NODE_H = 150;

roots.forEach(root => {
  const hierarchyData = buildHierarchy(root.id);
  const rootH = d3.hierarchy(hierarchyData);
  const treeLayout = d3.tree().nodeSize([NODE_W, NODE_H]);
  treeLayout(rootH);
  let minX = Infinity, maxX = -Infinity;
  rootH.each(d => { minX = Math.min(minX, d.x); maxX = Math.max(maxX, d.x); });
  rootH.each(d => {
    allLaidOut.push({ id: d.data.id, x: d.x - minX + offsetX, y: d.depth * 170 + 60 });
  });
  offsetX += (maxX - minX) + 220;
});

function buildHierarchy(id) {
  return { id: id, children: (childrenMap[id] || []).map(buildHierarchy) };
}

const posById = {};
allLaidOut.forEach(d => posById[d.id] = d);

// connected set for highlight
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
  const path = d3.path();
  path.moveTo(s.x, s.y);
  path.bezierCurveTo(s.x, (s.y+t.y)/2, t.x, (s.y+t.y)/2, t.x, t.y);
  linkGroup.append("path")
    .attr("d", path.toString())
    .attr("class", e.type === "parent" ? "link-parent" : (e.type === "spouse" ? "link-spouse" : "link-sibling"));
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
    .attr("transform", `translate(${d.x - 55}, ${d.y - 65}) scale(${isNew ? 0.2 : 1})`)
    .style("opacity", isNew ? 0 : 1)
    .on("click", () => selectPerson(d.id));

  grp.append("rect").attr("width", 110).attr("height", 130).attr("rx", 18);
  grp.append("clipPath").attr("id", "clip"+d.id).append("circle").attr("cx", 55).attr("cy", 46).attr("r", 34);
  grp.append("image")
    .attr("href", person.img).attr("x", 21).attr("y", 12).attr("width", 68).attr("height", 68)
    .attr("clip-path", `url(#clip${d.id})`);
  grp.append("text").attr("class", "node-name").attr("x", 55).attr("y", 100).text(person.name.length > 14 ? person.name.slice(0,13)+"…" : person.name);
  if (person.born) grp.append("text").attr("class", "node-sub").attr("x", 55).attr("y", 116).text(person.born);

  if (isNew) {
    grp.transition().duration(500).ease(d3.easeBackOut)
      .attr("transform", `translate(${d.x - 55}, ${d.y - 65}) scale(1)`)
      .style("opacity", 1);
  }
});

function selectPerson(id) {
  const url = new URL(window.parent.location.href);
  url.searchParams.set("selected", id);
  url.searchParams.delete("action");
  window.parent.location.href = url.toString();
}

function centerTree() {
  const target = justAdded || selectedId;
  const pos = target ? posById[target] : null;
  const cx = pos ? pos.x : (offsetX/2);
  const cy = pos ? pos.y : 200;
  svg.transition().duration(400).call(
    zoom.transform,
    d3.zoomIdentity.translate(width/2 - cx, height/2 - cy).scale(1)
  );
}
centerTree();
</script>
</body>
</html>
"""
    html = html.replace("__NODES__", nodes_json)
    html = html.replace("__EDGES__", edges_json)
    html = html.replace("__SELECTED__", selected_json)
    html = html.replace("__JUSTADDED__", just_added_json)
    return html

# =========================================================
# PROFILE DRAWER / BOTTOM SHEET (pure HTML, action links)
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
    if birth: details += f"<div>🎂 {birth}</div>"
    if loc: details += f"<div>📍 {loc}</div>"
    if interests: details += f"<div>❤️ {interests}</div>"
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
        .drawer {{
            top:auto; bottom:0; left:0; right:0; width:100%; height:auto; max-height:70vh;
            border-radius:24px 24px 0 0; animation: slideUp 0.28s ease;
        }}
        @keyframes slideUp {{ from {{ transform:translateY(100%); }} to {{ transform:translateY(0); }} }}
    }}
    .drawer img.avatar {{ width:88px; height:88px; border-radius:50%; object-fit:cover; box-shadow:0 4px 14px rgba(27,42,74,0.2); }}
    .drawer h2 {{ color:#1B2A4A; margin:12px 0 4px 0; }}
    .drawer-bio {{ color:#4B5563; font-size:0.9rem; line-height:1.5; }}
    .rel-row {{ font-size:0.85rem; color:#1B2A4A; padding:6px 0; border-bottom:1px solid #F3F0EA; }}
    .drawer-actions {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:16px; }}
    .drawer-actions a {{
        text-decoration:none; font-size:0.8rem; font-weight:700; padding:8px 12px; border-radius:12px;
        background:#FFF3E9; color:#F2704A;
    }}
    .close-x {{ position:absolute; top:18px; right:18px; text-decoration:none; color:#8A94A6; font-size:20px; }}
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
      <h4 style="margin-top:20px;color:#1B2A4A;">Family Connections</h4>
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
    if st.button("🌱 Add Yourself", use_container_width=False):
        st.query_params["action"] = "add"
        st.rerun()
else:
    tree_html = build_tree_html(people, rels, selected_id, st.session_state.just_added)
    components.html(tree_html, height=640, scrolling=False)
    st.session_state.just_added = None
    if selected_id:
        render_profile_drawer(selected_id)

    st.markdown(f"""
    <a class="fab" href="?action=add">+</a>
    <div class="bottom-nav">
      <a class="active" href="?">🌳</a>
      <a href="?action=add">➕</a>
    </div>
    """, unsafe_allow_html=True)