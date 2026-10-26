import streamlit as st
import requests
import pandas as pd

# Page config
st.set_page_config(page_title="AI-COS Dashboard", page_icon="🎓", layout="wide")
st.title("🎓 AI Campus Operating System (AI-COS)")
st.markdown("Top-Notch Intelligent Decision Support System for Campus Management")

BASE_URL = "http://127.0.0.1:8000/api/v1"

# Tabs for modules
tab1, tab2, tab3, tab4 = st.tabs([
    "📝 Exam Seating", 
    "📚 Prerequisite Analyzer", 
    "🍃 Green HVAC Scorer", 
    "🔐 Transcript Verifier"
])

# --- TAB 1: EXAM SEATING (CSP) ---
with tab1:
    st.header("Optimal Exam Seating Allocator (CSP)")
    col1, col2 = st.columns([1, 3])
    with col1:
        rows = st.number_input("Rows", min_value=2, max_value=10, value=4)
        cols = st.number_input("Columns", min_value=2, max_value=10, value=4)
        if st.button("Generate Seating Plan"):
            with st.spinner("Running MRV Heuristic..."):
                res = requests.get(f"{BASE_URL}/exam/seating", params={"rows": rows, "cols": cols})
                if res.status_code == 200:
                    data = res.json()
                    st.success(f"Status: {data['status']} | Zero Adjacent Conflicts")
                    
                    # Flatten the 2D grid for display
                    flat_data = []
                    for r, row_data in enumerate(data['matrix']):
                        for c, cell in enumerate(row_data):
                            if cell:
                                flat_data.append({
                                    "Seat": f"R{r+1}C{c+1}",
                                    "Roll No": cell['id'],
                                    "Branch": cell['branch'],
                                    "Paper": cell['paper']
                                })
                    st.dataframe(pd.DataFrame(flat_data), use_container_width=True)

# --- TAB 2: DAG PREREQUISITE ---
with tab2:
    st.header("Prerequisite Impact Analyzer (DAG)")
    course = st.selectbox("Select Course to Drop", ["CS101", "CS201", "CS301", "CS302", "CS401", "CS402"])
    if st.button("Analyze Impact"):
        res = requests.get(f"{BASE_URL}/academics/prereq-impact", params={"dropped": course})
        if res.status_code == 200:
            data = res.json()
            if data['risk_level'] == "CRITICAL":
                st.error(f"Risk Level: {data['risk_level']}")
            else:
                st.warning(f"Risk Level: {data['risk_level']}")
            
            st.write(f"**Dropped Course:** {data['target']}")
            st.write("**Cascading Blocked Courses:**")
            st.code("\n".join(data['cascading_blocks']))

# --- TAB 3: HVAC SCORER ---
with tab3:
    st.header("Campus Green HVAC Energy Scorer")
    if st.button("Calculate Savings"):
        res = requests.get(f"{BASE_URL}/facilities/energy-score")
        if res.status_code == 200:
            data = res.json()
            st.metric(label="Total Energy Saved (kWh)", value=f"{data['total_kwh_saved']} kWh")
            st.table(pd.DataFrame(data['zones']))

# --- TAB 4: TRANSCRIPT VERIFIER ---
with tab4:
    st.header("SHA-256 Digital Transcript Verifier")
    roll_input = st.text_input("Enter Student Roll Number", "2501331930010")
    if st.button("Verify Hash"):
        res = requests.get(f"{BASE_URL}/verify/transcript", params={"roll_no": roll_input})
        if res.status_code == 200:
            data = res.json()
            if data['authentic']:
                st.success("✅ Signature Verified & Authentic")
            st.json(data)
