
from pathlib import Path
import io, re, unicodedata, math, zipfile, tempfile, json
import pandas as pd
import numpy as np
import streamlit as st
from PIL import Image, ImageOps, ImageEnhance
import plotly.express as px
from rapidfuzz import fuzz, process
from pypdf import PdfReader
import pytesseract

st.set_page_config(page_title="Smart Visit Planner · V2", layout="wide")

BASE = Path(__file__).parent
DATA = BASE / "data"

# ------------------------------
# Helpers
# ------------------------------
def norm(s):
    s = "" if s is None or (isinstance(s, float) and pd.isna(s)) else str(s)
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = re.sub(r"[^A-Z0-9]+", " ", s.upper()).strip()
    return re.sub(r"\s+", " ", s)

def nnum(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return 0.0
    if isinstance(v, (int, float, np.number)):
        return float(v)
    s = str(v).strip().replace("€", "").replace("%", "").replace(" ", "")
    # European thousands/decimals
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        right = s.split(",")[-1]
        s = s.replace(".", "").replace(",", ".") if len(right) <= 2 else s.replace(",", "")
    elif "." in s:
        parts = s.split(".")
        # 21.025 -> 21025 ; 13.65 -> 13.65
        if len(parts[-1]) == 3 and len(parts) <= 3:
            s = s.replace(".", "")
    try:
        return float(s)
    except:
        return 0.0

def euro(v):
    try:
        return f"{float(v):,.0f} €".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "—"

def safe_read_csv(path_or_file):
    for enc in ("utf-8-sig", "utf-8", "latin1"):
        try:
            return pd.read_csv(path_or_file, encoding=enc)
        except Exception:
            pass
    return pd.read_csv(path_or_file)

def read_table_upload(upload):
    if upload is None:
        return None
    name = upload.name.lower()
    upload.seek(0)
    if name.endswith(".csv"):
        return safe_read_csv(upload)
    if name.endswith((".xlsx",".xls")):
        return pd.read_excel(upload)
    return None

def clean_lob(df):
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    # Normalize columns
    cols = {c: str(c).strip() for c in df.columns}
    df = df.rename(columns=cols)
    aliases = {
        "client": ["client","cliente","nombre client","nombre cliente"],
        "pos_id": ["pos_id","cpv","codi client","codigo cliente","código cliente"],
        "address": ["address","direccion","dirección","direccio","direcció"],
        "town": ["town","poblacion","población"],
        "province": ["province","provincia","província"],
        "postal_code": ["postal_code","cp","codigo postal","código postal"],
        "group": ["group","grupo","grup compra","grupo compra","grupos compra"],
        "coach": ["coach"]
    }
    ncols = {norm(c): c for c in df.columns}
    for std, opts in aliases.items():
        if std not in df.columns:
            for o in opts:
                if norm(o) in ncols:
                    df[std] = df[ncols[norm(o)]]
                    break
        if std not in df.columns:
            df[std] = ""
    # Numeric columns
    for c in df.columns:
        cu = str(c).upper()
        if any(k in cu for k in ["TOTAL_", "_2025", "_OBJ", "_YTD", "FACT", "IMPORT", "OBJECTIU", "OBJETIVO"]):
            if c not in ["pos_id"]:
                df[c] = df[c].map(nnum)
    df["pdv_key"] = df.apply(lambda r: pdv_key(r.get("address",""), r.get("postal_code",""), r.get("town","")), axis=1)
    return df

def pdv_key(address, postal="", town=""):
    a = norm(address)
    # remove administrative noise, preserve street number
    a = re.sub(r"\b(FARMACIA|FCIA|FCA|LOCAL|BAJOS|BAJO|ENTLO|PRAL)\b", " ", a)
    a = re.sub(r"\s+"," ",a).strip()
    return f"{a}|{norm(postal)}|{norm(town)}"

def pdv_similarity(k1, k2):
    a1, cp1, t1 = (k1.split("|")+["",""])[:3]
    a2, cp2, t2 = (k2.split("|")+["",""])[:3]
    score = fuzz.token_set_ratio(a1, a2)
    if cp1 and cp2 and cp1 == cp2: score += 8
    if t1 and t2 and t1 == t2: score += 5
    return min(score, 100)

def equivalent_rows(df, row):
    if df.empty:
        return df
    key = row["pdv_key"]
    exact = df[df["pdv_key"] == key]
    if len(exact):
        return exact
    scores = df["pdv_key"].map(lambda k: pdv_similarity(key, k))
    return df[scores >= 92]

# ------------------------------
# OCR and document parsing
# ------------------------------
def preprocess_image(img):
    if img.mode != "L":
        img = ImageOps.grayscale(img)
    img = ImageEnhance.Contrast(img).enhance(1.8)
    # upscale modestly
    if img.width < 1800:
        ratio = 1800 / img.width
        img = img.resize((int(img.width*ratio), int(img.height*ratio)))
    return img

@st.cache_data(show_spinner=False)
def ocr_bytes(raw, lang="spa"):
    img = Image.open(io.BytesIO(raw))
    img = preprocess_image(img)
    try:
        return pytesseract.image_to_string(img, lang=lang, config="--psm 6")
    except Exception:
        return pytesseract.image_to_string(img, config="--psm 6")

def extract_text(upload):
    if upload is None:
        return ""
    name = upload.name.lower()
    raw = upload.getvalue()
    if name.endswith(".pdf"):
        text = ""
        try:
            reader = PdfReader(io.BytesIO(raw))
            for p in reader.pages:
                text += "\n" + (p.extract_text() or "")
        except Exception:
            pass
        return text
    if name.endswith((".png",".jpg",".jpeg",".webp")):
        return ocr_bytes(raw)
    return ""

AGREEMENT_BRANDS = ["AVENE","DUCRAY","A-DERMA","KLORANE"]

def parse_agreement(files):
    """
    Parses the Evolución Pacto block. Rule:
    - collective objective is the repeated 'Obj. 15% A Colectivo' value
    - actual collective is repeated 'Fact. A Colectivo'
    - per-brand reference/current/gap comes from Fact A-1 Marca / Fact A Marca / Falta para Obj A Marca
    Never substitutes LOB objective if this cannot be read.
    """
    texts = [extract_text(f) for f in (files or [])]
    full = "\n".join(texts)
    lines = [re.sub(r"\s+"," ",l).strip() for l in full.splitlines() if l.strip()]
    brand_rows = []
    for brand in AGREEMENT_BRANDS:
        candidates = [l for l in lines if norm(l).startswith(brand)]
        for line in candidates:
            nums = [nnum(x) for x in re.findall(r"-?\d[\d\.,]*", line)]
            # Expected row usually has: collective prev, collective actual, evol, collective obj, falta collective,
            # brand prev, brand actual, evol, falta brand, %rfa, rfa
            if len(nums) >= 7:
                brand_rows.append((brand, nums, line))
                break

    result = {
        "objective_collective": None,
        "actual_collective": None,
        "missing_collective": None,
        "brands": [],
        "raw_text": full
    }
    # Best effort across rows
    obj_candidates, actual_candidates, miss_candidates = [], [], []
    for brand, nums, line in brand_rows:
        # strip likely percentages from early positions by using magnitude & sequence heuristics
        # For known table pattern: [prev_coll, actual_coll, evol%, obj_coll, falta_coll, prev_brand, actual_brand, evol%, falta_brand, ...]
        if len(nums) >= 9:
            prev_coll, actual_coll = nums[0], nums[1]
            obj_coll, falta_coll = nums[3], nums[4]
            prev_brand, actual_brand = nums[5], nums[6]
            falta_brand = nums[8]
            obj_candidates.append(obj_coll)
            actual_candidates.append(actual_coll)
            miss_candidates.append(falta_coll)
            result["brands"].append({
                "Marca": brand.replace("AVENE","Avène").title().replace("A-Derma","A-Derma"),
                "Referencia marca €": prev_brand,
                "Actual marca €": actual_brand,
                "Falta marca €": max(falta_brand,0)
            })

    # Repeated collective values are most reliable
    def modeish(vals):
        vals = [round(v,0) for v in vals if v and v > 100]
        if not vals: return None
        s = pd.Series(vals)
        return float(s.value_counts().idxmax())

    result["objective_collective"] = modeish(obj_candidates)
    result["actual_collective"] = modeish(actual_candidates)
    result["missing_collective"] = modeish(miss_candidates)
    return result

VEEVA_ALIASES = {
    "AVENE": {
        "G029 XERACALM": "Atopia / XeraCalm",
        "ASE ACNE": "Acné / Cleanance",
        "AHY HYDRANCE": "Hydrance",
        "ACZ CICALFATE": "Cicalfate",
        "ASO SOLAIRES": "Solar",
        "G036 HYALURON ACTIV": "Antiedad / Hyaluron Activ",
        "G034 DERMABSOLU": "Antiedad / DermAbsolu",
        "G038 AOXITIVE": "Antiedad / A-Oxitive",
        "APH TOLERANCE": "Tolérance",
        "ASS SOINS ESSENTIELS": "Esenciales",
        "AES EAU THERMALE": "Agua termal",
        "G031 COLD CREAM": "Cold Cream",
    },
    "DUCRAY": {
        "PEL ETATS PELLICULAIRES": "Anticaspa",
        "DIN PEAUX ATOPIQUES": "Atopia / Dexyane",
        "DCC CHUTE DE CHEVEUX": "Anticaída",
        "DSB PEAUX ACNEIQUES": "Acné / Keracnyl",
        "CCS PRURIT": "Prurito",
        "DCG AP CAPILLAIRES": "Capilar",
        "UGF CHEVEUX DELICATS": "Cabello delicado",
        "CVG CHEVEUX GRAS": "Cabello graso",
    },
    "A-DERMA": {
        "EXO EXOMEGA": "Atopia / Exomega",
        "G057 DERMALIBOUR": "Dermalibour+",
        "G058 CYTELIUM": "Cytelium",
        "SOL SOLAIRES": "Solar",
        "EPI EPITHELIALE": "Epitheliale",
    },
    "PFD": {"EMO EMOLLIENT": "Dexeryl"},
}

def parse_veeva(files):
    rows = []
    current_brand = None
    raw_texts = []
    for f in files or []:
        txt = extract_text(f)
        raw_texts.append(txt)
        for raw_line in txt.splitlines():
            line = re.sub(r"\s+"," ",raw_line).strip()
            nl = norm(line)
            if not nl:
                continue
            # detect brand headers
            for b in ["AVENE","DUCRAY","A-DERMA","PFD","KLORANE","FURTERER"]:
                if re.search(rf"\b{re.escape(norm(b))}\b", nl) and len(nl) < 80:
                    current_brand = b
                    # brand totals might also be parsed but we focus on gamas
                    break
            if not current_brand:
                continue
            aliases = VEEVA_ALIASES.get(current_brand,{})
            for code, friendly in aliases.items():
                if norm(code) in nl:
                    # remove percentage values first
                    tokens = re.findall(r"-?\d+(?:[\.,]\d+)?\s*%?", line)
                    vals = []
                    for t in tokens:
                        if "%" not in t:
                            vals.append(nnum(t))
                    # On Veeva rows, last two non-% numeric values are usually YTD and TAM12M
                    ytd = tam = None
                    if len(vals) >= 2:
                        ytd, tam = vals[-2], vals[-1]
                    elif len(vals) == 1:
                        ytd = tam = vals[0]
                    rows.append({
                        "Marca": "Dexeryl" if current_brand=="PFD" else current_brand.title().replace("A-Derma","A-Derma"),
                        "Gama": friendly,
                        "YTD uds": ytd,
                        "TAM12M uds": tam,
                        "Fuente": f.name
                    })
                    break
    if not rows:
        return pd.DataFrame(columns=["Marca","Gama","YTD uds","TAM12M uds","Fuente"]), "\n".join(raw_texts)
    df = pd.DataFrame(rows)
    # deduplicate: prefer the row with largest TAM/YTD (usually broader/clearer screenshot)
    df["score"] = df[["YTD uds","TAM12M uds"]].fillna(0).sum(axis=1)
    df = df.sort_values("score", ascending=False).drop_duplicates(["Marca","Gama"]).drop(columns="score")
    return df, "\n".join(raw_texts)

# ------------------------------
# Cycle/product parsing
# ------------------------------
def extract_pdf_lines(upload):
    txt = extract_text(upload)
    return [re.sub(r"\s+"," ",x).strip() for x in txt.splitlines() if x.strip()]

def parse_order_sheets(files):
    rows = []
    for f in files or []:
        txt = extract_text(f)
        # generic line matcher: CN 6 digits + product + price
        for line in txt.splitlines():
            l = re.sub(r"\s+"," ",line).strip()
            m = re.search(r"\b(\d{6})\b\s+(.+?)\s+(\d{1,3}[\.,]\d{1,2})\s*€?", l)
            if m:
                cn, product, pvl = m.group(1), m.group(2).strip(), nnum(m.group(3))
                rows.append({"CN":cn,"Producto":product,"PVL":pvl,"Fuente":f.name})
    if not rows:
        return pd.DataFrame(columns=["CN","Producto","PVL","Fuente"])
    return pd.DataFrame(rows).drop_duplicates("CN")

def normalize_product_catalog(df):
    if df is None or df.empty:
        return pd.DataFrame(columns=["Marca","Gama","CN","Producto","PVL","Heroe","Novedad"])
    d = df.copy()
    cm = {norm(c): c for c in d.columns}
    def pick(names, default=""):
        for n in names:
            if norm(n) in cm:
                return d[cm[norm(n)]]
        return pd.Series([default]*len(d))
    out = pd.DataFrame({
        "Marca": pick(["Marca","Brand"]),
        "Gama": pick(["Gama","Categoria","Categoría","Category"]),
        "CN": pick(["CN","Codigo Nacional","Código Nacional"]).astype(str).str.replace(r"\.0$","",regex=True),
        "Producto": pick(["Producto","Product"]),
        "PVL": pick(["PVL","Precio","Precio tarifa"]).map(nnum),
        "Heroe": pick(["Heroe","Héroe","Hero"],False),
        "Novedad": pick(["Novedad","Novetat","New"],False)
    })
    out["Marca"] = out["Marca"].astype(str)
    out["Gama"] = out["Gama"].astype(str)
    return out

def relevant_actions(texts, brand=None, gama=None):
    full = "\n".join(texts or [])
    if not full.strip():
        return []
    keywords = []
    if brand: keywords += [norm(brand)]
    if gama: keywords += [norm(gama)] + norm(gama).split()
    lines = [re.sub(r"\s+"," ",x).strip() for x in full.splitlines() if x.strip()]
    scored=[]
    for l in lines:
        nl=norm(l)
        score=sum(1 for k in keywords if k and k in nl)
        if score and any(w in nl for w in ["DESCUENTO","PROMOCION","INCENTIVO","VISIBILIDAD","MUESTRAS","SELL OUT","CAMPAÑA","CAMPANA","3X2","REGALO","BONIFIC"]):
            scored.append((score,l))
    return [l for _,l in sorted(scored, reverse=True)[:6]]

# ------------------------------
# Analysis
# ------------------------------
BRAND_KEYS = [
    ("AVENE SIN SOLAR","Avène sin Solar"),
    ("AVENE SOLAR","Avène Solar"),
    ("DUCRAY","Ducray"),
    ("A-DERMA","A-Derma"),
    ("DEXERYL","Dexeryl"),
]

def brand_snapshot(row):
    rows=[]
    for key,label in BRAND_KEYS:
        obj=nnum(row.get(f"{key}_OBJ",0))
        ytd=nnum(row.get(f"{key}_YTD",0))
        prev=nnum(row.get(f"{key}_YTD1",0))
        rows.append({"Marca":label,"Objetivo LOB €":obj,"YTD €":ytd,"YTD-1 €":prev,
                     "Evolución %":((ytd/prev)-1)*100 if prev else np.nan,
                     "Gap LOB €":max(obj-ytd,0)})
    return pd.DataFrame(rows)

def agreement_plan(agr, brand_df):
    actions=[]
    if agr.get("objective_collective"):
        obj=agr["objective_collective"]
        act=agr.get("actual_collective") or 0
        miss=max(obj-act,0) if act else agr.get("missing_collective")
        if miss is not None:
            actions.append(("ACUERDO", f"Faltan {euro(miss)} para el objetivo del acuerdo.", "alta" if miss>0 else "ok"))
        bdf=pd.DataFrame(agr.get("brands",[]))
        if not bdf.empty:
            bdf=bdf.sort_values("Falta marca €",ascending=False)
            for _,r in bdf.head(3).iterrows():
                if r["Falta marca €"]>0:
                    actions.append(("RECUPERAR",f"{r['Marca']}: faltan {euro(r['Falta marca €'])} según la ficha 2026.","alta"))
    else:
        # no fake agreement target
        actions.append(("ACUERDO","Objetivo del acuerdo no confirmado. No se sustituye por el objetivo LOB.","aviso"))
    return actions

def veeva_opportunities(vdf):
    out=[]
    if vdf.empty:
        return out
    for _,r in vdf.iterrows():
        y=nnum(r["YTD uds"]); t=nnum(r["TAM12M uds"])
        if y==0 and t==0:
            out.append(("IMPLANTAR",f"{r['Marca']} · {r['Gama']}: sin compra YTD ni TAM12M detectada.","oportunidad"))
        elif t>0 and y < 0.35*t:
            out.append(("RECUPERAR GAMA",f"{r['Marca']} · {r['Gama']}: {int(y)} uds YTD vs {int(t)} uds TAM12M.","media"))
    return out

def build_conservative_order(catalog, selected_brand, selected_gama, veeva_df):
    d=catalog.copy()
    if d.empty:
        return d
    if selected_brand:
        d=d[d["Marca"].map(norm).str.contains(norm(selected_brand),na=False)]
    if selected_gama:
        d=d[d["Gama"].map(norm).str.contains(norm(selected_gama),na=False)]
    if d.empty:
        return d
    hist=veeva_df[(veeva_df["Marca"].map(norm)==norm(selected_brand)) & (veeva_df["Gama"].map(norm)==norm(selected_gama))]
    ytd=tam=0
    if not hist.empty:
        ytd=nnum(hist.iloc[0]["YTD uds"]); tam=nnum(hist.iloc[0]["TAM12M uds"])
    remaining=max(tam-ytd,0) if tam else 0
    # Conservative order: never dump huge quantities. Start from 1-3 per line.
    n=len(d)
    base_total = min(max(int(math.ceil(remaining/3)) if remaining else min(6,n*2), n), 24)
    units=[]
    for _,r in d.iterrows():
        u=1
        if bool(r.get("Novedad")): u+=1
        if bool(r.get("Heroe")): u+=1
        units.append(u)
    # scale but cap 6 per SKU
    total=sum(units)
    if total < base_total and n:
        i=0
        while sum(units)<base_total and i<1000:
            j=i%n
            if units[j]<6: units[j]+=1
            i+=1
            if all(x>=6 for x in units): break
    d=d.copy()
    d["Unidades"]=units
    d["Importe"]=d["PVL"]*d["Unidades"]
    d["Motivo"]=d.apply(lambda r: "Novedad" if bool(r["Novedad"]) else ("Héroe / rotación" if bool(r["Heroe"]) else "Surtido / reposición"),axis=1)
    return d

# ------------------------------
# Load defaults / session cycle
# ------------------------------
@st.cache_data
def default_lob():
    p=DATA/"lob_master.csv"
    return clean_lob(safe_read_csv(p)) if p.exists() else pd.DataFrame()

if "lob" not in st.session_state:
    st.session_state["lob"]=default_lob()
if "compar" not in st.session_state:
    st.session_state["compar"]=None
if "catalog" not in st.session_state:
    st.session_state["catalog"]=pd.DataFrame(columns=["Marca","Gama","CN","Producto","PVL","Heroe","Novedad"])
if "cycle_texts" not in st.session_state:
    st.session_state["cycle_texts"]=[]
if "cycle_name" not in st.session_state:
    st.session_state["cycle_name"]="Ciclo actual"

# ------------------------------
# UI
# ------------------------------
st.title("Smart Visit Planner · V2")
st.caption("Objetivo = acuerdo de la Ficha 2026 · LOB/COMPAR = contraste económico · Veeva = unidades/gamas · identidad = punto de venta físico")

with st.sidebar:
    st.header("Modo")
    mode=st.radio("Análisis",["Visita individual","Grupo / consolidado","Gestión de ciclo"])
    st.divider()
    st.caption(f"Ciclo activo: **{st.session_state['cycle_name']}**")

if mode=="Gestión de ciclo":
    st.header("Gestión de ciclo")
    st.info("Carga los nuevos archivos del ciclo. Esta V2 los usa sin modificar el código. Para que sean permanentes tras reinicios de Streamlit, sustituye los archivos de /data del repositorio con el pack validado.")
    cycle_name=st.text_input("Nombre del ciclo",st.session_state["cycle_name"])
    lob_up=st.file_uploader("LOB del ciclo (CSV/XLSX)",type=["csv","xlsx","xls"])
    compar_up=st.file_uploader("COMPAR / histórico económico (CSV/XLSX)",type=["csv","xlsx","xls"])
    catalog_up=st.file_uploader("Tarifa / catálogo estructurado (CSV/XLSX)",type=["csv","xlsx","xls"])
    order_files=st.file_uploader("Hojas de pedido del ciclo (PDF, varias)",type=["pdf"],accept_multiple_files=True)
    condition_files=st.file_uploader("Chuleta / condiciones / campañas sell-out (PDF, varias)",type=["pdf"],accept_multiple_files=True)
    if st.button("Activar ciclo"):
        if lob_up:
            st.session_state["lob"]=clean_lob(read_table_upload(lob_up))
        if compar_up:
            st.session_state["compar"]=read_table_upload(compar_up)
        if catalog_up:
            st.session_state["catalog"]=normalize_product_catalog(read_table_upload(catalog_up))
        elif order_files:
            parsed=parse_order_sheets(order_files)
            if not parsed.empty:
                tmp=parsed.rename(columns={"Fuente":"Gama"})
                tmp["Marca"]=""; tmp["Heroe"]=False; tmp["Novedad"]=False
                st.session_state["catalog"]=normalize_product_catalog(tmp)
        st.session_state["cycle_texts"]=[extract_text(f) for f in (condition_files or [])]
        st.session_state["cycle_name"]=cycle_name
        st.success("Ciclo activado.")
    c1,c2,c3,c4=st.columns(4)
    c1.metric("LOB","OK" if not st.session_state["lob"].empty else "Falta")
    c2.metric("COMPAR","OK" if st.session_state["compar"] is not None else "Opcional")
    c3.metric("Catálogo",len(st.session_state["catalog"]))
    c4.metric("Documentos ciclo",len(st.session_state["cycle_texts"]))
    st.stop()

lob=st.session_state["lob"]
if lob.empty:
    st.error("No hay LOB cargado. Entra en Gestión de ciclo y carga el LOB.")
    st.stop()

if mode=="Grupo / consolidado":
    st.header("Grupo / consolidado")
    groups=sorted([g for g in lob["group"].dropna().astype(str).unique() if norm(g) not in ("","NO GRUPOS","NO GRUPO")])
    if not groups:
        st.warning("El LOB actual no contiene grupos identificables.")
        st.stop()
    group=st.selectbox("Grupo",groups)
    g=lob[lob["group"].astype(str)==group].copy()
    # consolidate by physical location
    agg_cols=[c for c in g.columns if any(k in str(c).upper() for k in ["TOTAL_2025","TOTAL_OBJ","TOTAL_YTD1","TOTAL_YTD",
                                                                        "AVENE SIN SOLAR_YTD","AVENE SOLAR_YTD","DUCRAY_YTD","A-DERMA_YTD","DEXERYL_YTD"])]
    aggs={c:"sum" for c in agg_cols}
    aggs.update({"client":lambda x:" / ".join(pd.unique(x.astype(str))),"pos_id":lambda x:", ".join(pd.unique(x.astype(str))),
                 "address":"first","town":"first","province":"first"})
    pdv=g.groupby("pdv_key",dropna=False).agg(aggs).reset_index()
    ytd= pdv["TOTAL_YTD"].sum() if "TOTAL_YTD" in pdv else 0
    prev= pdv["TOTAL_YTD1"].sum() if "TOTAL_YTD1" in pdv else 0
    obj= pdv["TOTAL_OBJ"].sum() if "TOTAL_OBJ" in pdv else 0
    cols=st.columns(4)
    cols[0].metric("YTD grupo",euro(ytd))
    cols[1].metric("YTD-1 grupo",euro(prev),f"{((ytd/prev)-1)*100:+.1f}%" if prev else None)
    cols[2].metric("Objetivo LOB grupo*",euro(obj))
    cols[3].metric("Puntos de venta",len(pdv))
    st.caption("*En modo grupo, si no hay fichas individuales, el objetivo disponible es el LOB. No se presenta como objetivo de acuerdo.")
    if "TOTAL_YTD1" in pdv:
        pdv["Δ YTD €"]=pdv["TOTAL_YTD"]-pdv["TOTAL_YTD1"]
    if "TOTAL_OBJ" in pdv:
        pdv["Gap LOB €"]=(pdv["TOTAL_OBJ"]-pdv["TOTAL_YTD"]).clip(lower=0)
    showcols=[c for c in ["address","town","client","pos_id","TOTAL_YTD1","TOTAL_YTD","Δ YTD €","Gap LOB €"] if c in pdv]
    st.subheader("Prioridad de visitas")
    rank=pdv.sort_values(["Δ YTD €","Gap LOB €"],ascending=[True,False]) if "Δ YTD €" in pdv else pdv
    st.dataframe(rank[showcols],use_container_width=True,hide_index=True)
    if "Δ YTD €" in rank:
        chart=rank.head(12).copy()
        chart["PDV"]=chart["address"].astype(str)+" · "+chart["town"].astype(str)
        fig=px.bar(chart,x="Δ YTD €",y="PDV",orientation="h",title="Dónde se concentra la caída / crecimiento YTD")
        st.plotly_chart(fig,use_container_width=True)
    st.subheader("Lectura ejecutiva")
    if len(rank):
        worst=rank.head(min(4,len(rank)))
        names=", ".join(worst["address"].astype(str))
        st.error(f"Prioridad de recuperación: {names}.")
        st.write("Usa la caída YTD vs YTD-1 y el gap LOB como criterio para ordenar visitas. Después, en cada farmacia, la Ficha 2026 sustituye el objetivo LOB por el objetivo real del acuerdo.")
    st.stop()

# Individual
with st.sidebar:
    st.header("Cliente")
    q=st.text_input("Buscar cliente / CPV / dirección")
    opts=lob.copy()
    if q:
        nq=norm(q)
        mask=(opts["client"].map(norm).str.contains(nq,na=False) |
              opts["pos_id"].astype(str).map(norm).str.contains(nq,na=False) |
              opts["address"].map(norm).str.contains(nq,na=False))
        opts=opts[mask]
    labels=(opts["client"].astype(str)+" · "+opts["pos_id"].astype(str)+" · "+opts["address"].astype(str)).tolist()
    if not labels:
        st.warning("Sin coincidencias.")
        st.stop()
    sel=st.selectbox("Punto de venta",labels)
    idx=labels.index(sel)
    row=opts.iloc[idx]

    st.header("Documentos de la visita")
    ficha_files=st.file_uploader("Ficha cliente 2026 (PDF o capturas, varias)",type=["pdf","png","jpg","jpeg"],accept_multiple_files=True)
    veeva_files=st.file_uploader("Capturas Veeva (varias)",type=["png","jpg","jpeg"],accept_multiple_files=True)

equiv=equivalent_rows(lob,row)
current=equiv.iloc[-1] if len(equiv) else row
st.header(f"{current['client']} · {current['pos_id']}")
st.caption(f"{current['address']} · {current['town']} · {current['province']}")

if len(equiv)>1:
    st.info("Cambio de titular / CPV o duplicidad histórica detectada por ubicación.")
    st.dataframe(equiv[["client","pos_id","address","town"]],hide_index=True,use_container_width=True)

agr=parse_agreement(ficha_files)
vdf, veeva_raw=parse_veeva(veeva_files)
bdf=brand_snapshot(current)

# Main plan first
st.subheader("⚡ Plan de visita")
actions=agreement_plan(agr,bdf)+veeva_opportunities(vdf)
# Add economic recovery from LOB only as context, not agreement objective
if not actions:
    actions=[("DATOS","Carga Ficha 2026 y capturas Veeva para generar prioridades automáticas.","aviso")]

c1,c2,c3=st.columns(3)
obj=agr.get("objective_collective")
act=agr.get("actual_collective")
miss=agr.get("missing_collective")
c1.metric("Objetivo acuerdo",euro(obj) if obj else "Pendiente")
c2.metric("Actual acuerdo",euro(act) if act else "Pendiente")
c3.metric("Falta acuerdo",euro(miss) if miss is not None else "Pendiente")

for typ,msg,sev in actions[:7]:
    if sev in ("alta","aviso"):
        st.warning(f"**{typ}** · {msg}")
    elif sev=="oportunidad":
        st.info(f"**{typ}** · {msg}")
    else:
        st.success(f"**{typ}** · {msg}")

st.subheader("1 · Acuerdo 2026")
if obj:
    st.success("Objetivo leído de la Ficha 2026. El LOB no sustituye este objetivo.")
    if agr["brands"]:
        adf=pd.DataFrame(agr["brands"]).sort_values("Falta marca €",ascending=False)
        st.dataframe(adf,hide_index=True,use_container_width=True)
        fig=px.bar(adf,x="Falta marca €",y="Marca",orientation="h",title="Qué marca explica el gap del acuerdo")
        st.plotly_chart(fig,use_container_width=True)
else:
    st.warning("No he podido confirmar el objetivo del acuerdo en la Ficha 2026. La app no inventa ni usa el objetivo LOB en su lugar.")

st.subheader("2 · Contraste económico LOB")
st.dataframe(bdf,hide_index=True,use_container_width=True)
st.caption("LOB = seguimiento/contraste económico. No define el objetivo del acuerdo de la visita.")

st.subheader("3 · Veeva · unidades y gamas reales")
if vdf.empty:
    st.info("No hay datos Veeva confirmados en las capturas. No se inventan históricos de unidades.")
else:
    st.dataframe(vdf,hide_index=True,use_container_width=True)
    chart=vdf.copy()
    chart["Etiqueta"]=chart["Marca"]+" · "+chart["Gama"]
    fig=px.bar(chart,x="YTD uds",y="Etiqueta",orientation="h",title="Unidades YTD detectadas en Veeva")
    st.plotly_chart(fig,use_container_width=True)
    # Specific Ducray anticaida check
    dcc=vdf[(vdf["Marca"].map(norm)=="DUCRAY") & (vdf["Gama"].map(norm).str.contains("ANTICAIDA",na=False))]
    if dcc.empty:
        st.info("Ducray Anticaída: no aparece compra confirmada en las capturas cargadas. Si la vista Veeva incluye la gama DCC-CHUTE DE CHEVEUX con 0 YTD/TAM12M, se marcará como oportunidad real.")
    elif nnum(dcc.iloc[0]["YTD uds"])==0 and nnum(dcc.iloc[0]["TAM12M uds"])==0:
        st.success("OPORTUNIDAD · Ducray Anticaída: sin compra YTD ni TAM12M detectada. Pregunta qué necesita la farmacia para introducir la gama.")

st.subheader("4 · Acciones sell-out y condiciones vigentes")
texts=st.session_state["cycle_texts"]
if not texts:
    st.info("Carga la chuleta/campañas en Gestión de ciclo.")
else:
    focus_brand = None
    focus_gama = None
    if agr.get("brands"):
        adf=pd.DataFrame(agr["brands"]).sort_values("Falta marca €",ascending=False)
        if len(adf): focus_brand=adf.iloc[0]["Marca"]
    acts=relevant_actions(texts,focus_brand,focus_gama)
    if acts:
        for a in acts: st.write("• "+a)
    else:
        st.caption("No se han detectado automáticamente líneas de acción vinculadas al foco actual; revisa los documentos del ciclo.")

st.subheader("5 · Propuesta de pedido")
catalog=st.session_state["catalog"]
if catalog.empty:
    st.info("Carga tarifa/catálogo u hojas de pedido en Gestión de ciclo para construir una propuesta.")
else:
    brands=sorted([x for x in catalog["Marca"].dropna().astype(str).unique() if x and x!="nan"])
    sel_brand=st.selectbox("Marca para propuesta",brands if brands else [""])
    gamas=sorted(catalog[catalog["Marca"].map(norm)==norm(sel_brand)]["Gama"].dropna().astype(str).unique()) if sel_brand else []
    sel_gama=st.selectbox("Gama",gamas if gamas else [""])
    order=build_conservative_order(catalog,sel_brand,sel_gama,vdf)
    if order.empty:
        st.warning("No hay referencias estructuradas para esta selección.")
    else:
        edited=st.data_editor(order[["CN","Producto","PVL","Heroe","Novedad","Unidades","Importe","Motivo"]],
                              hide_index=True,use_container_width=True,
                              column_config={"Unidades":st.column_config.NumberColumn(min_value=0,step=1),
                                             "PVL":st.column_config.NumberColumn(format="%.2f €"),
                                             "Importe":st.column_config.NumberColumn(format="%.2f €")},
                              disabled=["CN","Producto","PVL","Heroe","Novedad","Importe","Motivo"])
        edited["Importe"]=pd.to_numeric(edited["Unidades"],errors="coerce").fillna(0)*pd.to_numeric(edited["PVL"],errors="coerce").fillna(0)
        total_uds=int(pd.to_numeric(edited["Unidades"],errors="coerce").fillna(0).sum())
        total_eur=float(edited["Importe"].sum())
        m1,m2=st.columns(2)
        m1.metric("Unidades pedido",total_uds)
        m2.metric("Pedido estimado",euro(total_eur))
        st.caption("La V2 usa una propuesta conservadora basada en Veeva cuando hay histórico. Evita pedidos desproporcionados y prioriza surtido, héroes y novedades.")

st.subheader("6 · Preguntas para la visita")
questions=[]
for typ,msg,sev in actions:
    if typ=="IMPLANTAR":
        target=msg.split(":")[0]
        questions.append(f"¿Qué necesitaría la farmacia para introducir {target}?")
    if typ=="RECUPERAR GAMA":
        target=msg.split(":")[0]
        questions.append(f"¿Qué está frenando la rotación de {target} y qué apoyo sell-out ayudaría?")
if agr.get("brands"):
    adf=pd.DataFrame(agr["brands"]).sort_values("Falta marca €",ascending=False)
    if len(adf):
        questions.append(f"¿Qué pedido podemos cerrar hoy para recuperar {adf.iloc[0]['Marca']} sin sobredimensionar stock?")
if not questions:
    questions=["Validar stock actual y prioridades del cliente antes de cerrar el pedido."]
for q in questions[:4]:
    st.write("• "+q)

with st.expander("Diagnóstico / texto OCR (para validar lecturas)"):
    st.caption("Este bloque existe para comprobar la lectura automática, no para preparar la visita.")
    if agr.get("raw_text"): st.text_area("Ficha 2026 · OCR",agr["raw_text"],height=180)
    if veeva_raw: st.text_area("Veeva · OCR",veeva_raw,height=180)
