import streamlit as st
import pandas as pd
import json
import gspread
from datetime import datetime
import os
import time
import streamlit.components.v1 as components
import pytz
import extra_streamlit_components as stx

# --- 1. GÖRSEL TASARIM VE KURUMSAL KİMLİK (CSS) ---
st.set_page_config(page_title="Pro Kasa Elite Cloud", layout="wide")

st.markdown("""
    <style>
    .stApp { background: radial-gradient(circle at top, #1a1f25, #0d1117); color: #c9d1d9; }
    [data-testid="stHeader"] { display: none; }
    .stSidebar { background-color: #0d1117 !important; border-right: 1px solid #30363d; }
    div[data-testid="stMetric"] {
        background-color: #161b22; border: 1px solid #30363d;
        border-radius: 12px; padding: 10px !important;
    }
    .stButton>button {
        border-radius: 8px; background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
        color: white; font-weight: bold; border: none; transition: 0.3s;
    }
    .footer {
        position: fixed; left: 0; bottom: 0; width: 100%;
        background-color: rgba(13, 17, 23, 0.9); color: #8b949e;
        text-align: center; padding: 5px; font-size: 11px;
    }
    </style>
    """, unsafe_allow_html=True)

tr_timezone = pytz.timezone('Europe/Istanbul')
def su_an(): return datetime.now(tr_timezone).strftime("%d/%m/%Y %H:%M")

cookie_manager = stx.CookieManager(key="cerez_yonetici")

# --- 2. VERİ BAĞLANTISI ---
@st.cache_resource
def get_gspread_client():
    creds_dict = json.loads(st.secrets["gcp_credentials"])
    return gspread.service_account_from_dict(creds_dict)

gc = get_gspread_client()
SHEET_URL = "https://docs.google.com/spreadsheets/d/1BxOPA_JDtFYLZqxOVK3GCW1ZBh2dINF5HnqD0TbZ4h8/edit?gid=0#gid=0" 

def verileri_yukle():
    sh = gc.open_by_url(SHEET_URL)
    df_s = pd.DataFrame(sh.worksheet("Sayfa1").get_all_records()).astype(str)
    df_u = pd.DataFrame(sh.worksheet("Kullanicilar").get_all_records()).astype(str)
    if 'Marka' not in df_s.columns: df_s['Marka'] = "Genel"
    return df_s, df_u

def kaydet(df_stok, df_user):
    sh = gc.open_by_url(SHEET_URL)
    sh.worksheet("Sayfa1").clear()
    sh.worksheet("Sayfa1").update(values=[df_stok.columns.values.tolist()] + df_stok.astype(str).values.tolist())
    sh.worksheet("Kullanicilar").clear()
    sh.worksheet("Kullanicilar").update(values=[df_user.columns.values.tolist()] + df_user.astype(str).values.tolist())
    return True

# --- 3. OTURUM YÖNETİMİ ---
if "user" not in st.session_state: st.session_state.user = None
if "rol" not in st.session_state: st.session_state.rol = None
if "okunan_barkod" not in st.session_state: st.session_state.okunan_barkod = None
if "sepet" not in st.session_state: st.session_state.sepet = []
if "scanner_key" not in st.session_state: st.session_state.scanner_key = 0

if "veriler_cekildi" not in st.session_state:
    st.session_state.df_stok, st.session_state.df_user = verileri_yukle()
    st.session_state.veriler_cekildi = True

# Otomatik Giriş
if st.session_state.user is None:
    kayitli = cookie_manager.get(cookie="kullanici_adi")
    if kayitli:
        match = st.session_state.df_user[st.session_state.df_user['Kullanici_Adi'] == kayitli]
        if not match.empty:
            st.session_state.user = kayitli
            st.session_state.rol = match.iloc[0]['Rol']
            st.rerun()

# Kamera Eklentisi (Görünmez Dosya Hazırlığı)
if not os.path.exists("scanner_plugin"): os.mkdir("scanner_plugin")
with open("scanner_plugin/index.html", "w", encoding="utf-8") as f:
    f.write("<html><head><script src='https://unpkg.com/html5-qrcode'></script></head><body style='margin:0;background:#0d1117;'><div id='reader'></div><script>function playBeep(){var c=new AudioContext();var o=c.createOscillator();o.connect(c.destination);o.type='sine';o.frequency.value=880;o.start();o.stop(c.currentTime+0.1);}var h=new Html5Qrcode('reader');h.start({facingMode:'environment'},{fps:15,qrbox:250},function(t){playBeep();h.stop().then(function(){window.parent.postMessage({isStreamlitMessage:true,type:'streamlit:setComponentValue',value:t},'*');});});</script></body></html>")
canli_okuyucu = components.declare_component("canli_okuyucu", path="scanner_plugin")

# --- 4. GİRİŞ EKRANI ---
if st.session_state.user is None:
    _, col_login, _ = st.columns([1, 1.2, 1])
    with col_login:
        st.markdown("<h1 style='text-align:center; color:#58a6ff;'>🏪 Güllüoğlu Giriş</h1>", unsafe_allow_html=True)
        with st.form("login"):
            k_ad = st.text_input("Kullanıcı Adı")
            k_sif = st.text_input("Şifre", type="password")
            if st.form_submit_button("Giriş Yap", use_container_width=True):
                match = st.session_state.df_user[(st.session_state.df_user['Kullanici_Adi'] == k_ad) & (st.session_state.df_user['Sifre'] == k_sif)]
                if not match.empty:
                    st.session_state.user, st.session_state.rol = k_ad, match.iloc[0]['Rol']
                    cookie_manager.set("kullanici_adi", k_ad, max_age=30*24*60*60)
                    st.rerun()
                else: st.error("Hatalı Giriş!")
    st.stop()

# --- 5. ANA PANEL VE SOL MENÜ ---
df_stok = st.session_state.df_stok
df_user = st.session_state.df_user

with st.sidebar:
    st.markdown(f"### 🏪 Güllüoğlu Sistem\n---\n**Hoşgeldin,** {st.session_state.user}\n`Yetki: {st.session_state.rol}`")
    st.divider()
    secilen_menu = st.radio("📌 MENÜ", ["🛒 İşlemler", "📊 Envanter", "👥 Yönetim"], label_visibility="collapsed")
    st.divider()
    if st.button("🔄 Verileri Yenile", use_container_width=True):
        del st.session_state.veriler_cekildi; st.rerun()
    if st.button("🔴 Çıkış Yap", use_container_width=True, type="secondary"):
        cookie_manager.delete("kullanici_adi")
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

def tabanca_tetiklendi():
    barkod = st.session_state.get("tabanca_input", "")
    if barkod:
        st.session_state.okunan_barkod = barkod
        filtre = df_stok['Barkod'] == barkod
        if not df_stok[filtre].empty:
            u = df_stok[filtre].iloc[0]
            mevcut = next((i for i in st.session_state.sepet if i["Barkod"] == barkod), None)
            if mevcut: mevcut["Adet"] += 1
            else: st.session_state.sepet.append({"Barkod": barkod, "Urun_Adi": u['Urun_Adi'], "Fiyat": float(u['Fiyat']), "Adet": 1})
        st.session_state.tabanca_input = ""

# --- 🛒 SEKME 1: İŞLEMLER ---
if secilen_menu == "🛒 İşlemler":
    col_kasa, col_sepet = st.columns([1.3, 1])
    
    with col_kasa:
        mod = st.radio("Cihaz:", ["💻 Tabanca", "📱 Kamera"], horizontal=True, label_visibility="collapsed")
        if mod == "💻 Tabanca":
            st.html("<script>setTimeout(()=>{const i=window.parent.document.querySelectorAll('input[type=\"text\"]');for(let x of i){if(x.getAttribute('aria-label')==='🔫'){x.focus();break;}}},100);</script>")
            st.text_input("🔫", key="tabanca_input", on_change=tabanca_tetiklendi, placeholder="Barkod okutun...")
        else:
            okunan = canli_okuyucu(key=f"cam_{st.session_state.scanner_key}")
            if okunan: st.session_state.okunan_barkod = okunan; st.session_state.scanner_key += 1; st.rerun()

        if st.session_state.okunan_barkod:
            barkod = st.session_state.okunan_barkod
            u_ara = df_stok[df_stok['Barkod'] == barkod]
            
            if not u_ara.empty:
                u = u_ara.iloc[0]
                stok_n = int(float(u['Stok']))
                st.markdown(f"### 📦 {u['Urun_Adi']} <span style='font-size:14px; color:#888;'>({barkod})</span>", unsafe_allow_html=True)
                
                # KOMPAKT YAN YANA PANEL
                cf, cs = st.columns(2)
                cf.markdown(f"<div style='text-align:center;padding:10px;border-radius:10px;border:2px solid #fff;background:#0d1117;'><small>BİRİM FİYAT</small><br><b style='font-size:28px;'>💰 {u['Fiyat']} TL</b></div>", unsafe_allow_html=True)
                sr = "#2ea043" if stok_n > 10 else "#f85149"
                cs.markdown(f"<div style='text-align:center;padding:10px;border-radius:10px;border:2px solid {sr};background:#0d1117;'><small>STOK</small><br><b style='font-size:28px;color:{sr};'>{stok_n} Adet</b></div>", unsafe_allow_html=True)

                # HIZLI GRUP/MARKA YÖNETİMİ
                with st.expander("🏷️ Grup/Marka Ayarı"):
                    m_list = sorted(df_stok['Marka'].unique())
                    m_curr = str(u.get('Marka', 'Genel'))
                    c1, c2 = st.columns(2)
                    m_s = c1.selectbox("Seç:", m_list, index=m_list.index(m_curr) if m_curr in m_list else 0)
                    m_y = c2.text_input("Veya Yeni:")
                    y_m = m_y.strip().upper() if m_y.strip() else m_s
                    if y_m != m_curr:
                        if st.button(f"Grup Yap: {y_m}", use_container_width=True):
                            df_stok.loc[df_stok['Barkod'] == barkod, 'Marka'] = y_m
                            if kaydet(df_stok, df_user): st.rerun()
                
                if mod == "📱 Kamera":
                    if st.button("🛒 Sepete Ekle", type="primary", use_container_width=True):
                        mevcut = next((i for i in st.session_state.sepet if i["Barkod"] == barkod), None)
                        if mevcut: mevcut["Adet"] += 1
                        else: st.session_state.sepet.append({"Barkod": barkod, "Urun_Adi": u['Urun_Adi'], "Fiyat": float(u['Fiyat']), "Adet": 1})
                        st.session_state.okunan_barkod = None; st.rerun()
                
                if st.button("🔄 Ekranı Temizle", use_container_width=True):
                    st.session_state.okunan_barkod = None; st.rerun()
            else:
                st.warning(f"Kayıtsız Barkod: {barkod}")
                with st.form("yeni"):
                    y_ad = st.text_input("Ürün Adı")
                    y_m = st.text_input("Marka", "GENEL")
                    y_f, y_s = st.number_input("Fiyat"), st.number_input("Stok")
                    if st.form_submit_button("💾 Kaydet"):
                        y_df = pd.DataFrame([{"Barkod": barkod, "Urun_Adi": y_ad, "Marka": y_m.upper(), "Fiyat": str(y_f), "Stok": str(y_s), "Son_satis_sayisi": "0", "Son_guncelleme_tarihi": su_an()}])
                        df_stok = pd.concat([df_stok, y_df], ignore_index=True)
                        if kaydet(df_stok, df_user): st.session_state.okunan_barkod = None; st.rerun()

    with col_sepet:
        st.subheader("🛍️ Sepet")
        if not st.session_state.sepet: st.info("Sepet boş.")
        else:
            ds = pd.DataFrame(st.session_state.sepet)
            ds['Toplam'] = ds['Fiyat'] * ds['Adet']
            edt = st.data_editor(ds, hide_index=True, use_container_width=True, disabled=["Barkod", "Urun_Adi", "Fiyat", "Toplam"])
            st.session_state.sepet = edt.drop(columns=['Toplam']).to_dict('records')
            
            total = edt['Toplam'].sum()
            st.markdown(f"<div style='background:#161b22;padding:10px;border-radius:10px;border:1px solid #58a6ff;text-align:center;'><h2>Toplam: <span style='color:#58a6ff;'>{total:,.2f} TL</span></h2></div>", unsafe_allow_html=True)
            
            if st.button("💳 SATIŞI TAMAMLA", type="primary", use_container_width=True):
                for item in st.session_state.sepet:
                    idx = df_stok.index[df_stok['Barkod'] == item['Barkod']]
                    if not idx.empty:
                        i = idx[0]
                        df_stok.loc[i, 'Stok'] = str(max(0, float(df_stok.loc[i, 'Stok']) - item['Adet']))
                        df_stok.loc[i, 'Son_satis_sayisi'] = str(int(float(df_stok.loc[i, 'Son_satis_sayisi'] or 0)) + item['Adet'])
                        df_stok.loc[i, 'Son_guncelleme_tarihi'] = su_an()
                if kaydet(df_stok, df_user): st.session_state.sepet = []; st.session_state.okunan_barkod = None; st.success("Satış Başarılı!"); time.sleep(1); st.rerun()

# --- 📊 SEKME 2: ENVANTER ---
elif secilen_menu == "📊 Envanter":
    if st.session_state.rol == "Patron":
        with st.expander("🚀 Toplu Zam / İndirim"):
            c1, c2, c3 = st.columns(3)
            m_list = sorted(df_stok['Marka'].unique())
            s_m = c1.selectbox("Grup:", m_list)
            islem = c2.selectbox("İşlem:", ["Zam (+)", "İndirim (-)"])
            yuzde = c3.number_input("%", 1.0, 100.0, 10.0)
            if st.button(f"{s_m} Grubuna Uygula", use_container_width=True):
                mask = df_stok['Marka'] == s_m
                cp = (1 + (yuzde/100)) if islem == "Zam (+)" else (1 - (yuzde/100))
                df_stok.loc[mask, 'Fiyat'] = (pd.to_numeric(df_stok.loc[mask, 'Fiyat']).fillna(0) * cp).round(2).astype(str)
                if kaydet(df_stok, df_user): st.success("Fiyatlar Güncellendi!"); st.rerun()

    # İstatistikler
    try:
        sermaye = (pd.to_numeric(df_stok['Fiyat']).fillna(0) * pd.to_numeric(df_stok['Stok']).fillna(0)).sum()
        st.columns(3)[0].metric("💰 Toplam Sermaye", f"{sermaye:,.2f} TL")
    except: pass

    # Tablo ve Toplu İşlem
    ara = st.text_input("🔍 Ürün/Barkod Ara:")
    df_g = df_stok.copy()
    if ara: df_g = df_g[df_g['Urun_Adi'].str.contains(ara, case=False) | df_g['Barkod'].str.contains(ara)]
    
    if st.session_state.rol == "Patron":
        df_g.insert(0, "Seç", False)
        edt_g = st.data_editor(df_g, hide_index=True, use_container_width=True, key="env_ed", disabled=["Barkod", "Son_satis_sayisi"])
        
        # TOPLU TAŞIMA PANELİ
        secili = edt_g[edt_g['Seç'] == True]
        if not secili.empty:
            st.markdown(f"🎯 **{len(secili)} Ürün Seçildi**")
            c1, c2, c3, c4 = st.columns([2,1.5,1.2,1.2])
            m_l = sorted(df_stok['Marka'].unique())
            h_m = c1.selectbox("Hedef Grup:", m_l)
            h_y = c2.text_input("Veya Yeni Yaz:")
            y_final = h_y.strip().upper() if h_y.strip() else h_m
            if c3.button("🔄 Taşı", use_container_width=True):
                df_stok.loc[df_stok['Barkod'].isin(secili['Barkod']), 'Marka'] = y_final
                if kaydet(df_stok, df_user): st.rerun()
            if c4.button("❌ Gruptan Çıkar", use_container_width=True):
                df_stok.loc[df_stok['Barkod'].isin(secili['Barkod']), 'Marka'] = "GENEL"
                if kaydet(df_stok, df_user): st.rerun()
        
        if st.button("💾 Tablo Değişikliklerini Kaydet", use_container_width=True):
            for _, r in edt_g.iterrows():
                idx = df_stok.index[df_stok['Barkod'] == r['Barkod']]
                if not idx.empty:
                    i = idx[0]
                    df_stok.loc[i, ['Urun_Adi', 'Marka', 'Fiyat', 'Stok']] = [r['Urun_Adi'], str(r['Marka']).upper(), str(r['Fiyat']), str(r['Stok'])]
            if kaydet(df_stok, df_user): st.success("Kaydedildi!"); st.rerun()
    else: st.dataframe(df_g, hide_index=True, use_container_width=True)

# --- 👥 SEKME 3: YÖNETİM ---
elif secilen_menu == "👥 Yönetim":
    if st.session_state.rol == "Patron":
        st.subheader("Personel Listesi")
        st.dataframe(df_user, hide_index=True, use_container_width=True)
        with st.expander("➕ Yeni Personel"):
            with st.form("y_p"):
                n1, n2, n3 = st.columns(3)
                u_n = n1.text_input("Kullanıcı Adı")
                u_p = n2.text_input("Şifre")
                u_r = n3.selectbox("Yetki", ["Calisan", "Patron"])
                if st.form_submit_button("Ekle"):
                    df_user = pd.concat([df_user, pd.DataFrame([{"Kullanici_Adi": u_n, "Sifre": u_p, "Rol": u_r}])], ignore_index=True)
                    if kaydet(df_stok, df_user): st.rerun()
    else: st.error("Yetkiniz yok.")

st.markdown("<div class='footer'>Made by Ege Demircioğlu | Güllüoğlu Sistem V3.0</div>", unsafe_allow_html=True)
