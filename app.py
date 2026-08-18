from pathlib import Path
import io, re, unicodedata
import pandas as pd
import streamlit as st
import plotly.express as px
from pypdf import PdfReader

st.set_page_config(page_title="Smart Visit Planner NEW", layout="wide")
BASE=Path(__file__).parent
DATA=BASE; REF=BASE

def norm(x):
    s='' if pd.isna(x) else str(x)
    s=''.join(c for c in unicodedata.normalize('NFKD',s) if not unicodedata.combining(c))
    return re.sub(r'[^A-Z0-9]+',' ',s.upper()).strip()

def money(v):
    try:return f"{float(v):,.0f} €".replace(',','X').replace('.',',').replace('X','.')
    except:return '—'

def nnum(v):
    try:return float(v)
    except:return 0.0

@st.cache_data
def load_lob():
    return pd.read_csv(DATA/'lob_master.csv',encoding='utf-8-sig')

@st.cache_data
def load_products():
    d=pd.read_csv(DATA/'product_catalog.csv',encoding='utf-8-sig')
    d['brand_key']=d.brand.map(norm); d['cat_key']=d.category.map(norm)
    return d

@st.cache_data
def load_compar():
    f=REF/'COMPAR_JUNIO_2026.xlsx'
    d=pd.read_excel(f,sheet_name='INFORME DE VENTAS JUNIO 2026',header=1)
    d.columns=[str(c).strip() for c in d.columns]
    # keep first occurrence names and rename by position because source has duplicate labels
    cols=list(d.columns)
    rename={cols[0]:'LOB',cols[4]:'CLIENTE'}
    # positions from source sheet
    pos={9:'TOTAL_2025',10:'TOTAL_YTD25',11:'TOTAL_YTD26',12:'TOTAL_EVOL',
         18:'AVENE_NS_2025',19:'AVENE_NS_YTD25',20:'AVENE_NS_YTD26',
         23:'AVENE_SOLAR_2025',24:'AVENE_SOLAR_YTD25',25:'AVENE_SOLAR_YTD26',
         28:'DUCRAY_2025',29:'DUCRAY_YTD25',30:'DUCRAY_YTD26',
         33:'ADERMA_2025',34:'ADERMA_YTD25',35:'ADERMA_YTD26',
         38:'DEXERYL_2025',39:'DEXERYL_YTD25',40:'DEXERYL_YTD26'}
    for i,n in pos.items():
        if i<len(cols): rename[cols[i]]=n
    # duplicate-column rename by assignment safer
    names=[]
    for i,c in enumerate(cols): names.append(pos.get(i, 'LOB' if i==0 else 'CLIENTE' if i==4 else f'C{i}'))
    d.columns=names
    d['client_key']=d.CLIENTE.map(norm)
    return d

def extract_pdf_text(files):
    out=[]
    for f in files or []:
        try:
            r=PdfReader(io.BytesIO(f.getvalue()))
            txt='\n'.join((p.extract_text() or '') for p in r.pages)
            out.append((f.name,txt))
        except Exception as e: out.append((f.name,f"No se pudo leer: {e}"))
    return out

def campaign_hits(client,pos):
    hits=[]
    specs=[
      ('Solar · 20% septiembre','SELL_OUT_SOLAR_SEPT.xlsx'),
      ('Ducray Caída · 20% + incentivo 3€ sept-oct','SELL_OUT_CAIDA_SEPT_OCT.xlsx'),
      ('Avène Cleanance · 20% + 3€ sept-oct','SELL_OUT_CLEANANCE_SEPT_OCT.xlsx'),
      ('Ducray Keracnyl · incentivo 3€ septiembre','SELL_OUT_KERACNYL_SEPT.xlsx')]
    ck=norm(client); pk=norm(pos)
    for label,fn in specs:
        try:
            x=pd.read_excel(REF/fn,header=None,dtype=str)
            text=x.fillna('').astype(str).apply(lambda col: col.map(norm))
            found=text.apply(lambda col: col.str.contains(ck,regex=False) if ck else False).any().any()
            if not found and pk:
                found=text.apply(lambda col: col.str.contains(pk,regex=False)).any().any()
            if found:hits.append(label)
        except: pass
    return hits

lob=load_lob(); products=load_products()
st.title('Smart Visit Planner · NEW V1.0')
st.caption('Reinicio limpio · Euros = LOB/COMPAR · Unidades = Veeva · Sin inferencias entre marcas o gamas')

with st.sidebar:
    st.header('1 · Cliente')
    q=st.text_input('Buscar cliente / CPV')
    opts=lob.copy()
    if q:
        m=opts.client.fillna('').str.contains(q,case=False,na=False)|opts.pos_id.astype(str).str.contains(q,case=False,na=False)
        opts=opts[m]
    labels=(opts.client.fillna('')+' · '+opts.pos_id.astype(str)).tolist()
    sel=st.selectbox('Cliente LOB',labels if labels else ['Sin coincidencias'])
    row=None
    if labels:
        row=opts.iloc[labels.index(sel)]
    st.header('2 · Documentos')
    ficha_2026 = st.file_uploader(
    "Ficha cliente 2026",
    type=["pdf","png","jpg","jpeg"]
)
    veeva_imgs=st.file_uploader('Capturas Veeva (varias)',type=['png','jpg','jpeg'],accept_multiple_files=True)
    veeva_file=st.file_uploader('Veeva estructurado (opcional CSV/XLSX)',type=['csv','xlsx'])
    st.info('Las capturas quedan asociadas a la visita. En V1.0, para evitar errores de OCR, las unidades se confirman en la tabla Veeva editable.')

if row is None:
    st.warning('Selecciona un cliente.'); st.stop()

client=row.client; pos=str(row.pos_id)
st.subheader(f'{client} · {pos}')

# ECONOMIC BLOCK
st.header('1 · Situación económica oficial')
brands=['AVENE SIN SOLAR','AVENE SOLAR','DUCRAY','A-DERMA','DEXERYL']
cols=st.columns(4)
obj=nnum(row.TOTAL_OBJ); ytd=nnum(row.TOTAL_YTD); gap=max(obj-ytd,0)
cols[0].metric('YTD LOB',money(ytd)); cols[1].metric('Objetivo LOB',money(obj)); cols[2].metric('Falta',money(gap)); cols[3].metric('Cumplimiento',f'{(ytd/obj*100 if obj else 0):.1f}%')
rows=[]
for b in brands:
    o=nnum(row.get(b+'_OBJ')); y=nnum(row.get(b+'_YTD')); prev=nnum(row.get(b+'_YTD1'))
    rows.append({'Marca':b,'Objetivo €':o,'YTD €':y,'Falta €':max(o-y,0),'Evol. vs YTD-1 %':((y/prev-1)*100 if prev else None)})
econ=pd.DataFrame(rows)
st.dataframe(econ,hide_index=True,use_container_width=True,column_config={'Objetivo €':st.column_config.NumberColumn(format='%.0f €'),'YTD €':st.column_config.NumberColumn(format='%.0f €'),'Falta €':st.column_config.NumberColumn(format='%.0f €'),'Evol. vs YTD-1 %':st.column_config.NumberColumn(format='%.1f%%')})
fig=px.bar(econ,x='Marca',y=['YTD €','Falta €'],barmode='stack',title='Facturación YTD y gap hasta objetivo LOB')
st.plotly_chart(fig,use_container_width=True)

# COMPAR
st.header('2 · Contraste COMPAR')
try:
    comp=load_compar(); hit=comp[comp.client_key==norm(client)]
    if hit.empty:
        st.info('Cliente no localizado de forma exacta en COMPAR. El LOB sigue siendo la fuente económica oficial.')
    else:
        c=hit.iloc[0]
        comp_rows=[]
        for label,prefix in [('Avène sin Solar','AVENE_NS'),('Avène Solar','AVENE_SOLAR'),('Ducray','DUCRAY'),('A-Derma','ADERMA'),('Dexeryl/PFD','DEXERYL')]:
            a=nnum(c.get(prefix+'_YTD25')); b=nnum(c.get(prefix+'_YTD26'))
            comp_rows.append({'Marca':label,'YTD 2025 €':a,'YTD 2026 €':b,'Evolución %':((b/a-1)*100 if a else None)})
        st.dataframe(pd.DataFrame(comp_rows),hide_index=True,use_container_width=True)
except Exception as e:
    st.warning(f'COMPAR no disponible: {e}')

# VEEVA
st.header('3 · Veeva · unidades reales')
st.caption('REGLA: cada fila pertenece a una marca + gama concreta. Nunca se copian o suman datos entre Avène/Ducray ni entre gamas con nombres parecidos.')
seed=pd.DataFrame(columns=['Marca','Gama Veeva','YTD uds','TAM12M uds','Año anterior uds','Héroe comprado YTD/12M'])
if veeva_file:
    try:
        seed=pd.read_excel(veeva_file) if veeva_file.name.lower().endswith('xlsx') else pd.read_csv(veeva_file)
    except: pass
veeva=st.data_editor(seed,num_rows='dynamic',use_container_width=True,key='veeva',column_config={'Marca':st.column_config.SelectboxColumn(options=['Avène','Ducray','A-Derma','Dexeryl/PFD','Klorane','René Furterer']),'YTD uds':st.column_config.NumberColumn(min_value=0,step=1),'TAM12M uds':st.column_config.NumberColumn(min_value=0,step=1),'Año anterior uds':st.column_config.NumberColumn(min_value=0,step=1),'Héroe comprado YTD/12M':st.column_config.CheckboxColumn()})
if veeva_imgs:
    with st.expander(f'Ver {len(veeva_imgs)} capturas Veeva'):
        for im in veeva_imgs: st.image(im,caption=im.name,use_container_width=True)

# OPPORTUNITIES
st.header('4 · Oportunidades reales')
opp=[]
for _,r in veeva.iterrows():
    brand=str(r.get('Marca','')).strip(); gama=str(r.get('Gama Veeva','')).strip()
    if not brand or not gama: continue
    y=nnum(r.get('YTD uds')); t=nnum(r.get('TAM12M uds')); prev=nnum(r.get('Año anterior uds')); hero=bool(r.get('Héroe comprado YTD/12M',False))
    if y==0 and t==0 and prev==0:
        typ='IMPLANTACIÓN'; reason='0 uds YTD + 0 uds TAM12M + 0 uds año anterior'
    elif not hero:
        typ='OPORTUNIDAD HÉROE'; reason='No consta compra de producto héroe en YTD/12M'
    else:
        typ='TRABAJADA'; reason='La gama tiene compra real en Veeva'
    opp.append({'Marca':brand,'Gama':gama,'Lectura':typ,'Motivo':reason})
if opp: st.dataframe(pd.DataFrame(opp),hide_index=True,use_container_width=True)
else: st.info('Añade datos Veeva para detectar implantaciones. Sin Veeva no se inventan oportunidades de gama.')

# CAMPAIGNS
st.header('5 · Acciones sell-out ya compradas')
hits=campaign_hits(client,pos)
if hits:
    for h in hits: st.success('✓ '+h)
else: st.info('No se ha localizado al cliente en los cuatro listados de campañas integrados. Esto no significa que no tenga otras condiciones en su ficha/chuleta.')

# ORDER PROPOSAL
st.header('6 · Propuesta de pedido')
st.caption('La propuesta parte del catálogo/hojas de pedido. Las unidades son editables y NO se calculan a partir de un objetivo ficticio de gama.')
brand_choice=st.selectbox('Marca para propuesta',['Avène','Ducray','A-Derma','Dexeryl'])
cat_opts=sorted(products[products.brand.map(norm)==norm(brand_choice)].category.dropna().unique().tolist())
cat_choice=st.selectbox('Gama',cat_opts if cat_opts else ['—'])
sub=products[(products.brand.map(norm)==norm(brand_choice))&(products.category==cat_choice)].copy()
sub['Unidades']=0
sub['Importe €']=0.0
show=sub[['cn','description','format','pvl','hero','novelty','Unidades']].rename(columns={'cn':'CN','description':'Producto','format':'Formato','pvl':'PVL','hero':'Héroe','novelty':'Novedad'})
edit=st.data_editor(show,num_rows='dynamic',use_container_width=True,key=f'order_{brand_choice}_{cat_choice}',column_config={'Unidades':st.column_config.NumberColumn(min_value=0,step=1),'PVL':st.column_config.NumberColumn(format='%.2f €')})
edit['Importe €']=pd.to_numeric(edit['PVL'],errors='coerce').fillna(0)*pd.to_numeric(edit['Unidades'],errors='coerce').fillna(0)
order_total=edit['Importe €'].sum(); units=pd.to_numeric(edit['Unidades'],errors='coerce').fillna(0).sum()
c1,c2,c3=st.columns(3); c1.metric('Pedido',money(order_total)); c2.metric('Unidades',f'{units:.0f}'); c3.metric('Gap LOB tras pedido',money(max(gap-order_total,0)))

# FICHA
st.header('7 · Ficha 2026 / acuerdo')
if ficha:
    texts=extract_pdf_text([ficha])
    with st.expander('Texto extraído de la ficha 2026'):
        st.text(texts[0][1][:20000])
else:
    st.info('Carga la ficha 2026 para consultar acuerdo, rappel y condiciones particulares durante la preparación.')

st.divider()
st.caption('Smart Visit Planner NEW V1.0 · Primero fiabilidad de datos; después automatización y exportaciones.')
