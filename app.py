import io,re,zipfile,xml.etree.ElementTree as ET
import pandas as pd
import streamlit as st

st.set_page_config(page_title='Question Paper → CSV Converter',page_icon='📝',layout='wide')

QSTART=re.compile(r'^\s*(\d+)\s*[\.\)]\s*')
OMARK=re.compile(r'(?:^|\s)(?:\(?\s*([A-Da-d])\s*[\)\.:]|Option\s*([A-Da-d])\s*[:\-])\s*',re.I)
AMARK=re.compile(r'(?:^|\s)(?:correct\s+answer|answer|ans)\s*[:=\-]\s*\(?\s*([A-Da-d])\s*\)?\s*$',re.I)

def read_docx(f):
    with zipfile.ZipFile(io.BytesIO(f.getvalue())) as z: xml=z.read('word/document.xml')
    root=ET.fromstring(xml); ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    out=[]
    for p in root.findall('.//w:p',ns):
        s=[]
        for n in p.iter():
            if n.tag==f"{{{ns['w']}}}t" and n.text: s.append(n.text)
            elif n.tag==f"{{{ns['w']}}}tab": s.append(' ')
        v=re.sub(r'\s+',' ',''.join(s)).strip()
        if v: out.append(v)
    return out

def split_questions(paragraphs):
    qs=[]; cur=[]
    for p in paragraphs:
        if QSTART.match(p):
            if cur: qs.append(' '.join(cur))
            cur=[p]
        elif cur: cur.append(p)
    if cur: qs.append(' '.join(cur))
    return qs

def parse_one(raw):
    raw=re.sub(r'\s+',' ',raw).strip(); num=QSTART.match(raw).group(1); body=QSTART.sub('',raw,1).strip()
    ms=list(OMARK.finditer(body)); opts={}; ans=''
    if ms:
        question=body[:ms[0].start()].strip()
        for i,m in enumerate(ms):
            letter=(m.group(1) or m.group(2)).lower(); end=ms[i+1].start() if i+1<len(ms) else len(body)
            opts[letter]=body[m.end():end].strip()
        am=AMARK.search(body)
        if am: ans=am.group(1).upper()
    else: question=body
    warnings=[]
    if not ms: warnings.append('No options detected')
    for k in 'abcd':
        if not opts.get(k): warnings.append(f'Option {k.upper()} missing')
    if not ans: warnings.append('Answer not detected')
    return {'number':num,'question':question,'option_1':opts.get('a',''),'option_2':opts.get('b',''),'option_3':opts.get('c',''),'option_4':opts.get('d',''),'answer':ans,'warning':'; '.join(warnings)}

def parse_doc(paragraphs): return [parse_one(x) for x in split_questions(paragraphs)]

st.title('📝 Question Paper → CSV Converter')
st.caption('Upload a Microsoft Word question paper, configure the fields, preview the result, and download CSV.')
with st.sidebar:
    st.header('Question Settings')
    group=st.text_input('Question Group','119')
    qtype=st.selectbox('Question Type',['single_choice','multiple_choice','true_false','short_answer','essay'])
    level=st.selectbox('Question Level',['easy','medium','hard'])
    marks=st.number_input('Marks',min_value=0,value=1,step=1)

uploaded=st.file_uploader('Upload Microsoft Word (.docx)',type=['docx'])
if uploaded and st.button('🚀 Convert Questions',type='primary',use_container_width=True):
    try:
        paragraphs=read_docx(uploaded)
        parsed=parse_doc(paragraphs)
        if not parsed:
            st.error("No numbered questions were detected. Questions should begin with formats such as '1.', '2.', '3.'.")
            with st.expander('Show extracted Word text'):
                for p in paragraphs: st.write(p)
        else:
            rows=[{'question_type':qtype,'question_group':group,'question_level':level,'marks':marks,**{k:x[k] for k in ['question','option_1','option_2','option_3','option_4','answer']}} for x in parsed]
            st.session_state.df=pd.DataFrame(rows); st.session_state.parsed=parsed; st.session_state.name=uploaded.name
    except Exception as e: st.exception(e)

if 'df' in st.session_state:
    df=st.session_state.df; parsed=st.session_state.parsed
    st.divider(); st.subheader(f'Preview — {len(df)} questions detected')
    md=sum(not x['option_4'] for x in parsed); ma=sum(not x['answer'] for x in parsed)
    if md: st.warning(f'{md} question(s) do not contain Option D. Option D is left blank.')
    if ma: st.warning(f'{ma} question(s) do not contain a detectable answer. Answer is left blank.')
    with st.expander('Question extraction diagnostics'):
        st.dataframe(pd.DataFrame([{'Question':x['number'],'Status':x['warning'] or 'OK'} for x in parsed]),use_container_width=True,hide_index=True)
    st.dataframe(df,use_container_width=True,hide_index=True)
    name=re.sub(r'\.docx$','',st.session_state.name,flags=re.I)+'_converted.csv'
    st.download_button('⬇️ Download CSV',df.to_csv(index=False).encode('utf-8-sig'),file_name=name,mime='text/csv',type='primary',use_container_width=True)
    st.info('The app never invents missing options or answers.')
