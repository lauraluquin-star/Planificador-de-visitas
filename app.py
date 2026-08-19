
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

st.set_page_config(page_title="Smart Visit Planner · V2.3", page_icon="⚡", layout="wide")

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
 "AVENE":r"^AVENE\s*SIN\s*SOL[^\n]*",
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
st.title("Smart Visit Planner · V2.3")
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
        st.plotly_chart(fig,use_container_width=True)
    st.stop()

# ---------------- Individual ----------------
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
# remove duplicate coach lines from same exact record
eq_unique=eq.drop_duplicates(["client","pos_id","address"],keep="first") if len(eq) else eq
current=eq.iloc[0] if len(eq) else row

st.header(f"{current['client']} · {current['pos_id']}")
st.caption(f"{current['address']} · {current['town']} · {current['province']}")

unique_identity=eq_unique[["client","pos_id","address"]].drop_duplicates() if len(eq_unique) else pd.DataFrame()
if len(unique_identity)>1:
    st.info("Cambio de titular / CPV detectado por ubicación física. El histórico económico se consolida por punto de venta.")
    st.dataframe(eq_unique[["client","pos_id","address","town"]],hide_index=True,use_container_width=True)

with st.spinner("Leyendo Ficha 2026 y Veeva…"):
    ficha=parse_ficha(ficha_files)
    vcats,vprods,veeva_text=parse_veeva(veeva_files)

lobdf=brand_lob(current)
actions=opportunity_and_focus(ficha,vcats,date.today().month)
sellhits=load_sellout_hits(current["pos_id"],current["client"])
proposal,proposal_notes=build_proposal(ficha,vcats,vprods)

# Top dashboard
st.markdown("<div class='section-title'>⚡ PLAN DE VISITA EXPRESS</div>",unsafe_allow_html=True)
c=st.columns(5)
with c[0]:
    val=euro(ficha["objective"]) if ficha["objective"] else "Pendiente"
    st.markdown(f"<div class='card card-blue'><div class='kicker'>Objetivo acuerdo</div><div class='big'>{val}</div><div class='small'>Fuente: Ficha 2026</div></div>",unsafe_allow_html=True)
with c[1]:
    val=euro(ficha["actual"]) if ficha["actual"] else "Pendiente"
    st.markdown(f"<div class='card card-blue'><div class='kicker'>Actual acuerdo</div><div class='big'>{val}</div><div class='small'>Colectivo principal</div></div>",unsafe_allow_html=True)
with c[2]:
    gap=ficha["gap"]
    sev="red" if gap and gap>1000 else "amber" if gap else "green"
    val=euro(gap) if gap is not None else "Pendiente"
    st.markdown(f"<div class='card card-{sev}'><div class='kicker'>Falta acuerdo</div><div class='big'>{val}</div><div class='small'>A cerrar durante el año</div></div>",unsafe_allow_html=True)
with c[3]:
    # No mostrar un falso 0% si el mapeo del LOB no aporta TOTAL_YTD/TOTAL_OBJ fiables.
    lob_known=lobdf[(lobdf["Objetivo LOB €"]>0) | (lobdf["YTD €"]>0)]
    if len(lob_known):
        ytd=float(lob_known["YTD €"].sum()); obj=float(lob_known["Objetivo LOB €"].sum())
        ratio=ytd/obj if obj else None
        if ratio is not None:
            sev=status_from_ratio(ratio,date.today().timetuple().tm_yday/365)
            st.markdown(f"<div class='card card-{sev}'><div class='kicker'>LOB · contraste</div><div class='big'>{ratio:.0%}</div><div class='small'>{euro(ytd)} YTD · no sustituye acuerdo</div></div>",unsafe_allow_html=True)
        else:
            st.markdown("<div class='card card-amber'><div class='kicker'>LOB · contraste</div><div class='big'>Revisar</div><div class='small'>Sin objetivo LOB comparable</div></div>",unsafe_allow_html=True)
    else:
        st.markdown("<div class='card card-amber'><div class='kicker'>LOB · contraste</div><div class='big'>Sin dato</div><div class='small'>No se muestra un 0% artificial</div></div>",unsafe_allow_html=True)
with c[4]:
    st.markdown(f"<div class='card card-green'><div class='kicker'>Datos Veeva</div><div class='big'>{len(vcats)} gamas</div><div class='small'>{len(vprods)} productos detectados</div></div>",unsafe_allow_html=True)

# Main actions
st.markdown("<div class='section-title'>1 · QUÉ HACER HOY</div>",unsafe_allow_html=True)
if actions:
    cols=st.columns(2)
    for i,a in enumerate(actions[:4]):
        with cols[i%2]:action_card(a["sev"],a["title"],a["text"])
else:
    st.info("Carga la Ficha 2026 y capturas Veeva para generar prioridades.")

# Agreement
st.markdown("<div class='section-title'>2 · ACUERDO 2026 · DÓNDE ESTÁ EL GAP</div>",unsafe_allow_html=True)
if ficha["objective"] and not ficha["agreement"].empty:
    adf=ficha["agreement"].copy()
    st.success(f"Objetivo principal detectado: {euro(ficha['objective'])} · actual {euro(ficha['actual'])} · faltan {euro(ficha['gap'])}.")
    show=adf[["Marca","Referencia marca €","Actual marca €","Falta marca €"]].copy()
    st.dataframe(show,use_container_width=True,hide_index=True,
                 column_config={"Referencia marca €":st.column_config.NumberColumn(format="%.0f €"),
                                "Actual marca €":st.column_config.NumberColumn(format="%.0f €"),
                                "Falta marca €":st.column_config.NumberColumn(format="%.0f €")})
    agreement_bar(show)
else:
    st.warning("No se ha confirmado el objetivo del acuerdo. Revisa que la captura incluya completa la zona «Evolución Pacto».")

# LOB
st.markdown("<div class='section-title'>3 · LOB · CONTRASTE ECONÓMICO</div>",unsafe_allow_html=True)
st.dataframe(lobdf,use_container_width=True,hide_index=True,
             column_config={"Objetivo LOB €":st.column_config.NumberColumn(format="%.0f €"),
                            "YTD €":st.column_config.NumberColumn(format="%.0f €"),
                            "YTD-1 €":st.column_config.NumberColumn(format="%.0f €"),
                            "Evolución %":st.column_config.NumberColumn(format="%+.1f %%"),
                            "Gap LOB €":st.column_config.NumberColumn(format="%.0f €")})
st.caption("El LOB sirve para evolución y control económico. El objetivo comercial de la visita sigue siendo el de la Ficha 2026.")

# Veeva
st.markdown("<div class='section-title'>4 · VEEVA · QUÉ COMPRA Y QUÉ QUEDA POR VENDER</div>",unsafe_allow_html=True)
if vcats.empty:
    st.error("No se han podido estructurar las gamas de las capturas Veeva. No se inventan datos.")
else:
    v=vcats.copy()
    v["Resto TAM12M uds"]=(v["TAM12M uds"]-v["YTD uds"]).clip(lower=0)
    v["Lectura"]=v.apply(lambda r:"SIN ACTIVIDAD" if r["YTD uds"]==0 and r["TAM12M uds"]==0 else
                                   ("REVISAR ROTACIÓN" if r["Resto TAM12M uds"]>=20 else "MANTENER"),axis=1)
    st.dataframe(v[["Marca","Gama","YTD uds","TAM12M uds","Resto TAM12M uds","Lectura"]],
                 use_container_width=True,hide_index=True)

    # Avène Solar: la fuente operativa de unidades es Veeva. El LOB se contrasta en euros.
    solar=v[(v["Marca"].map(norm)=="AVENE") & (v["Gama"].map(norm).str.contains("SOLAR",na=False))]
    if not solar.empty:
        sytd=float(solar["YTD uds"].sum()); stam=float(solar["TAM12M uds"].sum())
        lobsolar=lobdf[lobdf["Marca"].map(norm).str.contains("AVENE SOLAR",na=False)]
        if not lobsolar.empty:
            lr=lobsolar.iloc[0]; lev=lr["Evolución %"]
            levtxt=f"{lev:+.1f}%" if pd.notna(lev) else "sin evolución comparable"
            st.warning(f"⚠️ AVÈNE SOLAR · Fuente de unidades: Veeva = {sytd:.0f} uds YTD / {stam:.0f} uds TAM12M. "
                       f"LOB = {euro(lr['YTD €'])} YTD y evolución {levtxt}. Unidades y facturación no corresponden directamente; revisar la diferencia antes de decidir pedido.")
        else:
            st.info(f"AVÈNE SOLAR · Fuente de unidades: Veeva = {sytd:.0f} uds YTD / {stam:.0f} uds TAM12M. LOB se usa solo como contraste económico.")
    category_chart(v)
    st.caption("Resto TAM12M = TAM12M − YTD. Se usa como referencia del volumen comparable de los meses que quedan, no como pedido automático.")
    if len(vprods):
        with st.expander("Detalle de productos detectados en Veeva"):
            st.dataframe(vprods,use_container_width=True,hide_index=True)

# Sellout
st.markdown("<div class='section-title'>5 · SELL-OUT / PALANCAS DEL CICLO</div>",unsafe_allow_html=True)
if not sellhits.empty:
    st.success("El cliente aparece en acciones sell-out ya compradas:")
    st.dataframe(sellhits,use_container_width=True,hide_index=True)
else:
    st.info("No se ha encontrado el CPV/cliente en los listados SELL_OUT guardados en GitHub.")

# Proposal
st.markdown("<div class='section-title'>6 · PROPUESTA DE PEDIDO · EDITABLE Y REALISTA</div>",unsafe_allow_html=True)
if proposal.empty:
    st.warning("No puedo generar una propuesta fiable todavía: necesito gamas Veeva estructuradas y referencias del catálogo/tarifa.")
else:
    st.caption("La propuesta evita pedidos desproporcionados. Usa aproximadamente un mes de rotación comparable, con tope por gama, y prioriza héroes/novedades. Todas las referencias de la categoría disponible quedan visibles.")
    edited=st.data_editor(
        proposal,
        use_container_width=True,hide_index=True,num_rows="dynamic",
        column_config={
          "Unidades":st.column_config.NumberColumn(min_value=0,step=1),
          "PVL":st.column_config.NumberColumn(format="%.2f €"),
          "Importe":st.column_config.NumberColumn(format="%.2f €")
        },
        disabled=[c for c in proposal.columns if c not in ["Unidades"]]
    )
    edited["Unidades"]=pd.to_numeric(edited["Unidades"],errors="coerce").fillna(0).astype(int)
    edited["PVL"]=pd.to_numeric(edited["PVL"],errors="coerce").fillna(0.0)
    edited["Importe"]=edited["Unidades"]*edited["PVL"]
    total=float(edited["Importe"].sum());uds=int(edited["Unidades"].sum())
    c=st.columns(4)
    c[0].metric("Pedido propuesto",euro(total))
    c[1].metric("Unidades",uds)
    if ficha["gap"] is not None:
        c[2].metric("Gap acuerdo después*",euro(max(ficha["gap"]-total,0)))
        c[3].metric("Cobertura del gap*",f"{min(total/ficha['gap'],1):.0%}" if ficha["gap"] else "—")
    else:
        c[2].metric("Gap acuerdo después*","—");c[3].metric("Cobertura del gap*","—")
    st.caption("*Impacto económico aproximado usando PVL. No equivale a facturación neta hasta aplicar condiciones/descuentos correspondientes.")
    if proposal_notes:
        with st.expander("Cómo se ha calculado la propuesta"):
            for n in proposal_notes:st.write("• "+n)

    # download
    csv=edited.to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ Descargar propuesta CSV",csv,file_name=f"Propuesta_{current['pos_id']}.csv",mime="text/csv")

# Conversation prompts
st.markdown("<div class='section-title'>7 · PREGUNTAS PARA EL FARMACÉUTICO</div>",unsafe_allow_html=True)
qs=[]
if not vcats.empty:
    for _,r in vcats.iterrows():
        if r["YTD uds"]==0 and r["TAM12M uds"]==0 and r["Gama"]=="Anticaída":
            qs.append("Ducray Anticaída: ¿qué necesitaría la farmacia para introducir la gama y trabajarla de forma continuada?")
if not ficha["agreement"].empty:
    adf=ficha["agreement"].sort_values("Falta marca €",ascending=False)
    for _,r in adf.head(2).iterrows():
        if r["Falta marca €"]>0:
            qs.append(f"{r['Marca']}: ¿qué pedido y qué apoyo sell-out podemos cerrar hoy para recuperar parte de los {euro(r['Falta marca €'])} pendientes?")
if not qs:qs=["Validar stock, rotación y prioridades antes de cerrar el pedido."]
for q in qs[:4]:st.write("• "+q)

with st.expander("Diagnóstico de lectura · solo para comprobar datos"):
    st.write("**Ficha 2026**")
    st.text_area("OCR Ficha",ficha["text"],height=220)
    st.write("**Veeva**")
    st.text_area("OCR Veeva",veeva_text,height=220)
