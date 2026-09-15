import streamlit as st
import json
import datetime
import os
import pandas as pd
import io
import firebase_admin
from firebase_admin import credentials, firestore, auth
from st_click_detector import click_detector

st.set_page_config(page_title="Registro RFI", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
        .block-container { padding-top: 2rem; padding-bottom: 2rem; }
        .stButton>button { border-radius: 6px; font-weight: bold; }
        .stSelectbox label, .stTextInput label, .stNumberInput label, .stTextArea label, .stDateInput label {
            color: #8892b0 !important; font-weight: 600 !important; font-size: 0.85rem !important;
        }
        .streamlit-expanderHeader { font-weight: 600 !important; color: #f1f5f9 !important; }
        .stHtml { margin-bottom: 0 !important; }
        .login-container {
            max-width: 400px; margin: 0 auto; padding: 30px; 
            background-color: #112240; border-radius: 10px; 
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3); border: 1px solid #233554;
        }
    </style>
""", unsafe_allow_html=True)

if not firebase_admin._apps:
    try:
        if os.path.exists("chiave_firebase.json"):
            cred = credentials.Certificate("chiave_firebase.json")
        elif "firebase" in st.secrets:
            cert_dict = dict(st.secrets["firebase"])
            cred = credentials.Certificate(cert_dict)
        else:
            raise Exception("Nessun file chiave trovato.")
            
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"Errore di connessione a Firebase. Dettaglio: {e}")

db = firestore.client() if firebase_admin._apps else None

if 'user' not in st.session_state: st.session_state.user = None
if 'records' not in st.session_state: st.session_state.records = []
if 'form_asset' not in st.session_state: st.session_state.form_asset = None
if 'form_track' not in st.session_state: st.session_state.form_track = "Non specificato"
if 'filter_asset' not in st.session_state: st.session_state.filter_asset = None
if 'auth_error' not in st.session_state: st.session_state.auth_error = None
if 'schema_binario' not in st.session_state: st.session_state.schema_binario = "Tutti"
if 'edit_id' not in st.session_state: st.session_state.edit_id = None
if 'ui_pk_num' not in st.session_state: st.session_state.ui_pk_num = 0.0
if 'ui_pk_det' not in st.session_state: st.session_state.ui_pk_det = ""
if 'last_clicked_raw' not in st.session_state: st.session_state.last_clicked_raw = ""

def login_user(email, password):
    try:
        user = auth.get_user_by_email(email)
        st.session_state.user = {'email': user.email, 'uid': user.uid}
        st.session_state.auth_error = None
        st.rerun()
    except Exception as e:
        st.session_state.auth_error = "Credenziali non valide o utente non registrato."

if not st.session_state.user:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("""
            <div class='login-container'>
                <div style='text-align: center; margin-bottom: 25px;'>
                    <h1 style='color: #38bdf8; margin-bottom: 0; font-size: 2.8rem; letter-spacing: 2px;'>RFI</h1>
                    <h3 style='color: #f1f5f9; margin-top: 5px; margin-bottom: 5px;'>Manutenzione App</h3>
                    <p style='color: #8892b0; font-size: 0.9rem; margin-top: 0;'>Accesso Riservato Operatori</p>
                </div>
        """, unsafe_allow_html=True)
        
        email = st.text_input("Email aziendale", placeholder="es. mario.rossi@rfi.it")
        password = st.text_input("Password", type="password")
        
        if st.button("Accedi", use_container_width=True, type="primary"):
            if email and password: login_user(email, password)
            else: st.error("Inserisci email e password")
            
        if st.session_state.auth_error:
            st.error(st.session_state.auth_error)
            
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

STATIONS = [
    { "id": "ST-BAT", "name": "Battipaglia", "pk": 0.000, "is_minor": False },
    { "id": "PM-SNV", "name": "P.M. S. Nicola", "pk": 5.719, "is_minor": True },
    { "id": "ST-CAP", "name": "Capaccio", "pk": 17.679, "is_minor": False },
    { "id": "ST-PAE", "name": "Paestum", "pk": 21.322, "is_minor": True },
    { "id": "ST-AGR", "name": "Agropoli", "pk": 29.686, "is_minor": False },
    { "id": "PM-TOR", "name": "Torchiara", "pk": 35.316, "is_minor": True },
    { "id": "PM-RUT", "name": "Rutino", "pk": 41.368, "is_minor": True },
    { "id": "ST-OMI", "name": "Omignano", "pk": 46.775, "is_minor": True },
    { "id": "ST-VAL", "name": "Vallo", "pk": 50.069, "is_minor": False },
    { "id": "ST-ASC", "name": "Ascea", "pk": 60.697, "is_minor": False },
    { "id": "ST-PSC", "name": "Pisciotta", "pk": 69.419, "is_minor": False },
    { "id": "PM-SMB", "name": "S. Mauro", "pk": 74.558, "is_minor": True },
    { "id": "ST-CEN", "name": "Centola", "pk": 78.808, "is_minor": True },
    { "id": "ST-CEL", "name": "Celle", "pk": 83.344, "is_minor": False },
    { "id": "ST-TOR", "name": "Torre Orsaia", "pk": 90.942, "is_minor": True },
    { "id": "ST-POL", "name": "Policastro", "pk": 96.041, "is_minor": False },
    { "id": "ST-SAP", "name": "Sapri", "pk": 104.789, "is_minor": False },
    { "id": "ST-ACQ", "name": "Acquafredda", "pk": 111.090, "is_minor": True },
    { "id": "ST-MAR", "name": "Maratea", "pk": 117.104, "is_minor": False },
    { "id": "ST-MMR", "name": "Marina Maratea", "pk": 121.679, "is_minor": True },
    { "id": "ST-PRA", "name": "Praja", "pk": 129.281, "is_minor": False },
    { "id": "ST-SCA", "name": "Scalea", "pk": 140.169, "is_minor": False },
    { "id": "ST-MCV", "name": "Marcellina", "pk": 145.301, "is_minor": True },
    { "id": "ST-GRS", "name": "Grisolia", "pk": 148.363, "is_minor": True },
    { "id": "ST-DIA", "name": "Diamante", "pk": 155.661, "is_minor": False },
    { "id": "ST-BEL", "name": "Belvedere", "pk": 163.061, "is_minor": True },
    { "id": "ST-CPB", "name": "Capo Bonifati", "pk": 169.834, "is_minor": False },
    { "id": "ST-CET", "name": "Cetraro", "pk": 177.895, "is_minor": False },
    { "id": "ST-ACP", "name": "Acquappesa", "pk": 181.147, "is_minor": True },
    { "id": "ST-GPT", "name": "Guardia P.T.", "pk": 184.386, "is_minor": True },
    { "id": "ST-FUS", "name": "Fuscaldo", "pk": 191.104, "is_minor": False },
    { "id": "ST-PAO", "name": "Paola", "pk": 197.001, "is_minor": False }
]

CUSTOM_TRATTE = [
    ("ST-BAT", "PM-SNV"), ("PM-SNV", "ST-CAP"), ("ST-CAP", "ST-AGR"),
    ("ST-AGR", "PM-RUT"), ("PM-RUT", "ST-VAL"), ("ST-VAL", "ST-ASC"),
    ("ST-ASC", "ST-PSC"), ("ST-PSC", "PM-SMB"), ("PM-SMB", "ST-CEL"),
    ("ST-CEL", "ST-POL"), ("ST-POL", "ST-SAP"), ("ST-SAP", "ST-MAR"),
    ("ST-MAR", "ST-PRA"), ("ST-PRA", "ST-SCA"), ("ST-SCA", "ST-DIA"),
    ("ST-DIA", "ST-CPB"), ("ST-CPB", "ST-CET"), ("ST-CET", "ST-FUS"),
    ("ST-FUS", "ST-PAO")
]

SECTIONS = []
for start_id, end_id in CUSTOM_TRATTE:
    start_st = next((s for s in STATIONS if s["id"] == start_id), None)
    end_st = next((s for s in STATIONS if s["id"] == end_id), None)
    if start_st and end_st:
        SECTIONS.append({
            "id": f"TR-{start_id.split('-')[1]}_{end_id.split('-')[1]}",
            "name": f"Tratta {start_st['name']} - {end_st['name']}",
            "pkStart": start_st["pk"],
            "pkEnd": end_st["pk"],
            "start_id": start_id,
            "end_id": end_id
        })

discipline_options = {
    "LAV": "LAV (Armamento)", "TE": "TE (Trazione Elettrica)",
    "IS": "IS (Impianti di Segnalamento e Sicurezza)", "CMA": "CMA (Cantiere Meccanizzato)",
    "DIA": "DIA (Diagnostica)", "TLC": "TLC (Telecomunicazioni)",
    "SSE": "SSE (Sottostazioni Elettriche)", "OC": "OC (Opere Civili)", "SO": "SO Ingegneria"
}

def fetch_records():
    if db:
        try:
            docs = db.collection('interventi').order_by('timestamp', direction=firestore.Query.DESCENDING).limit(100).stream()
            st.session_state.records = [ {**doc.to_dict(), "doc_id": doc.id} for doc in docs ]
        except Exception as e:
            st.error(f"Errore lettura database: {e}")

if not st.session_state.records and db: fetch_records()

def get_asset_info(asset_id):
    st_match = next((s for s in STATIONS if s["id"] == asset_id), None)
    if st_match: return st_match["name"], st_match["pk"], None
    sec_match = next((s for s in SECTIONS if s["id"] == asset_id), None)
    if sec_match: return sec_match["name"], sec_match["pkStart"], sec_match["pkEnd"]
    return asset_id, 0.0, 0.0

def get_color_for_asset(asset_id, is_tratta, track_filter, default_c=None):
    if not default_c:
        default_c = "#10b981" if is_tratta else "#0284c7"
        
    matches = [r for r in st.session_state.records if r.get('assetId') == asset_id]
    
    # Filtra in modo esatto in base al binario del grafico in corso di renderizzazione
    if track_filter in ["Pari", "Dispari"]:
        matches = [r for r in matches if r.get('track') == track_filter or r.get('track') == "Non specificato"]
        
    if not matches: return default_c
    
    try:
        latest = max(datetime.datetime.fromisoformat(r['timestamp'].replace('Z', '+00:00')) for r in matches)
        now = datetime.datetime.now(datetime.timezone.utc)
        hours_ago = (now - latest).total_seconds() / 3600
        if hours_ago < 24: return "#ef4444" # Rosso
        if hours_ago < 48: return "#f59e0b" # Giallo
    except: pass
    return default_c

h_col1, h_col2 = st.columns([4, 1])
with h_col1:
    st.markdown("<h1 style='color: #38bdf8; margin-bottom: 0;'>RFI - Linea Battipaglia &ndash; Paola (FL 142)</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #8892b0;'>Registro Cloud Manutenzione Interventi</p>", unsafe_allow_html=True)
with h_col2:
    st.markdown(f"<div style='text-align: right; padding-top: 15px; color: #8892b0; font-weight: bold;'>👤 {st.session_state.user['email']}</div>", unsafe_allow_html=True)
    st.markdown("<div style='padding-top: 5px;'></div>", unsafe_allow_html=True)
    if st.button("🚪 Esci"):
        st.session_state.user = None
        st.rerun()

st.divider()

st.markdown("<h3 style='color: #8892b0; font-size: 1rem; margin-bottom: 5px;'>SCHEMA UNIFILARE INTERATTIVO (Clicca su Sedi o Tratte)</h3>", unsafe_allow_html=True)

binario_col, legend_col = st.columns([1, 4])
with binario_col:
    selected_bin = st.selectbox("Binario", ["Tutti", "Pari", "Dispari"], index=["Tutti", "Pari", "Dispari"].index(st.session_state.schema_binario))
    if selected_bin != st.session_state.schema_binario:
        st.session_state.schema_binario = selected_bin
        st.rerun()
        
with legend_col:
    st.markdown("""
        <div style='font-size: 0.85rem; color: #8892b0; display:flex; gap: 15px; margin-top: 30px; justify-content: flex-end;'>
            <span><span style='color:#10b981'>●</span> Linea Regolare</span>
            <span><span style='color:#f59e0b'>●</span> Intervento &lt; 48h</span>
            <span><span style='color:#ef4444'>●</span> Intervento &lt; 24h</span>
        </div>
    """, unsafe_allow_html=True)

spacing = 220 
total_width = (len(STATIONS) - 1) * spacing + 120
svg_elements = ""

# Determina quanti binari disegnare (uno singolo o due paralleli)
tracks_to_render = ["Dispari", "Pari"] if st.session_state.schema_binario == "Tutti" else [st.session_state.schema_binario]

if len(tracks_to_render) == 2:
    y_offsets = {"Dispari": 60, "Pari": 180}
    svg_height = 280
else:
    y_offsets = {tracks_to_render[0]: 80}
    svg_height = 180

# Disegna le linee e le stazioni per ciascun binario richiesto
for track_name in tracks_to_render:
    yLine = y_offsets[track_name]
    
    # Etichetta del binario all'inizio della linea
    svg_elements += f'<text x="15" y="{yLine - 25}" font-size="16" fill="#8892b0" font-weight="bold" font-family="sans-serif">BINARIO {track_name.upper()}</text>'
    
    # Disegna Segmenti (Tratte)
    for sec in SECTIONS:
        start_idx = next((i for i, s in enumerate(STATIONS) if s["id"] == sec["start_id"]), 0)
        end_idx = next((i for i, s in enumerate(STATIONS) if s["id"] == sec["end_id"]), 0)
        x1 = 20 + start_idx * spacing
        x2 = 20 + end_idx * spacing
        color = get_color_for_asset(sec["id"], is_tratta=True, track_filter=track_name)
        # L'ID include il nome del binario per identificarlo al click
        svg_elements += f"""
            <a href='#' id='{sec['id']}__{track_name}'>
                <line class="track-line" x1="{x1}" y1="{yLine}" x2="{x2}" y2="{yLine}" stroke="{color}" />
            </a>
        """

    # Disegna Nodi (Stazioni e Fermate)
    for i, st_item in enumerate(STATIONS):
        x = 20 + i * spacing
        if st_item["is_minor"]:
            r = 8
            base_color = "#64748b" 
        else:
            r = 14
            base_color = "#0284c7" 
            
        color = get_color_for_asset(st_item["id"], is_tratta=False, track_filter=track_name, default_c=base_color)
        display_name = st_item["name"]
            
        svg_elements += f"""
            <a href='#' id='{st_item['id']}__{track_name}'>
                <g class="station-group">
                    <circle cx="{x}" cy="{yLine}" r="{r}" fill="{color}" stroke="#ffffff" stroke-width="2.5"/>
                    <text x="{x}" y="{yLine + 40}" class="label-station">{display_name}</text>
                    <text x="{x}" y="{yLine + 62}" class="label-pk">km {st_item['pk']:.3f}</text>
                </g>
            </a>
        """

full_html = f"""
<div style="width: 100%; overflow-x: auto; padding-bottom: 10px; text-align: left; margin: 0; scrollbar-width: thin; scrollbar-color: #233554 #152238;">
    <svg viewBox="0 0 {total_width} {svg_height}" width="{total_width}px" height="{svg_height}px" xmlns="http://www.w3.org/2000/svg" style="background-color: #152238; border-radius: 8px; border: 1px solid #233554; padding: 10px 0; display: block; margin-left: 0;">
        <style>
            .track-line {{ stroke-width: 9; stroke-linecap: round; cursor: pointer; transition: 0.2s; }}
            .track-line:hover {{ stroke-width: 15; opacity: 0.8; stroke: #38bdf8; }}
            .station-group {{ cursor: pointer; }}
            .station-group:hover circle {{ stroke: #38bdf8; stroke-width: 5; }}
            .label-station {{ font-size: 16px; fill: #f1f5f9; text-anchor: middle; font-weight: bold; font-family: sans-serif; pointer-events: none; }}
            .label-pk {{ font-size: 13px; fill: #8892b0; text-anchor: middle; font-family: sans-serif; pointer-events: none; }}
        </style>
        {svg_elements}
    </svg>
</div>
"""

clicked_raw = click_detector(full_html, key="synoptic_chart")

if clicked_raw and clicked_raw != st.session_state.last_clicked_raw:
    st.session_state.last_clicked_raw = clicked_raw
    clicked_id, clicked_track = clicked_raw.split("__")
    
    st.session_state.form_asset = clicked_id
    st.session_state.form_track = clicked_track
    st.session_state.filter_asset = clicked_id
    _, p_start, p_end = get_asset_info(clicked_id)
    st.session_state.ui_pk_num = p_start
    st.session_state.ui_pk_det = f"da km {p_start:.3f} a km {p_end:.3f}" if p_end else f"km {p_start:.3f}"
    st.rerun()

left_col, right_col = st.columns([1, 1.8])

with left_col:
    edit_rec = None
    if st.session_state.edit_id:
        edit_rec = next((r for r in st.session_state.records if r.get('doc_id') == st.session_state.edit_id), None)

    st.markdown(f"### {'Modifica' if edit_rec else 'Nuovo'} intervento manutentivo")
    
    asset_names = ["-- Seleziona punto linea --"]
    asset_options = {"-- Seleziona punto linea --": ""}
    
    for st_item in STATIONS:
        n = f"[{st_item['id']}] {st_item['name']}"
        asset_names.append(n)
        asset_options[n] = st_item['id']
        
    for sec in SECTIONS:
        n = f"[{sec['id']}] {sec['name']}"
        asset_names.append(n)
        asset_options[n] = sec['id']

    form_index = 0
    if edit_rec:
        for i, val in enumerate(asset_options.values()):
            if val == edit_rec.get('assetId'): form_index = i; break
    elif st.session_state.form_asset:
        for i, val in enumerate(asset_options.values()):
            if val == st.session_state.form_asset: form_index = i; break
                
    disc_idx = 0
    if edit_rec and edit_rec.get('discipline') in discipline_options:
        disc_idx = list(discipline_options.keys()).index(edit_rec.get('discipline'))

    with st.form("record_form"):
        sel_asset = st.selectbox("Sede Tecnica / Tratta / Impianto", asset_names, index=form_index)
        current_sel_id = asset_options[sel_asset]
        
        if current_sel_id != st.session_state.form_asset and current_sel_id != "":
            st.session_state.form_asset = current_sel_id
            st.session_state.filter_asset = current_sel_id
            _, p_start, p_end = get_asset_info(current_sel_id)
            st.session_state.ui_pk_num = p_start
            st.session_state.ui_pk_det = f"da km {p_start:.3f} a km {p_end:.3f}" if p_end else f"km {p_start:.3f}"
            st.rerun()
            
        discipline = st.selectbox("Struttura", list(discipline_options.keys()), format_func=lambda x: discipline_options[x], index=disc_idx)
        
        default_date = datetime.date.today()
        if edit_rec and 'interventionDate' in edit_rec:
            try: default_date = datetime.datetime.strptime(edit_rec['interventionDate'], "%Y-%m-%d").date()
            except: pass
            
        bin_opts = ["Non specificato", "Pari", "Dispari"]
        # Determina index del binario (dal record se in modifica, o dal click sullo schema)
        bin_idx = 0
        if edit_rec and edit_rec.get('track') in bin_opts:
            bin_idx = bin_opts.index(edit_rec.get('track'))
        elif st.session_state.form_track in bin_opts:
            bin_idx = bin_opts.index(st.session_state.form_track)

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            data_intervento = st.date_input("Data Intervento", value=default_date)
        with col_d2:
            binario_intervento = st.selectbox("Binario", bin_opts, index=bin_idx)
            
        if edit_rec and st.session_state.ui_pk_num == 0.0:
            st.session_state.ui_pk_num = float(edit_rec.get('pkKm', 0.0))
            st.session_state.ui_pk_det = edit_rec.get('pk', '')

        pk_num = st.number_input("Km esatto (Es: 158.200)", min_value=0.0, max_value=200.0, step=0.001, format="%.3f", key="ui_pk_num")
        pk_det = st.text_input("Km da - a (Es: da km 110+000 a 111+000)", key="ui_pk_det")
        
        op = st.text_input("Squadra / Reparto Operativo", value=edit_rec.get('operator', '') if edit_rec else "")
        nts = st.text_area("Descrizione Sintetica Lavorazione", value=edit_rec.get('notes', '') if edit_rec else "")
        
        st.markdown("<small style='color: #8892b0; font-weight: bold;'>Allega documenti</small>", unsafe_allow_html=True)
        uploaded_files = st.file_uploader("Trascina PDF o Immagini qui", type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True, label_visibility="collapsed")
        
        btn_label = "Aggiorna intervento" if edit_rec else "Registra intervento"
        submit_btn = st.form_submit_button(btn_label, use_container_width=True)
        
        if submit_btn:
            if not asset_options[sel_asset]:
                st.error("Seleziona una sede valida.")
            else:
                asset_id = asset_options[sel_asset]
                asset_name, _, _ = get_asset_info(asset_id)
                att_names = [f.name for f in uploaded_files] if uploaded_files else []
                if edit_rec and not uploaded_files:
                    att_names = edit_rec.get('attachments', [])
                    
                record_dict = {
                    "assetId": asset_id, "assetName": asset_name, "discipline": discipline,
                    "interventionDate": data_intervento.strftime("%Y-%m-%d"), "track": binario_intervento,
                    "pkKm": pk_num, "pk": pk_det, "operator": op, "notes": nts,
                    "attachments": att_names, "author": st.session_state.user['email']
                }
                
                try:
                    if edit_rec:
                        db.collection('interventi').document(st.session_state.edit_id).update(record_dict)
                        st.success("Intervento aggiornato!")
                        st.session_state.edit_id = None
                    else:
                        record_dict["timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                        db.collection('interventi').add(record_dict)
                        st.success("Intervento registrato!")
                        
                    # Reset stato binario form
                    st.session_state.form_track = "Non specificato"
                    fetch_records() 
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore salvataggio: {e}")

    if edit_rec:
        if st.button("❌ Annulla Modifica", use_container_width=True):
            st.session_state.edit_id = None
            st.rerun()

with right_col:
    st.markdown("### Ricerca intervento")
    
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        f_asset_idx = 0
        if st.session_state.filter_asset:
            for i, val in enumerate(asset_options.values()):
                if val == st.session_state.filter_asset: f_asset_idx = i; break
        f_asset = st.selectbox("Filtra per Sede", asset_names, index=f_asset_idx)
        if asset_options[f_asset] != st.session_state.filter_asset:
            st.session_state.filter_asset = asset_options[f_asset]
            st.rerun()
            
    with f_col2:
        f_disc = st.selectbox("Filtra per Struttura", ["Tutte"] + list(discipline_options.keys()))
    with f_col3:
        f_date = st.date_input("Filtra per Data", value=(), help="Clicca due date per creare un intervallo")
        
    filtered_recs = st.session_state.records
    
    if st.session_state.filter_asset:
        filtered_recs = [r for r in filtered_recs if r.get('assetId') == st.session_state.filter_asset]
    if f_disc != "Tutte":
        filtered_recs = [r for r in filtered_recs if r.get('discipline') == f_disc]
        
    if f_date:
        if isinstance(f_date, tuple) and len(f_date) == 2:
            d_start, d_end = f_date
            filtered_recs = [r for r in filtered_recs if 'interventionDate' in r and d_start <= datetime.datetime.strptime(r['interventionDate'], "%Y-%m-%d").date() <= d_end]
        elif isinstance(f_date, datetime.date):
            filtered_recs = [r for r in filtered_recs if r.get('interventionDate') == f_date.strftime("%Y-%m-%d")]

    col_res1, col_res2 = st.columns([3, 1])
    with col_res1:
        st.markdown(f"<div style='margin-bottom: 10px; padding-top:10px; color: #8892b0; font-size: 0.9rem;'>{len(filtered_recs)} registrazioni trovate.</div>", unsafe_allow_html=True)

    if filtered_recs:
        with col_res2:
            try:
                df = pd.DataFrame(filtered_recs)
                cols = ['interventionDate', 'assetName', 'discipline', 'track', 'pk', 'operator', 'notes', 'author']
                for c in cols:
                    if c not in df.columns: df[c] = ''
                    
                df_export = df[cols].rename(columns={
                    'interventionDate': 'Data', 'assetName': 'Sede/Tratta', 'discipline': 'Struttura',
                    'track': 'Binario', 'pk': 'Km', 'operator': 'Squadra', 'notes': 'Note', 'author': 'Autore'
                })
                
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_export.to_excel(writer, index=False, sheet_name='Interventi RFI')
                    
                st.download_button(
                    label="📊 Esporta Excel",
                    data=buffer.getvalue(),
                    file_name="Ricerca_Interventi_RFI.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            except Exception as e:
                st.error("Errore export")

    if not filtered_recs:
        st.info("Nessun intervento corrisponde ai criteri di ricerca.")
    else:
        for r in filtered_recs:
            dt_str = "Data sconosciuta"
            try: dt_str = datetime.datetime.fromisoformat(r['timestamp'].replace('Z', '+00:00')).strftime("%d/%m/%Y %H:%M")
            except: pass
                
            inv_date = r.get('interventionDate', 'Non specificata')
            if inv_date != 'Non specificata':
                try: inv_date = datetime.datetime.strptime(inv_date, "%Y-%m-%d").strftime("%d/%m/%Y")
                except: pass
            
            icon = "🔧" if r.get('discipline') == "LAV" else "⚡" if r.get('discipline') in ["TE", "SSE"] else "🚦" if r.get('discipline') == "IS" else "📋"
            
            # Etichetta espandibile migliorata
            track_label = f" [{r.get('track')}]" if r.get('track') and r.get('track') != "Non specificato" else ""
            exp_label = f"{icon} {inv_date} | {r.get('discipline')} | {r.get('assetName', r.get('assetId'))}{track_label}"
            
            with st.expander(exp_label):
                st.markdown(f"""
                <div style="color: #8892b0; font-size: 0.8rem; margin-bottom: 8px;">
                    Registrato il {dt_str} da {r.get('author', 'Sconosciuto').split('@')[0]}
                </div>
                <div style="color: #f1f5f9; font-size: 0.95rem; margin-bottom: 5px;"><strong>Posizione:</strong> {r.get('pk')} (km {r.get('pkKm', 0.0):.3f})</div>
                <div style="color: #f1f5f9; font-size: 0.95rem; margin-bottom: 12px;"><strong>Squadra:</strong> {r.get('operator')}</div>
                <div style="color: #cbd5e1; font-size: 0.9rem; line-height: 1.5; padding: 10px; background-color: #0f172a; border-radius: 6px; border-left: 3px solid #38bdf8;">
                    {r.get('notes')}
                </div>
                """, unsafe_allow_html=True)
                
                attachments = r.get('attachments', [])
                if attachments:
                    st.markdown("<hr style='margin: 10px 0; border-color: #233554;'>", unsafe_allow_html=True)
                    st.write("📎 **Allegati:** *(Modalità simulazione Download)*")
                    for att in attachments:
                        st.download_button(label=f"⬇️ Scarica {att}", data=b"Contenuto di prova in attesa di Storage", file_name=att, key=f"dl_{r.get('doc_id')}_{att}")
                
                st.markdown("<hr style='margin: 10px 0; border-color: #233554;'>", unsafe_allow_html=True)
                
                a_col1, a_col2 = st.columns(2)
                with a_col1:
                    if st.button("✏️ Modifica", key=f"edit_{r.get('doc_id')}", use_container_width=True):
                        st.session_state.edit_id = r.get('doc_id')
                        st.rerun()
                with a_col2:
                    if st.button("🗑️ Elimina", key=f"del_{r.get('doc_id')}", use_container_width=True):
                        try:
                            db.collection('interventi').document(r.get('doc_id')).delete()
                            if st.session_state.edit_id == r.get('doc_id'):
                                st.session_state.edit_id = None
                            fetch_records()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Errore durante l'eliminazione: {e}")