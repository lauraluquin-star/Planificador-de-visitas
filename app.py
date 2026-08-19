
from pathlib import Path
from datetime import date
import io, re, unicodedata, math
import pandas as pd
import numpy as np
import streamlit as st
from PIL import Image, ImageOps, ImageEnhance
import plotly.graph_objects as go
from rapidfuzz import fuzz
from pypdf import PdfReader
import pytesseract

st.set_page_config(page_title="Smart Visit Planner · V2.4.1", page_icon="⚡", layout="wide")

BASE = Path(__file__).parent

# ============================================================
# Visual system
# ============================================================
NAVY="#17324D"; BLUE="#2F6FDD"; RED="#E85D5D"; AMBER="#F2B84B"; GREEN="#4FA36C"
PALE_BLUE="#EEF5FF"; PALE_RED="#FDECEC"; PALE_AMBER="#FFF7DF"; PALE_GREEN="#EAF7EF"; GREY="#6B7280"

st.markdown(f"""
<style>
.block-container{{padding-top:1.0rem;max-width:1480px}}
h1,h2,h3{{color:{NAVY}}}
[data-testid="stMetricValue"]{{color:{NAVY};font-weight:800}}
.card{{border:1px solid #E4E8EE;border-radius:16px;padding:16px 18px;background:white;height:100%}}
.card-red{{border-left:7px solid {RED};background:{PALE_RED}}}
.card-amber{{border-left:7px solid {AMBER};background:{PALE_AMBER}}}
.card-green{{border-left:7px solid {GREEN};background:{PALE_GREEN}}}
.card-blue{{border-left:7px solid {BLUE};background:{PALE_BLUE}}}
.kicker{{font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;font-weight:800;color:{GREY}}}
.big{{font-size:1.75rem;font-weight:900;color:{NAVY};line-height:1.12;margin-top:4px}}
.small{{font-size:.82rem;color:{GREY};margin-top:4px}}
.action-title{{font-weight:900;color:{NAVY};font-size:1.05rem}}
.action-text{{font-size:.94rem;margin-top:4px}}
.section-title{{font-size:1.28rem;font-weight:900;color:{NAVY};margin-top:1.1rem;margin-bottom:.4rem}}
.badge{{display:inline-block;border-radius:999px;padding:4px 9px;font-size:.72rem;font-weight:900}}
.badge-red{{background:{PALE_RED};color:#A62B2B}} .badge-amber{{background:{PALE_AMBER};color:#8A5B00}}
.badge-green{{background:{PALE_GREEN};color:#17633F}} .badge-blue{{background:{PALE_BLUE};color:#1E5BB8}}
@media(max-width:800px){{
 .big{{font-size:1.45rem}}
 .block-container{{padding-left:.55rem;padding-right:.55rem}}
}}
</style>
""", unsafe_allow_html=True)

# ============================================================
# Generic helpers
# ============================================================
def norm(s):
    s="" if s is None or (isinstance(s,float) and pd.isna(s)) else str(s)
    s="".join(c for c in unicodedata.normalize("NFKD",s) if not unicodedata.combining(c))
    return re.sub(r"[^A-Z0-9]+"," ",s.upper()).strip()

def parse_num(v):
    if v is None or (isinstance(v,float) and pd.isna(v)): return 0.0
    if isinstance(v,(int,float,np.number)): return float(v)
    s=str(v).strip().replace("€","").replace("%","").replace(" ","").replace("$","5")
    s=s.strip("“”«»©=")
    if re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+",s):
        return float(s.replace(".",""))
    if re.fullmatch(r"-?\d{1,3}(?:,\d{3})+",s):
        return float(s.replace(",",""))
    if "," in s and "." not in s:
        s=s.replace(",",".")
    try:return float(s)
    except:return 0.0

def euro(v):
    try:return f"{float(v):,.0f} €".replace(",","X").replace(".",",").replace("X",".")
    except:return "—"

def pct(v):
    try:return f"{float(v):.0f}%"
    except:return "—"

def status_from_ratio(ratio, expected=None):
    if ratio is None or not np.isfinite(ratio): return "amber"
    if expected is None: expected=0.67
    delta=ratio-expected
    if delta < -0.10:return "red"
    if delta < -0.03:return "amber"
    return "green"

def pdv_key(address,cp="",town=""):
    a=norm(address)
    a=re.sub(r"\b(FARMACIA|FCIA|FCA|LOCAL|BAJOS|BAJO|PRAL|ENTLO)\b"," ",a)
    a=re.sub(r"\s+"," ",a).strip()
    return f"{a}|{norm(cp)}|{norm(town)}"

def read_csv_strings(path_or_file):
    for enc in ("utf-8-sig","utf-8","latin1"):
        try:
            if hasattr(path_or_file,"seek"): path_or_file.seek(0)
            return pd.read_csv(path_or_file,encoding=enc,dtype=str)
        except: pass
    if hasattr(path_or_file,"seek"): path_or_file.seek(0)
    return pd.read_csv(path_or_file,dtype=str)

def read_table(path_or_file,name=None,strings=False):
    fname=(name or getattr(path_or_file,"name",str(path_or_file))).lower()
    if fname.endswith(".csv"):
        return read_csv_strings(path_or_file) if strings else pd.read_csv(path_or_file)
    if fname.endswith((".xlsx",".xls")):
        if hasattr(path_or_file,"seek"): path_or_file.seek(0)
        return pd.read_excel(path_or_file,dtype=str if strings else None)
    return None

def clean_lob(df):
    if df is None or df.empty:return pd.DataFrame()
    d=df.copy()
    d.columns=[str(c).strip() for c in d.columns]
    lookup={norm(c):c for c in d.columns}
    aliases={
      "client":["client","cliente","nombre cliente"],
      "pos_id":["pos_id","pos id","cpv","codigo cliente","código cliente"],
      "address":["address","direccion","dirección"],
      "postal_code":["postal_code","postal code","cp","codigo postal","código postal"],
      "town":["town","poblacion","población"],
      "province":["province","provincia"],
      "group":["group","grupo","grupo compra","grupos compra","grup compra"],
      "coach":["coach","delegado","coach nombre"]
    }
    for std,opts in aliases.items():
        if std not in d.columns:
            found=next((lookup[norm(o)] for o in opts if norm(o) in lookup),None)
            d[std]=d[found] if found else ""
    numeric=[]
    for c in d.columns:
        uc=str(c).upper()
        if c!="pos_id" and any(k in uc for k in ["TOTAL_","_2025","_OBJ","_YTD","YTD1"]):
            numeric.append(c)
    for c in numeric:d[c]=d[c].map(parse_num)
    d["pdv_key"]=d.apply(lambda r:pdv_key(r.get("address",""),r.get("postal_code",""),r.get("town","")),axis=1)
    return d

def equivalent_rows(df,row):
    key=row["pdv_key"]
    exact=df[df["pdv_key"]==key]
    if len(exact):return exact
    a1,cp1,t1=(key.split("|")+["",""])[:3]
    scores=[]
    for k in df["pdv_key"]:
        a2,cp2,t2=(k.split("|")+["",""])[:3]
        s=fuzz.token_set_ratio(a1,a2)
        if cp1 and cp2 and cp1==cp2:s+=8
        if t1 and t2 and t1==t2:s+=5
        scores.append(min(s,100))
    return df[pd.Series(scores,index=df.index)>=92]

# ============================================================
# Persistent cycle
# ============================================================
@st.cache_data(show_spinner=False)
def repo_cycle():
    result={"lob":pd.DataFrame(),"compar":pd.DataFrame(),"compar_files":[],
            "catalog":pd.DataFrame(),"order_pdfs":[],"condition_pdfs":[],"sellout_files":[]}
    lob_paths=sorted(list(BASE.glob("lob_master.csv"))+list(BASE.glob("LOB*.csv"))+list(BASE.glob("LOB*.xlsx")))
    if lob_paths:
        result["lob"]=clean_lob(read_table(lob_paths[0],lob_paths[0].name,strings=True))

    cps=sorted(list(BASE.glob("COMPAR*.xlsx"))+list(BASE.glob("COMPAR*.xls"))+list(BASE.glob("COMPAR*.csv")))
    frames=[]
    for p in cps:
        try:
            x=read_table(p,p.name,strings=True)
            if x is not None and not x.empty:
                x=x.copy();x["_source_file"]=p.name;frames.append(x)
        except:pass
    result["compar_files"]=[p.name for p in cps]
    if frames:result["compar"]=pd.concat(frames,ignore_index=True,sort=False)

    cat=BASE/"product_catalog.csv"
    if cat.exists():
        try:result["catalog"]=pd.read_csv(cat,dtype={"cn":str})
        except:pass

    result["order_pdfs"]=[p.name for p in sorted(BASE.glob("*Hoja*pedido*.pdf"))]+[p.name for p in sorted(BASE.glob("*HOJA*PEDIDO*.pdf"))]
    result["condition_pdfs"]=[p.name for p in sorted(BASE.glob("CHULETA*.pdf"))]
    result["sellout_files"]=[p.name for p in sorted(BASE.glob("SELL_OUT*.xlsx"))]+[p.name for p in sorted(BASE.glob("SELL_OUT*.xls"))]
    return result

repo=repo_cycle()
if "lob" not in st.session_state:st.session_state["lob"]=repo["lob"]
if "compar" not in st.session_state:st.session_state["compar"]=repo["compar"]
if "catalog" not in st.session_state:st.session_state["catalog"]=repo["catalog"]
if "cycle_name" not in st.session_state:st.session_state["cycle_name"]="Ciclo actual"

# ============================================================
# OCR tuned to the two known layouts
# ============================================================
def prep_image(raw):
    img=Image.open(io.BytesIO(raw)).convert("RGB")
    if img.width<1800:
        scale=1800/img.width
        img=img.resize((int(img.width*scale),int(img.height*scale)))
    gray=ImageOps.grayscale(img)
    return ImageEnhance.Contrast(gray).enhance(1.45)

@st.cache_data(show_spinner=False)
def ocr_bytes(raw):
    img=prep_image(raw)
    try:return pytesseract.image_to_string(img,lang="spa",config="--psm 6")
    except:return pytesseract.image_to_string(img,config="--psm 6")

def upload_text(upload):
    if upload is None:return ""
    name=upload.name.lower()
    if name.endswith(".pdf"):
        try:
            r=PdfReader(io.BytesIO(upload.getvalue()))
            txt="\n".join((p.extract_text() or "") for p in r.pages)
            if len(txt.strip())>100:return txt
        except:pass
        return ""
    return ocr_bytes(upload.getvalue())

# ---------------- Ficha 2026 ----------------
FIN_PATTERNS={
 "AVENE":r"^(?:AVENE\s*SIN\s*SOL(?:AR)?|AVENESINSOL(?:AR)?)[^\n]*",
 "DUCRAY":r"^DUCRAY[^\n]*",
 "A-DERMA":r"^A-DERMA[^\n]*",
 "DEXERYL":r"^DEXERYL[^\n]*",
 "KLORANE":r"^KLORANE[^\n]*"
}

def ficha_financial(text):
    out={}
    for brand,pat in FIN_PATTERNS.items():
        m=re.search(pat,text,re.I|re.M)
        if not m:continue
        vals=[parse_num(x) for x in re.findall(r"-?[\d][\d\.,]*\s*%?",m.group(0))]
        if len(vals)>=3:
            out[brand]={"Fact año anterior":vals[0],"YTD anterior":vals[1],"YTD actual":vals[2],
                        "Evolución %":vals[3] if len(vals)>=4 else np.nan}
    return out

def _agreement_candidates(text):
    candidates=[]
    for m in re.finditer(r"\b(?:AVENE|DUCRAY|A-DERMA|DEXERYL|KLORANE)\b",text,re.I):
        seg=text[m.start():m.start()+190].replace("\n"," ")
        vals=[parse_num(x) for x in re.findall(r"[-−]?[\$\d][\d\.,]*\s*%?",seg)]
        for s in range(max(0,len(vals)-8)):
            a=vals[s:s+9]
            if len(a)<9:continue
            # prev colectivo, actual colectivo, evol, obj colectivo, falta colectivo,
            # prev marca, actual marca, evol marca, falta marca
            if a[0]>300 and a[1]>200 and a[3]>300 and a[5]>=0 and a[6]>=0:
                if abs((a[3]-a[1])-a[4])<150:
                    candidates.append(a)
    # unique
    seen=set();out=[]
    for a in candidates:
        k=tuple(round(x,2) for x in a)
        if k not in seen:out.append(a);seen.add(k)
    return out

def parse_ficha(files):
    text="\n".join(upload_text(f) for f in (files or []))
    fin=ficha_financial(text)
    refs={b:v["Fact año anterior"] for b,v in fin.items()}
    rows=[]
    used=set()
    for a in _agreement_candidates(text):
        if not refs:break
        b=min(refs,key=lambda k:abs(refs[k]-a[5]))
        tolerance=max(12,refs[b]*.025)
        if abs(refs[b]-a[5])<=tolerance and b not in used:
            rows.append({
              "BrandKey":b,
              "Marca":{"AVENE":"Avène","DUCRAY":"Ducray","A-DERMA":"A-Derma","DEXERYL":"Dexeryl","KLORANE":"Klorane"}[b],
              "Obj. colectivo €":a[3],
              "Actual colectivo €":a[1],
              "Referencia marca €":a[5],
              "Actual marca €":a[6],
              "Falta marca €":max(a[5]-a[6],0)
            });used.add(b)
    adf=pd.DataFrame(rows)
    # El objetivo colectivo es común a las filas de Evolución Pacto. Avène debe conservarse
    # siempre que esté presente: es la marca principal y puede contener el mayor gap.
    main=adf.copy() if not adf.empty else pd.DataFrame()
    objective=actual=gap=None
    if not main.empty:
        objective=float(main["Obj. colectivo €"].mode().iloc[0])
        actual=float(main["Actual colectivo €"].mode().iloc[0])
        gap=max(objective-actual,0)

    # identity
    ident={}
    m=re.search(r"CLIENTE\s*:\s*(.*?)\s+PROVINCIA\s*:",text,re.I)
    if m:ident["client"]=re.sub(r"\s+"," ",m.group(1)).strip()
    m=re.search(r"TELF\s*:\s*(\d+)",text,re.I)
    if m:ident["phone"]=m.group(1)
    m=re.search(r"DIRECCI[ÓO]N\s*:\s*([^\n]+)",text,re.I)
    if m:ident["address"]=m.group(1).strip()
    m=re.search(r"\b(C\d{5,7})\b",text,re.I)
    if m:ident["cpv"]=m.group(1).upper()

    # solar adelantada
    soladv=None
    m=re.search(r"SOLAR\s+ADELANTADA\s*[:\-]?\s*([\d\.,]+)",text,re.I)
    if m:soladv=parse_num(m.group(1))

    return {"text":text,"financial":fin,"agreement":adf,"objective":objective,"actual":actual,"gap":gap,
            "identity":ident,"solar_adelantada":soladv}

# ---------------- Veeva ----------------
CODE_MAP={
 "G039 TOLERANCE HYDRA 10":("AVENE","Tolérance Hydra 10"),
 "ASO SOLAIRES":("AVENE","Solar"),
 "AAR SOINS ANTI ROUGEURS":("AVENE","Antirrojeces"),
 "ASH HOMME":("AVENE","Hombre"),
 "ACO CORRECTEURS DU TEINT":("AVENE","Correctores"),
 "AHY HYDRANCE":("AVENE","Hidratación / Hydrance"),
 "G034 DERMABSOLU":("AVENE","Antiedad / DermAbsolu"),
 "G036 HYALURON ACTIV":("AVENE","Antiedad / Hyaluron Activ"),
 "APH TOLERANCE":("AVENE","Tolérance"),
 "G029 XERACALM":("AVENE","Atopia / XeraCalm"),
 "ASC SOINS CORPORELS":("AVENE","Corporal"),
 "ACZ CICALFATE":("AVENE","Cicalfate"),
 "ASS SOINS ESSENTIELS":("AVENE","Esenciales"),
 "G038 AOXITIVE":("AVENE","Antiedad / A-Oxitive"),
 "ASE ACNE":("AVENE","Acné / Cleanance"),
 "G031 COLD CREAM":("AVENE","Cold Cream"),
 "PEL ETATS PELLICULAIRES":("DUCRAY","Anticaspa"),
 "DIN PEAUX ATOPIQUES":("DUCRAY","Atopia / Dexyane"),
 "CCS PRURIT":("DUCRAY","Prurito"),
 "DCG AP CAPILLAIRES":("DUCRAY","AP Capilares"), # NO es Anticaída
 "DCC CHUTE DE CHEVEUX":("DUCRAY","Anticaída"),
 "DSB PEAUX ACNEIQUES":("DUCRAY","Acné / Keracnyl"),
 "CVG CHEVEUX GRAS":("DUCRAY","Cabello graso"),
 "UGF CHEVEUX DELICATS":("DUCRAY","Cabello delicado"),
 "EMO EMOLLIENT":("DEXERYL","Dexeryl"),
 "G058 CYTELIUM":("A-DERMA","Cytelium"),
 "EXO EXOMEGA":("A-DERMA","Atopia / Exomega"),
 "G057 DERMALIBOUR":("A-DERMA","Dermalibour+"),
 "SOL SOLAIRES":("A-DERMA","Solar"),
 "EPI EPITHELIALE":("A-DERMA","Epitheliale"),
 "SLA LES INDISPENSABLES":("A-DERMA","Indispensables")
}

def infer_product_category(name,current=None):
    u=norm(name)
    if current:return current
    if "HYALURON" in u or "HAP " in (" "+u):return ("AVENE","Antiedad / Hyaluron Activ")
    if "HYDR" in u:return ("AVENE","Hidratación / Hydrance")
    if "CICALFATE" in u:return ("AVENE","Cicalfate")
    if "CLEANANCE" in u or "COMEDOMED" in u:return ("AVENE","Acné / Cleanance")
    if "KELUAL" in u or "SQUANORM" in u:return ("DUCRAY","Anticaspa")
    if "ANAPHASE" in u or "ANACAPS" in u or "NEOPTIDE" in u:return ("DUCRAY","Anticaída")
    if "EXOMEGA" in u:return ("A-DERMA","Atopia / Exomega")
    if "DEXERYL" in u:return ("DEXERYL","Dexeryl")
    return None

def parse_veeva(files):
    catrows=[];prows=[];texts=[]
    for f in files or []:
        txt=upload_text(f);texts.append(txt);current=None
        for raw in txt.splitlines():
            line=re.sub(r"\s+"," ",raw).strip()
            if not line:continue
            nl=norm(line)
            match=None
            for code,(brand,cat) in CODE_MAP.items():
                if code in nl:
                    match=(brand,cat);break
            if match:
                current=match
                toks=re.findall(r"-?\d+(?:[\.,]\d+)?\s*%?",line)
                vals=[parse_num(t) for t in toks if "%" not in t]
                if len(vals)>=2:
                    catrows.append({"Marca":match[0],"Gama":match[1],"YTD uds":vals[-2],"TAM12M uds":vals[-1],"Fuente":f.name})
                continue

            # Product detail: only when line looks like a product + numeric tail
            if re.search(r"[A-Za-zÁÉÍÓÚÜÑ].{5,}",line) and re.search(r"\d",line):
                if any(x in nl for x in ["MIERCOLES","CLIENTES","PESO YTD","VALOR NETO","CUSTOMER CARD","CRONOLOGIA","DESCRIPCION GENERAL"]):
                    continue
                inferred=infer_product_category(line,current)
                if not inferred:continue
                toks=re.findall(r"-?\d+(?:[\.,]\d+)?\s*%?",line)
                vals=[parse_num(t) for t in toks if "%" not in t]
                if len(vals)>=1:
                    ytd=vals[-2] if len(vals)>=2 else 0
                    tam=vals[-1]
                    name=re.sub(r"\s+-?\d+(?:[\.,]\d+)?(?:\s+-?\d+(?:[\.,]\d+)?)*\s*$","",line).strip()
                    if len(name)>5:
                        prows.append({"Marca":inferred[0],"Gama":inferred[1],"Producto Veeva":name,
                                      "YTD uds":ytd,"TAM12M uds":tam,"Fuente":f.name})
    cats=pd.DataFrame(catrows)
    if not cats.empty:
        cats["score"]=cats[["YTD uds","TAM12M uds"]].fillna(0).sum(axis=1)
        cats=cats.sort_values("score",ascending=False).drop_duplicates(["Marca","Gama"]).drop(columns="score")
    else:cats=pd.DataFrame(columns=["Marca","Gama","YTD uds","TAM12M uds","Fuente"])
    prods=pd.DataFrame(prows)
    if not prods.empty:
        prods=prods.drop_duplicates(["Marca","Gama","Producto Veeva"],keep="first")
    else:prods=pd.DataFrame(columns=["Marca","Gama","Producto Veeva","YTD uds","TAM12M uds","Fuente"])
    return cats,prods,"\n".join(texts)

# ============================================================
# Business logic
# ============================================================
LOB_KEYS=[("AVENE SIN SOLAR","Avène sin Solar"),("AVENE SOLAR","Avène Solar"),("DUCRAY","Ducray"),("A-DERMA","A-Derma"),("DEXERYL","Dexeryl")]
def brand_lob(row):
    rows=[]
    for key,label in LOB_KEYS:
        obj=parse_num(row.get(key+"_OBJ",0));y=parse_num(row.get(key+"_YTD",0));prev=parse_num(row.get(key+"_YTD1",0))
        rows.append({"Marca":label,"Objetivo LOB €":obj,"YTD €":y,"YTD-1 €":prev,
                     "Evolución %":((y/prev)-1)*100 if prev else np.nan,"Gap LOB €":max(obj-y,0)})
    return pd.DataFrame(rows)

def brand_key_from_label(s):
    u=norm(s)
    if "DUCRAY" in u:return "DUCRAY"
    if "A DERMA" in u:return "A-DERMA"
    if "DEXERYL" in u:return "DEXERYL"
    if "KLORANE" in u:return "KLORANE"
    return "AVENE"

def category_family(g):
    u=norm(g)
    if "SOLAR" in u:return "Solar"
    if "CICALFATE" in u:return "Cicalfate"
    if "CLEANANCE" in u:return "Acné / Cleanance"
    if "KERACNYL" in u:return "Acné / Keracnyl"
    if "ANTICASPA" in u:return "Anticaspa"
    if "ANTICAIDA" in u:return "Anticaiguda"
    if "EXOMEGA" in u:return "Atopia"
    if "XERACALM" in u:return "Atopia"
    if "HYDRANCE" in u:return "Hidratació / Hydrance"
    if "ANTIEDAD" in u or "HYALURON" in u or "DERMABSOLU" in u or "AOXITIVE" in u:return "Antiedat"
    if "DEXERYL" in u:return "Dexeryl"
    return g

def opportunity_and_focus(ficha,cats,current_month):
    actions=[]
    agr=ficha["agreement"]
    if ficha["objective"]:
        actions.append({"sev":"blue","title":"ACUERDO","text":f"Faltan {euro(ficha['gap'])} para el objetivo principal del acuerdo."})
    else:
        actions.append({"sev":"amber","title":"ACUERDO","text":"Objetivo no confirmado en la Ficha 2026. No se sustituye por el LOB."})

    # Prioridades: gaps reales de TODAS las marcas, ordenados por importe.
    # Un gap pequeño (p.ej. Ducray 20 €) no desplaza a Avène/Klorane/Dexeryl.
    if not agr.empty:
        for _,r in agr[agr["Falta marca €"]>0].sort_values("Falta marca €",ascending=False).iterrows():
            gapm=float(r["Falta marca €"])
            sev="red" if gapm>=1000 else "amber"
            actions.append({"sev":sev,"title":f"RECUPERAR {r['Marca'].upper()}",
                            "text":f"Gap de marca: {euro(gapm)}. Priorizar cierre del acuerdo con las palancas y pedido adecuados."})
    # 0/0 significa SIN ACTIVIDAD, no oportunidad automática.
    # Las oportunidades comerciales requieren evidencia adicional del ciclo/campaña.
    # La rotación se analiza en el bloque Veeva; no llena el Plan Express con tarjetas TAM12M.
    if ficha.get("solar_adelantada") and current_month>=10:
        actions.append({"sev":"green","title":"PALANCA DE CIERRE",
                        "text":f"Solar adelantada disponible: {euro(ficha['solar_adelantada'])}. Puede ayudar al cierre anual; no se usa para calcular el rappel Solar."})
    return actions

def load_sellout_hits(cpv,client):
    hits=[]
    for p in sorted(list(BASE.glob("SELL_OUT*.xlsx"))+list(BASE.glob("SELL_OUT*.xls"))):
        try:
            xls=pd.ExcelFile(p)
            for sh in xls.sheet_names:
                d=pd.read_excel(p,sheet_name=sh,header=None,dtype=str)
                joined=d.fillna("").astype(str).agg(" | ".join,axis=1)
                mask=joined.str.contains(str(cpv),case=False,na=False,regex=False)
                if client:
                    mask=mask|joined.str.contains(str(client),case=False,na=False,regex=False)
                if mask.any():
                    hits.append({"Archivo":p.name,"Hoja":sh})
                    break
        except:pass
    return pd.DataFrame(hits).drop_duplicates() if hits else pd.DataFrame(columns=["Archivo","Hoja"])

def catalog_normalized():
    d=st.session_state.get("catalog",pd.DataFrame()).copy()
    if d.empty:return d
    cmap={norm(c):c for c in d.columns}
    def col(opts):
        c=next((cmap[norm(o)] for o in opts if norm(o) in cmap),None)
        return d[c] if c else pd.Series([""]*len(d),index=d.index)
    out=pd.DataFrame({
      "Categoria":col(["category","categoria","categoría"]),
      "Marca":col(["brand","marca"]),
      "CN":col(["cn","codigo nacional","código nacional"]).astype(str).str.replace(r"\.0$","",regex=True),
      "Producto":col(["description","producto","producte"]),
      "Formato":col(["format","formato"]),
      "PVL":col(["pvl","precio","tarifa"]).map(parse_num),
      "Tipo":col(["order_type","tipo"]),
      "Heroe":col(["hero","heroe","héroe"]).astype(str).str.upper().isin(["TRUE","1","SI","SÍ"]),
      "Novedad":col(["novelty","novedad"]).astype(str).str.upper().isin(["TRUE","1","SI","SÍ"])
    })
    return out

def matching_catalog(cat,brand,gama):
    if cat.empty:return cat
    fam=category_family(gama)
    bnorm=norm(brand)
    q=cat[cat["Marca"].map(norm).str.contains(bnorm,na=False)]
    # Dexeryl brand may already be exact
    if fam=="Atopia":
        if bnorm=="AVENE":q=q[q["Categoria"].map(norm).str.contains("ATOPIA",na=False)]
        elif bnorm=="A DERMA":q=q[q["Categoria"].map(norm).str.contains("ATOPIA",na=False)]
        else:q=q[q["Categoria"].map(norm).str.contains("ATOPIA",na=False)]
    else:
        q=q[q["Categoria"].map(norm).str.contains(norm(fam),na=False)]
    return q.copy()

def build_proposal(ficha,cats,prods):
    cat=catalog_normalized()
    if cat.empty:return pd.DataFrame(),[]
    months_remaining=max(1,12-date.today().month)
    agr=ficha["agreement"]
    brand_gap={}
    if not agr.empty:
        brand_gap={r["BrandKey"]:r["Falta marca €"] for _,r in agr.iterrows()}
    # Prioritize categories of brands with agreement gap; otherwise category history
    candidates=[]
    for _,r in cats.iterrows():
        b=r["Marca"];g=r["Gama"];y=parse_num(r["YTD uds"]);t=parse_num(r["TAM12M uds"])
        bkey=brand_key_from_label(b)
        gap=brand_gap.get(bkey,0)
        hist_remaining=max(t-y,0)
        # score: agreement gap + remaining historical seasonality
        score=(gap/100)+hist_remaining
        if y==0 and t==0 and g=="Anticaída":score+=100
        candidates.append((score,b,g,y,t,gap))
    candidates=sorted(candidates,reverse=True)[:5]

    rows=[];notes=[]
    for score,b,g,y,t,gap in candidates:
        pq=matching_catalog(cat,b,g)
        if pq.empty:continue
        hist_remaining=max(t-y,0)
        if y==0 and t==0:
            total_target=6
            reason="Implantación"
        else:
            monthly=hist_remaining/max(months_remaining,1)
            total_target=int(min(24,max(4,round(monthly))))
            reason="Reposición / ritmo histórico"
        # solar should be conservative unless we're in campaign/advance window
        if category_family(g)=="Solar" and date.today().month<10:
            total_target=min(total_target,12)
        # create all references visibly, allocating small quantities
        pq=pq.copy()
        pq["_rank"]=pq["Novedad"].astype(int)*4+pq["Heroe"].astype(int)*3+(pq["PVL"]>0).astype(int)
        pq=pq.sort_values(["_rank","Producto"],ascending=[False,True])
        units=[0]*len(pq)
        # at least 1 to hero/new; then fill round-robin up to 4 each
        for i,(_,pr) in enumerate(pq.iterrows()):
            if pr["Heroe"] or pr["Novedad"]:
                units[i]=1
        i=0
        while sum(units)<total_target and len(units):
            j=i%len(units)
            if units[j]<4:units[j]+=1
            i+=1
            if all(u>=4 for u in units):break

        # product-level Veeva can reduce/boost line units
        subp=prods[(prods["Marca"].map(norm)==norm(b)) & (prods["Gama"].map(norm)==norm(g))]
        for (idx,pr),u in zip(pq.iterrows(),units):
            prod_reason=reason
            # if product appears in Veeva and TAM12M=0, avoid replenishment unless novelty
            if not subp.empty:
                matches=subp[subp["Producto Veeva"].map(norm).apply(lambda x:fuzz.token_set_ratio(x,norm(pr["Producto"]))>=70)]
                if len(matches):
                    vr=matches.iloc[0]
                    rem=max(parse_num(vr["TAM12M uds"])-parse_num(vr["YTD uds"]),0)
                    if rem==0 and not pr["Novedad"]:u=0
                    elif rem>0:u=max(u,min(3,max(1,round(rem/max(months_remaining,1)))))
                    prod_reason=f"Histórico SKU: {int(parse_num(vr['YTD uds']))}/{int(parse_num(vr['TAM12M uds']))}"
            rows.append({"Prioridad":"ALTA" if gap>1000 else "MEDIA","Marca":b,"Gama":g,"CN":pr["CN"],
                         "Producto":pr["Producto"],"Formato":pr["Formato"],"Héroe":bool(pr["Heroe"]),
                         "Novedad":bool(pr["Novedad"]),"Unidades":int(u),"PVL":pr["PVL"],"Motivo":prod_reason})
        notes.append(f"{b} · {g}: propuesta base {total_target} uds; YTD {int(y)} / TAM12M {int(t)}.")
    if not rows:return pd.DataFrame(),notes
    out=pd.DataFrame(rows)
    out["Importe"]=out["Unidades"]*out["PVL"]
    return out,notes

# ============================================================
# Rendering helpers
# ============================================================
def action_card(sev,title,text):
    st.markdown(f"<div class='card card-{sev}'><div class='action-title'>{title}</div><div class='action-text'>{text}</div></div>",unsafe_allow_html=True)

def agreement_bar(df):
    if df is None or df.empty:return
    q=df.copy()
    q["ratio"]=np.where(q["Referencia marca €"]>0,q["Actual marca €"]/q["Referencia marca €"],0)
    fig=go.Figure()
    fig.add_trace(go.Bar(y=q["Marca"],x=q["Referencia marca €"],orientation="h",name="Referencia",marker_color="#DCE4EC"))
    fig.add_trace(go.Bar(y=q["Marca"],x=np.minimum(q["Actual marca €"],q["Referencia marca €"]),orientation="h",name="Actual",marker_color=BLUE))
    fig.update_layout(barmode="overlay",height=260,margin=dict(l=10,r=10,t=25,b=10),legend_orientation="h",
                      xaxis_title="€",yaxis_title="")
    st.plotly_chart(fig,use_container_width=True)

def category_chart(cats):
    if cats.empty:return
    q=cats.copy()
    q["Resto TAM12M"]=np.maximum(q["TAM12M uds"]-q["YTD uds"],0)
    q=q.sort_values("Resto TAM12M",ascending=True).tail(10)
    fig=go.Figure()
    fig.add_trace(go.Bar(y=q["Marca"]+" · "+q["Gama"],x=q["YTD uds"],orientation="h",name="YTD",marker_color=BLUE))
    fig.add_trace(go.Bar(y=q["Marca"]+" · "+q["Gama"],x=q["Resto TAM12M"],orientation="h",name="Resto comparable",marker_color=AMBER))
    fig.update_layout(barmode="stack",height=max(320,36*len(q)),margin=dict(l=10,r=10,t=30,b=10),legend_orientation="h",
                      xaxis_title="Unidades",yaxis_title="")
    st.plotly_chart(fig,use_container_width=True)

# ============================================================
# UI
# ============================================================
st.title("Smart Visit Planner · V2.4.1")
st.caption("Preparar la visita en segundos: acuerdo real + LOB/COMPAR + Veeva + ciclo comercial + propuesta de pedido")

with st.sidebar:
    st.header("Modo")
    mode=st.radio("Análisis",["Visita individual","Grupo / consolidado","Gestión de ciclo"])
    st.divider()
    st.caption(f"Ciclo activo: **{st.session_state['cycle_name']}**")

if mode=="Gestión de ciclo":
    st.markdown("<div class='section-title'>Gestión de ciclo</div>",unsafe_allow_html=True)
    st.success("Los archivos guardados en GitHub se cargan automáticamente. No tienes que adjuntarlos cada vez.")
    name=st.text_input("Nombre del ciclo",st.session_state["cycle_name"])
    lob_up=st.file_uploader("LOB (CSV/XLSX)",type=["csv","xlsx","xls"])
    compar_up=st.file_uploader("COMPAR (varios CSV/XLSX)",type=["csv","xlsx","xls"],accept_multiple_files=True)
    cat_up=st.file_uploader("Tarifa / catálogo (CSV/XLSX)",type=["csv","xlsx","xls"])
    if st.button("Validar y activar para esta sesión"):
        errs=[]
        if lob_up:
            try:st.session_state["lob"]=clean_lob(read_table(lob_up,lob_up.name,strings=True))
            except Exception as e:errs.append(f"LOB: {e}")
        if compar_up:
            fs=[]
            for f in compar_up:
                try:
                    x=read_table(f,f.name,strings=True);x["_source_file"]=f.name;fs.append(x)
                except Exception as e:errs.append(f"{f.name}: {e}")
            if fs:st.session_state["compar"]=pd.concat(fs,ignore_index=True,sort=False)
        if cat_up:
            try:st.session_state["catalog"]=read_table(cat_up,cat_up.name)
            except Exception as e:errs.append(f"Tarifa: {e}")
        if errs:st.error("\n".join(errs))
        else:
            st.session_state["cycle_name"]=name
            st.success("Ciclo validado y activado en esta sesión.")
    c=st.columns(5)
    c[0].metric("LOB","OK" if not repo["lob"].empty else "Falta")
    c[1].metric("COMPAR",len(repo["compar_files"]))
    c[2].metric("Catálogo",len(repo["catalog"]) if repo["catalog"] is not None else 0)
    c[3].metric("Hojas pedido",len(repo["order_pdfs"]))
    c[4].metric("Sell-out",len(repo["sellout_files"]))
    st.info("Excel normales .xlsx/.xls: sí. COMPAR: puedes cargar varios.")
    st.stop()

lob=st.session_state["lob"]
if lob is None or lob.empty:
    st.error("No hay LOB cargado.")
    st.stop()

# ---------------- Group mode ----------------
if mode=="Grupo / consolidado":
    st.markdown("<div class='section-title'>Análisis de grupo</div>",unsafe_allow_html=True)
    groups=sorted([g for g in lob["group"].dropna().astype(str).unique() if norm(g) not in ("","NO GRUPOS","NO GRUPO")])
    if not groups:
        st.warning("El LOB no contiene grupos identificados.");st.stop()
    group=st.selectbox("Grupo",groups)
    g=lob[lob["group"].astype(str)==group].copy()
    # Deduplicate exact CPV/coach duplicates before location consolidation
    g=g.sort_values("pos_id").drop_duplicates(["pos_id","client","address"],keep="first")
    sumcols=[c for c in ["TOTAL_YTD1","TOTAL_YTD","TOTAL_OBJ"] if c in g.columns]
    aggs={c:"sum" for c in sumcols}
    aggs.update({"client":lambda x:" / ".join(pd.unique(x.astype(str))),"pos_id":lambda x:", ".join(pd.unique(x.astype(str))),
                 "address":"first","town":"first","province":"first"})
    pdv=g.groupby("pdv_key",dropna=False).agg(aggs).reset_index()
    if "TOTAL_YTD" in pdv and "TOTAL_YTD1" in pdv:pdv["Δ YTD €"]=pdv["TOTAL_YTD"]-pdv["TOTAL_YTD1"]
    if "TOTAL_OBJ" in pdv and "TOTAL_YTD" in pdv:pdv["Gap LOB €"]=(pdv["TOTAL_OBJ"]-pdv["TOTAL_YTD"]).clip(lower=0)
    c=st.columns(4)
    c[0].metric("YTD grupo",euro(pdv["TOTAL_YTD"].sum() if "TOTAL_YTD" in pdv else 0))
    c[1].metric("YTD-1",euro(pdv["TOTAL_YTD1"].sum() if "TOTAL_YTD1" in pdv else 0))
    c[2].metric("Objetivo LOB*",euro(pdv["TOTAL_OBJ"].sum() if "TOTAL_OBJ" in pdv else 0))
    c[3].metric("Puntos de venta",len(pdv))
    st.caption("*En grupos sin Fichas 2026 individuales, el LOB se usa como referencia operativa, no como acuerdo.")
    rank=pdv.sort_values(["Δ YTD €","Gap LOB €"],ascending=[True,False]) if "Δ YTD €" in pdv else pdv
    st.dataframe(rank[[c for c in ["address","town","client","pos_id","TOTAL_YTD1","TOTAL_YTD","Δ YTD €","Gap LOB €"] if c in rank.columns]],
                 use_container_width=True,hide_index=True)
    if "Δ YTD €" in rank:
        q=rank.head(15).copy();q["PDV"]=q["address"].astype(str)+" · "+q["town"].astype(str)
        colors=[RED if x<0 else GREEN for x in q["Δ YTD €"]]
        fig=go.Figure(go.Bar(x=q["Δ YTD €"],y=q["PDV"],orientation="h",marker_color=colors))
        fig.update_layout(height=max(380,34*len(q)),xaxis_title="Δ YTD €",yaxis_title="")
        st.plotly_chart(fig,use_container_width=True,config={"staticPlot":True,"displayModeBar":False})
    st.stop()

# ---------------- Individual ----------------

# ---------------- Individual · V2.4 ----------------
# La pantalla individual se simplifica a dos herramientas:
# 1) Ficha visual de visita (estilo Business Review)
# 2) Pedido editable + simulación del gap posterior

BRAND_LABELS={"AVENE":"Avène","DUCRAY":"Ducray","A-DERMA":"A-Derma","DEXERYL":"Dexeryl","KLORANE":"Klorane"}
MAIN_AGREEMENT_BRANDS={"AVENE","DUCRAY","A-DERMA"}


def parse_ficha_v24(files):
    # Partimos del parser V2.3 porque ya reconstruye bien varias filas del pacto
    # (Ducray, A-Derma, Dexeryl, Klorane). V2.4 añade una capa de seguridad para
    # que Avène nunca desaparezca por el layout OCR de la ficha.
    base=parse_ficha(files)
    text=base.get("text","")
    adf=base.get("agreement",pd.DataFrame()).copy()
    if adf is None or adf.empty:
        adf=pd.DataFrame(columns=["BrandKey","Marca","Obj. colectivo €","Actual colectivo €","Referencia marca €","Actual marca €","Falta marca €","Fuente"])
    if "Fuente" not in adf.columns:
        adf["Fuente"]="Evolución Pacto"

    # Lectura robusta de AVÈNE SIN SOLAR.
    # El OCR de iPad puede devolver AVENE SIN SOL., AVENESINSOL., AVENE SIN SOLAR,
    # AVÈNE, espacios extra o caracteres pegados. Normalizamos antes de buscar.
    av_ref=av_cur=None
    text_av=norm(text).replace("AVÈNE","AVENE").replace("AVÉNE","AVENE")
    # 1) Buscar la fila completa y tomar sus tres primeras cifras:
    #    Fact. año anterior / YTD anterior / YTD actual.
    av_line=None
    for line in text_av.splitlines():
        compact=re.sub(r"[^A-Z0-9%-]","",line)
        if ("AVENESINSOL" in compact or "AVENESINSOLAR" in compact) and "SOLAR" not in compact.replace("AVENESINSOLAR",""):
            av_line=line
            break
    if av_line:
        nums=re.findall(r"-?\d[\d\.,]*\s*%?",av_line)
        vals=[parse_num(x) for x in nums]
        if len(vals)>=3:
            av_ref=vals[0]
            av_cur=vals[2]

    # 2) Si la fila quedó partida por el OCR, buscar AVENE + SIN + SOL y leer
    #    una ventana posterior suficientemente corta para no mezclar otras marcas.
    if not av_ref:
        m=re.search(r"AVENE\s*SIN\s*SOL(?:AR)?",text_av,re.I)
        if not m:
            m=re.search(r"AVENESINSOL(?:AR)?",re.sub(r"[^A-Z0-9%\.\n-]","",text_av),re.I)
        if m:
            seg=text_av[m.start():m.start()+115].replace("\n"," ")
            vals=[parse_num(x) for x in re.findall(r"-?\d[\d\.,]*\s*%?",seg)]
            if len(vals)>=3:
                av_ref=vals[0]
                av_cur=vals[2]

    # 3) Tercera vía: tabla financiera general.
    if not av_ref:
        fin=base.get("financial",{})
        if "AVENE" in fin:
            av_ref=parse_num(fin["AVENE"].get("Fact año anterior",0))
            av_cur=parse_num(fin["AVENE"].get("YTD actual",0))

    if av_ref and av_cur is not None:
        av_gap=max(av_ref-av_cur,0)
        if "BrandKey" in adf.columns and (adf["BrandKey"]=="AVENE").any():
            idx=adf.index[adf["BrandKey"]=="AVENE"][0]
            adf.loc[idx,"Referencia marca €"]=av_ref
            adf.loc[idx,"Actual marca €"]=av_cur
            adf.loc[idx,"Falta marca €"]=av_gap
            adf.loc[idx,"Fuente"]="Ficha 2026 · Avène validado"
        else:
            adf=pd.concat([adf,pd.DataFrame([{
                "BrandKey":"AVENE","Marca":"Avène",
                "Obj. colectivo €":base.get("objective",np.nan),
                "Actual colectivo €":base.get("actual",np.nan),
                "Referencia marca €":av_ref,"Actual marca €":av_cur,
                "Falta marca €":av_gap,"Fuente":"Ficha 2026 · Avène validado"
            }])],ignore_index=True)

    # Fallback adicional para cualquier marca financiera que falte totalmente.
    # Solo la añadimos como referencia anual/YTD, sin inventar colectivo.
    fin=base.get("financial",{})
    for b,v in fin.items():
        if b not in BRAND_LABELS: continue
        if "BrandKey" in adf.columns and (adf["BrandKey"]==b).any(): continue
        prev=parse_num(v.get("Fact año anterior",0));cur=parse_num(v.get("YTD actual",0))
        if prev>100 and cur>=0:
            adf=pd.concat([adf,pd.DataFrame([{
                "BrandKey":b,"Marca":BRAND_LABELS[b],"Obj. colectivo €":np.nan,"Actual colectivo €":np.nan,
                "Referencia marca €":prev,"Actual marca €":cur,"Falta marca €":max(prev-cur,0),
                "Fuente":"Ficha 2026 · tabla financiera"
            }])],ignore_index=True)

    base["agreement"]=adf
    return base

def static_plot(fig, **kwargs):
    st.plotly_chart(fig,use_container_width=True,config={"staticPlot":True,"displayModeBar":False,"responsive":True},**kwargs)


def brand_status(gap):
    gap=parse_num(gap)
    if gap<=0:return "PROTEGER",GREEN
    if gap<500:return "CONSOLIDAR",AMBER
    return "RECUPERAR",RED


def agreement_priority_chart_v24(adf):
    if adf is None or adf.empty:return
    q=adf.sort_values("Falta marca €",ascending=True).copy()
    colors=[GREEN if x<=0 else AMBER if x<500 else RED for x in q["Falta marca €"]]
    fig=go.Figure(go.Bar(x=q["Falta marca €"],y=q["Marca"],orientation="h",marker_color=colors,
                         text=[euro(x) for x in q["Falta marca €"]],textposition="outside"))
    fig.update_layout(height=max(250,48*len(q)),margin=dict(l=10,r=55,t=10,b=20),xaxis_title="Gap €",yaxis_title="",
                      showlegend=False,paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)")
    static_plot(fig)


def veeva_chart_v24(cats):
    if cats is None or cats.empty:return
    q=cats.copy()
    q["Resto comparable"]=np.maximum(pd.to_numeric(q["TAM12M uds"],errors="coerce").fillna(0)-pd.to_numeric(q["YTD uds"],errors="coerce").fillna(0),0)
    q=q.sort_values("Resto comparable",ascending=True).tail(10)
    labels=q["Marca"].astype(str)+" · "+q["Gama"].astype(str)
    fig=go.Figure()
    fig.add_trace(go.Bar(y=labels,x=q["YTD uds"],orientation="h",name="YTD",marker_color=BLUE))
    fig.add_trace(go.Bar(y=labels,x=q["Resto comparable"],orientation="h",name="Resto comparable",marker_color=AMBER))
    fig.update_layout(barmode="stack",height=max(330,40*len(q)),margin=dict(l=10,r=20,t=25,b=20),legend_orientation="h",
                      xaxis_title="Unidades",yaxis_title="",paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)")
    static_plot(fig)


def matching_catalog_v24(cat,brand,gama):
    if cat.empty:return cat
    b=norm(brand); fam=category_family(gama)
    q=cat[cat["Marca"].map(norm).str.contains(b,na=False)].copy()
    # Ajustes explícitos entre la nomenclatura Veeva y el catálogo.
    aliases={
      "Hidratació / Hydrance":"Hidratació / Hydrance",
      "Hidratación / Hydrance":"Hidratació / Hydrance",
      "Antiedad / Hyaluron Activ":"Antiedat",
      "Antiedad / DermAbsolu":"Antiedat",
      "Antiedad / A-Oxitive":"Antiedat",
      "Atopia / XeraCalm":"Atopia",
      "Atopia / Exomega":"Atopia",
      "Acné / Cleanance":"Acné / Cleanance",
      "Acné / Keracnyl":"Acné / Keracnyl",
      "Anticaída":"Anticaiguda"
    }
    fam=aliases.get(gama,fam)
    if fam=="Solar":
        return q[q["Categoria"].map(norm).str.contains("SOLAR",na=False)].copy()
    return q[q["Categoria"].map(norm).str.contains(norm(fam),na=False)].copy()


def build_proposal_v24(ficha,cats,prods):
    cat=catalog_normalized()
    if cat.empty or cats is None or cats.empty:return pd.DataFrame(),[]
    agr=ficha["agreement"]
    gapmap={r["BrandKey"]:parse_num(r["Falta marca €"]) for _,r in agr.iterrows()} if not agr.empty else {}
    months=max(1,12-date.today().month)

    candidates=[]
    for _,r in cats.iterrows():
        b=str(r["Marca"]);g=str(r["Gama"]);y=parse_num(r["YTD uds"]);t=parse_num(r["TAM12M uds"])
        bk=brand_key_from_label(b);rem=max(t-y,0);gap=gapmap.get(bk,0)
        # Solar se analiza operativamente con Veeva, pero está fuera del acuerdo principal.
        in_main=(bk in MAIN_AGREEMENT_BRANDS and not (bk=="AVENE" and category_family(g)=="Solar"))
        score=(gap/100 if in_main else 0)+rem
        if bk=="DUCRAY" and g=="Anticaída" and y==0 and t==0:score+=80
        candidates.append({"score":score,"Marca":b,"Gama":g,"YTD":y,"TAM12M":t,"Resto":rem,"gap":gap,"main":in_main})

    # Elegimos máximo 5 gamas, pero con diversidad por marca y prioridad real.
    chosen=[];count_brand={}
    for c in sorted(candidates,key=lambda x:x["score"],reverse=True):
        bk=brand_key_from_label(c["Marca"])
        if count_brand.get(bk,0)>=2:continue
        pq=matching_catalog_v24(cat,c["Marca"],c["Gama"])
        if pq.empty:continue
        chosen.append((c,pq));count_brand[bk]=count_brand.get(bk,0)+1
        if len(chosen)>=5:break

    rows=[];notes=[]
    for c,pq in chosen:
        b,g,y,t,rem=c["Marca"],c["Gama"],c["YTD"],c["TAM12M"],c["Resto"]
        # Aproximadamente un mes del volumen comparable restante, con límites conservadores.
        if y==0 and t==0:
            total_target=6 if (brand_key_from_label(b)=="DUCRAY" and g=="Anticaída") else 0
            reason="Implantación" if total_target else "Sin actividad · no forzar"
        else:
            total_target=int(max(3,min(12,round(rem/months)))) if rem>0 else 3
            reason="Reposición según Veeva"
        if category_family(g)=="Solar":
            total_target=min(total_target,6)
            reason="Solar · Veeva / estacionalidad"

        pq=pq.copy()
        pq["_rank"]=pq["Novedad"].astype(int)*4+pq["Heroe"].astype(int)*3+(pq["PVL"]>0).astype(int)
        pq=pq.sort_values(["_rank","Producto"],ascending=[False,True])
        units=[0]*len(pq)
        # Héroes/novedades reciben base 1; después se reparte sin superar 3 por SKU.
        for i,(_,pr) in enumerate(pq.iterrows()):
            if pr["Heroe"] or pr["Novedad"]:units[i]=1
        if total_target>0 and sum(units)==0:
            for i in range(min(3,len(units))):units[i]=1
        i=0
        while sum(units)<total_target and len(units):
            j=i%len(units)
            if units[j]<3:units[j]+=1
            i+=1
            if all(u>=3 for u in units):break

        for (_,pr),u in zip(pq.iterrows(),units):
            bk=brand_key_from_label(b)
            if bk=="AVENE" and category_family(g)=="Solar": objective_scope="FUERA ACUERDO PRINCIPAL"
            elif bk in MAIN_AGREEMENT_BRANDS: objective_scope="ACUERDO PRINCIPAL"
            else: objective_scope="OBJETIVO INDEPENDIENTE"
            rows.append({
              "Prioridad":"ALTA" if c["gap"]>=1000 and c["main"] else "MEDIA",
              "Marca":b,"Gama":g,"CN":pr["CN"],"Producto":pr["Producto"],"Formato":pr["Formato"],
              "Héroe":bool(pr["Heroe"]),"Novedad":bool(pr["Novedad"]),"Unidades":int(u),
              "PVL":parse_num(pr["PVL"]),"Descuento %":0.0,"Ámbito objetivo":objective_scope,"Motivo":reason
            })
        notes.append(f"{b} · {g}: base {total_target} uds · Veeva {int(y)} YTD / {int(t)} TAM12M.")

    if not rows:return pd.DataFrame(),notes
    out=pd.DataFrame(rows)
    return out,notes


def projection_by_brand(ficha,edited):
    agr=ficha["agreement"].copy()
    if agr.empty:return pd.DataFrame(),None
    e=edited.copy()
    e["Unidades"]=pd.to_numeric(e["Unidades"],errors="coerce").fillna(0)
    e["PVL"]=pd.to_numeric(e["PVL"],errors="coerce").fillna(0)
    e["Descuento %"]=pd.to_numeric(e["Descuento %"],errors="coerce").fillna(0).clip(0,100)
    e["Contribución €"]=e["Unidades"]*e["PVL"]*(1-e["Descuento %"]/100)

    rows=[]
    for _,r in agr.iterrows():
        bk=r["BrandKey"]
        mask=e["Marca"].map(brand_key_from_label).eq(bk)
        if bk=="AVENE":
            # Solar NO reduce el gap del acuerdo Avène principal.
            mask=mask & ~e["Gama"].map(category_family).eq("Solar")
        contrib=float(e.loc[mask,"Contribución €"].sum())
        before=parse_num(r["Falta marca €"])
        rows.append({"Marca":r["Marca"],"Gap antes €":before,"Pedido imputable €":contrib,
                     "Gap después €":max(before-contrib,0),"Fuente":r["Fuente"]})
    bdf=pd.DataFrame(rows)
    main_contrib=float(e[e["Ámbito objetivo"].eq("ACUERDO PRINCIPAL")]["Contribución €"].sum())
    global_after=max(parse_num(ficha.get("gap"))-main_contrib,0) if ficha.get("gap") is not None else None
    return bdf,global_after


with st.sidebar:
    st.header("Cliente")
    q=st.text_input("Buscar cliente / CPV / dirección")
    opts=lob.copy()
    if q:
        nq=norm(q)
        mask=(opts["client"].map(norm).str.contains(nq,na=False)|
              opts["pos_id"].astype(str).map(norm).str.contains(nq,na=False)|
              opts["address"].map(norm).str.contains(nq,na=False))
        opts=opts[mask]
    labels=(opts["client"].astype(str)+" · "+opts["pos_id"].astype(str)+" · "+opts["address"].astype(str)).tolist()
    if not labels:st.warning("Sin coincidencias.");st.stop()
    sel=st.selectbox("Punto de venta",labels)
    row=opts.iloc[labels.index(sel)]
    st.header("Documentos de la visita")
    ficha_files=st.file_uploader("Ficha cliente 2026 (PDF o capturas)",type=["pdf","png","jpg","jpeg"],accept_multiple_files=True)
    veeva_files=st.file_uploader("Capturas Veeva (varias)",type=["png","jpg","jpeg"],accept_multiple_files=True)

eq=equivalent_rows(lob,row)
eq_unique=eq.drop_duplicates(["client","pos_id","address"],keep="first") if len(eq) else eq
current=eq.iloc[0] if len(eq) else row

st.header(f"{current['client']} · {current['pos_id']}")
st.caption(f"{current['address']} · {current['town']} · {current['province']}")

if len(eq_unique[["client","pos_id","address"]].drop_duplicates())>1:
    st.info("Cambio de titular / CPV detectado por ubicación física. El histórico económico se consolida por punto de venta.")
    st.dataframe(eq_unique[["client","pos_id","address","town"]],hide_index=True,use_container_width=True)

with st.spinner("Analizando Ficha 2026 y Veeva…"):
    ficha=parse_ficha_v24(ficha_files)
    vcats,vprods,veeva_text=parse_veeva(veeva_files)

lobdf=brand_lob(current)

# ============================================================
# PANTALLA 1 · FICHA VISUAL
# ============================================================
st.markdown("<div class='section-title'>FICHA DE VISITA · RESUMEN EJECUTIVO</div>",unsafe_allow_html=True)

c=st.columns(4)
with c[0]:
    st.markdown(f"<div class='card card-blue'><div class='kicker'>OBJETIVO ACUERDO</div><div class='big'>{euro(ficha['objective']) if ficha['objective'] else 'Pendiente'}</div><div class='small'>Ficha 2026</div></div>",unsafe_allow_html=True)
with c[1]:
    st.markdown(f"<div class='card card-blue'><div class='kicker'>ACTUAL ACUERDO</div><div class='big'>{euro(ficha['actual']) if ficha['actual'] else 'Pendiente'}</div><div class='small'>Colectivo principal</div></div>",unsafe_allow_html=True)
with c[2]:
    sev="red" if ficha.get("gap") and ficha["gap"]>=1000 else "amber" if ficha.get("gap") else "green"
    st.markdown(f"<div class='card card-{sev}'><div class='kicker'>GAP PRINCIPAL</div><div class='big'>{euro(ficha['gap']) if ficha['gap'] is not None else 'Pendiente'}</div><div class='small'>Antes del pedido</div></div>",unsafe_allow_html=True)
with c[3]:
    st.markdown(f"<div class='card card-green'><div class='kicker'>VEEVA</div><div class='big'>{len(vcats)} gamas</div><div class='small'>{len(vprods)} productos detectados</div></div>",unsafe_allow_html=True)

if ficha["agreement"].empty:
    st.warning("No se han podido estructurar los objetivos por marca. La app no inventa gaps.")
else:
    adf=ficha["agreement"].sort_values("Falta marca €",ascending=False).copy()
    # Situación visual Proteger / Consolidar / Recuperar
    st.markdown("<div class='section-title'>Situación por marca</div>",unsafe_allow_html=True)
    s1,s2,s3=st.columns(3)
    buckets={"PROTEGER":[],"CONSOLIDAR":[],"RECUPERAR":[]}
    for _,r in adf.iterrows():
        status,_=brand_status(r["Falta marca €"])
        buckets[status].append(f"{r['Marca']} · {euro(r['Falta marca €'])}")
    with s1:
        st.markdown("<div class='card card-green'><div class='action-title'>🟢 PROTEGER</div><div class='action-text'>"+("<br>".join(buckets['PROTEGER']) if buckets['PROTEGER'] else "—")+"</div></div>",unsafe_allow_html=True)
    with s2:
        st.markdown("<div class='card card-amber'><div class='action-title'>🟡 CONSOLIDAR</div><div class='action-text'>"+("<br>".join(buckets['CONSOLIDAR']) if buckets['CONSOLIDAR'] else "—")+"</div></div>",unsafe_allow_html=True)
    with s3:
        st.markdown("<div class='card card-red'><div class='action-title'>🔴 RECUPERAR</div><div class='action-text'>"+("<br>".join(buckets['RECUPERAR']) if buckets['RECUPERAR'] else "—")+"</div></div>",unsafe_allow_html=True)

    st.markdown("<div class='section-title'>Prioridad por marca</div>",unsafe_allow_html=True)
    priority=adf[["Marca","Referencia marca €","Actual marca €","Falta marca €","Fuente"]].copy()
    st.dataframe(priority,use_container_width=True,hide_index=True,
                 column_config={"Referencia marca €":st.column_config.NumberColumn(format="%.0f €"),
                                "Actual marca €":st.column_config.NumberColumn(format="%.0f €"),
                                "Falta marca €":st.column_config.NumberColumn(format="%.0f €")})
    agreement_priority_chart_v24(adf)

# Avène Solar: fuente de unidades = Veeva, LOB = contraste económico
st.markdown("<div class='section-title'>Avène Solar · contraste Veeva / LOB</div>",unsafe_allow_html=True)
solar=vcats[(vcats["Marca"].map(norm)=="AVENE") & (vcats["Gama"].map(norm).str.contains("SOLAR",na=False))] if not vcats.empty else pd.DataFrame()
lobsolar=lobdf[lobdf["Marca"].map(norm).eq("AVENE SOLAR")]
if not solar.empty:
    sr=solar.iloc[0];sytd=parse_num(sr["YTD uds"]);stam=parse_num(sr["TAM12M uds"])
    if not lobsolar.empty:
        lr=lobsolar.iloc[0];lev=lr["Evolución %"]
        levtxt=f"{lev:+.1f}%" if pd.notna(lev) else "—"
        st.warning(f"⚠️ Veeva es la fuente operativa de unidades: {sytd:.0f} uds YTD / {stam:.0f} uds TAM12M. "
                   f"LOB muestra {euro(lr['YTD €'])} YTD frente a {euro(lr['YTD-1 €'])} YTD-1 ({levtxt}). "
                   "No son magnitudes equivalentes y la evolución económica no corresponde directamente con la rotación en unidades. Para decidir reposición Solar se usa Veeva; LOB queda como contraste.")
    else:
        st.info(f"Veeva Solar: {sytd:.0f} uds YTD / {stam:.0f} uds TAM12M. LOB no aporta un contraste comparable.")
else:
    st.info("No se ha detectado la fila ASO-SOLAIRES en las capturas Veeva cargadas.")

st.markdown("<div class='section-title'>Qué compra · Veeva</div>",unsafe_allow_html=True)
if vcats.empty:
    st.warning("No se han podido estructurar gamas Veeva.")
else:
    v=vcats.copy();v["Resto comparable uds"]=(v["TAM12M uds"]-v["YTD uds"]).clip(lower=0)
    v["Lectura"]=v.apply(lambda r:"SIN ACTIVIDAD" if r["YTD uds"]==0 and r["TAM12M uds"]==0 else
                                  ("REVISAR" if r["Resto comparable uds"]>=20 else "MANTENER"),axis=1)
    st.dataframe(v[["Marca","Gama","YTD uds","TAM12M uds","Resto comparable uds","Lectura"]],use_container_width=True,hide_index=True)
    veeva_chart_v24(v)

# ============================================================
# PANTALLA 2 · PEDIDO EDITABLE + GAP DESPUÉS
# ============================================================
st.markdown("<div class='section-title'>PROPUESTA DE PEDIDO · EDITABLE</div>",unsafe_allow_html=True)
proposal,proposal_notes=build_proposal_v24(ficha,vcats,vprods)
if proposal.empty:
    st.warning("No puedo construir una propuesta fiable con las gamas detectadas y el catálogo disponible.")
else:
    st.caption("Edita Unidades y, si quieres afinar la proyección, el Descuento %. Solar puede aparecer en el pedido, pero no reduce el gap del acuerdo principal.")
    editable_cols=["Prioridad","Marca","Gama","CN","Producto","Formato","Héroe","Novedad","Unidades","PVL","Descuento %","Ámbito objetivo","Motivo"]
    edited=st.data_editor(proposal[editable_cols],use_container_width=True,hide_index=True,key="pedido_v24",
                          column_config={"Unidades":st.column_config.NumberColumn(min_value=0,step=1),
                                         "PVL":st.column_config.NumberColumn(format="%.2f €"),
                                         "Descuento %":st.column_config.NumberColumn(min_value=0,max_value=100,step=1,format="%.0f %%")},
                          disabled=[c for c in editable_cols if c not in ["Unidades","Descuento %"]])
    edited["Unidades"]=pd.to_numeric(edited["Unidades"],errors="coerce").fillna(0).astype(int)
    edited["PVL"]=pd.to_numeric(edited["PVL"],errors="coerce").fillna(0.0)
    edited["Descuento %"]=pd.to_numeric(edited["Descuento %"],errors="coerce").fillna(0.0).clip(0,100)
    edited["Importe bruto €"]=edited["Unidades"]*edited["PVL"]
    edited["Contribución estimada €"]=edited["Importe bruto €"]*(1-edited["Descuento %"]/100)

    total_bruto=float(edited["Importe bruto €"].sum());total_net=float(edited["Contribución estimada €"].sum());uds=int(edited["Unidades"].sum())
    brandproj,global_after=projection_by_brand(ficha,edited)
    main_contrib=float(edited.loc[edited["Ámbito objetivo"].eq("ACUERDO PRINCIPAL"),"Contribución estimada €"].sum())

    k=st.columns(5)
    k[0].metric("Pedido bruto",euro(total_bruto))
    k[1].metric("Unidades",uds)
    k[2].metric("Imputable acuerdo",euro(main_contrib))
    k[3].metric("Gap antes",euro(ficha["gap"]) if ficha["gap"] is not None else "—")
    k[4].metric("Gap después",euro(global_after) if global_after is not None else "—")

    st.markdown("<div class='section-title'>Simulación por marca después del pedido</div>",unsafe_allow_html=True)
    if not brandproj.empty:
        st.dataframe(brandproj,use_container_width=True,hide_index=True,
                     column_config={"Gap antes €":st.column_config.NumberColumn(format="%.0f €"),
                                    "Pedido imputable €":st.column_config.NumberColumn(format="%.0f €"),
                                    "Gap después €":st.column_config.NumberColumn(format="%.0f €")})
        q=brandproj.sort_values("Gap después €",ascending=True)
        colors=[GREEN if x<=0 else AMBER if x<500 else RED for x in q["Gap después €"]]
        fig=go.Figure(go.Bar(x=q["Gap después €"],y=q["Marca"],orientation="h",marker_color=colors,
                             text=[euro(x) for x in q["Gap después €"]],textposition="outside"))
        fig.update_layout(height=max(250,48*len(q)),margin=dict(l=10,r=55,t=10,b=20),xaxis_title="Gap después €",yaxis_title="",showlegend=False)
        static_plot(fig)

    st.caption("La contribución al gap es una estimación basada en PVL y el descuento que indiques. El gap principal solo descuenta pedidos de Avène sin Solar, Ducray y A-Derma. Avène Solar se analiza por Veeva pero no se imputa al acuerdo principal.")
    csv=edited.to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ Descargar propuesta CSV",csv,file_name=f"Propuesta_{current['pos_id']}_V24.csv",mime="text/csv")
    if proposal_notes:
        with st.expander("Cómo se ha construido la propuesta"):
            for n in proposal_notes:st.write("• "+n)

with st.expander("Diagnóstico de lectura · solo para comprobar datos"):
    st.write("**Ficha 2026**")
    st.text_area("OCR Ficha",ficha["text"],height=220)
    st.write("**Veeva**")
    st.text_area("OCR Veeva",veeva_text,height=220)
