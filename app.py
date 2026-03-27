import streamlit as st
import pandas as pd
import json
from io import BytesIO
import re

st.set_page_config(page_title="BESS Energy - Financial Tool", layout="wide")

# --- 1. ΑΣΦΑΛΗΣ ΛΟΓΙΚΗ SESSION STATE ---
defaults = {
    "customer": "Client_Name", "p_mw": 20.0, "c_mwh": 40.0, "b_dur": 0,
    "dod_val": 95.0, "rte_val": 86.0, "avail_val": 99.0,
    "b_cost": 4000000.0, "bop_cost": 1000000.0, "years": 10,
    "ltv_val": 80, "int_rate": 6.0, "f_scen": "Tolling Agreement",
    "f_years": 5, "f_fee": 47000.0, "pshare_val": 50
}

for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# Συναρτήσεις Μορφοποίησης
def fmt_num(x, is_euro=True):
    if pd.isna(x) or isinstance(x, str): return x
    formatted = "{:,.2f}".format(x).replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{formatted} €" if is_euro else formatted

def to_excel(df_fin, df_inputs, df_loan):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_fin.to_excel(writer, index=False, sheet_name='Financial_Model')
        df_inputs.to_excel(writer, index=False, sheet_name='Project_Data')
        df_loan.to_excel(writer, index=False, sheet_name='Loan_Schedule')
    return output.getvalue()

# --- HEADER & BRANDING ---
col_logo, col_title = st.columns([1, 4])
with col_logo:
    st.image("https://bessenergy.gr/wp-content/uploads/2026/02/cropped-logo-bess-energy-2026.jpeg", width=150)
with col_title:
    st.title("🔋 BESS Financial Analysis Platform")
    st.markdown("##### Μια εφαρμογή της **BESS ENERGY**, GOTION Authorized Distributor")

tabs = st.tabs(["Main Model", "Loan Schedule", "Manual & Instructions"])

# --- TAB 3: MANUAL (ΑΚΡΙΒΕΣ ΚΕΙΜΕΝΟ) ---
with tabs[2]:
    st.header("📘 Ανάλυση Μοντέλου BESS")
    st.markdown("""
    ### 1. Δεδομένα Εισαγωγής (Inputs)
    * **Ετη Δανείου:** ο αριθμός των ετών του δανείου.
    * **Ισχύς Έργου (MW):** Η ονομαστική ισχύς σύνδεσης του συστήματος στο δίκτυο.
    * **Χωρητικότητα (MWh):** Η συνολική ενέργεια που μπορεί να αποθηκεύσει η μπαταρία.
    * **Βάθος Εκφόρτισης (DoD %):** Το ποσοστό της χωρητικότητας που χρησιμοποιούμε (π.χ. 95%), ώστε να προστατεύεται η διάρκεια ζωής της μπαταρίας.
    * **Απόδοση Συστήματος (RTE %):** Το Round Trip Efficiency. Δείχνει την απώλεια ενέργειας κατά τη μετατροπή (AC-DC-AC). Ένας συντελεστής 86% σημαίνει ότι για κάθε 100 μονάδες ενέργειας που απορροφούμε, επιστρέφουμε 86.
    * **Ετήσια Πτώση Απόδοσης (Degradation %):** Η φυσιολογική μείωση της χωρητικότητας της μπαταρίας χρόνο με το χρόνο.
    * **Διαθεσιμότητα Συστήματος (Availability %):** Το ποσοστό των ημερών του έτους που το σύστημα είναι διαθέσιμο για λειτουργία, αφαιρώντας τις ημέρες συντήρησης ή βλαβών (π.χ. 354 ημέρες αντί για 365).
    * **Ημερήσια Ενέργεια (MWh):** Η καθαρή ενέργεια που εκφορτίζεται σε μία ημέρα. 👉 Πράξη: *Χωρητικότητα × DoD × Κύκλοι*.
    * **Ετήσια Ενέργεια Έτους 1 (MWh):** Η συνολική ενέργεια που θα πουληθεί κατά τον πρώτο χρόνο λειτουργίας. 👉 Πράξη: *Ημερήσια Ενέργεια × 365 ημέρες*.
    * **Ετήσια Έξοδα O&M (€/MW):** Τα ετήσια σταθερά έξοδα Λειτουργίας και Συντήρησης (Operation & Maintenance) ανά μονάδα ισχύος.

    ### 2. Οικονομικά Στοιχεία Επένδυσης (CAPEX)
    * **Κόστος Εξοπλισμού Μπαταριών (€):** Το καθαρό κόστος αγοράς των μονάδων αποθήκευσης (καρφωτή τιμή).
    * **Λοιπό Κόστος (EPC, Άδειες κλπ) (€):** Το κόστος για ηλεκτρολογικά, υποσταθμούς, κατασκευή και αδειοδότηση.
    * **Συνολικό CAPEX Επένδυσης (€):** Το άθροισμα των δύο παραπάνω. Είναι το συνολικό κεφάλαιο που απαιτείται για την υλοποίηση.

    ### 3. Μεταβλητές Παράμετροι ανά Έτος (Dynamic Annual Table)
    * **Προβλεπόμενη Τιμή Πώλησης (€/MWh):** Η εκτιμώμενη τιμή εσόδων ανά έτος.
    * **Προβλεπόμενη Τιμή Αγοράς (€/MWh):** Το κόστος φόρτισης ανά έτος.
    * **Κύκλοι ανά Ημέρα (Μεταβαλλόμενοι):** Πρόβλεψη της χρήσης της μπαταρίας ανά έτος (π.χ. μείωση κύκλων όσο παλαιώνει η μονάδα).

    ### 4. Ανάλυση Πίνακα 10ετίας (Operational Table)
    Ο πίνακας αυτός υπολογίζει τη ροή χρήματος ανά έτος, λαμβάνοντας υπόψη τη γήρανση της μπαταρίας:
    * **Έτος:** Η χρονική περίοδος (1-10 έτη).
    * **Διαθέσιμη Χωρητικότητα (MWh):** Η χωρητικότητα κάθε έτους μειωμένη κατά το Degradation.
    * **Ετήσια Ενέργεια (MWh):** Η συνολική ενέργεια που εκφορτίζει (πουλάει) το σύστημα ετησίως. 👉 Πράξη: *Χωρητικότητα × DoD × Κύκλοι × 365 ημέρες*.
    * **Ετήσια Έσοδα (€):** Η αξία της ενέργειας που πωλήθηκε. 👉 Πράξη: *Ετήσια Ενέργεια × Προβλεπόμενη Τιμή Πώλησης (ανά έτος).*
    * **Ενέργεια Φόρτισης (MWh):** Η ενέργεια που απορρόφησε το σύστημα από το δίκτυο για να γεμίσει. 👉 Πράξη: *Ετήσια Ενέργεια / RTE (περιλαμβάνει τις απώλειες).*
    * **Συνολικό Κόστος Αγοράς (€):** Το κόστος της ενέργειας που αγοράστηκε για τη φόρτιση. 👉 Πράξη: *Ενέργεια Φόρτισης × Προβλεπόμενη Τιμή Αγοράς (ανά έτος).*
    * **Μικτό Κέρδος (€):** Η διαφορά μεταξύ πωλήσεων και κόστους αγοράς ενέργειας (το spread).
    * **Έξοδα Λειτουργίας O&M (€):** Σταθερά ετήσια έξοδα (συντήρηση, ασφάλιστρα, τηλεπικοινωνίες).
    * **EBITDA (€):** Τα καθαρά λειτουργικά κέρδη προ τόκων, φόρων και αποσβέσεων.

    ### 5. Δείκτες Απόδοσης
    * **Μέσο Ετήσιο EBITDA (€):** Ο μέσος όρος των κερδών στη 10ετία.
    * **Χρόνια Απόσβεσης (Payback Years):** Ο χρόνος που απαιτείται για να καλύψει το EBITDA το αρχικό CAPEX. 👉 Πράξη: *Συνολικό CAPEX / Μέσο Ετήσιο EBITDA.*
    """)

# --- TAB 1: MAIN MODEL ---
with tabs[0]:
    with st.expander("📂 Restore Project / Load Backup"):
        up = st.file_uploader("Επιλέξτε το αρχείο JSON", type="json")
        if up is not None:
            try:
                data = json.load(up)
                for k, v in data.items(): st.session_state[k] = v
                st.success("Τα δεδομένα φορτώθηκαν! Κάντε κλικ οπουδήποτε για ανανέωση.")
            except Exception as e: st.error(f"Σφάλμα: {e}")

    st.subheader("📋 Βασικά Δεδομένα Έργου & CAPEX")
    cust_name = st.text_input("Customer Name:", key="customer")
    clean_name = re.sub(r'\W+', '', cust_name.replace(" ", "_"))

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        p_mw = st.number_input("Power (MW)", key="p_mw")
        c_mwh = st.number_input("Capacity (MWh)", key="c_mwh")
        b_duration = st.selectbox("Duration (Hours)", [2, 3, 4, 5], key="b_dur")
    with c2:
        dod_input = st.number_input("DoD (%)", key="dod_val") / 100
        rte_input = st.number_input("RTE (%)", key="rte_val") / 100
        avail_input = st.number_input("Availability (%)", key="avail_val") / 100
    with c3:
        b_cost = st.number_input("Battery Cost (€)", key="b_cost")
        bop_cost = st.number_input("BoP Cost (€)", key="bop_cost")
        l_years = st.number_input("Loan Duration (Years)", min_value=1, key="years")
    with c4:
        total_capex = b_cost + bop_cost
        st.metric("Συνολικό CAPEX (€)", fmt_num(total_capex))
        ltv = st.slider("LTV (%)", 0, 100, key="ltv_val") / 100
        int_rate = st.number_input("Interest Rate (%)", key="int_rate") / 100

    st.divider()
    st.subheader("🤝 Συμφωνία ΦΟΣΕ")
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        fose_scenario = st.radio("Πρόγραμμα", ["Tolling Agreement", "Floor + Profit Sharing"], key="f_scen")
        fose_contract_years = st.number_input("Σύμβαση (Έτη)", min_value=1, key="f_years")
    with col_f2:
        fose_fee_mw = st.number_input("Fee (€/MW/Year)", key="f_fee")
    with col_f3:
        p_share_val = st.slider("Investor Profit Share %", 0, 100, key="pshare_val")

    # --- ANNUAL DATA ---
    st.divider()
    st.subheader(f"Annual Parameters (1 to {l_years} years)")
    deg_l, cyc_l, sell_l, buy_l, om_l = [], [], [], [], []
    
    for i in range(l_years):
        for prefix, d_val in [("deg", 1.5), ("cyc", 1.5), ("om", 5000.0), ("s", 100.0), ("b", 40.0)]:
            key = f"{prefix}_{i}"
            if key not in st.session_state: st.session_state[key] = d_val

    p_cols = st.columns(5)
    for i in range(l_years):
        with p_cols[i % 5]:
            with st.expander(f"Yr {i+1}", expanded=(i==0)):
                deg_l.append(st.number_input(f"Deg % Y{i+1}", key=f"deg_{i}")/100)
                cyc_l.append(st.number_input(f"Cyc Y{i+1}", key=f"cyc_{i}"))
                sell_l.append(st.number_input(f"Sell € Y{i+1}", key=f"s_{i}"))
                buy_l.append(st.number_input(f"Buy € Y{i+1}", key=f"b_{i}"))
                om_l.append(st.number_input(f"O&M € Y{i+1}", key=f"om_{i}"))

    # --- CALCULATIONS ---
    loan_amt = total_capex * ltv
    m_rate = (int_rate/100) / 12
    m_total = int(l_years * 12)
    m_principal = loan_amt / m_total
    c_bal = loan_amt
    loan_data, annual_debt = [], []
    for m in range(m_total):
        interest = c_bal * m_rate
        loan_data.append({"Μήνας": m+1, "Δόση Κεφαλαίου": m_principal, "Τόκοι": interest, "Σύνολο Δόσης": m_principal+interest, "Υπόλοιπο": max(0, c_bal-m_principal)})
        c_bal -= m_principal
    df_loan_full = pd.DataFrame(loan_data)
    for y in range(l_years): annual_debt.append(df_loan_full.iloc[y*12:(y+1)*12]["Σύνολο Δόσης"].sum())

    res_tech, res_fin = [], []
    curr_cap = c_mwh
    for i in range(l_years):
        curr_cap *= (1 - deg_l[i])
        en_out = curr_cap * dod_input * cyc_l[i] * 365 * avail_input
        en_in = en_out / rte_input
        m_rev, m_cost = en_out * sell_l[i], en_in * buy_l[i]
        m_spread = m_rev - m_cost
        
        if i < fose_contract_years:
            if fose_scenario == "Tolling Agreement":
                final_rev, extra_p = fose_fee_mw * p_mw, 0
            else:
                floor = fose_fee_mw * p_mw
                extra_p = max(0, (m_spread - floor) * (p_share_val/100))
                final_rev = floor + extra_p
        else:
            final_rev, extra_p = m_spread, 0
            
        ebitda = final_rev - (om_l[i] * p_mw)
        res_tech.append({
            "Έτος": i+1, "Χωρητικότητα (MWh)": curr_cap, "Κύκλοι ανά Ημέρα": cyc_l[i],
            "Τιμή Πώλησης (€/MWh)": sell_l[i], "Τιμή Αγοράς (€/MWh)": buy_l[i],
            "Ετήσια Ενέργεια Out (MWh)": en_out, "Ενέργεια Φόρτισης In (MWh)": en_in
        })
        res_fin.append({
            "Έτος": i+1, "Μικτό Κέρδος Αγοράς": m_spread, "Σταθερό Έσοδο ΦΟΣΕ": fose_fee_mw * p_mw if i < fose_contract_years else 0,
            "Profit Share": extra_p, "EBITDA": ebitda, "Δόση Δανείου": annual_debt[i], "Cash Flow": ebitda - annual_debt[i]
        })

    st.divider()
    st.subheader(f"Financial Summary: {cust_name}")
    
    st.markdown("**1. Τεχνική Ανάλυση & Τιμές**")
    dt_tech = pd.DataFrame(res_tech)
    dt_tech["Χωρητικότητα (MWh)"] = dt_tech["Χωρητικότητα (MWh)"].apply(lambda x: fmt_num(x, False))
    dt_tech["Ετήσια Ενέργεια Out (MWh)"] = dt_tech["Ετήσια Ενέργεια Out (MWh)"].apply(lambda x: fmt_num(x, False))
    dt_tech["Ενέργεια Φόρτισης In (MWh)"] = dt_tech["Ενέργεια Φόρτισης In (MWh)"].apply(lambda x: fmt_num(x, False))
    for c in ["Τιμή Πώλησης (€/MWh)", "Τιμή Αγοράς (€/MWh)"]: dt_tech[c] = dt_tech[c].apply(fmt_num)
    st.dataframe(dt_tech, use_container_width=True)

    st.markdown("**2. Οικονομική Απόδοση**")
    dt_fin = pd.DataFrame(res_fin)
    for c in dt_fin.columns[1:]: dt_fin[c] = dt_fin[c].apply(fmt_num)
    st.dataframe(dt_fin, use_container_width=True)

    c_ex1, c_ex2 = st.columns(2)
    with c_ex1:
        full_df = pd.merge(pd.DataFrame(res_tech), pd.DataFrame(res_fin), on="Έτος")
        st.download_button("📥 Excel Export", data=to_excel(full_df, pd.DataFrame([{"CAPEX": total_capex}]), df_loan_full), file_name=f"{clean_name}.xlsx")
    with c_ex2:
        save_data = {k: v for k, v in st.session_state.items() if not k.startswith("FormSubmit")}
        st.download_button("💾 Save JSON", data=json.dumps(save_data), file_name=f"{clean_name}.json")

# --- TAB 2: LOAN SCHEDULE ---
with tabs[1]:
    st.subheader("Monthly Loan Amortization Schedule")
    df_l_disp = df_loan_full.copy()
    for col in ["Δόση Κεφαλαίου", "Τόκοι", "Σύνολο Δόσης", "Υπόλοιπο"]:
        df_l_disp[col] = df_l_disp[col].apply(fmt_num)
    st.dataframe(df_l_disp, use_container_width=True)