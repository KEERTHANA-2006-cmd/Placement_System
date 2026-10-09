
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import csv
import io
from datetime import date, datetime, timedelta

# =========================================================
# PLACEMATE - COLLEGE PLACEMENT MANAGEMENT SYSTEM
# =========================================================

st.set_page_config(
    page_title="PlaceMate | Smart Placement System",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_NAME = "placement.db"

# -------------------- DATABASE ---------------------------

def get_connection():
    conn = sqlite3.connect(DB_NAME, timeout=20)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_columns(conn, table):
    return {
        row[1] for row in conn.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()
    }


def add_missing_columns(conn, table, columns):
    existing = get_columns(conn, table)
    for column, definition in columns.items():
        if column not in existing:
            conn.execute(
                f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
            )


def initialize_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS students (
                roll_no TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                department TEXT NOT NULL,
                year INTEGER NOT NULL,
                cgpa REAL NOT NULL,
                email TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                min_cgpa REAL NOT NULL,
                eligible_department TEXT NOT NULL,
                package_lpa REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS placements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                roll_no TEXT NOT NULL,
                company_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'Applied',
                application_date TEXT NOT NULL,
                UNIQUE(roll_no, company_id),
                FOREIGN KEY(roll_no) REFERENCES students(roll_no)
                    ON DELETE CASCADE,
                FOREIGN KEY(company_id) REFERENCES companies(id)
                    ON DELETE CASCADE
            );
        """)

        # Safely upgrade existing databases.
        add_missing_columns(conn, "students", {
            "skills": "TEXT DEFAULT ''",
            "projects": "TEXT DEFAULT ''",
            "certifications": "TEXT DEFAULT ''"
        })

        add_missing_columns(conn, "companies", {
            "job_description": "TEXT DEFAULT ''",
            "required_skills": "TEXT DEFAULT ''",
            "application_deadline": "TEXT DEFAULT ''",
            "openings": "INTEGER DEFAULT 1"
        })

        add_missing_columns(conn, "placements", {
            "interview_date": "TEXT DEFAULT ''",
            "interview_time": "TEXT DEFAULT ''",
            "interview_round": "TEXT DEFAULT ''",
            "interview_notes": "TEXT DEFAULT ''"
        })


initialize_db()

# -------------------- DESIGN -----------------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background: linear-gradient(135deg, #f7f8ff 0%, #eef2ff 55%, #f8faff 100%);
}

.block-container {
    padding-top: 1.7rem;
    padding-bottom: 3rem;
    max-width: 1450px;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #171744, #30276d 60%, #4338a8);
}

[data-testid="stSidebar"] * {
    color: white !important;
}

.hero {
    padding: 30px;
    border-radius: 22px;
    background: linear-gradient(120deg, #312e81, #5b46d6, #818cf8);
    color: white;
    margin-bottom: 22px;
    box-shadow: 0 12px 30px rgba(49,46,129,0.16);
}

.hero h1 {
    color: white;
    font-size: 34px;
    font-weight: 800;
    margin-bottom: 8px;
}

.hero p {
    color: #eeedff;
    font-size: 15px;
    margin-bottom: 0;
}

.metric-card {
    padding: 20px;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 18px;
    box-shadow: 0 5px 18px rgba(49,46,129,0.06);
    min-height: 120px;
}

.metric-label {
    color: #6b7280;
    font-size: 13px;
    font-weight: 600;
}

.metric-value {
    color: #312e81;
    font-size: 30px;
    font-weight: 800;
    margin-top: 8px;
}

.section-heading {
    color: #312e81;
    font-size: 22px;
    font-weight: 800;
    margin-top: 12px;
    margin-bottom: 12px;
}

div.stButton > button {
    border-radius: 10px;
    font-weight: 600;
    border: 1px solid #d7d9ff;
}

div.stButton > button[kind="primary"] {
    background: linear-gradient(90deg, #4f46e5, #7c3aed);
    color: white;
    border: none;
}

div[data-testid="stForm"] {
    background: rgba(255,255,255,0.8);
    border: 1px solid #e5e7eb;
    border-radius: 16px;
    padding: 18px;
}

.stTabs [data-baseweb="tab"] {
    font-weight: 600;
}

.small-note {
    color: #6b7280;
    font-size: 12px;
}
</style>
""", unsafe_allow_html=True)


# -------------------- HELPER FUNCTIONS -------------------

def read_df(query, params=()):
    with get_connection() as conn:
        return pd.read_sql_query(query, conn, params=params)


def execute_sql(query, params=()):
    with get_connection() as conn:
        cursor = conn.execute(query, params)
        return cursor.lastrowid


def metric_card(label, value, emoji):
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{emoji} {label}</div>
        <div class="metric-value">{value}</div>
    </div>
    """, unsafe_allow_html=True)


def csv_download(df, filename, label="⬇️ Download CSV"):
    data = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label=label,
        data=data,
        file_name=filename,
        mime="text/csv",
        use_container_width=False
    )


def clean_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def skills_set(value):
    return {
        item.strip().lower()
        for item in clean_text(value).replace(";", ",").split(",")
        if item.strip()
    }


def status_color(status):
    return {
        "Applied": "🔵",
        "Interview": "🟠",
        "Selected": "🟢",
        "Rejected": "🔴"
    }.get(status, "⚪")


def get_student(roll_no):
    df = read_df(
        "SELECT * FROM students WHERE roll_no = ?",
        (roll_no,)
    )
    return None if df.empty else df.iloc[0]


# -------------------- SIDEBAR ----------------------------

with st.sidebar:
    st.markdown("# 🎓 CampusConnect")
    st.caption("COLLEGE PLACEMENT PORTAL")
    st.markdown("---")

    page = st.radio(
        "NAVIGATION",
        [
            "🏠 Dashboard",
            "👩‍🎓 Student Management",
            "🏢 Company Management",
            "🎯 Eligibility Checker",
            "💡 Job Recommendations",
            "📋 Placement Tracking",
            "📊 Reports & Analytics",
            "📝 Resume Builder",
            "💻 Preparation Quiz",
            "🔔 Notifications"
        ],
        label_visibility="visible"
    )

    st.markdown("---")
    st.markdown("### ✨ CampusConnect")
    st.caption("Your journey from campus to career.")
    st.caption("Python • Streamlit • SQLite")


# -------------------- COMMON DATA -----------------------

students = read_df("SELECT * FROM students ORDER BY name")
companies = read_df("SELECT * FROM companies ORDER BY name")
placements = read_df("""
    SELECT p.*, s.name AS student_name, s.department,
           s.cgpa, s.email, c.name AS company_name,
           c.role, c.package_lpa
    FROM placements p
    JOIN students s ON p.roll_no = s.roll_no
    JOIN companies c ON p.company_id = c.id
    ORDER BY p.id DESC
""")

# -------------------- DASHBOARD --------------------------

if page == "🏠 Dashboard":
    st.markdown("""
    <div class="hero">
        <h1>🎓 Welcome to CampusConnect</h1>
        <p>Your smart college placement management and career-readiness dashboard.</p>
    </div>
    """, unsafe_allow_html=True)

    total_students = len(students)
    total_companies = len(companies)
    total_apps = len(placements)
    selected_apps = (
        int((placements["status"] == "Selected").sum())
        if not placements.empty else 0
    )
    selection_rate = (
        selected_apps / total_apps * 100 if total_apps else 0
    )

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        metric_card("Students", total_students, "👩‍🎓")
    with m2:
        metric_card("Companies", total_companies, "🏢")
    with m3:
        metric_card("Applications", total_apps, "📨")
    with m4:
        metric_card("Selected", selected_apps, "🏆")
    with m5:
        metric_card("Selection rate", f"{selection_rate:.1f}%", "📈")

    st.markdown('<div class="section-heading">📊 Placement overview</div>',
                unsafe_allow_html=True)

    left, right = st.columns(2)

    with left:
        st.subheader("Application status")
        if not placements.empty:
            status_counts = (
                placements["status"].value_counts()
                .rename_axis("Status").reset_index(name="Applications")
            )
            fig = px.pie(
                status_counts,
                names="Status",
                values="Applications",
                hole=0.55,
                title="Applications by status"
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Add placement applications to see the chart.")

    with right:
        st.subheader("Students by department")
        if not students.empty:
            dept = (
                students.groupby("department")
                .size().reset_index(name="Students")
            )
            fig = px.bar(
                dept, x="department", y="Students",
                color="department", title="Department-wise students"
            )
            fig.update_layout(
                showlegend=False,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Add students to see department statistics.")

    st.markdown('<div class="section-heading">🗓️ Upcoming interviews</div>',
                unsafe_allow_html=True)
    if not placements.empty:
        today = date.today().isoformat()
        upcoming = placements[
            (placements["interview_date"].fillna("") >= today) &
            (placements["interview_date"].fillna("") != "") &
            (placements["status"] == "Interview")
        ]
        if not upcoming.empty:
            st.dataframe(
                upcoming[[
                    "student_name", "roll_no", "company_name",
                    "role", "interview_date", "interview_time",
                    "interview_round"
                ]],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No upcoming interviews are scheduled.")

    st.markdown('<div class="section-heading">🕒 Recent applications</div>',
                unsafe_allow_html=True)
    if not placements.empty:
        st.dataframe(
            placements[[
                "student_name", "roll_no", "company_name",
                "role", "status", "application_date"
            ]].head(10),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No applications yet. Add students and companies first.")


# -------------------- STUDENT MANAGEMENT -----------------

elif page == "👩‍🎓 Student Management":
    st.markdown('<div class="section-heading">👩‍🎓 Student Management</div>',
                unsafe_allow_html=True)
    st.write("Add, edit, search, import, and manage student profiles.")

    add_tab, edit_tab, bulk_tab, view_tab = st.tabs([
        "➕ Add student", "✏️ Edit student",
        "📤 Bulk CSV upload", "🔎 View & delete"
    ])

    with add_tab:
        with st.form("add_student_form", clear_on_submit=True):
            a, b = st.columns(2)
            roll = a.text_input("Roll number *")
            name = b.text_input("Full name *")
            dept = a.selectbox(
                "Department *",
                ["CSE", "IT", "ECE", "EEE", "Mechanical",
                 "Civil", "AI & ML", "Data Science", "Other"]
            )
            year = b.selectbox("Academic year", [1, 2, 3, 4])
            cgpa = a.number_input(
                "CGPA (0–10)", min_value=0.0,
                max_value=10.0, value=7.0, step=0.1
            )
            email = b.text_input("Email address *")
            skills = st.text_input(
                "Skills", placeholder="Python, SQL, HTML, Communication"
            )
            projects = st.text_area("Projects", placeholder="Describe projects")
            certs = st.text_input(
                "Certifications", placeholder="Python certificate, AWS..."
            )
            submitted = st.form_submit_button(
                "➕ Add student", type="primary", use_container_width=True
            )

        if submitted:
            if not all([roll.strip(), name.strip(), dept, email.strip()]):
                st.error("Please fill in all required fields.")
            elif "@" not in email or "." not in email:
                st.error("Please enter a valid email address.")
            else:
                try:
                    execute_sql("""
                        INSERT INTO students
                        (roll_no, name, department, year, cgpa, email,
                         skills, projects, certifications)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        roll.strip(), name.strip(), dept, year,
                        cgpa, email.strip(), skills, projects, certs
                    ))
                    st.success("Student added successfully!")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("This roll number already exists.")

    with edit_tab:
        if students.empty:
            st.info("Add a student before editing.")
        else:
            selected_roll = st.selectbox(
                "Choose student",
                students["roll_no"].tolist(),
                format_func=lambda r: (
                    f"{r} — {students.loc[students['roll_no'] == r, 'name'].iloc[0]}"
                )
            )
            student = get_student(selected_roll)
            with st.form("edit_student_form"):
                c1, c2 = st.columns(2)
                new_name = c1.text_input("Full name", value=clean_text(student["name"]))
                depts = ["CSE", "IT", "ECE", "EEE", "Mechanical",
                         "Civil", "AI & ML", "Data Science", "Other"]
                old_dept = clean_text(student["department"])
                dept_index = depts.index(old_dept) if old_dept in depts else 0
                new_dept = c2.selectbox("Department", depts, index=dept_index)
                new_year = c1.selectbox(
                    "Academic year", [1, 2, 3, 4],
                    index=max(0, min(3, int(student["year"]) - 1))
                )
                new_cgpa = c2.number_input(
                    "CGPA", min_value=0.0, max_value=10.0,
                    value=float(student["cgpa"]), step=0.1
                )
                new_email = c1.text_input("Email", value=clean_text(student["email"]))
                new_skills = c2.text_input(
                    "Skills", value=clean_text(student.get("skills", ""))
                )
                new_projects = st.text_area(
                    "Projects", value=clean_text(student.get("projects", ""))
                )
                new_certs = st.text_input(
                    "Certifications",
                    value=clean_text(student.get("certifications", ""))
                )
                save_student = st.form_submit_button(
                    "💾 Save changes", type="primary"
                )

            if save_student:
                if not new_name.strip() or not new_email.strip():
                    st.error("Name and email cannot be empty.")
                else:
                    execute_sql("""
                        UPDATE students
                        SET name=?, department=?, year=?, cgpa=?, email=?,
                            skills=?, projects=?, certifications=?
                        WHERE roll_no=?
                    """, (
                        new_name.strip(), new_dept, new_year, new_cgpa,
                        new_email.strip(), new_skills, new_projects,
                        new_certs, selected_roll
                    ))
                    st.success("Student profile updated.")
                    st.rerun()

    with bulk_tab:
        st.write("Upload a CSV containing at least these columns:")
        st.code("roll_no,name,department,year,cgpa,email")
        st.caption(
            "Optional columns: skills, projects, certifications. "
            "Existing roll numbers will be skipped."
        )
        uploaded = st.file_uploader(
            "Choose student CSV", type=["csv"], key="student_csv"
        )
        if uploaded:
            try:
                import_df = pd.read_csv(uploaded)
                import_df.columns = [
                    str(c).strip().lower().replace(" ", "_")
                    for c in import_df.columns
                ]
                required = {
                    "roll_no", "name", "department",
                    "year", "cgpa", "email"
                }
                missing = required - set(import_df.columns)
                if missing:
                    st.error("Missing columns: " + ", ".join(sorted(missing)))
                else:
                    st.dataframe(import_df.head(10), use_container_width=True)
                    if st.button("📥 Import students", type="primary"):
                        added, skipped = 0, 0
                        with get_connection() as conn:
                            for _, row in import_df.iterrows():
                                try:
                                    r = clean_text(row["roll_no"])
                                    n = clean_text(row["name"])
                                    e = clean_text(row["email"])
                                    y = int(row["year"])
                                    g = float(row["cgpa"])
                                    d = clean_text(row["department"])
                                    if (
                                        not r or not n or not e or "@" not in e
                                        or y not in [1, 2, 3, 4]
                                        or not 0 <= g <= 10
                                    ):
                                        skipped += 1
                                        continue
                                    conn.execute("""
                                        INSERT INTO students
                                        (roll_no, name, department, year, cgpa,
                                         email, skills, projects, certifications)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """, (
                                        r, n, d, y, g, e,
                                        clean_text(row.get("skills", "")),
                                        clean_text(row.get("projects", "")),
                                        clean_text(row.get("certifications", ""))
                                    ))
                                    added += 1
                                except (sqlite3.IntegrityError, ValueError, TypeError):
                                    skipped += 1
                        st.success(f"Imported: {added} | Skipped: {skipped}")
                        st.rerun()
            except Exception as exc:
                st.error(f"Could not read CSV: {exc}")

    with view_tab:
        search = st.text_input("Search by roll number, name, or department")
        display_students = students.copy()
        if search:
            mask = (
                display_students["roll_no"].astype(str).str.contains(search, case=False, na=False) |
                display_students["name"].astype(str).str.contains(search, case=False, na=False) |
                display_students["department"].astype(str).str.contains(search, case=False, na=False)
            )
            display_students = display_students[mask]

        st.dataframe(display_students, use_container_width=True, hide_index=True)
        if not display_students.empty:
            csv_download(display_students, "students.csv")
            delete_roll = st.selectbox(
                "Select a student to delete",
                display_students["roll_no"].tolist(),
                key="delete_student"
            )
            if st.button("🗑️ Delete student", type="secondary"):
                execute_sql(
                    "DELETE FROM students WHERE roll_no=?",
                    (delete_roll,)
                )
                st.success("Student deleted. Their linked applications are also removed.")
                st.rerun()


# -------------------- COMPANY MANAGEMENT -----------------

elif page == "🏢 Company Management":
    st.markdown('<div class="section-heading">🏢 Company Management</div>',
                unsafe_allow_html=True)
    st.write("Manage recruiters, job openings, eligibility, and required skills.")

    add_tab, edit_tab, view_tab = st.tabs([
        "➕ Add company", "✏️ Edit company", "🔎 View companies"
    ])

    with add_tab:
        with st.form("add_company_form", clear_on_submit=True):
            company_name = st.text_input("Company name *")
            role = st.text_input("Job role *")
            c1, c2 = st.columns(2)
            min_cgpa = c1.number_input(
                "Minimum CGPA", min_value=0.0, max_value=10.0,
                value=6.0, step=0.1
            )
            package = c2.number_input(
                "Package (LPA)", min_value=0.0, value=4.0, step=0.5
            )
            eligible_dept = st.text_input(
                "Eligible departments (comma-separated; All for everyone)",
                value="All"
            )
            openings = st.number_input(
                "Number of openings", min_value=1, value=1, step=1
            )
            deadline = st.date_input(
                "Application deadline",
                value=date.today() + timedelta(days=30)
            )
            required_skills = st.text_input(
                "Required skills", placeholder="Python, SQL, Communication"
            )
            description = st.text_area("Job description")
            add_company = st.form_submit_button(
                "🏢 Add company", type="primary", use_container_width=True
            )

        if add_company:
            if not company_name.strip() or not role.strip():
                st.error("Company name and job role are required.")
            else:
                execute_sql("""
                    INSERT INTO companies
                    (name, role, min_cgpa, eligible_department, package_lpa,
                     job_description, required_skills, application_deadline, openings)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    company_name.strip(), role.strip(), min_cgpa,
                    eligible_dept.strip() or "All", package, description,
                    required_skills, deadline.isoformat(), int(openings)
                ))
                st.success("Company opportunity added.")
                st.rerun()

    with edit_tab:
        if companies.empty:
            st.info("Add a company before editing.")
        else:
            company_ids = companies["id"].tolist()
            chosen_id = st.selectbox(
                "Choose company",
                company_ids,
                format_func=lambda i: (
                    f"{companies.loc[companies['id'] == i, 'name'].iloc[0]} — "
                    f"{companies.loc[companies['id'] == i, 'role'].iloc[0]}"
                )
            )
            comp = companies.loc[companies["id"] == chosen_id].iloc[0]
            with st.form("edit_company_form"):
                edit_name = st.text_input("Company name", value=clean_text(comp["name"]))
                edit_role = st.text_input("Job role", value=clean_text(comp["role"]))
                x1, x2 = st.columns(2)
                edit_min = x1.number_input(
                    "Minimum CGPA", 0.0, 10.0,
                    value=float(comp["min_cgpa"]), step=0.1
                )
                edit_package = x2.number_input(
                    "Package (LPA)", min_value=0.0,
                    value=float(comp["package_lpa"]), step=0.5
                )
                edit_dept = st.text_input(
                    "Eligible departments",
                    value=clean_text(comp["eligible_department"])
                )
                edit_openings = st.number_input(
                    "Openings", min_value=1,
                    value=max(1, int(comp.get("openings", 1) or 1))
                )
                old_deadline = clean_text(comp.get("application_deadline", ""))
                try:
                    deadline_value = date.fromisoformat(old_deadline)
                except ValueError:
                    deadline_value = date.today() + timedelta(days=30)
                edit_deadline = st.date_input(
                    "Deadline", value=deadline_value, key="edit_deadline"
                )
                edit_skills = st.text_input(
                    "Required skills", value=clean_text(comp.get("required_skills", ""))
                )
                edit_desc = st.text_area(
                    "Job description", value=clean_text(comp.get("job_description", ""))
                )
                save_company = st.form_submit_button(
                    "💾 Save company changes", type="primary"
                )

            if save_company:
                if not edit_name.strip() or not edit_role.strip():
                    st.error("Company name and role are required.")
                else:
                    execute_sql("""
                        UPDATE companies
                        SET name=?, role=?, min_cgpa=?, eligible_department=?,
                            package_lpa=?, job_description=?, required_skills=?,
                            application_deadline=?, openings=?
                        WHERE id=?
                    """, (
                        edit_name.strip(), edit_role.strip(), edit_min,
                        edit_dept.strip() or "All", edit_package, edit_desc,
                        edit_skills, edit_deadline.isoformat(),
                        int(edit_openings), int(chosen_id)
                    ))
                    st.success("Company details updated.")
                    st.rerun()

    with view_tab:
        if companies.empty:
            st.info("No company opportunities yet.")
        else:
            st.dataframe(companies, use_container_width=True, hide_index=True)
            csv_download(companies, "companies.csv")
            company_to_delete = st.selectbox(
                "Select a company to delete",
                companies["id"].tolist(),
                format_func=lambda i: (
                    f"{companies.loc[companies['id'] == i, 'name'].iloc[0]} — "
                    f"{companies.loc[companies['id'] == i, 'role'].iloc[0]}"
                )
            )
            if st.button("🗑️ Delete company"):
                execute_sql(
                    "DELETE FROM companies WHERE id=?",
                    (int(company_to_delete),)
                )
                st.success("Company deleted along with its linked applications.")
                st.rerun()


# -------------------- ELIGIBILITY CHECKER ----------------

elif page == "🎯 Eligibility Checker":
    st.markdown('<div class="section-heading">🎯 Eligibility Checker</div>',
                unsafe_allow_html=True)
    st.write("Find students who meet the academic and department requirements.")

    if students.empty or companies.empty:
        st.info("Add students and companies first.")
    else:
        selected_company_id = st.selectbox(
            "Select company opportunity",
            companies["id"].tolist(),
            format_func=lambda i: (
                f"{companies.loc[companies['id'] == i, 'name'].iloc[0]} — "
                f"{companies.loc[companies['id'] == i, 'role'].iloc[0]}"
            )
        )
        comp = companies.loc[companies["id"] == selected_company_id].iloc[0]
        st.markdown(f"### 🏢 {comp['name']} — {comp['role']}")
        a, b, c = st.columns(3)
        a.metric("Minimum CGPA", f"{float(comp['min_cgpa']):.1f}")
        b.metric("Package", f"₹{float(comp['package_lpa']):.1f} LPA")
        c.metric("Openings", int(comp.get("openings", 1) or 1))

        eligible_depts = [
            d.strip().lower()
            for d in clean_text(comp["eligible_department"]).split(",")
            if d.strip()
        ]
        all_departments = not eligible_depts or "all" in eligible_depts

        eligible = students[
            students["cgpa"].astype(float) >= float(comp["min_cgpa"])
        ].copy()

        if not all_departments:
            eligible = eligible[
                eligible["department"].astype(str).str.lower().isin(eligible_depts)
            ]

        st.success(f"🎉 {len(eligible)} eligible student(s) found.")
        if eligible.empty:
            st.warning("No students currently meet this opportunity's requirements.")
        else:
            st.dataframe(
                eligible[[
                    "roll_no", "name", "department", "year",
                    "cgpa", "email", "skills"
                ]],
                use_container_width=True,
                hide_index=True
            )
            csv_download(eligible, "eligible_students.csv")

        with st.expander("ℹ️ How eligibility is calculated"):
            st.write(
                "Students must meet the minimum CGPA and belong to an eligible "
                "department. A company with department set to 'All' accepts "
                "students from every department. Always verify the official job "
                "criteria before applying."
            )


# -------------------- JOB RECOMMENDATIONS ----------------

elif page == "💡 Job Recommendations":
    st.markdown('<div class="section-heading">💡 Job Recommendations</div>',
                unsafe_allow_html=True)
    st.write("Find opportunities that may fit a student's CGPA, department, and skills.")

    if students.empty or companies.empty:
        st.info("Add student profiles and company opportunities first.")
    else:
        selected_roll = st.selectbox(
            "Select student",
            students["roll_no"].tolist(),
            format_func=lambda r: (
                f"{r} — {students.loc[students['roll_no'] == r, 'name'].iloc[0]}"
            )
        )
        stu = get_student(selected_roll)
        stu_skills = skills_set(stu.get("skills", ""))
        st.markdown(
            f"### 👋 {stu['name']}  \n"
            f"Department: **{stu['department']}** · CGPA: **{float(stu['cgpa']):.2f}**"
        )

        results = []
        for _, comp in companies.iterrows():
            depts = [
                d.strip().lower()
                for d in clean_text(comp["eligible_department"]).split(",")
                if d.strip()
            ]
            dept_ok = (
                not depts or "all" in depts
                or str(stu["department"]).lower() in depts
            )
            cgpa_ok = float(stu["cgpa"]) >= float(comp["min_cgpa"])
            needed = skills_set(comp.get("required_skills", ""))
            matched = stu_skills & needed
            skill_score = (
                len(matched) / len(needed) * 100 if needed else 100
            )
            overall_score = (
                (50 if cgpa_ok else 0)
                + (25 if dept_ok else 0)
                + (25 * skill_score / 100)
            )
            results.append({
                "Company": comp["name"],
                "Role": comp["role"],
                "Package (LPA)": comp["package_lpa"],
                "Minimum CGPA": comp["min_cgpa"],
                "Eligible by CGPA": "Yes" if cgpa_ok else "No",
                "Eligible by department": "Yes" if dept_ok else "No",
                "Matched skills": ", ".join(sorted(matched)) or "None",
                "Skill match (%)": round(skill_score, 1),
                "Match score (%)": round(overall_score, 1)
            })

        recs = pd.DataFrame(results).sort_values(
            "Match score (%)", ascending=False
        )
        st.caption(
            "Match score is a simple guidance score, not a hiring prediction "
            "or a guarantee of eligibility."
        )
        st.dataframe(recs, use_container_width=True, hide_index=True)
        csv_download(recs, "job_recommendations.csv")

        st.markdown("### 🚀 Suggested next steps")
        if not stu_skills:
            st.info("Add the student's skills in Student Management to improve matching.")
        else:
            st.write("Consider adding projects and certifications to strengthen the profile.")
        st.write("Review each official job description before applying.")


# -------------------- PLACEMENT TRACKING -----------------

elif page == "📋 Placement Tracking":
    st.markdown('<div class="section-heading">📋 Placement Tracking</div>',
                unsafe_allow_html=True)
    st.write("Record applications, update progress, and schedule interviews.")

    add_tab, update_tab, view_tab = st.tabs([
        "➕ New application", "🗓️ Update / schedule", "📄 Applications"
    ])

    with add_tab:
        if students.empty or companies.empty:
            st.info("Add at least one student and one company first.")
        else:
            with st.form("add_placement_form", clear_on_submit=True):
                roll = st.selectbox(
                    "Student",
                    students["roll_no"].tolist(),
                    format_func=lambda r: (
                        f"{r} — {students.loc[students['roll_no'] == r, 'name'].iloc[0]}"
                    )
                )
                company_id = st.selectbox(
                    "Company",
                    companies["id"].tolist(),
                    format_func=lambda i: (
                        f"{companies.loc[companies['id'] == i, 'name'].iloc[0]} — "
                        f"{companies.loc[companies['id'] == i, 'role'].iloc[0]}"
                    )
                )
                app_date = st.date_input("Application date", value=date.today())
                add_app = st.form_submit_button(
                    "📨 Add application", type="primary"
                )

            if add_app:
                try:
                    execute_sql("""
                        INSERT INTO placements
                        (roll_no, company_id, status, application_date)
                        VALUES (?, ?, 'Applied', ?)
                    """, (roll, int(company_id), app_date.isoformat()))
                    st.success("Application added.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.warning("This student already has an application for this company.")

    with update_tab:
        if placements.empty:
            st.info("Create an application before updating it.")
        else:
            app_id = st.selectbox(
                "Choose application",
                placements["id"].tolist(),
                format_func=lambda i: (
                    f"#{i} — "
                    f"{placements.loc[placements['id'] == i, 'student_name'].iloc[0]} / "
                    f"{placements.loc[placements['id'] == i, 'company_name'].iloc[0]}"
                )
            )
            app_row = placements.loc[placements["id"] == app_id].iloc[0]
            statuses = ["Applied", "Interview", "Selected", "Rejected"]
            status_index = (
                statuses.index(app_row["status"])
                if app_row["status"] in statuses else 0
            )
            with st.form("update_application_form"):
                new_status = st.selectbox(
                    "Application status", statuses, index=status_index
                )
                current_date = clean_text(app_row.get("interview_date", ""))
                try:
                    interview_date_value = date.fromisoformat(current_date)
                except ValueError:
                    interview_date_value = date.today() + timedelta(days=1)
                schedule_date = st.date_input(
                    "Interview date", value=interview_date_value
                )
                interview_time = st.text_input(
                    "Interview time (e.g. 10:30 AM)",
                    value=clean_text(app_row.get("interview_time", ""))
                )
                interview_round = st.selectbox(
                    "Interview round",
                    ["Not scheduled", "Aptitude Test", "Coding Test",
                     "Technical Interview", "HR Interview", "Group Discussion",
                     "Final Interview", "Other"],
                    index=(
                        ["Not scheduled", "Aptitude Test", "Coding Test",
                         "Technical Interview", "HR Interview", "Group Discussion",
                         "Final Interview", "Other"].index(
                            clean_text(app_row.get("interview_round", ""))
                        )
                        if clean_text(app_row.get("interview_round", "")) in
                        ["Not scheduled", "Aptitude Test", "Coding Test",
                         "Technical Interview", "HR Interview", "Group Discussion",
                         "Final Interview", "Other"] else 0
                    )
                )
                interview_notes = st.text_area(
                    "Interview notes",
                    value=clean_text(app_row.get("interview_notes", "")),
                    placeholder="Venue/link, preparation notes, contact details..."
                )
                save_app = st.form_submit_button(
                    "💾 Save application", type="primary"
                )

            if save_app:
                actual_date = (
                    "" if interview_round == "Not scheduled"
                    else schedule_date.isoformat()
                )
                actual_time = (
                    "" if interview_round == "Not scheduled"
                    else interview_time.strip()
                )
                actual_round = (
                    "" if interview_round == "Not scheduled"
                    else interview_round
                )
                execute_sql("""
                    UPDATE placements
                    SET status=?, interview_date=?, interview_time=?,
                        interview_round=?, interview_notes=?
                    WHERE id=?
                """, (
                    new_status, actual_date, actual_time,
                    actual_round, interview_notes, int(app_id)
                ))
                st.success("Application and interview details updated.")
                st.rerun()

    with view_tab:
        if placements.empty:
            st.info("No applications have been recorded.")
        else:
            filter_status = st.selectbox(
                "Filter by status",
                ["All", "Applied", "Interview", "Selected", "Rejected"]
            )
            display_apps = placements.copy()
            if filter_status != "All":
                display_apps = display_apps[
                    display_apps["status"] == filter_status
                ]
            st.dataframe(
                display_apps[[
                    "id", "student_name", "roll_no", "company_name",
                    "role", "status", "application_date", "interview_date",
                    "interview_time", "interview_round", "interview_notes"
                ]],
                use_container_width=True,
                hide_index=True
            )
            csv_download(display_apps, "placement_applications.csv")
            delete_app_id = st.selectbox(
                "Select application to delete",
                display_apps["id"].tolist(),
                format_func=lambda i: (
                    f"#{i} — "
                    f"{display_apps.loc[display_apps['id'] == i, 'student_name'].iloc[0]} / "
                    f"{display_apps.loc[display_apps['id'] == i, 'company_name'].iloc[0]}"
                ),
                key="delete_app_id"
            )
            if st.button("🗑️ Delete application"):
                execute_sql("DELETE FROM placements WHERE id=?", (int(delete_app_id),))
                st.success("Application deleted.")
                st.rerun()


# -------------------- REPORTS & ANALYTICS ----------------

elif page == "📊 Reports & Analytics":
    st.markdown('<div class="section-heading">📊 Reports & Analytics</div>',
                unsafe_allow_html=True)
    st.write("Review academic performance and placement outcomes.")

    if students.empty:
        st.info("Add student records to begin analyzing performance.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Average CGPA", f"{students['cgpa'].mean():.2f}")
        c2.metric("Highest CGPA", f"{students['cgpa'].max():.2f}")
        c3.metric("Students", len(students))

        st.markdown("### 🏫 Department performance")
        dept_report = (
            students.groupby("department")
            .agg(
                Students=("roll_no", "count"),
                Average_CGPA=("cgpa", "mean"),
                Highest_CGPA=("cgpa", "max")
            )
            .reset_index()
        )
        dept_report["Average_CGPA"] = dept_report["Average_CGPA"].round(2)
        dept_report["Highest_CGPA"] = dept_report["Highest_CGPA"].round(2)
        st.dataframe(dept_report, use_container_width=True, hide_index=True)
        fig = px.bar(
            dept_report, x="department", y="Average_CGPA",
            color="department", title="Average CGPA by department",
            range_y=[0, 10]
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        csv_download(dept_report, "department_performance.csv")

        st.markdown("### 🏆 Top-performing students")
        top_n = st.slider("Number of students to display", 3, 20, 10)
        top_students = students.sort_values(
            "cgpa", ascending=False
        ).head(top_n)
        st.dataframe(
            top_students[[
                "roll_no", "name", "department", "year", "cgpa", "email"
            ]],
            use_container_width=True,
            hide_index=True
        )
        csv_download(top_students, "top_students.csv")

    st.markdown("### 💼 Placement outcomes")
    if placements.empty:
        st.info("Add applications to calculate placement outcomes.")
    else:
        total = len(placements)
        selected_count = int((placements["status"] == "Selected").sum())
        interview_count = int((placements["status"] == "Interview").sum())
        rate = selected_count / total * 100 if total else 0

        a, b, c = st.columns(3)
        a.metric("Applications", total)
        b.metric("Selected applications", selected_count)
        c.metric("Selection rate", f"{rate:.1f}%")

        selected_df = placements[placements["status"] == "Selected"]
        if not selected_df.empty:
            packages = pd.to_numeric(
                selected_df["package_lpa"], errors="coerce"
            ).dropna()
            if not packages.empty:
                x, y = st.columns(2)
                x.metric("Average selected package", f"{packages.mean():.2f} LPA")
                y.metric("Highest selected package", f"{packages.max():.2f} LPA")
        st.caption(
            "Selection rate here means selected applications divided by all "
            "recorded applications; it is not the percentage of unique students selected."
        )

        company_report = (
            placements.groupby(["company_name", "role", "package_lpa"])
            .agg(
                Applications=("id", "count"),
                Selected=("status", lambda s: int((s == "Selected").sum()))
            )
            .reset_index()
        )
        st.dataframe(company_report, use_container_width=True, hide_index=True)
        csv_download(company_report, "company_placement_report.csv")


# -------------------- RESUME BUILDER ---------------------

elif page == "📝 Resume Builder":
    st.markdown('<div class="section-heading">📝 Student Resume Builder</div>',
                unsafe_allow_html=True)
    st.write("Create a simple text-based resume using a student profile.")

    if students.empty:
        st.info("Add a student profile first.")
    else:
        roll = st.selectbox(
            "Select student",
            students["roll_no"].tolist(),
            format_func=lambda r: (
                f"{r} — {students.loc[students['roll_no'] == r, 'name'].iloc[0]}"
            )
        )
        stu = get_student(roll)
        objective = st.text_area(
            "Career objective",
            value="Motivated student seeking an opportunity to apply technical skills and contribute to a professional team."
        )
        phone = st.text_input("Phone number (optional)")
        linkedin = st.text_input("LinkedIn URL (optional)")
        github = st.text_input("GitHub URL (optional)")
        extra_projects = st.text_area(
            "Additional project details (optional)",
            value=clean_text(stu.get("projects", ""))
        )

        resume_text = f"""
{stu['name'].upper()}
Email: {stu['email']}
Phone: {phone}
LinkedIn: {linkedin}
GitHub: {github}

CAREER OBJECTIVE
{objective}

EDUCATION
Department: {stu['department']}
Academic Year: {stu['year']}
CGPA: {float(stu['cgpa']):.2f}/10

TECHNICAL SKILLS
{clean_text(stu.get('skills', 'Add your skills in Student Management'))}

PROJECTS
{extra_projects or 'Add your project details here.'}

CERTIFICATIONS
{clean_text(stu.get('certifications', 'Add your certifications here.'))}

IMPORTANT
Review all details before sending this resume to a recruiter.
"""
        st.markdown("### 👀 Resume preview")
        st.code(resume_text, language="text")
        st.download_button(
            "⬇️ Download resume as TXT",
            data=resume_text.encode("utf-8"),
            file_name=f"{roll}_resume.txt",
            mime="text/plain",
            type="primary"
        )
        st.caption("This is a basic text resume, not a professionally formatted PDF.")


# -------------------- PREPARATION QUIZ -------------------

elif page == "💻 Preparation Quiz":
    st.markdown('<div class="section-heading">💻 Placement Preparation Quiz</div>',
                unsafe_allow_html=True)
    st.write("Practice common Python, SQL, and interview fundamentals.")

    quiz_bank = {
        "Python": [
            ("Which keyword defines a function in Python?",
             ["func", "def", "function", "make"], 1),
            ("Which data type stores key-value pairs?",
             ["List", "Tuple", "Dictionary", "Set"], 2),
            ("What does len([1, 2, 3]) return?",
             ["2", "3", "4", "Error"], 1),
            ("Which symbol starts a Python comment?",
             ["//", "/*", "#", "--"], 2),
            ("Which type is immutable?",
             ["List", "Dictionary", "Set", "Tuple"], 3)
        ],
        "SQL": [
            ("Which SQL command retrieves data?",
             ["GET", "SELECT", "OPEN", "FETCH ALL"], 1),
            ("Which clause filters rows?",
             ["ORDER BY", "GROUP BY", "WHERE", "JOIN"], 2),
            ("Which key uniquely identifies a row?",
             ["Foreign key", "Primary key", "Duplicate key", "Sort key"], 1),
            ("Which command adds a new row?",
             ["INSERT", "UPDATE", "ALTER", "SELECT"], 0),
            ("Which function counts rows?",
             ["SUM()", "TOTAL()", "COUNT()", "NUMBER()"], 2)
        ],
        "Interview Basics": [
            ("What is a good first step before an interview?",
             ["Ignore the job description", "Research the company",
              "Arrive unprepared", "Avoid questions"], 1),
            ("Which is a useful teamwork skill?",
             ["Communication", "Interrupting", "Blaming", "Ignoring feedback"], 0),
            ("How should you answer a question you do not know?",
             ["Invent facts", "Stay honest and explain your thinking",
              "Leave immediately", "Criticize the question"], 1),
            ("What should a resume contain?",
             ["Relevant skills and experience", "Passwords",
              "Unrelated personal secrets", "False qualifications"], 0),
            ("What is useful after an interview?",
             ["Reflect on your answers", "Forget all feedback",
              "Share confidential questions publicly", "Never improve"], 0)
        ]
    }

    topic = st.selectbox("Choose a topic", list(quiz_bank.keys()))
    questions = quiz_bank[topic]

    with st.form(f"quiz_form_{topic}"):
        answers = []
        for idx, (question, options, correct) in enumerate(questions):
            answer = st.radio(
                f"{idx + 1}. {question}",
                options,
                index=None,
                key=f"{topic}_{idx}"
            )
            answers.append(answer)
        submitted = st.form_submit_button("✅ Submit quiz", type="primary")

    if submitted:
        score = 0
        for idx, answer in enumerate(answers):
            q, options, correct = questions[idx]
            if answer == options[correct]:
                score += 1

        st.markdown("### 📊 Your result")
        st.metric("Score", f"{score}/{len(questions)}")
        st.progress(score / len(questions))
        if score == len(questions):
            st.success("Excellent work! You answered every question correctly.")
        elif score >= len(questions) * 0.6:
            st.info("Good effort! Review the answers below and keep practicing.")
        else:
            st.warning("Keep learning and try again. Practice improves confidence.")

        with st.expander("📖 Review answers"):
            for idx, (q, options, correct) in enumerate(questions):
                st.write(f"**{idx + 1}. {q}**")
                st.write(f"Correct answer: {options[correct]}")
                st.write(
                    "Your answer: " +
                    (answers[idx] if answers[idx] is not None else "Not answered")
                )


# -------------------- NOTIFICATIONS ---------------------

elif page == "🔔 Notifications":
    st.markdown('<div class="section-heading">🔔 Placement Notifications</div>',
                unsafe_allow_html=True)
    st.write("Review application deadlines and upcoming interviews.")

    today = date.today()
    deadlines = []

    for _, comp in companies.iterrows():
        deadline_text = clean_text(comp.get("application_deadline", ""))
        if deadline_text:
            try:
                deadline_date = date.fromisoformat(deadline_text)
                days_left = (deadline_date - today).days
                if days_left >= 0:
                    deadlines.append({
                        "Company": comp["name"],
                        "Role": comp["role"],
                        "Deadline": deadline_text,
                        "Days remaining": days_left,
                        "Package (LPA)": comp["package_lpa"]
                    })
            except ValueError:
                pass

    st.markdown("### ⏰ Application deadlines")
    if deadlines:
        deadline_df = pd.DataFrame(deadlines).sort_values("Days remaining")
        st.dataframe(deadline_df, use_container_width=True, hide_index=True)
        urgent = deadline_df[deadline_df["Days remaining"] <= 7]
        if not urgent.empty:
            st.warning(
                f"{len(urgent)} opportunity deadline(s) are within the next 7 days."
            )
    else:
        st.info("No future deadlines are currently recorded.")

    st.markdown("### 🗓️ Upcoming interviews")
    if placements.empty:
        st.info("No applications or interviews have been recorded.")
    else:
        interview_df = placements[
            (placements["status"] == "Interview") &
            (placements["interview_date"].fillna("") >= today.isoformat()) &
            (placements["interview_date"].fillna("") != "")
        ].copy()

        if interview_df.empty:
            st.info("No upcoming interviews are scheduled.")
        else:
            interview_df = interview_df.sort_values(
                ["interview_date", "interview_time"]
            )
            st.dataframe(
                interview_df[[
                    "student_name", "roll_no", "company_name", "role",
                    "interview_date", "interview_time", "interview_round",
                    "interview_notes"
                ]],
                use_container_width=True,
                hide_index=True
            )

    st.caption(
        "These are in-app reminders shown when you open this page. "
        "They do not send email, SMS, or push notifications."
    )


# -------------------- FOOTER -----------------------------

st.markdown("---")
st.markdown(
    "<p style='text-align:center;color:#777;font-size:12px;'>"
    "🎓 CampusConnect · College Placement Management System · "
    "Built with Python, Streamlit, SQLite, Pandas & Plotly"
    "</p>",
    unsafe_allow_html=True
)