import streamlit as st
import pandas as pd
import json
from io import BytesIO
import re

st.set_page_config(page_title="BESS Energy - Financial Tool", layout="wide")

# --- Συναρτήσεις Μορφοποίησης ---
def fmt_num(x, is_euro=True):
    if pd.isna(x): return ""
    formatted = "{:,.2f}".format(x).replace(",", "X").replace(".", ",").replace("X", ".")
    if is_euro: return f"{formatted} €"
    return formatted

def to_excel(df_fin, df_inputs, df_loan):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_fin.to_excel(writer, index=False, sheet_name='Financial_Model')
        df_inputs.to_excel(writer, index=False, sheet_name='Project_Data')
        df_loan.to_excel(writer, index=False, sheet_name='Loan_Schedule')
        workbook = writer.book
        for sheetname in ['Financial_Model', 'Loan_Schedule']:
            sheet = workbook[sheetname]
            for row in sheet.iter_rows(min_row=2, max_col=sheet.max_column):
                for cell in row:
                    header = sheet.cell(row=1, column=cell.column).value
                    if isinstance(cell.value, (int, float)):
                        if header in ["Έτος", "Μήνας", "Χωρητικότητα (MWh)"]:
                            cell.number_format = '#,##0.00'
                        else:
                            cell.number_format = '#,##0.00 "€"'
    return output.getvalue()

# --- HEADER & BRANDING ---
col_logo, col_title = st.columns([1, 4])
with col_logo:
    st.image("https://bessenergy.gr/wp-content/uploads/2026/02/cropped-logo-bess-energy-2026.jpeg", width=150)
with col_title:
    st.title("🔋 BESS Financial Analysis Platform")
    st.markdown("##### Μια εφαρμογή της **BESS ENERGY**, εξουσιοδοτημένου διανομέα των μπαταριών αποθήκευσης ενέργειας **GOTION**")

tabs = st.tabs(["Main Model", "Loan Schedule", "Manual & Instructions"])

# --- TAB 3: MANUAL ---
with tabs[2]:
    st.header("📘 Ανάλυση Μοντέλου BESS")
    
    # Πρώτο κομμάτι οδηγιών
    st.markdown("""
    ### 1. Δεδομένα Εισαγωγής (Inputs)
    * **Ετη Δανείου:** ο αριθμός των ετών του δανείου
    * **Ισχύς Έργου (MW):** Η ονομαστική ισχύς σύνδεσης του συστήματος στο δίκτυο.
    * **Χωρητικότητα (MWh):** Η συνολική ενέργεια που μπορεί να αποθηκεύσει η μπαταρία.
    * **Βάθος Εκφόρτισης (DoD %):** Το ποσοστό της χωρητικότητας που χρησιμοποιούμε (π.χ. 95%), ώστε να προστατεύεται η διάρκεια ζωής της μπαταρίας.
    * **Απόδοση Συστήματος (RTE %):** Το Round Trip Efficiency. Δείχνει την απώλεια ενέργειας κατά τη μετατροπή (AC-DC-AC). Ένας συντελεστής 86% σημαίνει ότι για κάθε 100 μονάδες ενέργειας που απορροφούμε, επιστρέφουμε 86.
    * **Ετήσια Πτώση Απόδοσης (Degradation %):** Η φυσιολογική μείωση της χωρητικότητας της μπαταρίας χρόνο με το χρόνο.
    * **Διαθεσιμότητα Συστήματος (Availability %):** Το ποσοστό των ημερών του έτους που το σύστημα είναι διαθέσιμο για λειτουργία, αφαιρώντας τις ημέρες συντήρησης ή βλαβών (π.χ. 354 ημέρες αντί για 365).
    * **Ημερήσια Ενέργεια (MWh):** Η καθαρή ενέργεια που εκφορτίζεται σε μία ημέρα.
      * 👉 Πράξη: Χωρητικότητα × DoD × Κύκλοι.
    * **Ετήσια Ενέργεια Έτους 1 (MWh):** Η συνολική ενέργεια που θα πουληθεί κατά τον πρώτο χρόνο λειτουργίας.
      * 👉 Πράξη: Ημερήσια Ενέργεια × 365 ημέρες.
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
    * **Ετήσια Ενέργεια (MWh):** Η συνολική ενέργεια που εκφορτίζει (πουλάει) το σύστημα ετησίως.
      * 👉 Πράξη: Χωρητικότητα × DoD × Κύκλοι × 365 ημέρες.
    * **Ετήσια Έσοδα (€):** Η αξία της ενέργειας που πωλήθηκε.
      * 👉 Πράξη: Ετήσια Ενέργεια × Προβλεπόμενη Τιμή Πώλησης (ανά έτος).
    * **Ενέργεια Φόρτισης (MWh):** Η ενέργεια που απορρόφησε το σύστημα από το δίκτυο για να γεμίσει.
      * 👉 Πράξη: Ετήσια Ενέργεια / RTE (περιλαμβάνει τις απώλειες).
    * **Συνολικό Κόστος Αγοράς (€):** Το κόστος της ενέργειας που αγοράστηκε για τη φόρτιση.
      * 👉 Πράξη: Ενέργεια Φόρτισης × Προβλεπόμενη Τιμή Αγοράς (ανά έτος).
    * **Μικτό Κέρδος (€):** Η διαφορά μεταξύ πωλήσεων και κόστους αγοράς ενέργειας (το spread).
    * **Έξοδα Λειτουργίας O&M (€):** Σταθερά ετήσια έξοδα (συντήρηση, ασφάλιστρα, τηλεπικοινωνίες).
    * **EBITDA (€):** Τα καθαρά λειτουργικά κέρδη προ τόκων, φόρων και αποσβέσεων.
    
    ### 5. Δείκτες Απόδοσης
    * **Μέσο Ετήσιο EBITDA (€):** Ο μέσος όρος των κερδών στη 10ετία.
    * **Χρόνια Απόσβεσης (Payback Years):** Ο χρόνος που απαιτείται για να καλύψει το EBITDA το αρχικό CAPEX.
      * 👉 Πράξη: Συνολικό CAPEX / Μέσο Ετήσιο EBITDA.
    """)

    st.divider()
    
    # Δεύτερο κομμάτι οδηγιών (ΦΟΣΕ)
    st.subheader("🤝 Λογική Profit Sharing (Floor Scenario)")
    st.markdown("""
    Όταν επιλέγεται το σενάριο **Floor + Profit Sharing**, οι υπολογισμοί ακολουθούν τα εξής βήματα:
    1. **Σταθερό Έσοδο:** Ο ΦΟΣΕ εγγυάται ένα ποσό (Floor) ανά MW.
    2. **Υπολογισμός Spread:** (Ετήσια Έσοδα από Αγορά/Πώληση) - (Ετήσιο Κόστος Ενέργειας).
    3. **Υπεραπόδοση (Upside):** Spread - Σταθερό Έσοδο.
    4. **Μοιρασιά:** Αν το Upside είναι θετικό, ο επενδυτής λαμβάνει το ποσοστό **Profit Share %** που έχει οριστεί.
    """)

# --- TAB 1: MAIN MODEL ---
with tabs[0]:
    # --- BASIC PROJECT DATA ---
    st.subheader("📋 Βασικά Δεδομένα Έργου")
    cust_name = st.text_input("Customer Name (English):", value=st.session_state.get("customer", "Client_Name"))
    clean_name = re.sub(r'\W+', '', cust_name.replace(" ", "_"))

    c1, c2, c3 = st.columns(3)
    with c1:
        p_mw = st.number_input("Power (MW)", value=st.session_state.get("p_mw", 20.0), key="p_mw")
        c_mwh = st.number_input("Capacity (MWh)", value=st.session_state.get("c_mwh", 40.0), key="c_mwh")
    with c2:
        b_duration = st.selectbox("Duration (Hours)", [2, 3, 4, 5], index=0, key="b_dur")
        l_years = st.number_input("Loan Duration (Years)", value=int(st.session_state.get("years", 10)), min_value=1, key="years")
    with c3:
        b_cost = st.number_input("Battery Cost (€)", value=float(st.session_state.get("b_cost", 4000000.0)), key="b_cost")
        bop_cost = st.number_input("BoP Cost (€)", value=float(st.session_state.get("bop_cost", 1000000.0)), key="bop_cost")

    st.divider()
    
    # --- ΕΝΟΤΗΤΑ ΦΟΣΕ (ΕΜΠΟΡΙΚΗ ΣΥΜΦΩΝΙΑ) ---
    st.subheader("🤝 Συμφωνία με Φορέα Σωρευτικής Εκπροσώπησης (ΦΟΣΕ)")
    
    col_fose1, col_fose2, col_fose3 = st.columns(3)
    with col_fose1:
        fose_scenario = st.radio("Επιλογή Προγράμματος", ["Tolling Agreement", "Floor + Profit Sharing"], key="f_scen")
        fose_contract_years = st.number_input("Διάρκεια Σύμβασης ΦΟΣΕ (Έτη)", value=5, min_value=1, max_value=20)
    
    with col_fose2:
        if fose_scenario == "Tolling Agreement":
            fose_fee_mw = st.number_input(f"Tolling Fee (€/MW/Year) - {b_duration}h BESS", value=47000)
        else:
            fose_fee_mw = st.number_input(f"Floor Fee (€/MW/Year) - {b_duration}h BESS", value=36000)
            
    with col_fose3:
        p_share_val = st.slider("Profit Share % (Ποσοστό Επενδυτή)", 0, 100, 50, key="pshare_val")

    st.divider()
    
    # --- ANNUAL PARAMETERS ---
    st.subheader(f"Annual Parameters (Years 1 to {l_years})")
    deg_l, cyc_l, sell_l, buy_l, om_l = [], [], [], [], []
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("📉 **Degradation (%)**")
        r_deg = st.columns(5)
        for i in range(l_years):
            with r_deg[i % 5]:
                v = st.number_input(f"Yr{i+1}", value=st.session_state.get(f"deg_{i}", 1.5), key=f"deg_{i}")
                deg_l.append(v/100)
    with col_b:
        st.markdown("🔄 **Daily Cycles**")
        r_cyc = st.columns(5)
        for i in range(l_years):
            with r_cyc[i % 5]:
                v = st.number_input(f"Yr{i+1}", value=st.session_state.get(f"cyc_{i}", 1.5), key=f"cyc_{i}")
                cyc_l.append(v)

    st.markdown("💰 **Prices & O&M**")
    p_rows = st.columns(3)
    with p_rows[0]:
        for i in range(l_years): sell_l.append(st.number_input(f"Sell Yr{i+1}", value=st.session_state.get(f"s_{i}", 100.0), key=f"s_{i}"))
    with p_rows[1]:
        for i in range(l_years): buy_l.append(st.number_input(f"Buy Yr{i+1}", value=st.session_state.get(f"b_{i}", 40.0), key=f"b_{i}"))
    with p_rows[2]:
        for i in range(l_years): om_l.append(st.number_input(f"O&M Yr{i+1}", value=st.session_state.get(f"om_{i}", 5000.0), key=f"om_{i}"))

    # --- CALCULATIONS ---
    # Loan
    loan_amt = (b_cost + bop_cost) * (st.session_state.get("ltv_val", 80)/100)
    m_rate = (st.session_state.get("int_rate", 6.0)/100) / 12
    m_total_months = int(l_years * 12)
    m_principal = loan_amt / m_total_months
    curr_bal_loan = loan_amt
    annual_debt = []
    loan_data = []
    for m in range(m_total_months):
        interest = curr_bal_loan * m_rate
        loan_data.append({"Μήνας": m+1, "Δόση Κεφαλαίου": m_principal, "Τόκοι": interest, "Σύνολο Δόσης": m_principal+interest, "Υπόλοιπο Κεφαλαίου": max(0, curr_bal_loan-m_principal)})
        curr_bal_loan -= m_principal
    df_loan_full = pd.DataFrame(loan_data)
    for y in range(l_years):
        annual_debt.append(df_loan_full.iloc[y*12:(y+1)*12]["Σύνολο Δόσης"].sum())

    # Results Logic
    results = []
    curr_cap = c_mwh
    for i in range(l_years):
        curr_cap *= (1 - deg_l[i])
        energy_out = curr_cap * 0.95 * cyc_l[i] * 365 * 0.99
        energy_in = energy_out / 0.86
        market_rev = energy_out * sell_l[i]
        market_cost = energy_in * buy_l[i]
        spread = market_rev - market_cost
        
        # ΦΟΣΕ Logic
        if i < fose_contract_years: # Όσο διαρκεί η σύμβαση
            if fose_scenario == "Tolling Agreement":
                final_revenue = fose_fee_mw * p_mw
                extra_profit = 0
            else: # Floor + Profit Sharing
                floor_income = fose_fee_mw * p_mw
                extra_profit = max(0, (spread - floor_income) * (p_share_val / 100))
                final_revenue = floor_income + extra_profit
        else: # Μετά τη λήξη της σύμβασης (Free Market)
            final_revenue = spread
            extra_profit = 0
            
        ebitda = final_revenue - (om_l[i] * p_mw)
        
        results.append({
            "Έτος": i+1,
            "Χωρητικότητα (MWh)": curr_cap,
            "Spread Αγοράς (€)": spread,
            "Σταθερό Έσοδο (€)": fose_fee_mw * p_mw if i < fose_contract_years else 0,
            "Profit Share (€)": extra_profit,
            "Συνολικά Έσοδα (€)": final_revenue,
            "EBITDA (€)": ebitda,
            "Δόση Δανείου (€)": annual_debt[i],
            "Cash Flow (€)": ebitda - annual_debt[i]
        })
    df_final = pd.DataFrame(results)

    # --- DISPLAY ---
    st.divider()
    st.subheader(f"Financial Summary: {cust_name} ({fose_scenario})")
    df_disp = df_final.copy()
    df_disp["Χωρητικότητα (MWh)"] = df_disp["Χωρητικότητα (MWh)"].apply(lambda x: fmt_num(x, False))
    for col in df_disp.columns[2:]: df_disp[col] = df_disp[col].apply(fmt_num)
    st.dataframe(df_disp, use_container_width=True)

    # --- EXPORTS & UPLOAD ---
    c_ex1, c_ex2 = st.columns(2)
    with c_ex1:
        st.download_button(f"📥 Excel Export", data=to_excel(df_final, df_final.head(1), df_loan_full), file_name=f"{clean_name}.xlsx")
    with c_ex2:
        save_dict = {"customer": cust_name, "p_mw": p_mw, "years": l_years, "ltv_val": st.session_state.get("ltv_val", 80), "int_rate": st.session_state.get("int_rate", 6.0)}
        st.download_button(f"💾 Save JSON", data=json.dumps(save_dict), file_name=f"{clean_name}.json")

    st.divider()
    up = st.file_uploader("Upload JSON File", type="json")
    if up:
        data = json.load(up)
        for k, v in data.items(): st.session_state[k] = v
        st.rerun()

# --- TAB 2: LOAN SCHEDULE ---
with tabs[1]:
    st.subheader("Monthly Loan Amortization Schedule")
    df_l_disp = df_loan_full.copy()
    for col in df_l_disp.columns[1:]: df_l_disp[col] = df_l_disp[col].apply(fmt_num)
    st.dataframe(df_l_disp, use_container_width=True)