
from pathlib import Path
import io, re, unicodedata, math, glob
import pandas as pd
import numpy as np
import streamlit as st
from PIL import Image, ImageOps, ImageEnhance
import plotly.express as px
from rapidfuzz import fuzz
from pypdf import PdfReader
import pytesseract

st.set_page_config(page_title="Smart Visit Planner · V2.1", layout="wide")

BASE = Path(__file__).parent

# =========================================================
# Helpers
# =========================================================
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
    s = str(v).strip().replace("€","").replace("%","").replace(" ","")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".","").replace(",",".")
        else:
            s = s.replace(",","")
    elif "," in s:
        right = s.split(",")[-1]
        s = s.replace(".","").replace(",",".") if len(right) <= 2 else s.replace(",","")
    elif "." in s:
        parts = s.split(".")
        if len(parts[-1]) == 3 and len(parts) <= 3:
            s = s.replace(".","")
    try:
        return float(s)
    except:
        return 0.0

def euro(v):
    try:
        return f"{float(v):,.0f} €".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "—"

def read_csv_any(path_or_file):
    for enc in ("utf-8-sig","utf-8","latin1"):
        try:
            if hasattr(path_or_file, "seek"): path_or_file.seek(0)
            return pd.read_csv(path_or_file, encoding=enc)
        except Exception:
            pass
    if hasattr(path_or_file, "seek"): path_or_file.seek(0)
    return pd.read_csv(path_or_file)

def read_table(path_or_file, name=None):
    fname = (name or getattr(path_or_file, "name", str(path_or_file))).lower()
    if fname.endswith(".csv"):
        return read_csv_any(path_or_file)
    if fname.endswith((".xlsx",".xls")):
        if hasattr(path_or_file, "seek"): path_or_file.seek(0)
        return pd.read_excel(path_or_file)
    return None

def clean_lob(df):
    if df is None or df.empty:
        return pd.DataFrame()
    d = df.copy()
    d.columns = [str(c).strip() for c in d.columns]
    lookup = {norm(c): c for c in d.columns}
    aliases = {
        "client":["client","cliente","nombre cliente"],
        "pos_id":["pos id","pos_id","cpv","codigo cliente","código cliente"],
        "address":["address","direccion","dirección"],
        "postal_code":["postal code","postal_code","cp","codigo postal","código postal"],
        "town":["town","poblacion","población"],
        "province":["province","provincia"],
        "group":["group","grupo","grupo compra","grupos compra","grup compra"]
    }
    for std, opts in aliases.items():
        if std not in d.columns:
            found = None
            for o in opts:
                if norm(o) in lookup:
                    found = lookup[norm(o)]; break
            d[std] = d[found] if found else ""
    for c in d.columns:
        uc = str(c).upper()
        if c != "pos_id" and any(k in uc for k in ["_OBJ","_YTD","YTD1","TOTAL_","FACT","OBJET"]):
            d[c] = d[c].map(nnum)
    d["pdv_key"] = d.apply(lambda r: pdv_key(r.get("address",""), r.get("postal_code",""), r.get("town","")), axis=1)
    return d

def pdv_key(address, cp="", town=""):
    a = norm(address)
    a = re.sub(r"\b(FARMACIA|FCIA|FCA|LOCAL|BAJO|BAJOS|PRAL|ENTLO)\b"," ",a)
    a = re.sub(r"\s+"," ",a).strip()
    return f"{a}|{norm(cp)}|{norm(town)}"

def equivalent_rows(df, row):
    if df.empty:
        return df
    key = row["pdv_key"]
    exact = df[df["pdv_key"] == key]
    if len(exact): return exact
    a1,cp1,t1 = (key.split("|")+["",""])[:3]
    scores=[]
    for k in df["pdv_key"]:
        a2,cp2,t2 = (k.split("|")+["",""])[:3]
        s = fuzz.token_set_ratio(a1,a2)
        if cp1 and cp2 and cp1==cp2: s+=8
        if t1 and t2 and t1==t2: s+=5
        scores.append(min(s,100))
    return df[pd.Series(scores,index=df.index)>=92]

# =========================================================
# Persistent cycle files from GitHub root
# =========================================================
def find_first(patterns):
    for pat in patterns:
        matches = sorted(BASE.glob(pat))
        if matches:
            return matches[0]
    return None

@st.cache_data(show_spinner=False)
def load_repo_cycle():
    result = {
        "lob": pd.DataFrame(),
        "compar_files": [],
        "compar": pd.DataFrame(),
        "catalog": pd.DataFrame(),
        "order_pdfs": [],
        "condition_pdfs": [],
        "sellout_files": []
    }

    lob_path = find_first(["lob_master.csv","LOB*.csv","LOB*.xlsx","lob*.xlsx"])
    if lob_path:
        result["lob"] = clean_lob(read_table(lob_path, lob_path.name))

    compar_paths = sorted(list(BASE.glob("COMPAR*.xlsx")) + list(BASE.glob("COMPAR*.xls")) + list(BASE.glob("COMPAR*.csv")))
    result["compar_files"] = [p.name for p in compar_paths]
    frames=[]
    for p in compar_paths:
        try:
            x=read_table(p,p.name)
            if x is not None and not x.empty:
                x=x.copy(); x["_source_file"]=p.name; frames.append(x)
        except: pass
    if frames:
        result["compar"] = pd.concat(frames, ignore_index=True, sort=False)

    cat_path = find_first(["product_catalog.csv","product_catalog.xlsx","*tarifa*.xlsx","*TARIFA*.xlsx"])
    if cat_path:
        try:
            result["catalog"] = read_table(cat_path,cat_path.name)
        except: pass

    result["order_pdfs"] = [p.name for p in sorted(BASE.glob("*Hoja*pedido*.pdf"))] + [p.name for p in sorted(BASE.glob("*hoja*pedido*.pdf"))]
    result["condition_pdfs"] = [p.name for p in sorted(BASE.glob("CHULETA*.pdf"))] + [p.name for p in sorted(BASE.glob("*CONDICIONES*.pdf"))]
    result["sellout_files"] = [p.name for p in sorted(BASE.glob("SELL_OUT*.xlsx"))] + [p.name for p in sorted(BASE.glob("SELL_OUT*.xls"))]

    return result

repo = load_repo_cycle()

if "lob" not in st.session_state:
    st.session_state["lob"] = repo["lob"]
if "compar" not in st.session_state:
    st.session_state["compar"] = repo["compar"]
if "compar_files" not in st.session_state:
    st.session_state["compar_files"] = repo["compar_files"]
if "catalog" not in st.session_state:
    st.session_state["catalog"] = repo["catalog"]
if "cycle_name" not in st.session_state:
    st.session_state["cycle_name"] = "Ciclo actual"

# =========================================================
# OCR
# =========================================================
def prep_image(img):
    img = ImageOps.grayscale(img)
    img = ImageEnhance.Contrast(img).enhance(1.7)
    if img.width < 1800:
        r = 1800/img.width
        img = img.resize((int(img.width*r), int(img.height*r)))
    return img

@st.cache_data(show_spinner=False)
def ocr_image(raw):
    img = prep_image(Image.open(io.BytesIO(raw)))
    try:
        return pytesseract.image_to_string(img, lang="spa", config="--psm 6")
    except:
        return pytesseract.image_to_string(img, config="--psm 6")

def extract_text(upload):
    if upload is None: return ""
    name = upload.name.lower()
    raw = upload.getvalue()
    if name.endswith(".pdf"):
        try:
            r=PdfReader(io.BytesIO(raw))
            return "\n".join((p.extract_text() or "") for p in r.pages)
        except:
            return ""
    if name.endswith((".png",".jpg",".jpeg",".webp")):
        return ocr_image(raw)
    return ""

def parse_agreement(files):
    # Robust-but-conservative parser for Evolución Pacto.
    txt = "\n".join(extract_text(f) for f in (files or []))
    lines=[re.sub(r"\s+"," ",l).strip() for l in txt.splitlines() if l.strip()]
    brand_rows=[]
    for brand in ["AVENE","DUCRAY","A-DERMA","KLORANE"]:
        for l in lines:
            if norm(l).startswith(brand):
                nums=[nnum(x) for x in re.findall(r"-?\d[\d\.,]*",l)]
                if len(nums)>=9:
                    brand_rows.append((brand,nums,l)); break
    out={"objective_collective":None,"actual_collective":None,"missing_collective":None,"brands":[],"raw":txt}
    objs=[]; acts=[]; gaps=[]
    for b,nums,l in brand_rows:
        objs.append(nums[3]); acts.append(nums[1]); gaps.append(nums[4])
        out["brands"].append({
            "Marca": b.replace("AVENE","Avène").title().replace("A-Derma","A-Derma"),
            "Referencia marca €": nums[5],
            "Actual marca €": nums[6],
            "Falta marca €": max(nums[8],0)
        })
    def modeish(vals):
        vals=[round(v,0) for v in vals if v>100]
        if not vals:return None
        s=pd.Series(vals); return float(s.value_counts().idxmax())
    out["objective_collective"]=modeish(objs)
    out["actual_collective"]=modeish(acts)
    out["missing_collective"]=modeish(gaps)
    return out

VEEVA_MAP = {
    ("AVENE","G029 XERACALM"):"Atopia / XeraCalm",
    ("AVENE","ASE ACNE"):"Acné / Cleanance",
    ("AVENE","AHY HYDRANCE"):"Hydrance",
    ("AVENE","ACZ CICALFATE"):"Cicalfate",
    ("AVENE","ASO SOLAIRES"):"Solar",
    ("DUCRAY","PEL ETATS PELLICULAIRES"):"Anticaspa",
    ("DUCRAY","DCC CHUTE DE CHEVEUX"):"Anticaída",
    ("DUCRAY","DSB PEAUX ACNEIQUES"):"Acné / Keracnyl",
    ("DUCRAY","DIN PEAUX ATOPIQUES"):"Atopia / Dexyane",
    ("A-DERMA","EXO EXOMEGA"):"Atopia / Exomega",
    ("PFD","EMO EMOLLIENT"):"Dexeryl",
}

def parse_veeva(files):
    rows=[]; alltxt=[]
    for f in files or []:
        txt=extract_text(f); alltxt.append(txt)
        current=None
        for raw in txt.splitlines():
            l=re.sub(r"\s+"," ",raw).strip(); nl=norm(l)
            if not nl: continue
            for b in ["AVENE","DUCRAY","A-DERMA","PFD","KLORANE","FURTERER"]:
                if re.search(rf"\b{re.escape(norm(b))}\b",nl) and len(nl)<90:
                    current=b; break
            if not current: continue
            for (b,code),friendly in VEEVA_MAP.items():
                if b==current and norm(code) in nl:
                    toks=re.findall(r"-?\d+(?:[\.,]\d+)?\s*%?",l)
                    vals=[nnum(x) for x in toks if "%" not in x]
                    y=t=None
                    if len(vals)>=2: y,t=vals[-2],vals[-1]
                    elif len(vals)==1: y=t=vals[0]
                    rows.append({
                        "Marca":"Dexeryl" if current=="PFD" else current.title().replace("A-Derma","A-Derma"),
                        "Gama":friendly,"YTD uds":y,"TAM12M uds":t,"Fuente":f.name
                    })
                    break
    if not rows:
        return pd.DataFrame(columns=["Marca","Gama","YTD uds","TAM12M uds","Fuente"]),"\n".join(alltxt)
    d=pd.DataFrame(rows)
    d["score"]=d[["YTD uds","TAM12M uds"]].fillna(0).sum(axis=1)
    d=d.sort_values("score",ascending=False).drop_duplicates(["Marca","Gama"]).drop(columns="score")
    return d,"\n".join(alltxt)

# =========================================================
# Economic snapshot
# =========================================================
BRANDS=[
    ("AVENE SIN SOLAR","Avène sin Solar"),
    ("AVENE SOLAR","Avène Solar"),
    ("DUCRAY","Ducray"),
    ("A-DERMA","A-Derma"),
    ("DEXERYL","Dexeryl"),
]
def brand_snapshot(row):
    rows=[]
    for key,label in BRANDS:
        rows.append({
            "Marca":label,
            "Objetivo LOB €":nnum(row.get(key+"_OBJ",0)),
            "YTD €":nnum(row.get(key+"_YTD",0)),
            "YTD-1 €":nnum(row.get(key+"_YTD1",0)),
        })
    d=pd.DataFrame(rows)
    d["Evolución %"]=np.where(d["YTD-1 €"]>0,(d["YTD €"]/d["YTD-1 €"]-1)*100,np.nan)
    d["Gap LOB €"]=(d["Objetivo LOB €"]-d["YTD €"]).clip(lower=0)
    return d

# =========================================================
# UI
# =========================================================
st.title("Smart Visit Planner · V2.1")
st.caption("Objetivo = acuerdo Ficha 2026 · LOB/COMPAR = contraste · Veeva = unidades · identidad = punto de venta físico")

with st.sidebar:
    st.header("Modo")
    mode=st.radio("Análisis",["Visita individual","Grupo / consolidado","Gestión de ciclo"])
    st.divider()
    st.caption(f"Ciclo activo: **{st.session_state['cycle_name']}**")

if mode=="Gestión de ciclo":
    st.header("Gestión de ciclo")
    st.success("Los archivos que ya están en GitHub se cargan automáticamente al abrir la app. No hace falta adjuntarlos cada vez.")
    st.caption("Los uploads de esta pantalla sirven para probar/activar un ciclo nuevo en la sesión. Cuando esté validado, súbelo a GitHub para dejarlo permanente.")

    cycle_name=st.text_input("Nombre del ciclo",st.session_state["cycle_name"])
    lob_up=st.file_uploader("LOB del ciclo (CSV/XLSX)",type=["csv","xlsx","xls"])
    compar_up=st.file_uploader("COMPAR / histórico económico (VARIOS CSV/XLSX)",type=["csv","xlsx","xls"],accept_multiple_files=True)
    catalog_up=st.file_uploader("Tarifa / catálogo estructurado (CSV/XLSX)",type=["csv","xlsx","xls"])
    order_files=st.file_uploader("Hojas de pedido del ciclo (PDF, varias)",type=["pdf"],accept_multiple_files=True)
    condition_files=st.file_uploader("Chuleta / condiciones / campañas sell-out (PDF, varias)",type=["pdf"],accept_multiple_files=True)

    if st.button("Validar y activar ciclo"):
        errors=[]
        if lob_up:
            try: new_lob=clean_lob(read_table(lob_up,lob_up.name))
            except Exception as e: errors.append(f"LOB: {e}"); new_lob=None
        else:
            new_lob=st.session_state["lob"]

        new_comp_frames=[]
        for f in (compar_up or []):
            try:
                x=read_table(f,f.name)
                if x is not None:
                    x=x.copy(); x["_source_file"]=f.name; new_comp_frames.append(x)
            except Exception as e:
                errors.append(f"COMPAR {f.name}: {e}")
        new_compar=pd.concat(new_comp_frames,ignore_index=True,sort=False) if new_comp_frames else st.session_state["compar"]

        if catalog_up:
            try: new_cat=read_table(catalog_up,catalog_up.name)
            except Exception as e: errors.append(f"Tarifa: {e}"); new_cat=None
        else:
            new_cat=st.session_state["catalog"]

        if errors:
            st.error("No se ha activado el ciclo:\n- "+"\n- ".join(errors))
        else:
            st.session_state["lob"]=new_lob
            st.session_state["compar"]=new_compar
            st.session_state["compar_files"]=[f.name for f in (compar_up or [])] or st.session_state.get("compar_files",[])
            st.session_state["catalog"]=new_cat
            st.session_state["cycle_name"]=cycle_name
            st.success("Ciclo activado para esta sesión.")

    st.subheader("Estado permanente detectado en GitHub")
    c1,c2,c3,c4=st.columns(4)
    c1.metric("LOB","OK" if not repo["lob"].empty else "Falta")
    c2.metric("COMPAR",f"{len(repo['compar_files'])} archivo(s)")
    c3.metric("Catálogo","OK" if repo["catalog"] is not None and not repo["catalog"].empty else "Falta")
    c4.metric("Hojas pedido",len(repo["order_pdfs"]))
    c5,c6=st.columns(2)
    c5.metric("Chuletas / condiciones",len(repo["condition_pdfs"]))
    c6.metric("Sell-out",len(repo["sellout_files"]))

    if repo["compar_files"]:
        st.write("**COMPAR cargados automáticamente:** "+", ".join(repo["compar_files"]))
    st.info("Sí: LOB, COMPAR y tarifa pueden ser Excel normales (.xlsx/.xls). COMPAR admite varios archivos.")
    st.stop()

lob=st.session_state["lob"]
if lob is None or lob.empty:
    st.error("No hay LOB cargado.")
    st.stop()

if mode=="Grupo / consolidado":
    st.header("Grupo / consolidado")
    groups=sorted([g for g in lob["group"].dropna().astype(str).unique() if norm(g) not in ("","NO GRUPO","NO GRUPOS")])
    if not groups:
        st.warning("El LOB no contiene grupos identificables.")
        st.stop()
    group=st.selectbox("Grupo",groups)
    g=lob[lob["group"].astype(str)==group].copy()

    sumcols=[c for c in ["TOTAL_YTD1","TOTAL_YTD","TOTAL_OBJ"] if c in g.columns]
    aggs={c:"sum" for c in sumcols}
    aggs.update({"client":lambda x:" / ".join(pd.unique(x.astype(str))),
                 "pos_id":lambda x:", ".join(pd.unique(x.astype(str))),
                 "address":"first","town":"first"})
    pdv=g.groupby("pdv_key",dropna=False).agg(aggs).reset_index()

    if "TOTAL_YTD" in pdv and "TOTAL_YTD1" in pdv:
        pdv["Δ YTD €"]=pdv["TOTAL_YTD"]-pdv["TOTAL_YTD1"]
    if "TOTAL_OBJ" in pdv and "TOTAL_YTD" in pdv:
        pdv["Gap LOB €"]=(pdv["TOTAL_OBJ"]-pdv["TOTAL_YTD"]).clip(lower=0)

    c1,c2,c3,c4=st.columns(4)
    ytd=pdv["TOTAL_YTD"].sum() if "TOTAL_YTD" in pdv else 0
    prev=pdv["TOTAL_YTD1"].sum() if "TOTAL_YTD1" in pdv else 0
    obj=pdv["TOTAL_OBJ"].sum() if "TOTAL_OBJ" in pdv else 0
    c1.metric("YTD grupo",euro(ytd))
    c2.metric("YTD-1 grupo",euro(prev),f"{((ytd/prev)-1)*100:+.1f}%" if prev else None)
    c3.metric("Objetivo LOB grupo*",euro(obj))
    c4.metric("Puntos de venta",len(pdv))
    st.caption("*Sin Fichas 2026 individuales, en grupo se utiliza el LOB como referencia operativa, no como objetivo de acuerdo.")

    rank=pdv.sort_values(["Δ YTD €","Gap LOB €"],ascending=[True,False]) if "Δ YTD €" in pdv else pdv
    st.subheader("Prioridad de visitas")
    cols=[c for c in ["address","town","client","pos_id","TOTAL_YTD1","TOTAL_YTD","Δ YTD €","Gap LOB €"] if c in rank.columns]
    st.dataframe(rank[cols],use_container_width=True,hide_index=True)
    if "Δ YTD €" in rank:
        chart=rank.head(15).copy()
        chart["PDV"]=chart["address"].astype(str)+" · "+chart["town"].astype(str)
        st.plotly_chart(px.bar(chart,x="Δ YTD €",y="PDV",orientation="h",title="Dónde se concentra la caída / crecimiento"),use_container_width=True)
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
        st.warning("Sin coincidencias."); st.stop()
    sel=st.selectbox("Punto de venta",labels)
    row=opts.iloc[labels.index(sel)]
    st.header("Documentos de la visita")
    ficha_files=st.file_uploader("Ficha cliente 2026 (PDF o capturas, varias)",type=["pdf","png","jpg","jpeg"],accept_multiple_files=True)
    veeva_files=st.file_uploader("Capturas Veeva (varias)",type=["png","jpg","jpeg"],accept_multiple_files=True)

eq=equivalent_rows(lob,row)
current=eq.iloc[-1] if len(eq) else row
st.header(f"{current['client']} · {current['pos_id']}")
st.caption(f"{current['address']} · {current['town']} · {current['province']}")

if len(eq)>1:
    st.info("Posible cambio de titular / CPV detectado por ubicación física. El histórico económico se consolida por punto de venta.")
    st.dataframe(eq[["client","pos_id","address","town"]],hide_index=True,use_container_width=True)

agreement=parse_agreement(ficha_files)
veeva,veeva_raw=parse_veeva(veeva_files)
bdf=brand_snapshot(current)

st.subheader("⚡ Plan de visita")
a1,a2,a3=st.columns(3)
a1.metric("Objetivo acuerdo",euro(agreement["objective_collective"]) if agreement["objective_collective"] else "Pendiente")
a2.metric("Actual acuerdo",euro(agreement["actual_collective"]) if agreement["actual_collective"] else "Pendiente")
a3.metric("Falta acuerdo",euro(agreement["missing_collective"]) if agreement["missing_collective"] is not None else "Pendiente")

if not agreement["objective_collective"]:
    st.warning("Objetivo de acuerdo no confirmado. La app NO lo sustituye por el objetivo LOB.")
else:
    st.success("Objetivo leído desde la Ficha 2026.")

if agreement["brands"]:
    adf=pd.DataFrame(agreement["brands"]).sort_values("Falta marca €",ascending=False)
    for _,r in adf.head(3).iterrows():
        if r["Falta marca €"]>0:
            st.warning(f"**RECUPERAR {r['Marca']}** · faltan {euro(r['Falta marca €'])} según la Ficha 2026.")

if not veeva.empty:
    for _,r in veeva.iterrows():
        y=nnum(r["YTD uds"]); t=nnum(r["TAM12M uds"])
        if y==0 and t==0:
            st.info(f"**OPORTUNIDAD DE IMPLANTACIÓN** · {r['Marca']} · {r['Gama']}: 0 YTD y 0 TAM12M.")
        elif t>0 and y<0.35*t:
            st.info(f"**REVISAR ROTACIÓN** · {r['Marca']} · {r['Gama']}: {int(y)} uds YTD vs {int(t)} TAM12M.")

st.subheader("1 · Acuerdo 2026")
if agreement["brands"]:
    adf=pd.DataFrame(agreement["brands"]).sort_values("Falta marca €",ascending=False)
    st.dataframe(adf,hide_index=True,use_container_width=True)
    st.plotly_chart(px.bar(adf,x="Falta marca €",y="Marca",orientation="h",title="Qué marca explica el gap del acuerdo"),use_container_width=True)
else:
    st.caption("Carga Ficha 2026 para leer objetivo global y por marca.")

st.subheader("2 · Contraste económico LOB")
st.dataframe(bdf,hide_index=True,use_container_width=True)
st.caption("LOB = seguimiento económico, no objetivo principal de la visita.")

st.subheader("3 · Veeva · unidades/gamas")
if veeva.empty:
    st.info("Sin datos Veeva confirmados en las capturas.")
else:
    st.dataframe(veeva,hide_index=True,use_container_width=True)
    vv=veeva.copy(); vv["Etiqueta"]=vv["Marca"]+" · "+vv["Gama"]
    st.plotly_chart(px.bar(vv,x="YTD uds",y="Etiqueta",orientation="h",title="Unidades YTD detectadas"),use_container_width=True)

st.subheader("4 · Ciclo comercial")
st.write(f"**Ciclo activo:** {st.session_state['cycle_name']}")
c1,c2,c3,c4=st.columns(4)
c1.metric("COMPAR persistentes",len(repo["compar_files"]))
c2.metric("Hojas de pedido",len(repo["order_pdfs"]))
c3.metric("Chuletas",len(repo["condition_pdfs"]))
c4.metric("Sell-out",len(repo["sellout_files"]))
st.caption("Estos archivos se leen desde GitHub automáticamente y no hay que subirlos en cada visita.")

with st.expander("Diagnóstico OCR"):
    if agreement["raw"]: st.text_area("Ficha 2026",agreement["raw"],height=180)
    if veeva_raw: st.text_area("Veeva",veeva_raw,height=180)
