import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date, time as datetime_time, timedelta
import calendar
import time
import logging
import shutil
import json
from pathlib import Path

# ========================================
# CONFIGURARE LOGGING
# ========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========================================
# ⭐ CONFIGURARE PROGRAM MEDICAL
# ========================================
PROGRAM_MEDICAL = {
    'bilet_trimitere': {
        'ora_start': datetime_time(8, 20),
        'ora_end': datetime_time(12, 40),
        'interval_minute': 20,
        'max_pacienti': 14,
        'zile_lucratoare': [0, 1, 2, 3, 4]
    },
    'cu_plata': {
        'ora_start': datetime_time(13, 0),
        'ora_end': datetime_time(18, 0),
        'interval_minute': 20,
        'max_pacienti': 999
    }
}

# ========================================
# SĂRBĂTORI LEGALE ROMÂNIA 2026
# ========================================
SARBATORI_LEGALE = [
    # Sărbători fixe
    (1, 1),   # Anul Nou
    (1, 2),   # Anul Nou
    (1, 24),  # Unirea Principatelor
    (5, 1),   # Ziua Muncii
    (6, 1),   # Ziua Copilului
    (8, 15),  # Adormirea Maicii Domnului
    (11, 30), # Sfântul Andrei
    (12, 1),  # Ziua Națională
    (12, 25), # Crăciun
    (12, 26), # Crăciun
]

# Paște 2026: 12 aprilie (duminică)
# Rusalii 2026: 31 mai (duminică)
PASTE_2026 = [
    (4, 10),  # Vinerea Mare
    (4, 12),  # Paștele
    (4, 13),  # Paștele
]

RUSALII_2026 = [
    (5, 31),  # Rusalii
    (6, 1),   # Rusalii (a doua zi)
]

def este_sarbatoare_legala(data):
    """
    Verifică dacă o dată este sărbătoare legală sau weekend
    
    Args:
        data: obiect date
    
    Returns:
        bool: True dacă este sărbătoare sau weekend
    """
    # Verifică weekend (sâmbătă=5, duminică=6)
    if data.weekday() >= 5:
        return True
    
    # Verifică sărbători fixe
    if (data.month, data.day) in SARBATORI_LEGALE:
        return True
    
    # Verifică Paște 2026 (doar pentru 2026)
    if data.year == 2026 and (data.month, data.day) in PASTE_2026:
        return True
    
    # Verifică Rusalii 2026 (doar pentru 2026)
    if data.year == 2026 and (data.month, data.day) in RUSALII_2026:
        return True
    
    return False

def obtine_nume_sarbatoare(data):
    """
    Returnează numele sărbătorii sau tipul zilei libere
    
    Args:
        data: obiect date
    
    Returns:
        str: Numele sărbătorii sau "Sâmbătă"/"Duminică"
    """
    # Verifică weekend
    if data.weekday() == 5:
        return "Sâmbătă"
    elif data.weekday() == 6:
        return "Duminică"
    
    # Dictionary sărbători fixe
    sarbatori_dict = {
        (1, 1): "Anul Nou",
        (1, 2): "Anul Nou (zi 2)",
        (1, 24): "Unirea Principatelor Române",
        (5, 1): "Ziua Muncii",
        (6, 1): "Ziua Copilului",
        (8, 15): "Adormirea Maicii Domnului",
        (11, 30): "Sfântul Andrei",
        (12, 1): "Ziua Națională a României",
        (12, 25): "Crăciunul",
        (12, 26): "Crăciunul (zi 2)",
    }
    
    # Verifică sărbători fixe
    if (data.month, data.day) in sarbatori_dict:
        return sarbatori_dict[(data.month, data.day)]
    
    # Paște 2026
    paste_dict = {
        (4, 10): "Vinerea Mare",
        (4, 12): "Paștele",
        (4, 13): "Paștele (zi 2)",
    }
    
    if data.year == 2026 and (data.month, data.day) in paste_dict:
        return paste_dict[(data.month, data.day)]
    
    # Rusalii 2026
    rusalii_dict = {
        (5, 31): "Rusaliile",
        (6, 1): "Rusaliile (zi 2)",
    }
    
    if data.year == 2026 and (data.month, data.day) in rusalii_dict:
        return rusalii_dict[(data.month, data.day)]
    
    # Fallback
    return "Zi liberă"

# ========================================
# CONFIGURARE PAGINĂ STREAMLIT
# ========================================
st.set_page_config(
    page_title="Cabinet Medical - Dr. Pop V. Maria",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========================================
# CSS GLOBAL
# ========================================

st.markdown("""
<style>
    /* Background principal */
    .main {
        background-color: #f5f7fa;
    }
    
    /* Sidebar */
    div[data-testid="stSidebar"] {
        background-color: #2c3e50;
    }
    
    div[data-testid="stSidebar"] .element-container {
        color: white;
    }
    
    /* Butoane generale */
    .stButton button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    
    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    
    /* Stat cards */
    .stat-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        border-left: 4px solid #667eea;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
    /* ==================== ELIMINARE COMPLETĂ SPAȚII CALENDAR ==================== */
    
    /* Container principal horizontal block */
    section[data-testid="stHorizontalBlock"] {
        gap: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    
    /* Vertical blocks container */
    section[data-testid="stHorizontalBlock"] > div[data-testid="stVerticalBlock"] {
        gap: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    
    /* Rows de zile */
    section[data-testid="stHorizontalBlock"] > div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"] {
        gap: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    
    /* Toate div-urile din vertical block */
    section[data-testid="stHorizontalBlock"] div[data-testid="stVerticalBlock"] > div {
        gap: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    
    /* Coloanele (zilele) - PADDING ZERO */
    section[data-testid="stHorizontalBlock"] div[data-testid="column"] {
        padding: 0 1px !important;
        margin: 0 !important;
        min-width: 0 !important;
        flex: 1 1 0 !important;
    }
    
    /* Element containers - ZERO margin */
    section[data-testid="stHorizontalBlock"] .element-container {
        margin: 0 !important;
        padding: 0 !important;
    }
    
    /* ==================== BUTOANE - DIMENSIUNI FIXE ==================== */
    
    section[data-testid="stHorizontalBlock"] button {
        margin: 0 !important;
        padding: 3px 1px !important;
        min-height: 36px !important;
        height: 36px !important;
        max-height: 36px !important;
        font-size: 11px !important;
        line-height: 1.1 !important;
        border-radius: 4px !important;
        white-space: pre-line !important;
        width: 100% !important;
        box-sizing: border-box !important;
    }
    
    /* Conținut buton */
    section[data-testid="stHorizontalBlock"] button > div {
        padding: 0 !important;
        margin: 0 !important;
    }
    
    /* ==================== DIV SĂRBĂTORI - DIMENSIUNI FIXE ==================== */
    
    section[data-testid="stHorizontalBlock"] div[style*="linear-gradient(135deg, #FF8C00"] {
        height: 36px !important;
        min-height: 36px !important;
        max-height: 36px !important;
        line-height: 36px !important;
        margin: 0 !important;
        padding: 0 !important;
        box-sizing: border-box !important;
    }
    
    /* ==================== CULORI ==================== */
    
    /* Zi curentă - ROZ/ROZ (ca în imagine) */
    section[data-testid="stHorizontalBlock"] button[kind="primary"]:not([disabled]) {
        background: linear-gradient(135deg, #FF8C00 0%, #FF6600 100%);
        border: 2px solid #AD1457 !important;
        color: white !important;
        font-weight: 700 !important;
    }
    
    section[data-testid="stHorizontalBlock"] button[kind="primary"]:not([disabled]):hover {
        background: linear-gradient(135deg, #D81B60, #C2185B) !important;
        transform: scale(1.03) !important;
    }
    
    /* Zile normale */
    section[data-testid="stHorizontalBlock"] button[kind="secondary"]:not([disabled]) {
        border: 1px solid rgba(255,255,255,0.1) !important;
        background: #2c3e50 !important;
        color: white !important;
    }
    
    section[data-testid="stHorizontalBlock"] button[kind="secondary"]:not([disabled]):hover {
        transform: scale(1.03) !important;
        background: #34495e !important;
    }
</style>
""", unsafe_allow_html=True)

# ========================================
# FUNCȚII BAZĂ DE DATE
# ========================================

def initializeaza_baza_date():
    """Creează tabelele dacă nu există"""
    try:
        with sqlite3.connect('cabinet.db') as conn:
            c = conn.cursor()
            
            c.execute('''
                CREATE TABLE IF NOT EXISTS pacienti (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cnp TEXT UNIQUE NOT NULL,
                    nume TEXT NOT NULL,
                    prenume TEXT NOT NULL,
                    data_nasterii DATE,
                    telefon TEXT,
                    email TEXT,
                    adresa TEXT,
                    observatii TEXT,
                    data_inregistrare DATE DEFAULT CURRENT_DATE
                )
            ''')
            
            c.execute('''
                CREATE TABLE IF NOT EXISTS programari (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cnp TEXT NOT NULL,
                    data_consultatie DATE NOT NULL,
                    ora_consultatie TIME NOT NULL,
                    tip_plata TEXT NOT NULL,
                    status TEXT DEFAULT 'Programat',
                    observatii TEXT,
                    data_creare TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (cnp) REFERENCES pacienti(cnp)
                )
            ''')
            
            conn.commit()
            logger.info("Baza de date inițializată")
            return True
    except Exception as e:
        logger.error(f"Eroare inițializare DB: {e}")
        return False

# ========================================
# FUNCȚII HELPER
# ========================================

def formateaza_data_ro(data_str):
    """Formatează data în DD/MM/YYYY"""
    if not data_str:
        return "N/A"
    try:
        if isinstance(data_str, str):
            data = datetime.strptime(data_str, '%Y-%m-%d')
        else:
            data = data_str
        return data.strftime('%d/%m/%Y')
    except:
        return str(data_str)

def formateaza_nume_majuscula(nume, prenume):
    """
    Formatează nume și prenume cu MAJUSCULĂ
    
    Args:
        nume: Numele pacientului
        prenume: Prenumele pacientului
    
    Returns:
        str: "NUME PRENUME" în majusculă
    """
    if not nume or not prenume:
        return "N/A"
    return f"{str(nume).upper()} {str(prenume).upper()}"

def valideaza_cnp(cnp):
    """Validează CNP românesc"""
    if not cnp or len(cnp) != 13 or not cnp.isdigit():
        return False, "CNP invalid: 13 cifre necesare"
    if cnp[0] not in '1256':
        return False, "CNP invalid: prima cifră trebuie 1,2,5 sau 6"
    return True, "CNP valid"

def obtine_pacient_cnp(cnp):
    """Caută pacient după CNP"""
    try:
        with sqlite3.connect('cabinet.db') as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM pacienti WHERE cnp = ?", (cnp,))
            return c.fetchone()
    except Exception as e:
        logger.error(f"Eroare căutare pacient: {e}")
        return None

def adauga_pacient(cnp, nume, prenume, data_nasterii, telefon, email, adresa, observatii):
    """Adaugă pacient nou"""
    valid, msg = valideaza_cnp(cnp)
    if not valid:
        return False, msg, None
    
    try:
        with sqlite3.connect('cabinet.db') as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO pacienti (cnp, nume, prenume, data_nasterii, telefon, email, adresa, observatii)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (cnp, nume.upper(), prenume.upper(), data_nasterii, telefon, email, adresa, observatii))
            conn.commit()
            logger.info(f"Pacient adăugat: {nume} {prenume}")
            return True, f"✅ Pacient adăugat: {nume} {prenume}", c.lastrowid
    except sqlite3.IntegrityError:
        return False, f"❌ CNP {cnp} există deja", None
    except Exception as e:
        logger.error(f"Eroare adăugare: {e}")
        return False, f"❌ Eroare: {str(e)}", None

def obtine_toti_pacientii():
    """Returnează toți pacienții"""
    try:
        with sqlite3.connect('cabinet.db') as conn:
            df = pd.read_sql_query("SELECT * FROM pacienti ORDER BY nume, prenume", conn)
            return df
    except Exception as e:
        logger.error(f"Eroare obținere pacienți: {e}")
        return pd.DataFrame()

def sterge_pacient(cnp, sterge_si_programari=False):
    """Șterge pacient"""
    try:
        with sqlite3.connect('cabinet.db') as conn:
            c = conn.cursor()
            
            c.execute("SELECT COUNT(*) FROM programari WHERE cnp = ?", (cnp,))
            nr_prog = c.fetchone()[0]
            
            if nr_prog > 0 and not sterge_si_programari:
                return False, f"❌ Pacient cu {nr_prog} programări", None
            
            if sterge_si_programari:
                c.execute("DELETE FROM programari WHERE cnp = ?", (cnp,))
            
            c.execute("DELETE FROM pacienti WHERE cnp = ?", (cnp,))
            conn.commit()
            
            return True, "✅ Pacient șters", None
    except Exception as e:
        logger.error(f"Eroare ștergere: {e}")
        return False, f"❌ Eroare: {str(e)}", None

def obtine_programari():
    """Returnează toate programările"""
    try:
        with sqlite3.connect('cabinet.db') as conn:
            df = pd.read_sql_query('''
                SELECT p.id, p.cnp, pac.nume, pac.prenume, p.data_consultatie, 
                       p.ora_consultatie, p.tip_plata, p.status, p.observatii
                FROM programari p
                JOIN pacienti pac ON p.cnp = pac.cnp
                ORDER BY p.data_consultatie DESC, p.ora_consultatie DESC
            ''', conn)
            return df
    except Exception as e:
        logger.error(f"Eroare obținere programări: {e}")
        return pd.DataFrame()

def obtine_numar_programari_zi(data_str, tip_plata=None):
    """Număr programări pentru o zi"""
    try:
        with sqlite3.connect('cabinet.db') as conn:
            c = conn.cursor()
            
            if tip_plata:
                c.execute('''
                    SELECT COUNT(*) FROM programari 
                    WHERE data_consultatie = ? AND tip_plata = ? AND status != 'Anulat'
                ''', (data_str, tip_plata))
            else:
                c.execute('''
                    SELECT COUNT(*) FROM programari 
                    WHERE data_consultatie = ? AND status != 'Anulat'
                ''', (data_str,))
            
            return c.fetchone()[0]
    except Exception as e:
        logger.error(f"Eroare numărare: {e}")
        return 0

@st.cache_data(ttl=60)
def obtine_programari_interval(data_start, data_end):
    """
    Obține număr programări pentru un interval (1 singur query!)
    """
    try:
        with sqlite3.connect('cabinet.db') as conn:
            c = conn.cursor()
            c.execute('''
                SELECT data_consultatie, COUNT(*) as nr
                FROM programari 
                WHERE data_consultatie BETWEEN ? AND ?
                  AND tip_plata = 'Bilet trimitere'
                  AND status != 'Anulat'
                GROUP BY data_consultatie
            ''', (data_start, data_end))
            
            rezultat = {row[0]: row[1] for row in c.fetchall()}
            logger.info(f"Cache: {len(rezultat)} zile cu programări între {data_start}-{data_end}")
            return rezultat
    except Exception as e:
        logger.error(f"Eroare obținere interval: {e}")
        return {}

def genereaza_ore_disponibile_bilet(data_str):
    """Ore disponibile bilet - folosește PROGRAM_MEDICAL"""
    try:
        config = PROGRAM_MEDICAL['bilet_trimitere']
        
        with sqlite3.connect('cabinet.db') as conn:
            c = conn.cursor()
            c.execute('''
                SELECT ora_consultatie 
                FROM programari 
                WHERE data_consultatie = ? AND tip_plata = "Bilet trimitere"
                  AND status != 'Anulat'
            ''', (data_str,))
            
            ore_ocupate = [row[0] for row in c.fetchall()]
            
            ore_posibile = []
            ora_start = config['ora_start']
            ora_sfarsit = config['ora_end']
            interval = config['interval_minute']
            max_pacienti = config['max_pacienti']
            
            ora_curenta = datetime.combine(date.today(), ora_start)
            ora_finala = datetime.combine(date.today(), ora_sfarsit)
            
            while ora_curenta <= ora_finala and len(ore_posibile) < max_pacienti:
                ora_str = ora_curenta.strftime('%H:%M')
                if ora_str not in ore_ocupate:
                    ore_posibile.append(ora_curenta.time())
                ora_curenta += timedelta(minutes=interval)
            
            return ore_posibile, len(ore_ocupate)
    except Exception as e:
        logger.error(f"Eroare generare ore: {e}")
        return [], 0

def verifica_interval_3_luni(cnp, data_noua):
    """Verifică 3 luni între programări bilet"""
    try:
        with sqlite3.connect('cabinet.db') as conn:
            c = conn.cursor()
            c.execute('''
                SELECT data_consultatie 
                FROM programari 
                WHERE cnp = ? AND tip_plata = "Bilet trimitere"
                ORDER BY data_consultatie DESC 
                LIMIT 1
            ''', (cnp,))
            
            rez = c.fetchone()
            
            if not rez:
                return True, 0, None
            
            ultima_data_str = rez[0]
            ultima_data = datetime.strptime(ultima_data_str, '%Y-%m-%d').date()
            
            if isinstance(data_noua, str):
                data_noua = datetime.strptime(data_noua, '%Y-%m-%d').date()
            
            diferenta = (data_noua - ultima_data).days
            
            if diferenta >= 90:
                return True, diferenta, formateaza_data_ro(ultima_data_str)
            else:
                return False, diferenta, formateaza_data_ro(ultima_data_str)
    except Exception as e:
        logger.error(f"Eroare verificare interval: {e}")
        return True, 0, None

def programeaza_optimizat(cnp, data_consultatie, ora_consultatie, observatii, tip_plata):
    """Adaugă programare"""
    try:
        with sqlite3.connect('cabinet.db') as conn:
            c = conn.cursor()
            
            c.execute('''
                SELECT COUNT(*) FROM programari 
                WHERE data_consultatie = ? AND ora_consultatie = ?
            ''', (data_consultatie, ora_consultatie))
            
            if c.fetchone()[0] > 0:
                return "❌ Ora ocupată!"
            
            c.execute('''
                INSERT INTO programari (cnp, data_consultatie, ora_consultatie, tip_plata, observatii)
                VALUES (?, ?, ?, ?, ?)
            ''', (cnp, data_consultatie, ora_consultatie, tip_plata, observatii))
            
            conn.commit()
            logger.info(f"Programare: CNP {cnp}, {data_consultatie} {ora_consultatie}")
            return f"✅ Programare confirmată {formateaza_data_ro(data_consultatie)} la {ora_consultatie}"
    except Exception as e:
        logger.error(f"Eroare programare: {e}")
        return f"❌ Eroare: {str(e)}"

def actualizeaza_status_programare(programare_id, nou_status):
    """Actualizează status programare"""
    try:
        with sqlite3.connect('cabinet.db') as conn:
            c = conn.cursor()
            c.execute("UPDATE programari SET status = ? WHERE id = ?", (nou_status, programare_id))
            conn.commit()
            logger.info(f"Status {programare_id} → {nou_status}")
            return True, f"✅ Status: {nou_status}"
    except Exception as e:
        logger.error(f"Eroare status: {e}")
        return False, f"❌ Eroare: {str(e)}"

def actualizeaza_programare_completa(programare_id, noua_data, noua_ora, observatii_noi):
    """
    Actualizează complet o programare (dată, oră, observații)
    
    Args:
        programare_id: ID-ul programării
        noua_data: Data nouă (string format YYYY-MM-DD)
        noua_ora: Ora nouă (string format HH:MM)
        observatii_noi: Observații noi
    
    Returns:
        tuple: (succes, mesaj)
    """
    try:
        with sqlite3.connect('cabinet.db') as conn:
            c = conn.cursor()
            
            # Verifică dacă noua dată/oră este ocupată (exclude programarea curentă)
            c.execute('''
                SELECT COUNT(*) FROM programari 
                WHERE data_consultatie = ? AND ora_consultatie = ? AND id != ?
            ''', (noua_data, noua_ora, programare_id))
            
            if c.fetchone()[0] > 0:
                return False, "❌ Ora este deja ocupată!"
            
            # Actualizează programarea
            c.execute('''
                UPDATE programari 
                SET data_consultatie = ?, ora_consultatie = ?, observatii = ?
                WHERE id = ?
            ''', (noua_data, noua_ora, observatii_noi, programare_id))
            
            conn.commit()
            logger.info(f"Programare {programare_id} modificată: {noua_data} {noua_ora}")
            return True, f"✅ Programare modificată: {formateaza_data_ro(noua_data)} la {noua_ora}"
            
    except Exception as e:
        logger.error(f"Eroare modificare programare: {e}")
        return False, f"❌ Eroare: {str(e)}"
    
def toggle_status_programare(programare_id, status_curent):
    """
    Toggle între Programat și Finalizat
    
    Args:
        programare_id: ID programare
        status_curent: Status actual
    
    Returns:
        tuple: (succes, mesaj, nou_status)
    """
    try:
        with sqlite3.connect('cabinet.db') as conn:
            c = conn.cursor()
            
            # Toggle: Programat → Finalizat → Programat
            if status_curent == 'Finalizat':
                nou_status = 'Programat'
                mesaj = "⏳"
            else:
                nou_status = 'Finalizat'
                mesaj = "✅"
            
            c.execute("UPDATE programari SET status = ? WHERE id = ?", (nou_status, programare_id))
            conn.commit()
            
            logger.info(f"Toggle status {programare_id}: {status_curent} → {nou_status}")
            return True, mesaj, nou_status
            
    except Exception as e:
        logger.error(f"Eroare toggle status: {e}")
        return False, f"❌ Eroare: {str(e)}", status_curent

def sterge_programare(programare_id):
    """Șterge programare"""
    try:
        with sqlite3.connect('cabinet.db') as conn:
            c = conn.cursor()
            c.execute("DELETE FROM programari WHERE id = ?", (programare_id,))
            conn.commit()
            logger.info(f"Programare {programare_id} ștearsă")
            return True, "✅ Programare ștearsă"
    except Exception as e:
        logger.error(f"Eroare ștergere: {e}")
        return False, f"❌ Eroare: {str(e)}"

def genereaza_calendar_luna(an, luna):
    """Generează calendar pentru o lună"""
    return calendar.monthcalendar(an, luna)

def componenta_sterge_pacient(cnp, nume_complet, key_prefix="del"):
    """
    Componentă reutilizabilă pentru ștergere cu confirmare
    """
    key_confirm = f'{key_prefix}_confirm_{cnp}'
    
    if key_confirm not in st.session_state:
        st.session_state[key_confirm] = False
    
    if not st.session_state[key_confirm]:
        if st.button("🗑️", key=f"{key_prefix}_btn_{cnp}", type="secondary", use_container_width=True, help="Șterge pacient"):
            st.session_state[key_confirm] = True
            st.rerun()
        return False
    else:
        col_c1, col_c2 = st.columns(2)
        
        with col_c1:
            if st.button("✅ DA", key=f"{key_prefix}_conf_{cnp}", type="primary", use_container_width=True):
                succes, msg, _ = sterge_pacient(cnp, sterge_si_programari=True)
                st.session_state[key_confirm] = False
                
                if succes:
                    st.success(msg)
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(msg)
                return False
        
        with col_c2:
            if st.button("❌ NU", key=f"{key_prefix}_canc_{cnp}", use_container_width=True):
                st.session_state[key_confirm] = False
                st.rerun()
        
        return True

# ========================================
# INIȚIALIZARE
# ========================================
initializeaza_baza_date()

# ========================================
# SISTEM BACKUP AUTOMAT ZILNIC iCloud
# ========================================

import platform  # ← ADAUGĂ la imports

class BackupManager:
    """Gestionare backup-uri automate în iCloud (cross-platform)"""
    
    def __init__(self):
        # Detectează sistemul de operare
        system = platform.system()
        
        if system == 'Darwin':  # macOS
            self.icloud_path = Path.home() / 'Library/Mobile Documents/com~apple~CloudDocs/cabinet_Backups'
        
        elif system == 'Windows':  # Windows
            # Încearcă mai multe variante
            possible_paths = [
                Path.home() / 'iCloudDrive' / 'cabinet_Backups',
                Path.home() / 'iCloud Drive' / 'cabinet_Backups',
            ]
            
            self.icloud_path = None
            for path in possible_paths:
                if path.parent.exists():
                    self.icloud_path = path
                    break
            
            # Fallback la Documents dacă iCloud nu există
            if self.icloud_path is None:
                logger.warning("⚠️ iCloud Drive nu a fost găsit, folosesc Documents")
                self.icloud_path = Path.home() / 'Documents' / 'cabinet_Backups'
        
        else:  # Linux
            self.icloud_path = Path.home() / 'Documents' / 'cabinet_Backups'
        
        self.db_file = Path('cabinet.db')
        self.config_file = self.icloud_path / 'backup_config.json'
        
        # Creează folder
        self.icloud_path.mkdir(parents=True, exist_ok=True)
        
        # Log pentru debugging
        logger.info(f"📁 Backup path: {self.icloud_path}")
    
    def get_last_backup_date(self):
        """Citește data ultimului backup"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    return datetime.fromisoformat(config.get('last_backup'))
            return None
        except:
            return None
    
    def save_last_backup_date(self, date):
        """Salvează data ultimului backup"""
        try:
            config = {
                'last_backup': date.isoformat(),
                'backup_count': self.get_backup_count()
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f)
        except Exception as e:
            logger.error(f"Eroare salvare config: {e}")
    
    def get_backup_count(self):
        """Numără backup-urile existente"""
        try:
            backups = list(self.icloud_path.glob('backup_*.db'))
            return len(backups)
        except:
            return 0
    
    def needs_backup(self):
        """Verifică dacă este necesar backup (mai mult de 24h)"""
        last_backup = self.get_last_backup_date()
        
        if last_backup is None:
            return True
        
        # Verifică dacă au trecut >24h
        time_diff = datetime.now() - last_backup
        return time_diff.total_seconds() > 86400  # 24 ore în secunde
    
    def create_backup(self):
        """Creează backup al bazei de date"""
        try:
            if not self.db_file.exists():
                return False, "❌ Baza de date nu există"
            
            # Nume fișier cu timestamp
            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            backup_file = self.icloud_path / f'backup_{timestamp}.db'
            
            # Copiază fișierul
            shutil.copy2(self.db_file, backup_file)
            
            # Salvează data backup-ului
            self.save_last_backup_date(datetime.now())
            
            # Curățare backup-uri vechi (păstrează ultimele 30)
            self.cleanup_old_backups(keep=30)
            
            logger.info(f"Backup creat: {backup_file}")
            return True, f"✅ Backup salvat în iCloud: {backup_file.name}"
        
        except Exception as e:
            logger.error(f"Eroare backup: {e}")
            return False, f"❌ Eroare backup: {str(e)}"
    
    def cleanup_old_backups(self, keep=30):
        """Șterge backup-urile mai vechi (păstrează ultimele X)"""
        try:
            backups = sorted(self.icloud_path.glob('backup_*.db'))
            
            if len(backups) > keep:
                # Șterge cele mai vechi
                for backup in backups[:-keep]:
                    backup.unlink()
                    logger.info(f"Backup vechi șters: {backup.name}")
        
        except Exception as e:
            logger.error(f"Eroare cleanup: {e}")
    
    def get_backup_info(self):
        """Returnează informații despre backup-uri"""
        try:
            last_backup = self.get_last_backup_date()
            backup_count = self.get_backup_count()
            
            if last_backup:
                time_ago = datetime.now() - last_backup
                hours = int(time_ago.total_seconds() / 3600)
                
                if hours < 24:
                    last_backup_text = f"{hours}h în urmă"
                else:
                    days = int(hours / 24)
                    last_backup_text = f"{days} zile în urmă"
            else:
                last_backup_text = "Niciodată"
            
            return {
                'last_backup': last_backup_text,
                'backup_count': backup_count,
                'needs_backup': self.needs_backup()
            }
        
        except:
            return {
                'last_backup': 'N/A',
                'backup_count': 0,
                'needs_backup': True
            }

# ========================================
# FUNCȚIE RESTAURARE BACKUP
# ========================================

def restore_from_backup(backup_file):
    """Restaurează baza de date dintr-un backup"""
    try:
        if not backup_file.exists():
            return False, "❌ Fișier backup nu există"
        
        # Backup curent înainte de restore
        shutil.copy2('cabinet.db', 'cabinet_before_restore.db')
        
        # Restore
        shutil.copy2(backup_file, 'cabinet.db')
        
        return True, f"✅ Baza de date restaurată din {backup_file.name}"
    
    except Exception as e:
        return False, f"❌ Eroare restore: {str(e)}"

# Creează instanță globală
backup_manager = BackupManager()
# Creează instanță globală
backup_manager = BackupManager()

# ⭐ VERIFICARE AUTOMATĂ LA PORNIRE APLICAȚIE ⭐
if backup_manager.needs_backup():
    logger.info("🔄 Backup automat declanșat...")
    succes, mesaj = backup_manager.create_backup()
    if succes:
        logger.info(mesaj)
    else:
        logger.error(mesaj)

# Session state
if 'pagina' not in st.session_state:
    st.session_state.pagina = "Acasă"
if 'afiseaza_detalii_zi' not in st.session_state:
    st.session_state.afiseaza_detalii_zi = False
if 'data_selectata_calendar' not in st.session_state:
    st.session_state.data_selectata_calendar = None
if 'pacient_detalii_selectat' not in st.session_state:
    st.session_state.pacient_detalii_selectat = None
if 'pacient_selectat_id' not in st.session_state:
    st.session_state.pacient_selectat_id = None
if 'pacient_modifica' not in st.session_state:
    st.session_state.pacient_modifica = None
if 'pacient_search_selectat' not in st.session_state:
    st.session_state.pacient_search_selectat = None
if 'pacient_modifica_search' not in st.session_state:
    st.session_state.pacient_modifica_search = None

# ========================================
# SIDEBAR
# ========================================
with st.sidebar:
    st.markdown("""
    <div style='text-align: center; padding: 3px 6px; margin-bottom: 3px;'>
        <!-- Emoji ⚕️ cu border circular -->
        <div style='width: 40px; 
                    height: 40px; 
                    margin: 0 auto 4px auto;
                    border: 3px solid white;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    background: transparent;
                    box-shadow: 0 2px 6px rgba(0,0,0,0.2);'>
            <span style='font-size: 24px; line-height: 1;'>⚕️</span>
        </div>
        <h2 style='margin: 0 0 2px 0; font-size: 15px; line-height: 1.1;'>Cabinet Medical</h2>
        <p style='color: #666; margin: 0; font-size: 14px; line-height: 0;'>Dr. Pop V. Maria</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("<div style='height: 60px;'></div>", unsafe_allow_html=True)
    
    if st.button("🏠 Acasă", use_container_width=True, type="primary" if st.session_state.pagina == "Acasă" else "secondary"):
        st.session_state.pagina = "Acasă"
        st.session_state.afiseaza_detalii_zi = False
        st.rerun()
    
    if st.button("➕ Adaugă Pacient", use_container_width=True, type="primary" if st.session_state.pagina == "Adaugă Pacient" else "secondary"):
        st.session_state.pagina = "Adaugă Pacient"
        st.rerun()
    
    if st.button("📅 Programează", use_container_width=True, type="primary" if st.session_state.pagina == "Programează" else "secondary"):
        st.session_state.pagina = "Programează"
        st.rerun()
    
    if st.button("🔍 Caută Pacient", use_container_width=True, type="primary" if st.session_state.pagina == "Caută Pacient" else "secondary"):
        st.session_state.pagina = "Caută Pacient"
        st.rerun()
    
    if st.button("👥 Toți Pacienții", use_container_width=True, type="primary" if st.session_state.pagina == "Toți Pacienții" else "secondary"):
        st.session_state.pagina = "Toți Pacienții"
        st.rerun()

    st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)        
    
    st.markdown("---")
    st.markdown(f"**Astăzi:** {datetime.now().strftime('%d/%m/%Y')}")
    st.metric("Total Pacienți", len(obtine_toti_pacientii()))

    # ========================================
    # SECȚIUNE BACKUP iCloud
    # ========================================
    
    st.markdown("---")
    st.markdown("### 💾 Backup iCloud")
    
    # Informații backup
    backup_info = backup_manager.get_backup_info()
    
    col_b1, col_b2 = st.columns(2)
    
    with col_b1:
        st.metric("Ultimul backup", backup_info['last_backup'])
    
    with col_b2:
        st.metric("Total backup-uri", backup_info['backup_count'])
    
    # Buton backup manual
    if st.button("💾 Backup Acum", 
                 use_container_width=True, 
                 type="primary" if backup_info['needs_backup'] else "secondary"):
        with st.spinner("Salvare în iCloud..."):
            succes, mesaj = backup_manager.create_backup()
            if succes:
                st.success(mesaj)
                time.sleep(1.5)
                st.rerun()
            else:
                st.error(mesaj)
    
    # Indicator vizual
    if backup_info['needs_backup']:
        st.warning("⚠️ Backup necesar (>24h)")
    else:
        st.success("✅ Backup la zi")

    # ========================================
    # SECȚIUNE RESTAURARE (Expander)
    # ========================================
    
    with st.expander("🔄 Restaurare din Backup"):
        # Lista backup-uri disponibile
        backups = sorted(backup_manager.icloud_path.glob('backup_*.db'), reverse=True)
        
        if backups:
            backup_names = [b.name for b in backups[:10]]  # Ultimele 10
            
            selected_backup = st.selectbox(
                "Selectează backup:",
                backup_names,
                key="restore_select"
            )
            
            if st.button("🔄 Restaurează", 
                        type="secondary", 
                        use_container_width=True,
                        key="btn_restore"):
                backup_path = backup_manager.icloud_path / selected_backup
                succes, mesaj = restore_from_backup(backup_path)
                
                if succes:
                    st.success(mesaj)
                    st.warning("⚠️ Reîncarcă aplicația pentru a vedea datele restaurate!")
                    st.info("💡 Apasă Ctrl+R sau F5")
                else:
                    st.error(mesaj)
        else:
            st.info("📭 Niciun backup disponibil")

# ========================================
# ROUTING
# ========================================
pagina = st.session_state.pagina

# ========================================
# PAGINA: ACASĂ
# ========================================

if pagina == "Acasă":
    # ⭐ ADAUGĂ CSS PENTRU ELIMINARE SPAȚIU TOP ⭐
    
    col_titlu, col_stats = st.columns([2, 3])
    
    with col_titlu:
        st.markdown("""
        <div style='padding-top: 0px; margin-top: -10px;'>
            <h1 style='margin: 0 0 3px 0; font-size: 50px;'>
                Programări Pacienți
            </h1>
        </div>
        """, unsafe_allow_html=True)
    
    with col_stats:
        # ⭐ FOLOSEȘTE data_afisata ÎN LOC DE data_azi ⭐
        data_afisata_stats = st.session_state.get('data_selectata_calendar')
        if not data_afisata_stats:
            data_afisata_stats = datetime.now().date().strftime('%Y-%m-%d')
        
        try:
            with sqlite3.connect('cabinet.db') as conn:
                c = conn.cursor()
                
                # Total programați (exclude Anulat)
                c.execute('''
                    SELECT COUNT(*) FROM programari 
                    WHERE data_consultatie = ? AND status != 'Anulat'
                ''', (data_afisata_stats,))
                programati_azi = c.fetchone()[0]
                
                # Bilete trimitere (exclude Anulat)
                c.execute('''
                    SELECT COUNT(*) FROM programari 
                    WHERE data_consultatie = ? AND tip_plata = 'Bilet trimitere' AND status != 'Anulat'
                ''', (data_afisata_stats,))
                cu_bilet = c.fetchone()[0]
                
                # Cu plată (exclude Anulat)
                c.execute('''
                    SELECT COUNT(*) FROM programari 
                    WHERE data_consultatie = ? AND tip_plata = 'Cu plată' AND status != 'Anulat'
                ''', (data_afisata_stats,))
                cu_plata = c.fetchone()[0]
        except:
            programati_azi = 0
            cu_bilet = 0
            cu_plata = 0
      
        st.markdown(f"""
        <div style='display: flex; gap: 30px; justify-content: flex-end; align-items: center; padding-top: 8px;'>
            <div style='text-align: center;'>
                <div style='font-size: 13px; color: white; font-weight: 400; margin-bottom: 2px;'>📅 Programați</div>
                <div style='font-size: 32px; font-weight: 300; color: white;'>{programati_azi}</div>
            </div>
            <div style='text-align: center;'>
                <div style='font-size: 13px; color: white; font-weight: 400; margin-bottom: 2px;'>📋 Bilete Trimitere</div>
                <div style='font-size: 32px; font-weight: 300; color: white;'>{cu_bilet}</div>
            </div>
            <div style='text-align: center;'>
                <div style='font-size: 13px; color: white; font-weight: 400; margin-bottom: 2px;'>💳 Cu Plată</div>
                <div style='font-size: 32px; font-weight: 300; color: white;'>{cu_plata}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<hr style='margin: 15px 0; border: none; border-top: 1px solid #ddd;'>", unsafe_allow_html=True)
    
    # ⭐ DEFINIȚIE data_afisata ⭐
    data_afisata = st.session_state.get('data_selectata_calendar')
    if not data_afisata:
        data_afisata = datetime.now().date().strftime('%Y-%m-%d')
    
    st.markdown(f"""
    <div style='margin-bottom: 10px;'>
        <h4 style='margin: 0 0 8px 0; font-size: 18px; color: #667eea;'>
            📋 Programați {formateaza_data_ro(data_afisata)}
        </h4>
    </div>
    """, unsafe_allow_html=True)
    
    try:
        with sqlite3.connect('cabinet.db') as conn:
            programari_zi = pd.read_sql_query('''
                SELECT 
                    p.id,
                    pac.nume,
                    pac.prenume,
                    pac.cnp,
                    pac.data_nasterii,
                    p.ora_consultatie,
                    pac.telefon,
                    p.tip_plata,
                    p.status,
                    p.observatii
                FROM programari p
                JOIN pacienti pac ON p.cnp = pac.cnp
                WHERE p.data_consultatie = ? AND p.status != 'Anulat'
                ORDER BY p.ora_consultatie
            ''', conn, params=(data_afisata,))
        
        if not programari_zi.empty:
            # CSS pentru butoane LATE și JOASE
            st.markdown("""
            <style>
            /* Eliminare spațiu între coloane în tabel programări zi */
            section[data-testid="stHorizontalBlock"]:has(+ hr) div[data-testid="column"] {
                padding: 0 3px !important;
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
            }
            
            /* Eliminare margin pentru element-container în tabel */
            section[data-testid="stHorizontalBlock"]:has(+ hr) .element-container {
                margin: 0 !important;
                padding: 0 !important;
            }
            
            /* Butoane LATE și JOASE - 14px height */
            section[data-testid="stHorizontalBlock"]:has(+ hr) .stButton button {
                padding: 0px 8px !important;
                margin: 0 auto !important;
                height: 14px !important;
                min-height: 14px !important;
                max-height: 14px !important;
                width: auto !important;
                min-width: 40px !important;
                font-size: 10px !important;
                line-height: 1 !important;
                border-radius: 3px !important;
            }
            
            /* Rânduri ultra-compacte */
            section[data-testid="stHorizontalBlock"]:has(+ hr) div[data-testid="stHorizontalBlock"] {
                gap: 0 !important;
                margin: 0 !important;
            }
            </style>
            """, unsafe_allow_html=True)
            
            # Header tabel (10 coloane OPTIMIZATE: Nr, Nume Prenume, Data Nașterii, Oră, Telefon, Observații, Tip, Modifică, Anulează, Status)
            st.markdown("""
            <div style='display: grid; 
                        grid-template-columns: 0.3fr 2fr 0.9fr 0.6fr 1fr 1.8fr 0.4fr 0.55fr 0.55fr 0.55fr; 
                        gap: 8px; 
                        padding: 10px 15px; 
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                        border-radius: 8px; 
                        margin-bottom: 8px;
                        font-weight: 700;
                        color: white;
                        font-size: 14px;
                        align-items: center;'>
                <div style='text-align: center;'>Nr.</div>
                <div style='text-align: left; padding-left: 8px;'>Nume Prenume</div>
                <div style='text-align: center;'>Data Nașterii</div>
                <div style='text-align: center;'>Oră</div>
                <div style='text-align: center;'>Telefon</div>
                <div style='text-align: left; padding-left: 8px;'>Observații</div>
                <div style='text-align: center;'>Tip</div>
                <div style='text-align: center; font-size: 12px;'>Modifică</div>
                <div style='text-align: center; font-size: 12px;'>Anulează</div>
                <div style='text-align: center; font-size: 12px;'>Status</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Afișare fiecare programare - OPTIMIZAT
            for idx, prog in programari_zi.iterrows():
                col1, col2, col3, col4, col5, col6, col7, col8, col9, col10 = st.columns([0.3, 2, 0.9, 0.6, 1, 1.8, 0.4, 0.55, 0.55, 0.55], gap="small")
                
                with col1:
                    # Nr. - centrat
                    st.markdown(f"<div style='padding: 0; margin: 0; display: flex; align-items: center; justify-content: center; height: 28px; color: #f0f0f0; font-size: 15px;'>{idx + 1}</div>", unsafe_allow_html=True)
                
                with col2:
                    # NUME PRENUME - stânga, padding 8px
                    nume_complet = f"{prog['nume'].upper()} {prog['prenume'].upper()}"
                    st.markdown(f"<div style='padding: 0 0 0 8px; margin: 0; display: flex; align-items: center; justify-content: flex-start; height: 28px; color: #f0f0f0; font-weight: 600; font-size: 15px;'>{nume_complet}</div>", unsafe_allow_html=True)
                
                with col3:
                    # Data Nașterii - centrat
                    data_nasterii_formatted = formateaza_data_ro(prog['data_nasterii']) if prog['data_nasterii'] else '-'
                    st.markdown(f"<div style='padding: 0; margin: 0; display: flex; align-items: center; justify-content: center; height: 28px; color: #f0f0f0; font-size: 14px;'>{data_nasterii_formatted}</div>", unsafe_allow_html=True)
                
                with col4:
                    # Oră - centrat, bold
                    st.markdown(f"<div style='padding: 0; margin: 0; display: flex; align-items: center; justify-content: center; height: 28px; color: #f0f0f0; font-weight: 600; font-size: 15px;'>{prog['ora_consultatie']}</div>", unsafe_allow_html=True)
                
                with col5:
                    # Telefon - centrat
                    telefon_display = prog['telefon'] if prog['telefon'] else '-'
                    st.markdown(f"<div style='padding: 0; margin: 0; display: flex; align-items: center; justify-content: center; height: 28px; color: #f0f0f0; font-size: 14px;'>{telefon_display}</div>", unsafe_allow_html=True)
                
                with col6:
                    # OBSERVAȚII - stânga, padding 8px, truncat 35 caractere
                    observatii_display = prog['observatii'] if prog['observatii'] else '-'
                    if len(str(observatii_display)) > 35:
                        observatii_display = str(observatii_display)[:35] + '...'
                    st.markdown(f"<div style='padding: 0 0 0 8px; margin: 0; display: flex; align-items: center; justify-content: flex-start; height: 28px; color: #f0f0f0; font-size: 13px;' title='{prog['observatii'] if prog['observatii'] else ''}'>{observatii_display}</div>", unsafe_allow_html=True)
                
                with col7:
                    # Tip - centrat, emoji
                    tip_emoji = "📋" if prog['tip_plata'] == 'Bilet trimitere' else "💳"
                    st.markdown(f"<div style='padding: 0; margin: 0; display: flex; align-items: center; justify-content: center; height: 28px; font-size: 16px;'>{tip_emoji}</div>", unsafe_allow_html=True)
                
                with col8:
                    if st.button("✏️", key=f"edit_prog_{prog['id']}", use_container_width=True, help="Modifică programarea"):
                        st.session_state[f'modifica_programare_{prog["id"]}'] = True
                        st.rerun()
                
                with col9:
                    if prog['status'] != 'Anulat':
                        if st.button("❌", key=f"anuleaza_{prog['id']}", use_container_width=True, type="secondary", help="Anulează programarea"):
                            actualizeaza_status_programare(prog['id'], 'Anulat')
                            st.rerun()
                    else:
                        st.markdown("<div style='display: flex; align-items: center; justify-content: center; height: 14px; font-size: 14px;'>❌</div>", unsafe_allow_html=True)
                
                with col10:
                    if prog['status'] == 'Anulat':
                        st.markdown("<div style='display: flex; align-items: center; justify-content: center; height: 14px; font-size: 13px; color: #dc2626;'>❌</div>", unsafe_allow_html=True)
                    elif prog['status'] == 'Finalizat':
                        if st.button("✅", key=f"valideaza_{prog['id']}", use_container_width=True, type="primary", help="Click pentru a retrage validarea"):
                            succes, msg, _ = toggle_status_programare(prog['id'], prog['status'])
                            if succes:
                                st.success(msg)
                                time.sleep(0.5)
                                st.rerun()
                    else:
                        if st.button("☐", key=f"valideaza_{prog['id']}", use_container_width=True, help="Click pentru a valida consultația"):
                            succes, msg, _ = toggle_status_programare(prog['id'], prog['status'])
                            if succes:
                                st.success(msg)
                                time.sleep(0.5)
                                st.rerun()
                
                # PĂSTREAZĂ restul codului (panel modificare) NESCHIMBAT
                
                if st.session_state.get(f'modifica_programare_{prog["id"]}', False):
                    st.markdown("""
                    <div style='background: #fff9e6; 
                                border-left: 4px solid #f59e0b; 
                                border-radius: 8px; 
                                padding: 15px; 
                                margin: 4px 0;
                                box-shadow: 0 4px 12px rgba(245,158,11,0.15);'>
                    """, unsafe_allow_html=True)
                    
                    st.markdown(f"### ✏️ Modifică Programare - {prog['nume']} {prog['prenume']}")
                    
                    with st.form(f"form_modifica_programare_{prog['id']}"):
                        col_m1, col_m2 = st.columns(2)
                        
                        with col_m1:
                            noua_data = st.date_input(
                                "Noua dată:",
                                value=datetime.strptime(data_afisata, '%Y-%m-%d').date(),
                                min_value=datetime.now().date(),
                                format="DD/MM/YYYY"
                            )
                        
                        with col_m2:
                            data_str_noua = noua_data.strftime('%Y-%m-%d')
                            ore_disp_modif, _ = genereaza_ore_disponibile_bilet(data_str_noua)
                            
                            if prog['tip_plata'] == 'Bilet trimitere' and ore_disp_modif:
                                ora_idx = st.selectbox(
                                    "Noua oră:",
                                    range(len(ore_disp_modif)),
                                    format_func=lambda x: ore_disp_modif[x].strftime('%H:%M')
                                )
                                noua_ora = ore_disp_modif[ora_idx]
                            else:
                                config_plata = PROGRAM_MEDICAL['cu_plata']
                                noua_ora = st.time_input(
                                    "Noua oră:",
                                    value=datetime.strptime(prog['ora_consultatie'], '%H:%M').time(),
                                    help=f"Program: {config_plata['ora_start'].strftime('%H:%M')}-{config_plata['ora_end'].strftime('%H:%M')}"
                                )
                        
                        observatii_noi = st.text_area("Observații noi:", value=prog['observatii'] if prog['observatii'] else "", height=80)
                        
                        col_btn1, col_btn2 = st.columns([3, 1])
                        
                        with col_btn1:
                            submit_modif = st.form_submit_button("✅ Salvează", use_container_width=True, type="primary")
                        
                        with col_btn2:
                            cancel_modif = st.form_submit_button("❌ Anulează", use_container_width=True)
                        
                        if submit_modif:
                            succes, mesaj = actualizeaza_programare_completa(
                                prog['id'],
                                data_str_noua,
                                noua_ora.strftime('%H:%M'),
                                observatii_noi
                            )
                            
                            if succes:
                                st.success(mesaj)
                                st.session_state[f'modifica_programare_{prog["id"]}'] = False
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(mesaj)
                        
                        if cancel_modif:
                            st.session_state[f'modifica_programare_{prog["id"]}'] = False
                            st.rerun()
                    
                    st.markdown("</div>", unsafe_allow_html=True)
            
            col_stats_footer, col_buton_inapoi = st.columns([3, 1])
            
            with col_stats_footer:
                nr_bilete = len(programari_zi[programari_zi['tip_plata'] == 'Bilet trimitere'])
                nr_plata = len(programari_zi[programari_zi['tip_plata'] == 'Cu plată'])
                st.caption(f"📊 Total: {len(programari_zi)} | 📋 {nr_bilete} | 💳 {nr_plata}")
            
            with col_buton_inapoi:
                if st.session_state.get('afiseaza_detalii_zi', False):
                    if st.button("🔙 Înapoi", use_container_width=True, key="inapoi_footer"):
                        st.session_state.afiseaza_detalii_zi = False
                        st.rerun()
        
        else:
            st.info(f"📭 Nicio programare pentru {formateaza_data_ro(data_afisata)}")
            
            if st.session_state.get('afiseaza_detalii_zi', False):
                if st.button("🔙 Înapoi", use_container_width=True, key="inapoi_gol"):
                    st.session_state.afiseaza_detalii_zi = False
                    st.rerun()
                    
    except Exception as e:
        st.error(f"Eroare: {e}")
        logger.error(f"Eroare tabel: {e}")
    
    st.markdown("<hr style='margin: 15px 0;'>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    if not st.session_state.get('afiseaza_detalii_zi', False):
        st.subheader("📅 Programări lunare")
        
        data_curenta = datetime.now()
        luni_afisate = []
        
        for i in range(4):
            data_luna = data_curenta + timedelta(days=30*i)
            data_luna = data_luna.replace(day=1)
            luni_afisate.append((data_luna.year, data_luna.month))
        
        luni_afisate = sorted(list(set(luni_afisate)))[:4]
        
        luni_ro = ['', 'Ianuarie', 'Februarie', 'Martie', 'Aprilie', 'Mai', 'Iunie',
                   'Iulie', 'August', 'Septembrie', 'Octombrie', 'Noiembrie', 'Decembrie']
        
        prima_luna_an, prima_luna_nr = luni_afisate[0]
        ultima_luna_an, ultima_luna_nr = luni_afisate[-1]
        
        data_start = datetime(prima_luna_an, prima_luna_nr, 1).strftime('%Y-%m-%d')
        
        ultima_zi_luna = datetime(ultima_luna_an, ultima_luna_nr, 1) + timedelta(days=32)
        ultima_zi_luna = ultima_zi_luna.replace(day=1) - timedelta(days=1)
        data_end = ultima_zi_luna.strftime('%Y-%m-%d')
        
        programari_cache = obtine_programari_interval(data_start, data_end)
        
        logger.info(f"📊 Cache calendar: {data_start} → {data_end} ({len(programari_cache)} zile cu programări)")
        
        # ⭐ CSS PENTRU CULORI ⭐

        # ⭐ ACEASTĂ BUCLĂ TREBUIE SĂ APARĂ DOAR O DATĂ ⭐
        for rand in range(2):
            cols_cal = st.columns(2)
            
            for col_idx in range(2):
                luna_idx = rand * 2 + col_idx
                
                if luna_idx < len(luni_afisate):
                    an, luna = luni_afisate[luna_idx]
                    
                    with cols_cal[col_idx]:
                        # HEADER lunii
                        st.markdown(f"""
                        <div style='border: 3px solid #667eea;
                                    border-radius: 12px;
                                    padding: 6px 8px;
                                    margin: 8px 4px;
                                    box-shadow: 0 4px 16px rgba(102,126,234,0.5);
                                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);'>
                            <h4 style='text-align: center; 
                                       color: white; 
                                       margin: 0; 
                                       font-size: 16px; 
                                       font-weight: 800;
                                       letter-spacing: 0.5px;'>
                                📆 {luni_ro[luna]} {an}
                            </h4>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Header zile săptămână
                        cols_header = st.columns(7)
                        for idx, zi in enumerate(['L', 'M', 'M', 'J', 'V', 'S', 'D']):
                            with cols_header[idx]:
                                st.markdown(f"""
                                <div style='text-align: center; 
                                            font-weight: 800; 
                                            font-size: 12px;
                                            color: #1a1a1a; 
                                            padding: 6px 2px;
                                            margin: 2px 1px;
                                            background: #ffffff;
                                            border-radius: 5px; 
                                            border: 2px solid #667eea;'>
                                    {zi}
                                </div>
                                """, unsafe_allow_html=True)
                        
                        # Grid zile lunii
                        cal_luna = genereaza_calendar_luna(an, luna)
                        data_azi = datetime.now().date()
                        
                        for saptamana in cal_luna:
                            cols_zile = st.columns(7, gap="small")
                            
                            for idx_zi, zi in enumerate(saptamana):
                                if zi == 0:
                                    cols_zile[idx_zi].markdown("<div style='height: 36px;'></div>", unsafe_allow_html=True)
                                else:
                                    data_zi = datetime(an, luna, zi).date()
                                    data_zi_str = data_zi.strftime('%Y-%m-%d')
                                    
                                    este_azi = (data_zi == datetime.now().date())
                                    este_trecut = data_zi < datetime.now().date()
                                    
                                    nr_prog = programari_cache.get(data_zi_str, 0)
                                    
                                    if este_trecut:
                                        emoji = "⚫"
                                    elif nr_prog >= 14:
                                        emoji = "🔴"
                                    elif nr_prog >= 12:
                                        emoji = "🟠"
                                    elif nr_prog > 0:
                                        emoji = "🟢"
                                    else:
                                        emoji = "⚪"
                                    
                                    try:
                                        este_sarbatoare = este_sarbatoare_legala(data_zi)
                                    except:
                                        este_sarbatoare = False
                                    
                                    # ⭐ FORȚEAZĂ: Ziua curentă NU este niciodată sărbătoare
                                    if este_azi:
                                        este_sarbatoare = False
                                    
                                    # ⭐ DACĂ ESTE SĂRBĂTOARE - HTML PORTOCALIU ⭐
                                    if este_sarbatoare:
                                        # ⭐ Obține numele sărbătorii ÎNAINTE de a o folosi
                                        nume_sarbatoare = obtine_nume_sarbatoare(data_zi)
                                        
                                        cols_zile[idx_zi].markdown(f"""
                                        <div style='
                                            background: linear-gradient(135deg, #FF8C00 0%, #FF6600 100%);
                                            background: linear-gradient(135deg, #607D8B, #455A64);
                                            border-radius: 4px;
                                            padding: 0;
                                            text-align: center;
                                            color: white;
                                            font-weight: 900;
                                            font-size: 13px;
                                            cursor: not-allowed;
                                            margin: 0;
                                            height: 36px;
                                            line-height: 36px;
                                            box-shadow: 0 4px 8px rgba(0,0,0,0.2) !important;
                                            opacity: 0.8;
                                            transition: opacity 0.2s ease;                       
                                        '
                                        title='{nume_sarbatoare} - {data_zi.strftime("%d/%m/%Y")}'
                                        onmouseover="this.style.opacity='1'"                           
                                        onmouseout="this.style.opacity='0.8'">   
                                           {zi}
                                        </div>
                                        """, unsafe_allow_html=True)
                                    
                                    # ⭐ ALTFEL - BUTON STREAMLIT ⭐
                                    else:
                                        if este_azi:
                                            buton_text = f"{emoji}\n{zi}"
                                            buton_type = "primary"
                                            buton_help = f"🌟 AZI - {data_zi.strftime('%d/%m/%Y')} - {nr_prog}/14"
                                        else:
                                            buton_text = f"{emoji}\n{zi}"
                                            buton_type = "secondary"
                                            buton_help = f"{data_zi.strftime('%d/%m/%Y')} - {nr_prog}/14"
                                        
                                        if cols_zile[idx_zi].button(
                                            buton_text,
                                            key=f"cal_{rand}_{col_idx}_{an}_{luna}_{zi}",
                                            use_container_width=True,
                                            type=buton_type,
                                            help=buton_help
                                        ):
                                            st.session_state['data_selectata_calendar'] = data_zi_str
                                            st.session_state['afiseaza_detalii_zi'] = True
                                            st.rerun()
                            
                            st.markdown("</div>", unsafe_allow_html=True)
    
    else:
        if st.button("🔙 Înapoi la calendar", use_container_width=True, type="primary"):
            st.session_state.afiseaza_detalii_zi = False
            st.rerun()
            
# ========================================
# PAGINA: ADAUGĂ PACIENT
# ========================================

elif pagina == "Adaugă Pacient":
    st.title("➕ Adaugă Pacient Nou")
    
    st.markdown("---")
    
    if 'cnp_input_temp' not in st.session_state:
        st.session_state.cnp_input_temp = ""
    
    cnp_input = st.text_input(
        "🔢 CNP Pacient *", 
        max_chars=13,
        placeholder="Introdu CNP-ul (13 cifre) - verificare automată",
        key="cnp_adauga_pacient",
        help="CNP-ul este verificat automat în baza de date"
    )
    
    if cnp_input and len(cnp_input) == 13:
        pacient_existent = obtine_pacient_cnp(cnp_input)
        
        if pacient_existent:
            st.error("⚠️ **PACIENT EXISTENT ÎN BAZA DE DATE!**")
            
            col_info1, col_info2 = st.columns(2)
            
            with col_info1:
                st.info(f"""
                **Nume:** {formateaza_nume_majuscula(pacient_existent[2], pacient_existent[3])}  
                **CNP:** {pacient_existent[1]}  
                **Data nașterii:** {formateaza_data_ro(pacient_existent[4]) if pacient_existent[4] else 'N/A'}
                """)
            
            with col_info2:
                st.info(f"""
                **Telefon:** {pacient_existent[5] if pacient_existent[5] else 'N/A'}  
                **Email:** {pacient_existent[6] if pacient_existent[6] else 'N/A'}  
                **Adresă:** {pacient_existent[7] if pacient_existent[7] else 'N/A'}
                """)
            
            st.markdown("---")
            
            col_act1, col_act2 = st.columns(2)
            
            with col_act1:
                if st.button("📅 Programează acest pacient", use_container_width=True, type="primary"):
                    st.session_state.pacient_selectat_id = cnp_input
                    st.session_state.pagina = "Programează"
                    st.rerun()
            
            with col_act2:
                if st.button("👁️ Vezi detalii complete", use_container_width=True):
                    st.session_state.pacient_detalii_selectat = cnp_input
                    st.session_state.pagina = "Toți Pacienții"
                    st.rerun()
            
            st.warning("💡 Șterge CNP-ul din câmp pentru a adăuga un pacient NOU")
            
        else:
            st.success("✅ CNP valid - Pacient NOU (nu există în baza de date)")
            
            st.markdown("---")
            st.markdown("### 📋 Date Pacient Nou")
            
            with st.form("form_pacient_nou", clear_on_submit=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    nume = st.text_input("Nume *", placeholder="Ex: Popescu")
                    prenume = st.text_input("Prenume *", placeholder="Ex: Maria")
                    data_nasterii = st.date_input(
                        "Data nașterii *",
                        min_value=date(1900, 1, 1),
                        max_value=date.today(),
                        value=date(2000, 1, 1),
                        format="DD/MM/YYYY"
                    )
                
                with col2:
                    telefon = st.text_input("Telefon", placeholder="0712 345 678")
                    email = st.text_input("Email", placeholder="nume@email.ro")
                    adresa = st.text_input("Adresă", placeholder="Str. Exemplu, Nr. 1")
                
                observatii = st.text_area("Observații medicale (opțional)", height=80)
                
                st.markdown("---")
                
                col_btn1, col_btn2 = st.columns([3, 1])
                
                with col_btn1:
                    submit = st.form_submit_button("✅ Salvează Pacient", use_container_width=True, type="primary")
                
                with col_btn2:
                    cancel = st.form_submit_button("❌ Anulează", use_container_width=True)
                
                if submit:
                    if not nume or not prenume:
                        st.error("❌ Numele și prenumele sunt obligatorii!")
                    else:
                        valid, msg_valid = valideaza_cnp(cnp_input)
                        
                        if not valid:
                            st.error(msg_valid)
                        else:
                            succes, mesaj, _ = adauga_pacient(
                                cnp_input, nume, prenume, data_nasterii,
                                telefon, email, adresa, observatii
                            )
                            
                            if succes:
                                st.success(mesaj)
                                st.balloons()
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error(mesaj)
                
                if cancel:
                    st.rerun()
    
    elif cnp_input and len(cnp_input) > 0:
        st.info(f"⏳ Continuă să tastezi... ({len(cnp_input)}/13 cifre)")
    
    else:
        st.info("""
        💡 **Cum funcționează:**
        
        1. Introdu CNP-ul pacientului (13 cifre)
        2. Verificarea se face **automat** când ajungi la 13 cifre
        3. Dacă pacientul există → vezi detaliile și opțiuni
        4. Dacă NU există → completezi formularul
        5. Apasă **ENTER** sau butonul pentru a salva
        """)

# ========================================
# PAGINA: PROGRAMEAZĂ
# ========================================

elif pagina == "Programează":
    st.title("📅 Programare Nouă")
    st.markdown("---")
    
    tab1, tab2, tab3 = st.tabs(["🆕 Programare Nouă", "📋 Programări Existente", "📅 Istoric Programări"])
    
    with tab1:
        st.subheader("🔍 Pasul 1: Selectează Pacient")
        
        if 'pacient_selectat_id' not in st.session_state:
            st.session_state.pacient_selectat_id = None
        
        col_search1, col_search2 = st.columns([3, 1])
        
        with col_search1:
            search_query = st.text_input(
                "🔍 Caută pacient (Nume, Prenume sau CNP):",
                key="search_pacient_programare"
            )
        
        with col_search2:
            st.write("")
            st.write("")
            if st.button("🔄 Resetează", use_container_width=True):
                st.session_state.pacient_selectat_id = None
                st.rerun()
        
        pacienti_df = obtine_toti_pacientii()
        
        if search_query and len(search_query) >= 2:
            mask = (
                pacienti_df['nume'].str.contains(search_query, case=False, na=False) |
                pacienti_df['prenume'].str.contains(search_query, case=False, na=False) |
                pacienti_df['cnp'].str.contains(search_query, case=False, na=False)
            )
            pacienti_filtrati = pacienti_df[mask]
            
            if not pacienti_filtrati.empty:
                st.success(f"✅ {len(pacienti_filtrati)} rezultat(e)")
                
                # CSS pentru rezultate ULTRA-COMPACTE
                st.markdown("""
                <style>
                /* Rânduri rezultate căutare ultra-compacte */
                [data-testid="stVerticalBlock"]:has(div[style*="✅"]) [data-testid="stHorizontalBlock"] div[data-testid="column"] {
                    padding: 0 2px !important;
                }
                
                [data-testid="stVerticalBlock"]:has(div[style*="✅"]) .element-container {
                    margin: 0 !important;
                    padding: 0 !important;
                }
                
                /* Butoane mici în rezultate */
                [data-testid="stVerticalBlock"]:has(div[style*="✅"]) .stButton button {
                    padding: 2px 8px !important;
                    margin: 0 !important;
                    height: 26px !important;
                    min-height: 26px !important;
                    font-size: 12px !important;
                }
                
                /* Zero gap între rânduri */
                [data-testid="stVerticalBlock"]:has(div[style*="✅"]) div[data-testid="stHorizontalBlock"] {
                    gap: 0 !important;
                    margin: 0 !important;
                }
                
                /* Ascunde separatoare HR */
                [data-testid="stVerticalBlock"]:has(div[style*="✅"]) hr {
                    display: none !important;
                }
                </style>
                """, unsafe_allow_html=True)
                
                for idx, row in pacienti_filtrati.iterrows():
                    col_pac1, col_pac2, col_pac3 = st.columns([3, 2, 1], gap="small")
                    
                    with col_pac1:
                        st.markdown(f"<div style='padding: 2px 0; margin: 0; color: #f0f0f0; font-weight: 600; font-size: 15px;'>{formateaza_nume_majuscula(row['nume'], row['prenume'])}</div>", unsafe_allow_html=True)
                    
                    with col_pac2:
                        st.markdown(f"<div style='padding: 2px 0; margin: 0; color: #f0f0f0; font-size: 14px;'>CNP: {row['cnp']}</div>", unsafe_allow_html=True)
                    
                    with col_pac3:
                        if st.button("✅ Selectează", key=f"sel_{row['cnp']}", use_container_width=True):
                            st.session_state.pacient_selectat_id = row['cnp']
                            st.rerun()
            else:
                st.warning("⚠️ Niciun pacient găsit")
        
        if st.session_state.pacient_selectat_id:
            cnp_sel = st.session_state.pacient_selectat_id
            pac_info = obtine_pacient_cnp(cnp_sel)
            
            if pac_info:
                st.success(f"✅ **Pacient selectat:** {formateaza_nume_majuscula(pac_info[2], pac_info[3])} (CNP: {pac_info[1]})")
                
                st.markdown("---")
                
                # Header Pasul 2 cu număr consultații disponibile pe același rând
                col_h1, col_h2 = st.columns([2, 1])
                
                with col_h1:
                    st.subheader("📋 Pasul 2: Detalii Programare")
                
                with col_h2:
                    # Număr consultații disponibile - aliniat cu header
                    ore_disp_bilet_preview, nr_ocup_bilet_preview = genereaza_ore_disponibile_bilet(datetime.now().date().strftime('%Y-%m-%d'))
                    if len(ore_disp_bilet_preview) >= 1:
                        st.markdown(f"""
                        <div style='text-align: right; padding-top: 8px;'>
                            <span style='background: #4CAF50; 
                                         color: white; 
                                         padding: 6px 12px; 
                                         border-radius: 6px; 
                                         font-size: 14px; 
                                         font-weight: 600;'>
                                ✅ {len(ore_disp_bilet_preview)} consultații disponibile
                            </span>
                        </div>
                        """, unsafe_allow_html=True)
                
                with st.form("form_programare"):
                    # RÂND 1: Data, Oră, Tip (3 coloane pe același rând)
                    col_d1, col_d2, col_d3 = st.columns([1, 1, 1])
                    
                    with col_d1:
                        data_cons = st.date_input(
                            "Data consultației *",
                            min_value=datetime.now().date(),
                            format="DD/MM/YYYY"
                        )
                    
                    # ⭐ VERIFICARE SĂRBĂTOARE ⭐
                    if este_sarbatoare_legala(data_cons):
                        st.error("❌ Nu se pot face programări în weekend sau sărbători legale!")
                        data_valida = False
                    else:
                        data_valida = True
                    
                    data_str = data_cons.strftime('%Y-%m-%d')
                    
                    # ⭐ GENERARE ORE DISPONIBILE ⭐
                    ore_disp_bilet, nr_ocup_bilet = genereaza_ore_disponibile_bilet(data_str)
                    
                    with col_d3:
                        # TIP PLATĂ - pe același rând cu Data și Oră
                        if len(ore_disp_bilet) >= 1:
                            tip_plata = st.selectbox("Tip plată:", ["Bilet trimitere", "Cu plată"])
                        else:
                            st.warning("⚠️ Bilete complete")
                            tip_plata = "Cu plată"
                    
                    with col_d2:
                        # ⭐ SELECTARE ORĂ - după verificare tip plată ⭐
                        if tip_plata == "Bilet trimitere":
                            # ========== BILET TRIMITERE ==========
                            ore_disponibile = ore_disp_bilet
                            
                            if ore_disponibile:
                                ora_idx = st.selectbox(
                                    "Selectează ora:",
                                    range(len(ore_disponibile)),
                                    index=0,
                                    format_func=lambda x: f"🕐 {ore_disponibile[x].strftime('%H:%M')}"
                                )
                                ora_cons = ore_disponibile[ora_idx]
                            else:
                                st.error("❌ Nicio oră disponibilă cu bilet!")
                                ora_cons = None
                        
                        else:
                            # ========== CU PLATĂ ==========
                            config_plata = PROGRAM_MEDICAL['cu_plata']
                            
                            # Query ore ocupate cu plată
                            ore_ocupate_plata = []
                            try:
                                with sqlite3.connect('cabinet.db') as conn:
                                    c = conn.cursor()
                                    c.execute('''
                                        SELECT ora_consultatie
                                        FROM programari 
                                        WHERE data_consultatie = ? AND tip_plata = "Cu plată" AND status != 'Anulat'
                                    ''', (data_str,))
                                    ore_ocupate_plata = [row[0] for row in c.fetchall()]
                            except Exception as e:
                                logger.error(f"Eroare query ore ocupate: {e}")
                            
                            # Generare ore disponibile
                            ore_disponibile_plata = []
                            ora_start = config_plata['ora_start']
                            ora_end = config_plata['ora_end']
                            interval = config_plata['interval_minute']
                            
                            ora_curenta = datetime.combine(date.today(), ora_start)
                            ora_finala = datetime.combine(date.today(), ora_end)
                            
                            while ora_curenta <= ora_finala:
                                ora_str = ora_curenta.strftime('%H:%M')
                                if ora_str not in ore_ocupate_plata:
                                    ore_disponibile_plata.append(ora_curenta.time())
                                ora_curenta += timedelta(minutes=interval)
                            
                            if ore_disponibile_plata:
                                ora_idx_plata = st.selectbox(
                                    "Selectează ora:",
                                    range(len(ore_disponibile_plata)),
                                    index=0,
                                    format_func=lambda x: f"🕐 {ore_disponibile_plata[x].strftime('%H:%M')}"
                                )
                                ora_cons = ore_disponibile_plata[ora_idx_plata]
                            else:
                                st.error("❌ Nicio oră disponibilă cu plată!")
                                ora_cons = None
                    
                    # RÂND 2: Observații (full width)
                    obs = st.text_area("Observații", height=100, placeholder="Introduceți observații despre consultație...")
                    
                    # RÂND 3: Butoane (dimensiuni egale, 50-50)
                    col_s1, col_s2 = st.columns(2)
                    
                    with col_s1:
                        submit_prog = st.form_submit_button("✅ Confirmă", use_container_width=True, type="primary")
                    
                    with col_s2:
                        cancel_prog = st.form_submit_button("❌ Anulează", use_container_width=True)
                    
                    # ⭐ PROCESARE SUBMIT ⭐
                    if submit_prog:
                        # Validare dată
                        if not data_valida:
                            st.error("❌ Selectați o dată validă (nu weekend/sărbătoare)!")
                        
                        # Validare oră
                        elif ora_cons is None:
                            st.error("❌ Selectați o oră validă!")
                        
                        # Procesare programare
                        else:
                            if tip_plata == "Bilet trimitere":
                                # Verificare interval 3 luni
                                poate, zile_dif, data_ult = verifica_interval_3_luni(cnp_sel, data_cons)
                                
                                if not poate:
                                    luni_ram = round((90 - zile_dif) / 30, 1)
                                    st.error(f"""
                                    ❌ **NU SE POATE cu bilet!**
                                    
                                    Ultima programare: {data_ult}  
                                    Zile trecute: {zile_dif}  
                                    Luni rămase: {luni_ram}
                                    
                                    💡 Opțiuni:
                                    1. Așteaptă 3 luni
                                    2. Programează cu plată
                                    """)
                                else:
                                    msg = programeaza_optimizat(
                                        cnp_sel, data_str,
                                        ora_cons.strftime('%H:%M'),
                                        obs, tip_plata
                                    )
                                    
                                    if "✅" in msg:
                                        st.success(msg)
                                        st.balloons()
                                        st.session_state.pacient_selectat_id = None
                                        time.sleep(2)
                                        st.rerun()
                                    else:
                                        st.error(msg)
                            
                            else:
                                # Programare cu plată
                                msg = programeaza_optimizat(
                                    cnp_sel, data_str,
                                    ora_cons.strftime('%H:%M'),
                                    obs, tip_plata
                                )
                                
                                if "✅" in msg:
                                    st.success(msg)
                                    st.balloons()
                                    st.session_state.pacient_selectat_id = None
                                    time.sleep(2)
                                    st.rerun()
                                else:
                                    st.error(msg)
                    
                    if cancel_prog:
                        st.session_state.pacient_selectat_id = None
                        st.rerun()
    
    with tab2:
        # Header cu număr programări găsite pe ACELAȘI RÂND
        col_th1, col_th2 = st.columns([2, 1])
        
        with col_th1:
            st.subheader("📋 Toate Programările")
        
        programari = obtine_programari()
        
        if not programari.empty:
            col_f1, col_f2, col_f3 = st.columns(3)
            
            with col_f1:
                data_de_la = st.date_input(
                    "De la:", 
                    value=datetime.now().date(),
                    format="DD/MM/YYYY"
                )
            
            with col_f2:
                data_pana_la = st.date_input(
                    "Până la:", 
                    value=datetime.now().date() + timedelta(days=1),
                    format="DD/MM/YYYY"
                )
            
            with col_f3:
                status_filtru = st.selectbox("Status:", ["Toate", "Programate", "Finalizate", "Anulate"])
            
            # ⭐ EXCLUDE AUTOMAT PROGRAMĂRILE ANULATE ⭐
            mask = (
                (programari['data_consultatie'] >= data_de_la.strftime('%Y-%m-%d')) &
                (programari['data_consultatie'] <= data_pana_la.strftime('%Y-%m-%d')) &
                (programari['status'] != 'Anulat')
            )
            
            if status_filtru != "Toate":
                mask &= (programari['status'] == status_filtru)
            
            prog_filt = programari[mask]
            
            # Afișare număr programări găsite în header (aliniat dreapta)
            with col_th2:
                st.markdown(f"""
                <div style='text-align: right; padding-top: 8px;'>
                    <span style='background: #4CAF50; 
                                 color: white; 
                                 padding: 6px 12px; 
                                 border-radius: 6px; 
                                 font-size: 14px; 
                                 font-weight: 600;'>
                        📊 {len(prog_filt)} programări găsite
                    </span>
                </div>
                """, unsafe_allow_html=True)
            
            # CSS pentru rânduri ULTRA-COMPACTE + ELIMINARE SEPARATOR ALB
            st.markdown("""
            <style>
            /* Rânduri programări compacte */
            [data-testid="stVerticalBlock"]:has(div[style*="📊"]) [data-testid="stHorizontalBlock"] div[data-testid="column"] {
                padding: 0 2px !important;
            }
            
            [data-testid="stVerticalBlock"]:has(div[style*="📊"]) .element-container {
                margin: 0 !important;
                padding: 0 !important;
            }
            
            /* Butoane mici */
            [data-testid="stVerticalBlock"]:has(div[style*="📊"]) .stButton button {
                padding: 2px 6px !important;
                margin: 0 !important;
                height: 28px !important;
                min-height: 28px !important;
                font-size: 12px !important;
            }
            
            /* Zero gap între rânduri */
            [data-testid="stVerticalBlock"]:has(div[style*="📊"]) div[data-testid="stHorizontalBlock"] {
                gap: 0 !important;
                margin: 0 !important;
            }
            
            /* ⭐ ASCUNDE separatoare HR (chenarul alb) */
            [data-testid="stVerticalBlock"]:has(div[style*="📊"]) hr {
                display: none !important;
            }
            
            /* ⭐ Elimină spațiu între rând și panel modificare */
            [data-testid="stVerticalBlock"]:has(div[style*="📊"]) div[style*="background: #fff9e6"] {
                margin: 0 !important;
            }
            
            /* ⭐ Forțează zero margin pentru vertical blocks */
            [data-testid="stVerticalBlock"]:has(div[style*="📊"]) > div {
                margin: 0 !important;
                padding: 0 !important;
            }
            </style>
            """, unsafe_allow_html=True)
            
            for idx, prog in prog_filt.iterrows():
                col_p1, col_p2, col_p3, col_p4, col_p5 = st.columns([2, 2, 1, 1, 1], gap="small")
                
                with col_p1:
                    st.markdown(f"<div style='padding: 2px 0; margin: 0; color: #f0f0f0; font-weight: 600; font-size: 15px;'>{formateaza_nume_majuscula(prog['nume'], prog['prenume'])}</div>", unsafe_allow_html=True)
                
                with col_p2:
                    st.markdown(f"<div style='padding: 2px 0; margin: 0; color: #f0f0f0; font-size: 14px;'>📅 {formateaza_data_ro(prog['data_consultatie'])} - {prog['ora_consultatie']}</div>", unsafe_allow_html=True)
                
                with col_p3:
                    if prog['status'] == 'Programat':
                        if st.button("✅ Prezent", key=f"prez_{prog['id']}", use_container_width=True):
                            actualizeaza_status_programare(prog['id'], 'Finalizat')
                            st.rerun()
                
                with col_p4:
                    # Buton Modifică Programare
                    if st.button("✏️ Modifică", key=f"edit_tab2_{prog['id']}", use_container_width=True, type="secondary"):
                        st.session_state[f'modifica_programare_tab2_{prog["id"]}'] = True
                        st.rerun()
                
                with col_p5:
                    if st.button("🗑️", key=f"del_prog_{prog['id']}", use_container_width=True):
                        sterge_programare(prog['id'])
                        st.rerun()
                
                # Panel modificare programare - REDESIGN (Observații + 2 butoane egale)
                if st.session_state.get(f'modifica_programare_tab2_{prog["id"]}', False):
                    st.markdown("""
                    <div style='background: #fff9e6; 
                                border-left: 4px solid #f59e0b; 
                                border-radius: 8px; 
                                padding: 15px; 
                                margin: 0;
                                box-shadow: 0 4px 12px rgba(245,158,11,0.15);'>
                    """, unsafe_allow_html=True)
                    
                    st.markdown(f"### ✏️ Modifică Programare - {formateaza_nume_majuscula(prog['nume'], prog['prenume'])}")
                    
                    with st.form(f"form_modifica_tab2_{prog['id']}"):
                        # RÂND 1: Data și Oră (2 coloane)
                        col_m1, col_m2 = st.columns(2)
                        
                        with col_m1:
                            noua_data = st.date_input(
                                "Noua dată:",
                                value=datetime.strptime(prog['data_consultatie'], '%Y-%m-%d').date(),
                                min_value=datetime.now().date(),
                                format="DD/MM/YYYY"
                            )
                        
                        with col_m2:
                            data_str_noua = noua_data.strftime('%Y-%m-%d')
                            ore_disp_modif, _ = genereaza_ore_disponibile_bilet(data_str_noua)
                            
                            if prog['tip_plata'] == 'Bilet trimitere' and ore_disp_modif:
                                ora_idx = st.selectbox(
                                    "Noua oră:",
                                    range(len(ore_disp_modif)),
                                    format_func=lambda x: ore_disp_modif[x].strftime('%H:%M'),
                                    key=f"ora_sel_tab2_{prog['id']}"
                                )
                                noua_ora = ore_disp_modif[ora_idx]
                            else:
                                config_plata = PROGRAM_MEDICAL['cu_plata']
                                noua_ora = st.time_input(
                                    "Noua oră:",
                                    value=datetime.strptime(prog['ora_consultatie'], '%H:%M').time(),
                                    help=f"Program: {config_plata['ora_start'].strftime('%H:%M')}-{config_plata['ora_end'].strftime('%H:%M')}",
                                    key=f"ora_time_tab2_{prog['id']}"
                                )
                        
                        # RÂND 2: Observații (FULL WIDTH)
                        observatii_noi = st.text_area(
                            "Observații:", 
                            value=prog['observatii'] if prog['observatii'] else "", 
                            height=100,
                            key=f"obs_tab2_{prog['id']}",
                            placeholder="Introduceți observații despre consultație..."
                        )
                        
                        # RÂND 3: Butoane EGALE (50-50)
                        col_btn1, col_btn2 = st.columns(2)
                        
                        with col_btn1:
                            submit_modif = st.form_submit_button("✅ Salvează", use_container_width=True, type="primary")
                        
                        with col_btn2:
                            cancel_modif = st.form_submit_button("❌ Anulează", use_container_width=True)
                        
                        if submit_modif:
                            succes, mesaj = actualizeaza_programare_completa(
                                prog['id'],
                                data_str_noua,
                                noua_ora.strftime('%H:%M'),
                                observatii_noi
                            )
                            
                            if succes:
                                st.success(mesaj)
                                st.session_state[f'modifica_programare_tab2_{prog["id"]}'] = False
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(mesaj)
                        
                        if cancel_modif:
                            st.session_state[f'modifica_programare_tab2_{prog["id"]}'] = False
                            st.rerun()
                    
                    st.markdown("</div>", unsafe_allow_html=True)
        
        else:
            st.info("📭 Fără programări")

    # ========================================
    # TAB 3: ISTORIC PROGRAMĂRI
    # ========================================
    with tab3:
        # Header cu număr pacienți găsiți pe ACELAȘI RÂND
        col_th1, col_th2 = st.columns([2, 1])
        
        with col_th1:
            st.subheader("📅 Istoric Programări Pacienți")
        
        st.markdown("---")
        
        # CSS pentru layout compact
        st.markdown("""
        <style>
        /* Rânduri rezultate căutare ultra-compacte */
        [data-testid="stVerticalBlock"]:has(div[style*="rezultat"]) [data-testid="stHorizontalBlock"] div[data-testid="column"] {
            padding: 0 2px !important;
        }
        
        [data-testid="stVerticalBlock"]:has(div[style*="rezultat"]) .element-container {
            margin: 0 !important;
            padding: 0 !important;
        }
        
        /* Butoane mici în rezultate */
        [data-testid="stVerticalBlock"]:has(div[style*="rezultat"]) .stButton button {
            padding: 2px 8px !important;
            margin: 0 !important;
            height: 26px !important;
            min-height: 26px !important;
            font-size: 12px !important;
        }
        
        /* Zero gap între rânduri */
        [data-testid="stVerticalBlock"]:has(div[style*="rezultat"]) div[data-testid="stHorizontalBlock"] {
            gap: 0 !important;
            margin: 0 !important;
        }
        
        /* Ascunde separatoare HR */
        [data-testid="stVerticalBlock"]:has(div[style*="rezultat"]) hr {
            display: none !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Motor de căutare LIVE
        search_istoric = st.text_input(
            "🔍 Caută pacient (Nume, Prenume, CNP sau Telefon):",
            value="",
            placeholder="Introdu minim 2 caractere - rezultate în timp real",
            key="search_istoric_dynamic",
            help="Căutare automată după nume, prenume, CNP sau telefon"
        )
        
        # Afișare rezultate instant (când len >= 2)
        if search_istoric and len(search_istoric) >= 2:
            # Obține toți pacienții
            pacienti_istoric = obtine_toti_pacientii()
            
            if not pacienti_istoric.empty:
                # Filtrare case-insensitive
                search_lower = search_istoric.lower()
                mask = (
                    pacienti_istoric['nume'].str.lower().str.contains(search_lower, na=False) |
                    pacienti_istoric['prenume'].str.lower().str.contains(search_lower, na=False) |
                    pacienti_istoric['cnp'].astype(str).str.contains(search_istoric, na=False) |
                    pacienti_istoric['telefon'].astype(str).str.lower().str.contains(search_lower, na=False)
                )
                
                rezultate_istoric = pacienti_istoric[mask]
                
                if not rezultate_istoric.empty:
                    # Afișare număr pacienți găsiți în header (dreapta)
                    with col_th2:
                        st.markdown(f"""
                        <div style='text-align: right; padding-top: 8px;'>
                            <span style='background: #4CAF50; 
                                         color: white; 
                                         padding: 6px 12px; 
                                         border-radius: 6px; 
                                         font-size: 14px; 
                                         font-weight: 600;'>
                                📊 {len(rezultate_istoric)} pacient(ți) găsit(ți) pentru: '{search_istoric}'
                            </span>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Inițializare session state
                    if 'pacient_istoric_selectat' not in st.session_state:
                        st.session_state.pacient_istoric_selectat = None
                    
                    # Header tabel (4 coloane) - DOAR O DATĂ
                    st.markdown("""
                    <div style='display: grid; 
                                grid-template-columns: 2.5fr 2fr 1fr 1fr; 
                                gap: 10px; 
                                padding: 8px 12px; 
                                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                border-radius: 8px; 
                                margin-bottom: 6px;
                                font-weight: 700;
                                color: white;
                                font-size: 13px;
                                align-items: center;'>
                        <div style='text-align: center;'>👤 Nume Prenume</div>
                        <div style='text-align: center;'>🆔 CNP</div>
                        <div style='text-align: center;'>📋 Istoric</div>
                        <div style='text-align: center;'>🗑️ Șterge Istoric</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Loop pacienți (4 coloane) - DOAR O DATĂ
                    for idx, pac in rezultate_istoric.iterrows():
                        col_pac1, col_pac2, col_pac3, col_pac4 = st.columns([2.5, 2, 1, 1], gap="small")
                        
                        with col_pac1:
                            st.markdown(f"<div style='padding: 4px 0; margin: 0; color: #f0f0f0; font-weight: 600; font-size: 15px; text-align: center;'>{formateaza_nume_majuscula(pac['nume'], pac['prenume'])}</div>", unsafe_allow_html=True)
                        
                        with col_pac2:
                            st.markdown(f"<div style='padding: 4px 0; margin: 0; color: #f0f0f0; font-size: 14px; text-align: center;'>{pac['cnp']}</div>", unsafe_allow_html=True)
                        
                        with col_pac3:
                            if st.button("📋 Istoric", key=f"istoric_tab3_{pac['cnp']}", use_container_width=True, help="Vezi istoric programări"):
                                if st.session_state.pacient_istoric_selectat == pac['cnp']:
                                    st.session_state.pacient_istoric_selectat = None
                                else:
                                    st.session_state.pacient_istoric_selectat = pac['cnp']
                                st.rerun()
                        
                        with col_pac4:
                            # Buton ȘTERGE ISTORIC cu confirmare
                            if not st.session_state.get(f'confirm_sterge_istoric_{pac["cnp"]}', False):
                                if st.button("🗑️", key=f"sterge_istoric_{pac['cnp']}", use_container_width=True, type="secondary", help="Șterge tot istoricul programărilor"):
                                    st.session_state[f'confirm_sterge_istoric_{pac["cnp"]}'] = True
                                    st.rerun()
                            else:
                                col_conf1, col_conf2 = st.columns(2)
                                with col_conf1:
                                    if st.button("✅", key=f"conf_sterge_istoric_yes_{pac['cnp']}", use_container_width=True, help="Confirmă ștergerea"):
                                        try:
                                            with sqlite3.connect('cabinet.db') as conn:
                                                c = conn.cursor()
                                                c.execute("DELETE FROM programari WHERE cnp = ?", (pac['cnp'],))
                                                conn.commit()
                                            
                                            st.success(f"✅ Istoric șters pentru {formateaza_nume_majuscula(pac['nume'], pac['prenume'])}!")
                                            st.session_state[f'confirm_sterge_istoric_{pac["cnp"]}'] = False
                                            time.sleep(1)
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"❌ Eroare: {e}")
                                with col_conf2:
                                    if st.button("❌", key=f"conf_sterge_istoric_no_{pac['cnp']}", use_container_width=True, help="Anulează"):
                                        st.session_state[f'confirm_sterge_istoric_{pac["cnp"]}'] = False
                                        st.rerun()
                        
                        # ⭐ PANEL ISTORIC (PĂSTREAZĂ codul existent - NU modifica) ⭐
                        if st.session_state.pacient_istoric_selectat == pac['cnp']:
                            st.markdown(f"""
                            <div style='background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%);
                                        border-left: 4px solid #667eea; 
                                        border-radius: 8px; 
                                        padding: 20px; 
                                        margin: 4px 0 15px 0;
                                        box-shadow: 0 4px 12px rgba(102,126,234,0.15);'>
                            """, unsafe_allow_html=True)
                            
                            st.markdown(f"### 📋 {formateaza_nume_majuscula(pac['nume'], pac['prenume'])}")
                            
                            col_d1, col_d2, col_d3 = st.columns(3)
                            
                            with col_d1:
                                st.markdown("**👤 Date Personale**")
                                st.write(f"**CNP:** {pac['cnp']}")
                                st.write(f"**Naștere:** {formateaza_data_ro(pac['data_nasterii'])}")
                                st.write(f"**Adresă:** {pac['adresa'] if pac['adresa'] else 'N/A'}")
                            
                            with col_d2:
                                st.markdown("**📞 Contact**")
                                st.write(f"**Tel:** {pac['telefon'] if pac['telefon'] else 'N/A'}")
                                st.write(f"**Email:** {pac['email'] if pac['email'] else 'N/A'}")
                            
                            with col_d3:
                                st.markdown("**🏥 Medical**")
                                try:
                                    with sqlite3.connect('cabinet.db') as conn:
                                        c = conn.cursor()
                                        
                                        c.execute("SELECT COUNT(*) FROM programari WHERE cnp = ?", (pac['cnp'],))
                                        total_prog = c.fetchone()[0]
                                        
                                        data_azi = datetime.now().date().strftime('%Y-%m-%d')
                                        c.execute("""
                                            SELECT COUNT(*) FROM programari 
                                            WHERE cnp = ? AND data_consultatie >= ? AND status != 'Anulat'
                                        """, (pac['cnp'], data_azi))
                                        viitoare = c.fetchone()[0]
                                        
                                        c.execute("""
                                            SELECT COUNT(*) FROM programari 
                                            WHERE cnp = ? AND data_consultatie < ?
                                        """, (pac['cnp'], data_azi))
                                        trecute = c.fetchone()[0]
                                        
                                        c.execute("""
                                            SELECT COUNT(*) FROM programari 
                                            WHERE cnp = ? AND status = 'Finalizat'
                                        """, (pac['cnp'],))
                                        validate = c.fetchone()[0]
                                        
                                        c.execute("""
                                            SELECT COUNT(*) FROM programari 
                                            WHERE cnp = ? AND status NOT IN ('Finalizat', 'Anulat')
                                        """, (pac['cnp'],))
                                        nevalidate = c.fetchone()[0]
                                        
                                except Exception as e:
                                    logger.error(f"Eroare statistici programări: {e}")
                                    total_prog = 0
                                    viitoare = 0
                                    trecute = 0
                                    validate = 0
                                    nevalidate = 0
                                
                                if total_prog > 0:
                                    col_med1, col_med2 = st.columns([1, 1])
                                    
                                    with col_med1:
                                        st.markdown(f"""
                                        <div style='margin-top: 5px;'>
                                            <div style='font-size: 13px; color: #b0b0b0; margin-bottom: 5px;'>Total programări:</div>
                                            <div style='font-size: 48px; font-weight: 700; color: #ffffff; line-height: 1;'>{total_prog}</div>
                                        </div>
                                        """, unsafe_allow_html=True)
                                    
                                    with col_med2:
                                        st.markdown(f"""
                                        <div style='margin-top: 5px; line-height: 1.8;'>
                                            <div style='margin-bottom: 4px;'>
                                                <span style='font-size: 13px; color: #c0c0c0;'>Viitoare:</span>
                                                <span style='font-size: 16px; font-weight: 600; color: #ffffff; margin-left: 6px;'>{viitoare}</span>
                                            </div>
                                            <div style='margin-bottom: 4px;'>
                                                <span style='font-size: 13px; color: #c0c0c0;'>Trecute:</span>
                                                <span style='font-size: 16px; font-weight: 600; color: #ffffff; margin-left: 6px;'>{trecute}</span>
                                            </div>
                                            <div style='margin-bottom: 4px;'>
                                                <span style='font-size: 13px; color: #c0c0c0;'>Validate:</span>
                                                <span style='font-size: 16px; font-weight: 600; color: #4CAF50; margin-left: 6px;'>{validate}</span>
                                            </div>
                                            <div style='margin-bottom: 4px;'>
                                                <span style='font-size: 13px; color: #c0c0c0;'>Nevalidate:</span>
                                                <span style='font-size: 16px; font-weight: 600; color: #FFA726; margin-left: 6px;'>{nevalidate}</span>
                                            </div>
                                        </div>
                                        """, unsafe_allow_html=True)
                                
                                else:
                                    st.success("✅ Fără programări")
                            
                            if pac['observatii']:
                                st.info(f"**📝 Observații:** {pac['observatii']}")
                            
                            st.markdown("---")
                            st.markdown("### 📅 Istoric Programări")
                            
                            # EXACT CA ÎN TOȚI PACIENȚII - cu cele 3 tabs
                            try:
                                with sqlite3.connect('cabinet.db') as conn:
                                    programari_pacient = pd.read_sql_query('''
                                        SELECT 
                                            id, data_consultatie, ora_consultatie, tip_plata, status, observatii
                                        FROM programari
                                        WHERE cnp = ?
                                        ORDER BY data_consultatie DESC, ora_consultatie DESC
                                    ''', conn, params=(pac['cnp'],))
                                
                                if not programari_pacient.empty:
                                    data_azi = datetime.now().date().strftime('%Y-%m-%d')
                                    
                                    prog_viitoare = programari_pacient[programari_pacient['data_consultatie'] >= data_azi]
                                    prog_trecute = programari_pacient[programari_pacient['data_consultatie'] < data_azi]
                                    
                                    tab_h1, tab_h2, tab_h3 = st.tabs([
                                        f"🔜 Viitoare ({len(prog_viitoare)})", 
                                        f"📅 Trecute ({len(prog_trecute)})", 
                                        f"📊 Toate ({len(programari_pacient)})"
                                    ])
                                    
                                    # ========== TAB VIITOARE ==========
                                    with tab_h1:
                                        if not prog_viitoare.empty:
                                            df_viitoare = prog_viitoare.copy()
                                            df_viitoare['data_consultatie'] = df_viitoare['data_consultatie'].apply(formateaza_data_ro)
                                            df_viitoare['tip_plata'] = df_viitoare['tip_plata'].apply(
                                                lambda x: '🎫 Bilet' if x == 'Bilet trimitere' else '💳 Plată'
                                            )
                                            df_viitoare['status'] = df_viitoare['status'].apply(
                                                lambda x: '✅ Finalizat' if x == 'Finalizat' else (
                                                    '❌ Anulat' if x == 'Anulat' else (
                                                        '🔵 Confirmat' if x == 'Confirmat' else '⏳ Programat'
                                                    )
                                                )
                                            )
                                            
                                            df_viitoare_display = df_viitoare[['data_consultatie', 'ora_consultatie', 'tip_plata', 'status', 'observatii']].copy()
                                            df_viitoare_display.columns = ['Data', 'Ora', 'Tip Plată', 'Status', 'Observații']
                                            df_viitoare_display['Observații'] = df_viitoare_display['Observații'].fillna('-')
                                            
                                            st.dataframe(
                                                df_viitoare_display,
                                                use_container_width=True,
                                                hide_index=True,
                                                height=min(400, 50 + len(df_viitoare_display) * 35)
                                            )
                                        else:
                                            st.info("📭 Nicio programare viitoare")
                                    
                                    # ========== TAB TRECUTE ==========
                                    with tab_h2:
                                        if not prog_trecute.empty:
                                            df_trecute = prog_trecute.copy()
                                            df_trecute['data_consultatie'] = df_trecute['data_consultatie'].apply(formateaza_data_ro)
                                            df_trecute['tip_plata'] = df_trecute['tip_plata'].apply(
                                                lambda x: '🎫 Bilet' if x == 'Bilet trimitere' else '💳 Plată'
                                            )
                                            df_trecute['status'] = df_trecute['status'].apply(
                                                lambda x: '✅ Finalizat' if x == 'Finalizat' else (
                                                    '❌ Anulat' if x == 'Anulat' else (
                                                        '🔵 Confirmat' if x == 'Confirmat' else '⏳ Programat'
                                                    )
                                                )
                                            )
                                            
                                            df_trecute_display = df_trecute[['data_consultatie', 'ora_consultatie', 'tip_plata', 'status', 'observatii']].copy()
                                            df_trecute_display.columns = ['Data', 'Ora', 'Tip Plată', 'Status', 'Observații']
                                            df_trecute_display['Observații'] = df_trecute_display['Observații'].fillna('-')
                                            
                                            st.dataframe(
                                                df_trecute_display,
                                                use_container_width=True,
                                                hide_index=True,
                                                height=min(400, 50 + len(df_trecute_display) * 35)
                                            )
                                        else:
                                            st.info("📭 Nicio programare trecută")
                                    
                                    
                                    # ========== TAB TOATE (cu MODIFICĂ și ȘTERGE) ==========
                                    with tab_h3:
                                        st.info(f"📌 {len(programari_pacient)} programare/programări în total")
                                        
                                        # CSS pentru butoane mici
                                        st.markdown("""
                                        <style>
                                        /* Butoane mici în tabel istoric */
                                        .stButton button {
                                            padding: 2px 6px !important;
                                            margin: 0 !important;
                                            height: 28px !important;
                                            min-height: 28px !important;
                                            font-size: 12px !important;
                                        }
                                        </style>
                                        """, unsafe_allow_html=True)
                                        
                                        # Header tabel (6 coloane: Data, Ora, Tip, Status, Modifică, Șterge)
                                        st.markdown("""
                                        <div style='display: grid; 
                                                    grid-template-columns: 1fr 0.8fr 1fr 1fr 0.7fr 0.7fr; 
                                                    gap: 8px; 
                                                    padding: 10px 15px; 
                                                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                                    border-radius: 8px; 
                                                    margin-bottom: 8px;
                                                    font-weight: 700;
                                                    color: white;
                                                    font-size: 13px;
                                                    align-items: center;'>
                                            <div style='text-align: center;'>📅 Data</div>
                                            <div style='text-align: center;'>🕐 Ora</div>
                                            <div style='text-align: center;'>💳 Tip Plată</div>
                                            <div style='text-align: center;'>📊 Status</div>
                                            <div style='text-align: center;'>✏️ Modifică</div>
                                            <div style='text-align: center;'>🗑️ Șterge</div>
                                        </div>
                                        """, unsafe_allow_html=True)
                                        
                                        # Rânduri tabel
                                        for idx_prog, prog in programari_pacient.iterrows():
                                            # Format data
                                            tip_emoji = '🎫 Bilet' if prog['tip_plata'] == 'Bilet trimitere' else '💳 Plată'
                                            
                                            if prog['status'] == 'Finalizat':
                                                status_text = '✅ Finalizat'
                                            elif prog['status'] == 'Anulat':
                                                status_text = '❌ Anulat'
                                            elif prog['status'] == 'Confirmat':
                                                status_text = '🔵 Confirmat'
                                            else:
                                                status_text = '⏳ Programat'
                                            
                                            # Container rând (6 coloane)
                                            col_t1, col_t2, col_t3, col_t4, col_t5, col_t6 = st.columns([1, 0.8, 1, 1, 0.7, 0.7], gap="small")
                                            
                                            with col_t1:
                                                st.markdown(f"<div style='padding: 4px 0; color: #f0f0f0; font-size: 13px; text-align: center;'>{formateaza_data_ro(prog['data_consultatie'])}</div>", unsafe_allow_html=True)
                                            
                                            with col_t2:
                                                st.markdown(f"<div style='padding: 4px 0; color: #f0f0f0; font-size: 13px; text-align: center;'>{prog['ora_consultatie']}</div>", unsafe_allow_html=True)
                                            
                                            with col_t3:
                                                st.markdown(f"<div style='padding: 4px 0; color: #f0f0f0; font-size: 13px; text-align: center;'>{tip_emoji}</div>", unsafe_allow_html=True)
                                            
                                            with col_t4:
                                                st.markdown(f"<div style='padding: 4px 0; color: #f0f0f0; font-size: 13px; text-align: center;'>{status_text}</div>", unsafe_allow_html=True)
                                            
                                            with col_t5:
                                                # Buton MODIFICĂ
                                                if st.button("✏️", key=f"edit_istoric_{prog['id']}", use_container_width=True, type="secondary", help="Modifică programarea"):
                                                    st.session_state[f'modifica_istoric_{prog["id"]}'] = True
                                                    st.rerun()
                                            
                                            with col_t6:
                                                # Buton ȘTERGE cu confirmare
                                                if not st.session_state.get(f'confirm_delete_istoric_{prog["id"]}', False):
                                                    if st.button("🗑️", key=f"del_istoric_{prog['id']}", use_container_width=True, type="secondary", help="Șterge programare"):
                                                        st.session_state[f'confirm_delete_istoric_{prog["id"]}'] = True
                                                        st.rerun()
                                                else:
                                                    col_conf1, col_conf2 = st.columns(2)
                                                    with col_conf1:
                                                        if st.button("✅", key=f"conf_istoric_yes_{prog['id']}", use_container_width=True, help="Confirmă ștergerea"):
                                                            sterge_programare(prog['id'])
                                                            st.session_state[f'confirm_delete_istoric_{prog["id"]}'] = False
                                                            st.success("✅ Șters!")
                                                            time.sleep(0.8)
                                                            st.rerun()
                                                    with col_conf2:
                                                        if st.button("❌", key=f"conf_istoric_no_{prog['id']}", use_container_width=True, help="Anulează"):
                                                            st.session_state[f'confirm_delete_istoric_{prog["id"]}'] = False
                                                            st.rerun()
                                            
                                            # Panel MODIFICARE programare
                                            if st.session_state.get(f'modifica_istoric_{prog["id"]}', False):
                                                st.markdown("""
                                                <div style='background: #fff9e6; 
                                                            border-left: 4px solid #f59e0b; 
                                                            border-radius: 8px; 
                                                            padding: 15px; 
                                                            margin: 0;
                                                            box-shadow: 0 4px 12px rgba(245,158,11,0.15);'>
                                                """, unsafe_allow_html=True)
                                                
                                                st.markdown(f"### ✏️ Modifică Programare")
                                                
                                                with st.form(f"form_modifica_istoric_{prog['id']}"):
                                                    # RÂND 1: Data și Oră
                                                    col_m1, col_m2 = st.columns(2)
                                                    
                                                    with col_m1:
                                                        noua_data_istoric = st.date_input(
                                                            "Noua dată:",
                                                            value=datetime.strptime(prog['data_consultatie'], '%Y-%m-%d').date(),
                                                            min_value=datetime.now().date(),
                                                            format="DD/MM/YYYY",
                                                            key=f"data_istoric_{prog['id']}"
                                                        )
                                                    
                                                    with col_m2:
                                                        data_str_noua_istoric = noua_data_istoric.strftime('%Y-%m-%d')
                                                        ore_disp_modif_istoric, _ = genereaza_ore_disponibile_bilet(data_str_noua_istoric)
                                                        
                                                        if prog['tip_plata'] == 'Bilet trimitere' and ore_disp_modif_istoric:
                                                            ora_idx_istoric = st.selectbox(
                                                                "Noua oră:",
                                                                range(len(ore_disp_modif_istoric)),
                                                                format_func=lambda x: ore_disp_modif_istoric[x].strftime('%H:%M'),
                                                                key=f"ora_istoric_{prog['id']}"
                                                            )
                                                            noua_ora_istoric = ore_disp_modif_istoric[ora_idx_istoric]
                                                        else:
                                                            config_plata = PROGRAM_MEDICAL['cu_plata']
                                                            noua_ora_istoric = st.time_input(
                                                                "Noua oră:",
                                                                value=datetime.strptime(prog['ora_consultatie'], '%H:%M').time(),
                                                                help=f"Program: {config_plata['ora_start'].strftime('%H:%M')}-{config_plata['ora_end'].strftime('%H:%M')}",
                                                                key=f"ora_time_istoric_{prog['id']}"
                                                            )
                                                    
                                                    # RÂND 2: Observații
                                                    observatii_noi_istoric = st.text_area(
                                                        "Observații:", 
                                                        value=prog['observatii'] if prog['observatii'] else "", 
                                                        height=100,
                                                        key=f"obs_istoric_{prog['id']}",
                                                        placeholder="Introduceți observații..."
                                                    )
                                                    
                                                    # RÂND 3: Butoane
                                                    col_btn1, col_btn2 = st.columns(2)
                                                    
                                                    with col_btn1:
                                                        submit_modif_istoric = st.form_submit_button("✅ Salvează", use_container_width=True, type="primary")
                                                    
                                                    with col_btn2:
                                                        cancel_modif_istoric = st.form_submit_button("❌ Anulează", use_container_width=True)
                                                    
                                                    if submit_modif_istoric:
                                                        succes, mesaj = actualizeaza_programare_completa(
                                                            prog['id'],
                                                            data_str_noua_istoric,
                                                            noua_ora_istoric.strftime('%H:%M'),
                                                            observatii_noi_istoric
                                                        )
                                                        
                                                        if succes:
                                                            st.success(mesaj)
                                                            st.session_state[f'modifica_istoric_{prog["id"]}'] = False
                                                            time.sleep(1)
                                                            st.rerun()
                                                        else:
                                                            st.error(mesaj)
                                                    
                                                    if cancel_modif_istoric:
                                                        st.session_state[f'modifica_istoric_{prog["id"]}'] = False
                                                        st.rerun()
                                                
                                                st.markdown("</div>", unsafe_allow_html=True)
                                        
                                else:
                                    st.info("📭 **Pacientul nu are nicio programare înregistrată**")
                            
                            except Exception as e:
                                st.error(f"❌ Eroare obținere programări: {e}")
                                logger.error(f"Eroare programări pacient {pac['cnp']}: {e}")
                            
                            st.markdown("---")
                            
                            # Buton închide
                            if st.button("🔙 Închide", key=f"close_istoric_{pac['cnp']}", use_container_width=True):
                                st.session_state.pacient_istoric_selectat = None
                                st.rerun()
                            
                            st.markdown("</div>", unsafe_allow_html=True)
                
                else:
                    st.warning(f"⚠️ Niciun pacient găsit pentru **'{search_istoric}'**")
            
            else:
                st.error("❌ Nu există pacienți în baza de date!")
        
        elif search_istoric and len(search_istoric) == 1:
            st.info(f"⏳ **Mai introdu un caracter...** (ai tastat: '{search_istoric}', mai trebuie minim 1)")
        

# ========================================
# PAGINA: CAUTĂ PACIENT
# ========================================

elif pagina == "Caută Pacient":
    st.title("🔍 Caută Pacient")
    st.markdown("---")
    
    # CSS pentru layout compact
    st.markdown("""
    <style>
    .element-container {
        margin-bottom: 0 !important;
    }
    
    div[data-testid="column"] {
        padding: 2px 4px !important;
    }
    
    .stButton button {
        padding: 6px 12px !important;
        margin: 0 !important;
        height: 34px !important;
        font-size: 13px !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # ⭐ INPUT SIMPLU - Streamlit re-rulează automat la modificare ⭐
    search = st.text_input(
        "🔍 Caută după nume, prenume sau CNP:",
        value="",
        placeholder="Introdu minim 2 caractere - rezultate în timp real",
        key="search_input_dynamic",
        help="Rezultatele apar automat pe măsură ce tastezi"
    )
    
    # ⭐ AFIȘARE REZULTATE INSTANT (fără validare ENTER) ⭐
    if search and len(search) >= 2:
        # Obține toți pacienții
        pacienti = obtine_toti_pacientii()
        
        if not pacienti.empty:
            # Filtrare case-insensitive
            search_lower = search.lower()
            mask = (
                pacienti['nume'].str.lower().str.contains(search_lower, na=False) |
                pacienti['prenume'].str.lower().str.contains(search_lower, na=False) |
                pacienti['cnp'].astype(str).str.contains(search, na=False)
            )
            
            rezultate = pacienti[mask]
            
            if not rezultate.empty:
                # Header cu număr rezultate
                st.success(f"✅ **{len(rezultate)} pacient(ți)** găsit(ți) pentru: **'{search}'**")
                
                # Inițializare session state
                if 'pacient_search_selectat' not in st.session_state:
                    st.session_state.pacient_search_selectat = None
                
                # Afișare fiecare pacient
                for idx, pac in rezultate.iterrows():
                    # Verifică dacă e în modul confirmare ștergere
                    este_in_confirmare = st.session_state.get(f'search_confirm_{pac["cnp"]}', False)
                    
                    if not este_in_confirmare:
                        # Rând normal cu date
                        col_nume, col_cnp, col_btn_prog, col_btn_mod, col_btn_del = st.columns([2.5, 2, 1.5, 0.8, 0.8])
                        
                        with col_nume:
                            if st.button(
                                f"👤 {formateaza_nume_majuscula(pac['nume'], pac['prenume'])}", 
                                key=f"click_nume_{pac['cnp']}", 
                                use_container_width=True,
                                help="Click pentru detalii"
                            ):
                                if st.session_state.pacient_search_selectat == pac['cnp']:
                                    st.session_state.pacient_search_selectat = None
                                else:
                                    st.session_state.pacient_search_selectat = pac['cnp']
                                st.rerun()
                        
                        with col_cnp:
                            st.markdown(f"<div style='padding: 8px 0; color: #f0f0f0;'>CNP: {pac['cnp']}</div>", unsafe_allow_html=True)
                        
                        with col_btn_prog:
                            if st.button("📅", key=f"prog_{pac['cnp']}", use_container_width=True, type="primary", help="Programează"):
                                st.session_state.pacient_selectat_id = pac['cnp']
                                st.session_state.pagina = "Programează"
                                st.rerun()
                        
                        with col_btn_mod:
                            if st.button("✏️", key=f"edit_search_{pac['cnp']}", use_container_width=True, help="Modifică"):
                                st.session_state.pacient_modifica_search = pac['cnp']
                                st.rerun()
                        
                        with col_btn_del:
                            componenta_sterge_pacient(
                                pac['cnp'], 
                                formateaza_nume_majuscula(pac['nume'], pac['prenume']), 
                                key_prefix=f"search"
                            )
                    
                    else:
                        # Banner confirmare ștergere
                        st.markdown(f"""
                        <div style='background: linear-gradient(135deg, #f59e0b 0%, #dc2626 100%);
                                    border-radius: 8px;
                                    padding: 12px;
                                    margin: 4px 0;
                                    color: white;
                                    font-weight: 600;
                                    text-align: center;
                                    box-shadow: 0 4px 12px rgba(245,158,11,0.3);'>
                            ⚠️ Confirmi ștergerea pacientului <strong>{formateaza_nume_majuscula(pac['nume'], pac['prenume'])}</strong>?
                        </div>
                        """, unsafe_allow_html=True)
                        
                        col_empty1, col_conf1, col_conf2, col_empty2 = st.columns([2, 1.5, 1.5, 2])
                        
                        with col_conf1:
                            if st.button("✅ DA, șterge", key=f"search_conf_{pac['cnp']}", type="primary", use_container_width=True):
                                succes, msg, _ = sterge_pacient(pac['cnp'], sterge_si_programari=True)
                                st.session_state[f'search_confirm_{pac["cnp"]}'] = False
                                
                                if succes:
                                    st.success(msg)
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error(msg)
                        
                        with col_conf2:
                            if st.button("❌ NU, anulează", key=f"search_canc_{pac['cnp']}", use_container_width=True):
                                st.session_state[f'search_confirm_{pac["cnp"]}'] = False
                                st.rerun()
                    
                    # Panel detalii (dacă e selectat)
                    if st.session_state.pacient_search_selectat == pac['cnp']:
                        st.markdown(f"""
                        <div style='background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%);
                                    border-left: 4px solid #667eea; 
                                    border-radius: 8px; 
                                    padding: 15px; 
                                    margin: 4px 0 8px 0;
                                    box-shadow: 0 4px 12px rgba(102,126,234,0.15);'>
                        """, unsafe_allow_html=True)
                        
                        col_d1, col_d2 = st.columns(2)
                        
                        with col_d1:
                            st.markdown("**👤 Date Personale**")
                            st.write(f"**Nume complet:** {formateaza_nume_majuscula(pac['nume'], pac['prenume'])}")
                            st.write(f"**CNP:** {pac['cnp']}")
                            st.write(f"**Data nașterii:** {formateaza_data_ro(pac['data_nasterii'])}")
                        
                        with col_d2:
                            st.markdown("**📞 Contact**")
                            st.write(f"**Telefon:** {pac['telefon'] if pac['telefon'] else 'N/A'}")
                            st.write(f"**Email:** {pac['email'] if pac['email'] else 'N/A'}")
                            st.write(f"**Adresă:** {pac['adresa'] if pac['adresa'] else 'N/A'}")
                        
                        if pac['observatii']:
                            st.info(f"**📝 Observații:** {pac['observatii']}")
                        
                        st.markdown("</div>", unsafe_allow_html=True)
                    
                    # Panel modificare (dacă e selectat)
                    if st.session_state.get('pacient_modifica_search') == pac['cnp']:
                        st.markdown("""
                        <div style='background: #fff9e6; 
                                    border-left: 4px solid #f59e0b; 
                                    border-radius: 8px; 
                                    padding: 15px; 
                                    margin: 4px 0 8px 0;
                                    box-shadow: 0 4px 12px rgba(245,158,11,0.15);'>
                        """, unsafe_allow_html=True)
                        
                        st.markdown(f"### ✏️ Modifică Date - {formateaza_nume_majuscula(pac['nume'], pac['prenume'])}")
                        
                        with st.form(f"form_modifica_search_{pac['cnp']}"):
                            col_m1, col_m2 = st.columns(2)
                            
                            with col_m1:
                                nume_nou = st.text_input("Nume *", value=pac['nume'])
                                prenume_nou = st.text_input("Prenume *", value=pac['prenume'])
                                data_nasterii_nou = st.date_input(
                                    "Data nașterii *",
                                    value=datetime.strptime(pac['data_nasterii'], '%Y-%m-%d').date() if pac['data_nasterii'] else date(2000, 1, 1),
                                    min_value=date(1900, 1, 1),
                                    max_value=date.today(),
                                    format="DD/MM/YYYY"
                                )
                            
                            with col_m2:
                                telefon_nou = st.text_input("Telefon", value=pac['telefon'] if pac['telefon'] else "")
                                email_nou = st.text_input("Email", value=pac['email'] if pac['email'] else "")
                                adresa_nou = st.text_input("Adresă", value=pac['adresa'] if pac['adresa'] else "")
                            
                            observatii_nou = st.text_area("Observații medicale", value=pac['observatii'] if pac['observatii'] else "", height=80)
                            
                            col_btn1, col_btn2 = st.columns([3, 1])
                            
                            with col_btn1:
                                submit_modifica = st.form_submit_button("✅ Salvează Modificările", use_container_width=True, type="primary")
                            
                            with col_btn2:
                                cancel_modifica = st.form_submit_button("❌ Anulează", use_container_width=True)
                            
                            if submit_modifica:
                                if not nume_nou or not prenume_nou:
                                    st.error("❌ Numele și prenumele sunt obligatorii!")
                                else:
                                    try:
                                        with sqlite3.connect('cabinet.db') as conn:
                                            c = conn.cursor()
                                            c.execute('''
                                                UPDATE pacienti 
                                                SET nume = ?, prenume = ?, data_nasterii = ?, 
                                                    telefon = ?, email = ?, adresa = ?, observatii = ?
                                                WHERE cnp = ?
                                            ''', (nume_nou.upper(), prenume_nou.upper(), data_nasterii_nou, 
                                                  telefon_nou, email_nou, adresa_nou, observatii_nou, pac['cnp']))
                                            conn.commit()
                                        
                                        st.success(f"✅ Date actualizate pentru {nume_nou} {prenume_nou}!")
                                        st.session_state.pacient_modifica_search = None
                                        time.sleep(1.5)
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ Eroare actualizare: {e}")
                            
                            if cancel_modifica:
                                st.session_state.pacient_modifica_search = None
                                st.rerun()
                        
                        st.markdown("</div>", unsafe_allow_html=True)
                    
                    # Separator
                    st.markdown("<hr style='margin: 2px 0; border: none; border-top: 1px solid #444;'>", unsafe_allow_html=True)
            
            else:
                # Niciun rezultat găsit
                st.warning(f"⚠️ Niciun pacient găsit pentru **'{search}'**")
                st.info("💡 **Sugestii:**\n- Verifică ortografia\n- Încearcă alte criterii (nume, prenume, CNP)\n- Folosește minim 2 caractere")
        
        else:
            st.error("❌ Nu există pacienți în baza de date!")
    
    elif search and len(search) == 1:
        # Un singur caracter - încurajează să continue
        st.info(f"⏳ **Mai introdu un caracter...** (ai tastat: '{search}', mai trebuie minim 1)")
    
    else:
        # Mesaj inițial când câmpul e gol
        st.markdown("""
        <div style='background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%);
                    border-left: 4px solid #667eea;
                    border-radius: 8px;
                    padding: 20px;
                    margin: 20px 0;'>
            <h3 style='margin: 0 0 15px 0; color: #667eea;'>💡 Căutare în timp real:</h3>
            <ul style='margin: 0; padding-left: 20px; line-height: 1.8;'>
                <li>Introdu <strong>minim 2 caractere</strong> (nume, prenume sau CNP)</li>
                <li>Rezultatele apar <strong>automat</strong> pe măsură ce tastezi</li>
                <li><strong>NU</strong> este nevoie să apeși ENTER</li>
                <li>Lista se actualizează <strong>dinamic</strong> cu fiecare caracter</li>
            </ul>
            <div style='margin-top: 15px; padding: 10px; background: rgba(102,126,234,0.1); border-radius: 6px;'>
                <strong>Exemplu:</strong> Tastează "po" → vezi toți pacienții cu "Pop", "Popescu", etc.
            </div>
        </div>
        """, unsafe_allow_html=True)

# ========================================
# PAGINA: TOȚI PACIENȚII
# ========================================

elif pagina == "Toți Pacienții":
    # ⭐ HEADER CU LAYOUT 2 COLOANE ⭐
    col_title, col_badge = st.columns([3, 1])
    
    with col_title:
        st.title("👥 Toți Pacienții")
    
    with col_badge:
        # Badge aliniat dreapta, pe același nivel cu titlul
        pacienti_temp = obtine_toti_pacientii()
        if not pacienti_temp.empty:
            st.markdown(f"""
            <div style='text-align: right; padding-top: 12px;'>
                <span style='background: #4CAF50; 
                             color: white; 
                             padding: 6px 12px; 
                             border-radius: 20px; 
                             font-size: 14px; 
                             font-weight: 600;
                             display: inline-block;'>
                    Total: {len(pacienti_temp)} pacienți
                </span>
            </div>
            """, unsafe_allow_html=True)
    
    # ✅ FORȚARE SORTARE EXPLICITĂ
    pacienti = obtine_toti_pacientii()
    
    if not pacienti.empty:
        # 🔥 SORTARE MANUALĂ DUPĂ NUME + PRENUME (case-insensitive)
        pacienti = pacienti.sort_values(by=['nume', 'prenume'], ascending=True, key=lambda col: col.str.upper())
        pacienti = pacienti.reset_index(drop=True)  # Resetare index pentru iterare corectă
        
         
        # ✅ DICT PROGRAMĂRI VIITOARE (pentru emoji)
        try:
            with sqlite3.connect('cabinet.db') as conn:
                data_azi = datetime.now().date().strftime('%Y-%m-%d')
                prog_viitoare_count = pd.read_sql_query("""
                    SELECT cnp, COUNT(*) as nr 
                    FROM programari 
                    WHERE data_consultatie >= ? AND status != 'Anulat'
                    GROUP BY cnp
                """, conn, params=(data_azi,))
                prog_viitoare_dict = dict(zip(prog_viitoare_count['cnp'], prog_viitoare_count['nr']))
        except:
            prog_viitoare_dict = {}
        
        st.markdown("""
        <style>
        /* SCOPED pentru pagina Toți Pacienții - folosim selector mai specific */
        
        /* Rând pacient - DOAR în această pagină */
        .pacient-row {
            background: white;
            border-left: 3px solid #667eea;
            border-radius: 8px;
            padding: 12px 15px;
            margin: 8px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.08);
            display: grid;
            grid-template-columns: 2fr 1.3fr 1.5fr 2fr 1fr 1fr 1fr;
            gap: 15px;
            align-items: center;
        }
        
        .pacient-nume {
            font-weight: 600;
            color: #ffffff;
            font-size: 15px;
        }
        
        .pacient-info {
            color: #f0f0f0;
            font-size: 14px;
        }
        
        /* Butoane DOAR în tabelul pacienți - selector mai specific */
        [data-testid="stVerticalBlock"]:has(> div > .pacient-nume) div[data-testid="column"] {
            padding: 0 4px !important;
        }
        
        [data-testid="stVerticalBlock"]:has(> div > .pacient-nume) .stButton button {
            padding: 4px 8px !important;
            margin: 0 !important;
            height: 32px !important;
            font-size: 13px !important;
            width: 100% !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div style='display: grid; 
                    grid-template-columns: 2fr 1.3fr 1.5fr 2fr 1fr 1fr 1fr; 
                    gap: 15px; 
                    padding: 10px 15px; 
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    border-radius: 8px; 
                    margin-bottom: 8px;
                    font-weight: 700;
                    color: white;
                    font-size: 13px;'>
            <div>👤 NUME PACIENT</div>
            <div>🎂 DATA NAȘTERII</div>
            <div>📞 TELEFON</div>
            <div>📧 EMAIL</div>
            <div style='text-align: center;'>📋 DETALII</div>
            <div style='text-align: center;'>✏️ MODIFICĂ</div>
            <div style='text-align: center;'>🗑️ ȘTERGE</div>
        </div>
        """, unsafe_allow_html=True)
        
        for idx, pac in pacienti.iterrows():
            emoji = "📋" if prog_viitoare_dict.get(pac['cnp'], 0) > 0 else "👤"
            
            data_nasterii_display = formateaza_data_ro(pac['data_nasterii']) if pac['data_nasterii'] else 'N/A'
            
            este_in_confirmare = st.session_state.get(f'list_confirm_{pac["cnp"]}', False)
            
            if not este_in_confirmare:
                col1, col2, col3, col4, col5, col6, col7 = st.columns([2, 1.3, 1.5, 2, 1, 1, 1])
                
                with col1:
                    nume_complet = formateaza_nume_majuscula(pac['nume'], pac['prenume'])
                    
                    if prog_viitoare_dict.get(pac['cnp'], 0) > 0:
                        st.markdown(f"""
                        <div class='pacient-nume'>
                            {nume_complet} 📋
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div class='pacient-nume'>
                            {nume_complet}
                        </div>
                        """, unsafe_allow_html=True)
                
                with col2:
                    st.markdown(f"<div class='pacient-info'>{data_nasterii_display}</div>", unsafe_allow_html=True)
                
                with col3:
                    telefon_display = pac['telefon'] if pac['telefon'] else '-'
                    st.markdown(f"<div class='pacient-info'>{telefon_display}</div>", unsafe_allow_html=True)
                
                with col4:
                    if pac['email'] and len(str(pac['email'])) > 20:
                        email_display = str(pac['email'])[:20] + '...'
                    else:
                        email_display = pac['email'] if pac['email'] else '-'
                    st.markdown(f"<div class='pacient-info'>{email_display}</div>", unsafe_allow_html=True)
                
                with col5:
                    if st.button("📋", key=f"det_{pac['cnp']}", use_container_width=True, help="Vezi detalii"):
                        if st.session_state.pacient_detalii_selectat == pac['cnp']:
                            st.session_state.pacient_detalii_selectat = None
                        else:
                            st.session_state.pacient_detalii_selectat = pac['cnp']
                        st.rerun()
                
                with col6:
                    if st.button("✏️", key=f"edit_{pac['cnp']}", use_container_width=True, help="Modifică detalii", type="secondary"):
                        st.session_state.pacient_modifica = pac['cnp']
                        st.rerun()
                
                with col7:
                    componenta_sterge_pacient(
                        pac['cnp'], 
                        formateaza_nume_majuscula(pac['nume'], pac['prenume']), 
                        key_prefix=f"list"
                    )
            
            else:
                st.markdown(f"""
                <div style='background: linear-gradient(135deg, #f59e0b 0%, #dc2626 100%);
                            border-radius: 8px;
                            padding: 15px;
                            margin: 8px 0;
                            color: white;
                            font-weight: 600;
                            text-align: center;
                            box-shadow: 0 4px 12px rgba(245,158,11,0.3);'>
                    ⚠️ Confirmi ștergerea pacientului <strong>{formateaza_nume_majuscula(pac['nume'], pac['prenume'])}</strong>?
                </div>
                """, unsafe_allow_html=True)
                
                col_empty1, col_conf1, col_conf2, col_empty2 = st.columns([2, 1.5, 1.5, 2])
                
                with col_conf1:
                    if st.button("✅ DA, șterge", key=f"list_conf_{pac['cnp']}", type="primary", use_container_width=True):
                        succes, msg, _ = sterge_pacient(pac['cnp'], sterge_si_programari=True)
                        st.session_state[f'list_confirm_{pac["cnp"]}'] = False
                        
                        if succes:
                            st.success(msg)
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(msg)
                
                with col_conf2:
                    if st.button("❌ NU, anulează", key=f"list_canc_{pac['cnp']}", use_container_width=True):
                        st.session_state[f'list_confirm_{pac["cnp"]}'] = False
                        st.rerun()
            
            # ✅ PANEL MODIFICARE (COMPLET)
            if st.session_state.get('pacient_modifica') == pac['cnp']:
                st.markdown("""
                <div style='background: #fff9e6; 
                            border-left: 4px solid #f59e0b; 
                            border-radius: 8px; 
                            padding: 15px; 
                            margin: 4px 0 8px 0;
                            box-shadow: 0 4px 12px rgba(245,158,11,0.15);'>
                """, unsafe_allow_html=True)
                
                st.markdown(f"### ✏️ Modifică Date - {formateaza_nume_majuscula(pac['nume'], pac['prenume'])}")
                
                with st.form(f"form_modifica_list_{pac['cnp']}"):
                    col_m1, col_m2 = st.columns(2)
                    
                    with col_m1:
                        nume_nou = st.text_input("Nume *", value=pac['nume'])
                        prenume_nou = st.text_input("Prenume *", value=pac['prenume'])
                        data_nasterii_nou = st.date_input(
                            "Data nașterii *",
                            value=datetime.strptime(pac['data_nasterii'], '%Y-%m-%d').date() if pac['data_nasterii'] else date(2000, 1, 1),
                            min_value=date(1900, 1, 1),
                            max_value=date.today(),
                            format="DD/MM/YYYY"
                        )
                    
                    with col_m2:
                        telefon_nou = st.text_input("Telefon", value=pac['telefon'] if pac['telefon'] else "")
                        email_nou = st.text_input("Email", value=pac['email'] if pac['email'] else "")
                        adresa_nou = st.text_input("Adresă", value=pac['adresa'] if pac['adresa'] else "")
                    
                    observatii_nou = st.text_area("Observații medicale", value=pac['observatii'] if pac['observatii'] else "", height=80)
                    
                    col_btn1, col_btn2 = st.columns([3, 1])
                    
                    with col_btn1:
                        submit_modifica = st.form_submit_button("✅ Salvează Modificările", use_container_width=True, type="primary")
                    
                    with col_btn2:
                        cancel_modifica = st.form_submit_button("❌ Anulează", use_container_width=True)
                    
                    if submit_modifica:
                        if not nume_nou or not prenume_nou:
                            st.error("❌ Numele și prenumele sunt obligatorii!")
                        else:
                            try:
                                with sqlite3.connect('cabinet.db') as conn:
                                    c = conn.cursor()
                                    c.execute('''
                                        UPDATE pacienti 
                                        SET nume = ?, prenume = ?, data_nasterii = ?, 
                                            telefon = ?, email = ?, adresa = ?, observatii = ?
                                        WHERE cnp = ?
                                    ''', (nume_nou.upper(), prenume_nou.upper(), data_nasterii_nou, 
                                          telefon_nou, email_nou, adresa_nou, observatii_nou, pac['cnp']))
                                    conn.commit()
                                
                                st.success(f"✅ Date actualizate pentru {nume_nou} {prenume_nou}!")
                                st.session_state.pacient_modifica = None
                                time.sleep(1.5)
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Eroare actualizare: {e}")
                    
                    if cancel_modifica:
                        st.session_state.pacient_modifica = None
                        st.rerun()
                
                st.markdown("</div>", unsafe_allow_html=True)
            
            # ✅ PANEL DETALII CU ISTORIC PROGRAMĂRI COMPLET
            if st.session_state.pacient_detalii_selectat == pac['cnp']:
                st.markdown(f"""
                <div style='background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%);
                            border-left: 4px solid #667eea; 
                            border-radius: 8px; 
                            padding: 20px; 
                            margin: 8px 0 15px 0;
                            box-shadow: 0 4px 12px rgba(102,126,234,0.15);'>
                """, unsafe_allow_html=True)
                
                st.markdown(f"### 📋 {formateaza_nume_majuscula(pac['nume'], pac['prenume'])}")
                
                col_d1, col_d2, col_d3 = st.columns(3)
                
                with col_d1:
                    st.markdown("**👤 Date Personale**")
                    st.write(f"**CNP:** {pac['cnp']}")
                    st.write(f"**Naștere:** {formateaza_data_ro(pac['data_nasterii'])}")
                    st.write(f"**Adresă:** {pac['adresa'] if pac['adresa'] else 'N/A'}")
                
                with col_d2:
                    st.markdown("**📞 Contact**")
                    st.write(f"**Tel:** {pac['telefon'] if pac['telefon'] else 'N/A'}")
                    st.write(f"**Email:** {pac['email'] if pac['email'] else 'N/A'}")
                
                with col_d3:
                    st.markdown("**🏥 Medical**")
                    try:
                        with sqlite3.connect('cabinet.db') as conn:
                            c = conn.cursor()
                            
                            c.execute("SELECT COUNT(*) FROM programari WHERE cnp = ?", (pac['cnp'],))
                            total_prog = c.fetchone()[0]
                            
                            data_azi = datetime.now().date().strftime('%Y-%m-%d')
                            c.execute("""
                                SELECT COUNT(*) FROM programari 
                                WHERE cnp = ? AND data_consultatie >= ? AND status != 'Anulat'
                            """, (pac['cnp'], data_azi))
                            viitoare = c.fetchone()[0]
                            
                            c.execute("""
                                SELECT COUNT(*) FROM programari 
                                WHERE cnp = ? AND data_consultatie < ?
                            """, (pac['cnp'], data_azi))
                            trecute = c.fetchone()[0]
                            
                            c.execute("""
                                SELECT COUNT(*) FROM programari 
                                WHERE cnp = ? AND status = 'Finalizat'
                            """, (pac['cnp'],))
                            validate = c.fetchone()[0]
                            
                            c.execute("""
                                SELECT COUNT(*) FROM programari 
                                WHERE cnp = ? AND status NOT IN ('Finalizat', 'Anulat')
                            """, (pac['cnp'],))
                            nevalidate = c.fetchone()[0]
                            
                    except Exception as e:
                        logger.error(f"Eroare statistici programări: {e}")
                        total_prog = 0
                        viitoare = 0
                        trecute = 0
                        validate = 0
                        nevalidate = 0
                    
                    if total_prog > 0:
                        col_med1, col_med2 = st.columns([1, 1])
                        
                        with col_med1:
                            st.markdown(f"""
                            <div style='margin-top: 5px;'>
                                <div style='font-size: 13px; color: #b0b0b0; margin-bottom: 5px;'>Total programări:</div>
                                <div style='font-size: 48px; font-weight: 700; color: #ffffff; line-height: 1;'>{total_prog}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with col_med2:
                            st.markdown(f"""
                            <div style='margin-top: 5px; line-height: 1.8;'>
                                <div style='margin-bottom: 4px;'>
                                    <span style='font-size: 13px; color: #c0c0c0;'>Viitoare:</span>
                                    <span style='font-size: 16px; font-weight: 600; color: #ffffff; margin-left: 6px;'>{viitoare}</span>
                                </div>
                                <div style='margin-bottom: 4px;'>
                                    <span style='font-size: 13px; color: #c0c0c0;'>Trecute:</span>
                                    <span style='font-size: 16px; font-weight: 600; color: #ffffff; margin-left: 6px;'>{trecute}</span>
                                </div>
                                <div style='margin-bottom: 4px;'>
                                    <span style='font-size: 13px; color: #c0c0c0;'>Validate:</span>
                                    <span style='font-size: 16px; font-weight: 600; color: #4CAF50; margin-left: 6px;'>{validate}</span>
                                </div>
                                <div style='margin-bottom: 4px;'>
                                    <span style='font-size: 13px; color: #c0c0c0;'>Nevalidate:</span>
                                    <span style='font-size: 16px; font-weight: 600; color: #FFA726; margin-left: 6px;'>{nevalidate}</span>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                    
                    else:
                        st.success("✅ Fără programări")
                
                if pac['observatii']:
                    st.info(f"**📝 Observații:** {pac['observatii']}")
                
                st.markdown("---")
                st.markdown("### 📅 Istoric Programări")
                
                try:
                    with sqlite3.connect('cabinet.db') as conn:
                        programari_pacient = pd.read_sql_query('''
                            SELECT 
                                id, data_consultatie, ora_consultatie, tip_plata, status, observatii
                            FROM programari
                            WHERE cnp = ?
                            ORDER BY data_consultatie DESC, ora_consultatie DESC
                        ''', conn, params=(pac['cnp'],))
                    
                    if not programari_pacient.empty:
                        data_azi = datetime.now().date().strftime('%Y-%m-%d')
                        
                        prog_viitoare = programari_pacient[programari_pacient['data_consultatie'] >= data_azi]
                        prog_trecute = programari_pacient[programari_pacient['data_consultatie'] < data_azi]
                        
                        tab1, tab2, tab3 = st.tabs([
                            f"🔜 Viitoare ({len(prog_viitoare)})", 
                            f"📅 Trecute ({len(prog_trecute)})", 
                            f"📊 Toate ({len(programari_pacient)})"
                        ])
                        
                        # ========== TAB 1: VIITOARE ==========
                        with tab1:
                            if not prog_viitoare.empty:
                                
                                
                                df_viitoare = prog_viitoare.copy()
                                df_viitoare['data_consultatie'] = df_viitoare['data_consultatie'].apply(formateaza_data_ro)
                                df_viitoare['tip_plata'] = df_viitoare['tip_plata'].apply(
                                    lambda x: '🎫 Bilet' if x == 'Bilet trimitere' else '💳 Plată'
                                )
                                df_viitoare['status'] = df_viitoare['status'].apply(
                                    lambda x: '✅ Finalizat' if x == 'Finalizat' else (
                                        '❌ Anulat' if x == 'Anulat' else (
                                            '🔵 Confirmat' if x == 'Confirmat' else '⏳ Programat'
                                        )
                                    )
                                )
                                
                                df_viitoare_display = df_viitoare[['data_consultatie', 'ora_consultatie', 'tip_plata', 'status', 'observatii']].copy()
                                df_viitoare_display.columns = ['Data', 'Ora', 'Tip Plată', 'Status', 'Observații']
                                df_viitoare_display['Observații'] = df_viitoare_display['Observații'].fillna('-')
                                
                                st.dataframe(
                                    df_viitoare_display,
                                    use_container_width=True,
                                    hide_index=True,
                                    height=min(400, 50 + len(df_viitoare_display) * 35)
                                )
                            else:
                                st.info("📭 Nicio programare viitoare")
                        
                        # ========== TAB 2: TRECUTE ==========
                        with tab2:
                            if not prog_trecute.empty:
                                                                
                                df_trecute = prog_trecute.copy()
                                df_trecute['data_consultatie'] = df_trecute['data_consultatie'].apply(formateaza_data_ro)
                                df_trecute['tip_plata'] = df_trecute['tip_plata'].apply(
                                    lambda x: '🎫 Bilet' if x == 'Bilet trimitere' else '💳 Plată'
                                )
                                df_trecute['status'] = df_trecute['status'].apply(
                                    lambda x: '✅ Finalizat' if x == 'Finalizat' else (
                                        '❌ Anulat' if x == 'Anulat' else (
                                            '🔵 Confirmat' if x == 'Confirmat' else '⏳ Programat'
                                        )
                                    )
                                )
                                
                                df_trecute_display = df_trecute[['data_consultatie', 'ora_consultatie', 'tip_plata', 'status', 'observatii']].copy()
                                df_trecute_display.columns = ['Data', 'Ora', 'Tip Plată', 'Status', 'Observații']
                                df_trecute_display['Observații'] = df_trecute_display['Observații'].fillna('-')
                                
                                st.dataframe(
                                    df_trecute_display,
                                    use_container_width=True,
                                    hide_index=True,
                                    height=min(400, 50 + len(df_trecute_display) * 35)
                                )
                            else:
                                st.info("📭 Nicio programare trecută")
                        
                        # ========== TAB 3: TOATE (TABEL HTML CU BUTOANE) ==========
                        with tab3:
                            
                            # Header tabel
                            st.markdown("""
                            <div style='display: grid; 
                                        grid-template-columns: 1.2fr 0.8fr 1fr 1fr 2fr 0.5fr; 
                                        gap: 8px; 
                                        padding: 10px 15px; 
                                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                        border-radius: 8px; 
                                        margin-bottom: 8px;
                                        font-weight: 700;
                                        color: white;
                                        font-size: 13px;
                                        align-items: center;'>
                                <div>📅 Data</div>
                                <div>🕐 Ora</div>
                                <div>💳 Tip Plată</div>
                                <div>📊 Status</div>
                                <div>📝 Observații</div>
                                <div style='text-align: center;'>🗑️ Acțiune</div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Rânduri tabel (fără modificări de height în DIV-uri)
                            for idx, prog in programari_pacient.iterrows():
                                # Format data
                                tip_emoji = '🎫 Bilet' if prog['tip_plata'] == 'Bilet trimitere' else '💳 Plată'
                                
                                if prog['status'] == 'Finalizat':
                                    status_text = '✅ Finalizat'
                                elif prog['status'] == 'Anulat':
                                    status_text = '❌ Anulat'
                                elif prog['status'] == 'Confirmat':
                                    status_text = '🔵 Confirmat'
                                else:
                                    status_text = '⏳ Programat'
                                
                                obs_text = prog['observatii'] if prog['observatii'] else '-'
                                
                                # Container rând
                                col1, col2, col3, col4, col5, col6 = st.columns([1.2, 0.8, 1, 1, 2, 0.5], gap="small")
                                
                                with col1:
                                    st.markdown(f"<div style='padding: 4px 0; color: #f0f0f0; font-size: 16px;'>{formateaza_data_ro(prog['data_consultatie'])}</div>", unsafe_allow_html=True)
                                
                                with col2:
                                    st.markdown(f"<div style='padding: 4px 0; color: #f0f0f0; font-size: 16px;'>{prog['ora_consultatie']}</div>", unsafe_allow_html=True)
                                
                                with col3:
                                    st.markdown(f"<div style='padding: 4px 0; color: #f0f0f0; font-size: 16px;'>{tip_emoji}</div>", unsafe_allow_html=True)
                                
                                with col4:
                                    st.markdown(f"<div style='padding: 4px 0; color: #f0f0f0; font-size: 16px;'>{status_text}</div>", unsafe_allow_html=True)
                                
                                with col5:
                                    st.markdown(f"<div style='padding: 4px 0; color: #f0f0f0; font-size: 16px;'>{obs_text}</div>", unsafe_allow_html=True)
                                
                                with col6:
                                    # Buton ștergere cu confirmare (dimensiune normală)
                                    if not st.session_state.get(f'confirm_delete_tab3_{prog["id"]}', False):
                                        if st.button("🗑️", key=f"del_tab3_{prog['id']}", use_container_width=True, type="secondary", help="Șterge programare"):
                                            st.session_state[f'confirm_delete_tab3_{prog["id"]}'] = True
                                            st.rerun()
                                    else:
                                        col_conf1, col_conf2 = st.columns(2)
                                        with col_conf1:
                                            if st.button("✅", key=f"conf_tab3_yes_{prog['id']}", use_container_width=True, help="Confirmă ștergerea"):
                                                sterge_programare(prog['id'])
                                                st.session_state[f'confirm_delete_tab3_{prog["id"]}'] = False
                                                st.success("✅ Șters!")
                                                time.sleep(0.8)
                                                st.rerun()
                                        with col_conf2:
                                            if st.button("❌", key=f"conf_tab3_no_{prog['id']}", use_container_width=True, help="Anulează"):
                                                st.session_state[f'confirm_delete_tab3_{prog["id"]}'] = False
                                                st.rerun()
                     
                    else:
                        st.info("📭 **Pacientul nu are nicio programare înregistrată**")
                        st.caption("💡 Poți programa acest pacient folosind butonul de mai jos")
                
                except Exception as e:
                    st.error(f"❌ Eroare obținere programări: {e}")
                    logger.error(f"Eroare programări pacient {pac['cnp']}: {e}")
                
                st.markdown("---")
                
                col_act1, col_act2 = st.columns(2)
                
                with col_act1:
                    if st.button("📅 Programează acest pacient", key=f"prog_det_{pac['cnp']}", use_container_width=True, type="primary"):
                        st.session_state.pacient_selectat_id = pac['cnp']
                        st.session_state.pagina = "Programează"
                        st.rerun()
                
                with col_act2:
                    if st.button("🔙 Închide", key=f"close_{pac['cnp']}", use_container_width=True):
                        st.session_state.pacient_detalii_selectat = None
                        st.rerun()
                
                st.markdown("</div>", unsafe_allow_html=True)
    
else:
    st.info("📭 Niciun pacient în baza de date")
    st.caption("💡 Adaugă primul pacient folosind meniul din stânga")
            
# ========================================
# FOOTER
# ========================================

st.markdown("---")
st.markdown("""
<div style='text-align: center; padding: 3px 6px; margin-bottom: 3px;'>
    <!-- Emoji ⚕️ cu border circular -->
<div style='text-align: center; color: #7f8c8d; padding: 20px;'>
    <p style='margin: 5px 0;'><strong>Cabinet Medical - Dr. Pop V. Maria</strong></p>
    <p style='margin: 5px 0; font-size: 0.9em;'>Sistem de management pacienți și programări</p>
    <p style='margin: 5px 0; font-size: 0.8em;'>Programări cu bilet: 08:20-12:40 (interval 20 min) | Validare: minim 3 luni între programări</p>
    <p style='margin: 5px 0; font-size: 0.8em;'>© 2024 - Toate drepturile rezervate</p>
</div>
""", unsafe_allow_html=True)        
