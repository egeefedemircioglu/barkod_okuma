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
import math  # 🌟 YUKARI YUVARLAMA BÜYÜSÜ İÇİN BUNU EKLE

# --- 1. GÖRSEL TASARIM VE KURUMSAL KİMLİK (CSS) ---
st.set_page_config(page_title="Pro Kasa Elite Cloud", layout="wide")

st.markdown("""
    <style>
    .stApp { background: radial-gradient(circle at top, #1a1f25, #0d1117); color: #c9d1d9; }
    [data-testid="stHeader"] { display: none !important; }
    .block-container { padding-top: 2rem !important; max-width: 95% !important; }
    div[data-testid="column"]:nth-of-type(1) { border-right: 2px solid #30363d; padding-right: 20px; }
    .footer {
        position: fixed; left: 0; bottom: 0; width: 100%;
        background-color: rgba(13, 17, 23, 0.9); color: #8b949e;
        text-align: center; padding: 10px; font-size: 13px;
        border-top: 1px solid #30363d; backdrop-filter: blur(5px); z-index: 999;
    }
    div[data-testid="stMetric"] { background-color: #161b22; border: 1px solid #30363d; border-radius: 15px; padding: 15px !important; transition: 0.3s; }
    .stButton>button { border-radius: 10px; background: linear-gradient(135deg, #238636 0%, #2ea043 100%); color: white; font-weight: bold; border: none; height: 3.5em; width: 100%; transition: 0.3s; }
    div.row-widget.stRadio > div { gap: 15px; font-size: 18px; }
    </style>
    """, unsafe_allow_html=True)

# 🇹🇷 TÜRKİYE SAATİ AYARI
tr_timezone = pytz.timezone('Europe/Istanbul')
def su_an(): return datetime.now(tr_timezone).strftime("%d/%m/%Y %H:%M")

cookie_manager = stx.CookieManager(key="cerez_yonetici")

# --- 2. GOOGLE SHEETS BAĞLANTISI VE VERİ YÖNETİMİ ---
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
    
    if 'Son_satis_tarihi' not in df_s.columns: df_s['Son_satis_tarihi'] = ""
    if 'Son_ekleme_tarihi' not in df_s.columns: df_s['Son_ekleme_tarihi'] = ""
    if 'Marka' not in df_s.columns: df_s['Marka'] = "Genel"
    
    # Müşteri ve Satış Veritabanını Çek
    try: df_m = pd.DataFrame(sh.worksheet("Musteriler").get_all_records()).astype(str)
    except: df_m = pd.DataFrame(columns=["Musteri_Adi", "Telefon", "Toplam_Harcama", "Kayit_Tarihi"])
    
    try: df_sat = pd.DataFrame(sh.worksheet("Satislar").get_all_records()).astype(str)
    except: df_sat = pd.DataFrame(columns=["Tarih", "Musteri_Adi", "Barkod", "Urun_Adi", "Adet", "Birim_Fiyat", "Toplam_Tutar"])
    
    return df_s, df_u, df_m, df_sat

def kaydet(df_stok, df_user, df_musteri, df_satis):
    sh = gc.open_by_url(SHEET_URL)
    df_stok_t, df_user_t = df_stok.astype(str).fillna(""), df_user.astype(str).fillna("")
    df_mus_t, df_sat_t = df_musteri.astype(str).fillna(""), df_satis.astype(str).fillna("")
    
    sh.worksheet("Sayfa1").clear()
    sh.worksheet("Sayfa1").update(values=[df_stok_t.columns.values.tolist()] + df_stok_t.values.tolist())
    sh.worksheet("Kullanicilar").clear()
    sh.worksheet("Kullanicilar").update(values=[df_user_t.columns.values.tolist()] + df_user_t.values.tolist())
    
    try: ws_m = sh.worksheet("Musteriler")
    except: ws_m = sh.add_worksheet("Musteriler", 1000, 10)
    ws_m.clear()
    ws_m.update(values=[df_mus_t.columns.values.tolist()] + df_mus_t.values.tolist())
    
    try: ws_s = sh.worksheet("Satislar")
    except: ws_s = sh.add_worksheet("Satislar", 5000, 15)
    ws_s.clear()
    ws_s.update(values=[df_sat_t.columns.values.tolist()] + df_sat_t.values.tolist())
    
    return True

# --- 3. OTURUM VE HAFIZA KURULUMU ---
if "user" not in st.session_state: st.session_state.user = None
if "rol" not in st.session_state: st.session_state.rol = None
if "okunan_barkod" not in st.session_state: st.session_state.okunan_barkod = None
if "scanner_key" not in st.session_state: st.session_state.scanner_key = 0
if "sepet" not in st.session_state: st.session_state.sepet = []
if "tabanca_input" not in st.session_state: st.session_state.tabanca_input = ""

if "veriler_cekildi" not in st.session_state:
    df_s_temp, df_u_temp, df_m_temp, df_sat_temp = verileri_yukle()
    st.session_state.df_stok = df_s_temp
    st.session_state.df_user = df_u_temp
    st.session_state.df_musteri = df_m_temp
    st.session_state.df_satis = df_sat_temp
    st.session_state.veriler_cekildi = True

if st.session_state.user is None and not st.session_state.get("cikis_yapildi", False):
    kayitli_kullanici = cookie_manager.get(cookie="kullanici_adi")
    if kayitli_kullanici:
        match = st.session_state.df_user[st.session_state.df_user['Kullanici_Adi'] == kayitli_kullanici]
        if not match.empty:
            st.session_state.user = kayitli_kullanici; st.session_state.rol = match.iloc[0]['Rol']
            st.rerun()

if not os.path.exists("scanner_plugin"): os.mkdir("scanner_plugin")
with open("scanner_plugin/index.html", "w", encoding="utf-8") as f:
    f.write("""
    <!DOCTYPE html><html><head><script src="https://unpkg.com/html5-qrcode" type="text/javascript"></script></head><body style="margin: 0; padding: 0; background-color: #161b22;"><div id="reader" style="width: 100%; border-radius: 15px; border: 2px solid #30363d; background: #0d1117; min-height: 250px;"></div><script>function playBeep(){try{var c=new (window.AudioContext||window.webkitAudioContext)();var o=c.createOscillator();var g=c.createGain();o.connect(g);g.connect(c.destination);o.type="sine";o.frequency.value=880;g.gain.value=0.1;o.start();o.stop(c.currentTime+0.15);}catch(e){}}function sendToPython(t,d){window.parent.postMessage(Object.assign({isStreamlitMessage:true,type:t},d),"*");}var h=new Html5Qrcode("reader");h.start({facingMode:"environment"},{fps:15,qrbox:{width:250,height:250},formatsToSupport:[Html5QrcodeSupportedFormats.QR_CODE,Html5QrcodeSupportedFormats.CODE_128,Html5QrcodeSupportedFormats.EAN_13]},function(d){playBeep();h.stop().then(function(){sendToPython("streamlit:setComponentValue",{value:d});});},function(e){}).catch(function(e){});window.addEventListener("message",function(e){if(e.data.type==="streamlit:render"){sendToPython("streamlit:setFrameHeight",{height:350});}});sendToPython("streamlit:componentReady",{apiVersion:1});</script></body></html>
    """)
canli_okuyucu = components.declare_component("canli_okuyucu", path="scanner_plugin")

# --- 4. GİRİŞ EKRANI ---
if st.session_state.user is None:
    _, col_login, _ = st.columns([1, 1.5, 1])
    with col_login:
        with st.form("login_form"):
            st.markdown("<div style='display:flex;justify-content:center;font-size:70px;margin-bottom:10px;'>🏪</div>", unsafe_allow_html=True)
            st.markdown("<h1 style='text-align:center;color:#58a6ff;'>Giriş Yap</h1>", unsafe_allow_html=True)
            k_ad = st.text_input("Kullanıcı Adı")
            k_sif = st.text_input("Şifre", type="password")
            if st.form_submit_button("Giriş"):
                match = st.session_state.df_user[(st.session_state.df_user['Kullanici_Adi'] == k_ad) & (st.session_state.df_user['Sifre'] == k_sif)]
                if not match.empty:
                    st.session_state.user = k_ad; st.session_state.rol = match.iloc[0]['Rol']
                    cookie_manager.set("kullanici_adi", k_ad, max_age=30*24*60*60); time.sleep(1); st.rerun()
                else: st.error("Hatalı Giriş!")
    st.stop()

# --- 5. ANA FONKSİYONLAR ---
df_stok, df_user = st.session_state.df_stok, st.session_state.df_user
df_musteri, df_satis = st.session_state.df_musteri, st.session_state.df_satis

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

def imleci_hapset():
    st.html("<script>const doc=window.parent.document;setTimeout(()=>{const i=doc.querySelectorAll('input[type=\"text\"]');for(let x=0;x<i.length;x++){if(i[x].getAttribute('aria-label')==='🔫 Barkod Numarası:'){i[x].focus();break;}}}, 100);</script>")

if 'Marka' not in df_stok.columns: df_stok['Marka'] = "Genel"

c_menu, c_icerik = st.columns([1.2, 8], gap="large")

# --- SOL SABİT MENÜ SÜTUNU ---
with c_menu:
    st.markdown("<h2 style='color:#58a6ff; text-align:center;'>MENÜ</h2>", unsafe_allow_html=True)
    st.divider()
    secilen_menu = st.radio("Menü Seçimi", ["🛒 İŞLEMLER", "📊 ENVANTER", "🤝 MÜŞTERİLER", "👥 YÖNETİM"], label_visibility="collapsed")
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    st.divider()
    st.markdown(f"👤 **{st.session_state.user}**\n\n🟢 Yetki: {st.session_state.rol}")
    st.divider()
    if st.button("🔄 Verileri Yenile", width="stretch"):
        if "veriler_cekildi" in st.session_state: del st.session_state.veriler_cekildi
        st.session_state.okunan_barkod = None; st.rerun()
    if st.button("🔴 Çıkış Yap", width="stretch"):
        cookie_manager.delete("kullanici_adi")
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.session_state.cikis_yapildi = True; time.sleep(1); st.rerun()

# --- ANA İÇERİK SÜTUNU ---
with c_icerik:
    
    # 🛒 İŞLEMLER 
    if secilen_menu == "🛒 İŞLEMLER":
        col_kasa, col_sepet = st.columns([1.3, 1], gap="large")
        
        with col_kasa:
            st.markdown("### 🛒 Barkod Okuma ve İşlem Alanı")
            cihaz_modu = st.radio("🔍 Cihaz Modu:", ["💻 Masaüstü (Tabanca)", "📱 Mobil (Kamera)"], horizontal=True)
            st.divider()

            if cihaz_modu == "💻 Masaüstü (Tabanca)":
                imleci_hapset() 
                st.text_input("🔫 Barkod Numarası:", key="tabanca_input", on_change=tabanca_tetiklendi)
            else:
                if st.session_state.okunan_barkod is None:
                    okunan = canli_okuyucu(key=f"kamera_{st.session_state.scanner_key}")
                    if okunan:
                        st.session_state.okunan_barkod = okunan; st.session_state.scanner_key += 1; st.rerun()

            if st.session_state.okunan_barkod:
                barkod = st.session_state.okunan_barkod
                filtre = df_stok['Barkod'] == barkod
                urun = df_stok[filtre]
                
                if not urun.empty:
                    u = urun.iloc[0]
                    stok_n = int(float(u['Stok']))
                    st.subheader(f"📦 {u['Urun_Adi']} | 🔖 {barkod}")
                    
                    c_fiyat, c_stok = st.columns([1.5, 1])
                    c_fiyat.markdown(f"<div style='text-align:center;padding:10px;border-radius:10px;border:2px solid #fff;background-color:#0d1117;'><div style='font-size:48px;color:#a3a3a3;'>Birim Fiyat</div><div style='font-size:56px;font-weight:900;color:#fff;'>💰 {u['Fiyat']} TL</div></div>", unsafe_allow_html=True)
                    s_renk = "#2ea043" if stok_n > 10 else "#f85149"
                    c_stok.markdown(f"<div style='text-align:center;padding:10px;border-radius:10px;border:2px solid {s_renk};background-color:#0d1117;'><div style='font-size:48px;color:#a3a3a3;'>Mevcut Stok</div><div style='font-size:56px;font-weight:900;color:{s_renk};'>{stok_n}</div></div>", unsafe_allow_html=True)
                    st.divider()

                    if cihaz_modu == "💻 Masaüstü (Tabanca)": st.success(f"⚡ {u['Urun_Adi']} sepete eklendi!")
                    else:
                        s_mik = st.number_input("Adet:", min_value=1, max_value=stok_n if stok_n > 0 else 1, value=1)
                        if st.button("🛒 Sepete Fırlat", type="primary", width="stretch"):
                            if stok_n < s_mik: st.error("Yetersiz Stok!")
                            else:
                                mevcut = next((i for i in st.session_state.sepet if i["Barkod"] == barkod), None)
                                if mevcut: mevcut["Adet"] += s_mik
                                else: st.session_state.sepet.append({"Barkod": barkod, "Urun_Adi": u['Urun_Adi'], "Fiyat": float(u['Fiyat']), "Adet": s_mik})
                                st.session_state.okunan_barkod = None; st.rerun()
                                
                    if st.button("🔄 Ekranı Temizle", width="stretch"): st.session_state.okunan_barkod = None; st.rerun()

                    with st.expander("⚙️ Hızlı Stok / Fiyat"):
                        c_ek, c_fiy = st.columns(2)
                        with c_ek:
                            e_mik = st.number_input("Stok Ekle", 1, value=1, key=f"stok_ekle_{barkod}")
                            if st.button(f"➕ Ekle", key=f"btn_ekle_{barkod}", width="stretch"):
                                df_stok.loc[filtre, 'Stok'] = str(stok_n + e_mik)
                                df_stok.loc[filtre, 'Son_guncelleme_tarihi'] = su_an()
                                if kaydet(df_stok, df_user, df_musteri, df_satis): st.session_state.df_stok = df_stok; st.rerun()
                        with c_fiy:
                            if st.session_state.rol == "Patron":
                                y_f = st.number_input("Yeni Fiyat", value=float(u['Fiyat']), key=f"fiyat_degis_{barkod}")
                                if st.button("🏷️ Güncelle", key=f"btn_fiyat_{barkod}", width="stretch"):
                                    df_stok.loc[filtre, 'Fiyat'] = str(y_f)
                                    df_stok.loc[filtre, 'Son_guncelleme_tarihi'] = su_an()
                                    if kaydet(df_stok, df_user, df_musteri, df_satis): st.session_state.df_stok = df_stok; st.rerun()
                            else: st.info("Yetki yok")
                else:
                    st.warning("Kayıtsız Barkod!")
                    with st.form("yeni_urun"):
                        y_ad = st.text_input("Ürün Adı")
                        y_f, y_s = st.number_input("Fiyat", 0.0), st.number_input("Stok", 0)
                        if st.form_submit_button("💾 Kaydet"):
                            yeni = pd.DataFrame([{"Barkod": barkod, "Urun_Adi": y_ad, "Marka": "Genel", "Fiyat": str(y_f), "Stok": str(y_s), "Son_satis_sayisi": "0", "Son_guncelleme_tarihi": su_an(), "Son_satis_tarihi": "", "Son_ekleme_tarihi": su_an()}])
                            df_stok = pd.concat([df_stok, yeni], ignore_index=True)
                            if kaydet(df_stok, df_user, df_musteri, df_satis): st.session_state.df_stok = df_stok; st.session_state.okunan_barkod = None; st.rerun()

       with col_sepet:
            st.markdown("### 🛍️ Sepet Alanı")
            st.divider()
            
            if len(st.session_state.sepet) == 0:
                st.info("Sepetiniz şu an boş.")
            else:
                df_sepet = pd.DataFrame(st.session_state.sepet)
                df_sepet['Toplam (TL)'] = df_sepet['Fiyat'] * df_sepet['Adet']
                
                # 🌟 BÜYÜ BURADA: Sepetin en başına "Sil" kutucuğu ekliyoruz
                df_sepet.insert(0, "🗑️ Sil", False)
                
                # key değerini değiştirdik ki tablo hata vermeden kendini güncellesin
                edited_sepet = st.data_editor(
                    df_sepet, 
                    width="stretch", 
                    hide_index=True, 
                    disabled=["Barkod", "Urun_Adi", "Toplam (TL)"], 
                    key="sepet_editor_v2"
                )
                
                # Sil kutucuğu işaretlenmemiş (False) olanları ayıkla
                kalan_urunler = edited_sepet[edited_sepet["🗑️ Sil"] == False]
                st.session_state.sepet = kalan_urunler.drop(columns=['Toplam (TL)', '🗑️ Sil']).to_dict('records')
                
                # Eğer silinen bir ürün olduysa ekranı saniyesinde yenile (Fiyat güncellensin)
                if edited_sepet["🗑️ Sil"].any():
                    st.rerun()
                    
                genel_toplam = kalan_urunler['Toplam (TL)'].sum()
                
                st.markdown(f"<div style='background-color:#161b22;padding:20px;border-radius:12px;border:2px solid #58a6ff;text-align:center;font-size:32px;font-weight:bold;'>Genel Toplam<br><span style='color:#58a6ff;'>{genel_toplam:,.2f} TL</span></div>", unsafe_allow_html=True)
                
                # MÜŞTERİ SEÇİMİ VE EKLEME PANELİ
                st.markdown("#### 🤝 Müşteri Seçimi")
                musteri_listesi = ["Genel Müşteri (Kayıtsız)"] + sorted(df_musteri['Musteri_Adi'].tolist())
                secilen_musteri = st.selectbox("Satış Yapılacak Müşteri:", musteri_listesi, label_visibility="collapsed")
                
                with st.expander("➕ Yeni Müşteri Ekle"):
                    y_m_ad = st.text_input("Müşteri Adı Soyadı/Firma")
                    y_m_tel = st.text_input("Telefon Numarası")
                    if st.button("Müşteriyi Kaydet", width="stretch"):
                        if y_m_ad:
                            yeni_m = pd.DataFrame([{"Musteri_Adi": y_m_ad.strip().upper(), "Telefon": y_m_tel, "Toplam_Harcama": "0", "Kayit_Tarihi": su_an()}])
                            df_musteri = pd.concat([df_musteri, yeni_m], ignore_index=True)
                            if kaydet(df_stok, df_user, df_musteri, df_satis):
                                st.session_state.df_musteri = df_musteri; st.success(f"{y_m_ad} eklendi!"); time.sleep(1); st.rerun()
                
                if st.button("💳 Satışı Onayla ve Tamamla", type="primary", width="stretch"):
                    with st.spinner("İşleniyor..."):
                        tarih_satis = su_an()
                        yeni_satislar = []
                        
                        for item in st.session_state.sepet:
                            b, satilan_adet, fiyat = item['Barkod'], item['Adet'], item['Fiyat']
                            idx = df_stok.index[df_stok['Barkod'] == b]
                            if not idx.empty:
                                i = idx[0]
                                mevcut_stok = float(df_stok.loc[i, 'Stok'])
                                df_stok.loc[i, 'Stok'] = str(max(0, mevcut_stok - satilan_adet))
                                eski_satis = int(float(df_stok.loc[i, 'Son_satis_sayisi'])) if str(df_stok.loc[i, 'Son_satis_sayisi']).strip() != "" else 0
                                df_stok.loc[i, 'Son_satis_sayisi'] = str(eski_satis + satilan_adet)
                                df_stok.loc[i, 'Son_satis_tarihi'] = tarih_satis
                                df_stok.loc[i, 'Son_guncelleme_tarihi'] = tarih_satis
                                
                            yeni_satislar.append({
                                "Tarih": tarih_satis, "Musteri_Adi": secilen_musteri, "Barkod": b, 
                                "Urun_Adi": item['Urun_Adi'], "Adet": str(satilan_adet), 
                                "Birim_Fiyat": str(fiyat), "Toplam_Tutar": str(satilan_adet * fiyat)
                            })
                            
                        if secilen_musteri != "Genel Müşteri (Kayıtsız)":
                            m_idx = df_musteri.index[df_musteri['Musteri_Adi'] == secilen_musteri]
                            if not m_idx.empty:
                                eski_harcama = float(df_musteri.loc[m_idx[0], 'Toplam_Harcama']) if str(df_musteri.loc[m_idx[0], 'Toplam_Harcama']) != "" else 0.0
                                df_musteri.loc[m_idx[0], 'Toplam_Harcama'] = str(eski_harcama + genel_toplam)
                        
                        if yeni_satislar:
                            df_satis = pd.concat([df_satis, pd.DataFrame(yeni_satislar)], ignore_index=True)
                            
                        if kaydet(df_stok, df_user, df_musteri, df_satis):
                            st.session_state.df_stok = df_stok; st.session_state.df_musteri = df_musteri; st.session_state.df_satis = df_satis
                            st.session_state.sepet = []; st.session_state.okunan_barkod = None
                            st.success("✅ İŞLEM ONAYLANDI!"); time.sleep(1.5); st.rerun()
                
                if st.button("🗑️ Sepeti Boşalt", width="stretch"): st.session_state.sepet = []; st.rerun()

    # 📊 ENVANTER 
    elif secilen_menu == "📊 ENVANTER":
        st.markdown("### 📊 Envanter ve Stok Durumu")
        
        if st.session_state.rol == "Patron":
            with st.expander("🚀 MARKAYA GÖRE TOPLU FİYAT GÜNCELLEME (ZAM/İNDİRİM)"):
                c_m1, c_m2, c_m3 = st.columns([2, 1, 1])
                mevcut_markalar_panel = [m for m in df_stok['Marka'].unique() if m.strip() != ""]
                if not mevcut_markalar_panel: mevcut_markalar_panel = ["Genel"]
                
                secilen_marka = c_m1.selectbox("İşlem Yapılacak Marka:", mevcut_markalar_panel)
                
                # 🌟 BÜYÜ BURADA: Sembolleri kaldırdım, Python'un kafası karışmasın diye netleştirdim
                islem_tipi = c_m2.selectbox("İşlem Tipi:", ["ZAM", "İNDİRİM"])
                yuzde = c_m3.number_input("Yüzde Oranı (%)", min_value=0.0, value=10.0, step=1.0)
                
                if st.button(f"⚡ {secilen_marka} Grubuna %{yuzde} {islem_tipi} Uygula", type="primary", width="stretch"):
                    with st.spinner("Fiyatlar hesaplanıyor ve buluta yazılıyor..."):
                        mask = df_stok['Marka'] == secilen_marka
                        
                        # 🌟 100% GARANTİLİ MATEMATİK MOTORU
                        if islem_tipi == "ZAM":
                            carpan = 1.0 + (yuzde / 100.0)
                        else:  # İNDİRİM
                            carpan = 1.0 - (yuzde / 100.0)
                            
                        # Virgüllü fiyat girildiyse (örn: 15,50) hata vermesin diye noktaya çeviriyoruz
                        fiyat_temiz = df_stok.loc[mask, 'Fiyat'].astype(str).str.replace(',', '.')
                        eski_fiyatlar = pd.to_numeric(fiyat_temiz, errors='coerce').fillna(0.0)
                        
                        # Çarp ve kaydet
                        df_stok.loc[mask, 'Fiyat'] = (eski_fiyatlar * carpan).apply(math.ceil).astype(str)
                        df_stok.loc[mask, 'Son_guncelleme_tarihi'] = su_an()
                        
                        if kaydet(df_stok, df_user, df_musteri, df_satis):
                            st.session_state.df_stok = df_stok
                            st.success(f"✅ Başarılı! {secilen_marka} grubundaki {mask.sum()} ürünün fiyatına %{yuzde} {islem_tipi} uygulandı.")
                            time.sleep(2); st.rerun()
            st.divider()

        df_goster = df_stok.copy()
        if 'Son_satis_tarihi' in df_goster.columns:
            df_goster['Siralama_Tarihi'] = pd.to_datetime(df_goster['Son_satis_tarihi'], format="%d/%m/%Y %H:%M", errors='coerce')
            df_goster = df_goster.sort_values(by='Siralama_Tarihi', ascending=False).drop(columns=['Siralama_Tarihi'])

        if st.session_state.rol == "Patron":
            try:
                toplam_sermaye = (pd.to_numeric(df_goster['Fiyat'], errors='coerce').fillna(0) * pd.to_numeric(df_goster['Stok'], errors='coerce').fillna(0)).sum()
                toplam_cesit = len(df_goster)
                toplam_adet = pd.to_numeric(df_goster['Stok'], errors='coerce').fillna(0).sum()
            except:
                toplam_sermaye, toplam_cesit, toplam_adet = 0.0, 0, 0

            cm1, cm2, cm3 = st.columns(3)
            cm1.metric("💰 Dükkandaki Toplam Sermaye", f"{toplam_sermaye:,.2f} TL")
            cm2.metric("📦 Toplam Ürün Adedi", f"{int(toplam_adet)} Adet")
            cm3.metric("🏷️ Ürün Çeşidi", f"{toplam_cesit} Kalem")
            st.divider()

        arama = st.text_input("🔍 Ürün Adı veya Barkod Yazın:")
        if arama:
            mask = df_goster['Urun_Adi'].str.contains(arama, case=False, na=False) | df_goster['Barkod'].str.contains(arama, case=False, na=False)
            df_goster = df_goster[mask]

        df_goster = df_goster.reset_index(drop=True)

        if st.session_state.rol == "Patron":
            st.info("💡 **HIZLI SEÇİM:** Tablodaki ürünlerin başındaki kutucuğu işaretleyerek ürünleri topluca bir gruba taşıyabilirsiniz.")
            
            df_goster.insert(0, "Seç", False)
            edited_df = st.data_editor(
                df_goster, width="stretch", num_rows="dynamic", hide_index=True,
                disabled=["Barkod", "Son_satis_sayisi", "Son_guncelleme_tarihi", "Son_satis_tarihi", "Son_ekleme_tarihi"],
                key="envanter_editor"
            )
            
            secili_satirlar = edited_df[edited_df['Seç'] == True]
            if not secili_satirlar.empty:
                secilen_adet = len(secili_satirlar)
                st.markdown(f"<div style='background-color:#1f2937;padding:15px;border-radius:10px;border-left:5px solid #3b82f6;margin-bottom:15px;'><strong style='color:#60a5fa;'>🎯 {secilen_adet} Adet Ürün Seçildi.</strong> Bu ürünleri bir gruba bağlayabilir veya gruptan çıkarabilirsiniz:</div>", unsafe_allow_html=True)
                
                c_top1, c_top2, c_top3, c_top4 = st.columns([2, 1.5, 1.5, 1.2])
                marka_listesi = sorted(list(df_stok['Marka'].astype(str).unique()))
                if "Genel" not in marka_listesi: marka_listesi.append("Genel")
                
                hedef_marka_sec = c_top1.selectbox("Mevcut Gruplardan Seç:", marka_listesi, key="toplu_m_sec")
                hedef_marka_yaz = c_top2.text_input("Veya Yeni Grup Yaz:", placeholder="Örn: EGE YILDIZ", key="toplu_m_yaz")
                uygulanacak_marka = hedef_marka_yaz.strip().upper() if hedef_marka_yaz.strip() != "" else hedef_marka_sec
                
                with c_top3:
                    st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
                    if st.button(f"🔄 Gruba Bağla", type="primary", width="stretch"):
                        with st.spinner("İşleniyor..."):
                            df_stok.loc[df_stok['Barkod'].isin(secili_satirlar['Barkod']), 'Marka'] = uygulanacak_marka
                            df_stok.loc[df_stok['Barkod'].isin(secili_satirlar['Barkod']), 'Son_guncelleme_tarihi'] = su_an()
                            if kaydet(df_stok, df_user, df_musteri, df_satis):
                                st.session_state.df_stok = df_stok; st.success(f"✅ {secilen_adet} ürün bağlandı."); time.sleep(1.5); st.rerun()

                with c_top4:
                    st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
                    if st.button("❌ Gruptan Çıkar", width="stretch"):
                        with st.spinner("İşleniyor..."):
                            df_stok.loc[df_stok['Barkod'].isin(secili_satirlar['Barkod']), 'Marka'] = "Genel"
                            df_stok.loc[df_stok['Barkod'].isin(secili_satirlar['Barkod']), 'Son_guncelleme_tarihi'] = su_an()
                            if kaydet(df_stok, df_user, df_musteri, df_satis):
                                st.session_state.df_stok = df_stok; st.warning(f"🗑️ {secilen_adet} ürün gruptan çıkarıldı."); time.sleep(1.5); st.rerun()
                st.divider()

            if st.button("💾 Tablodaki Manuel Değişiklikleri Kaydet", width="stretch"):
                with st.spinner("Kaydediliyor..."):
                    orijinal_barkodlar = df_goster['Barkod'].tolist()
                    kalan_barkodlar = edited_df['Barkod'].tolist()
                    silinenler = [b for b in orijinal_barkodlar if b not in kalan_barkodlar]
                    df_stok = df_stok[~df_stok['Barkod'].isin(silinenler)]
                    
                    for _, row in edited_df.iterrows():
                        idx = df_stok.index[df_stok['Barkod'] == row['Barkod']]
                        if not idx.empty:
                            i = idx[0]
                            df_stok.loc[i, ['Urun_Adi', 'Marka', 'Fiyat', 'Stok']] = [str(row['Urun_Adi']), str(row.get('Marka', 'Genel')).upper(), str(row['Fiyat']), str(row['Stok'])]
                            df_stok.loc[i, 'Son_guncelleme_tarihi'] = su_an()
                            
                    if kaydet(df_stok, df_user, df_musteri, df_satis):
                        st.session_state.df_stok = df_stok; st.success("✅ Tablo güncellendi!"); time.sleep(1); st.rerun() 
        else:
            st.info("💡 Sadece ürünleri görüntüleme yetkiniz var.")
            st.dataframe(df_goster, width="stretch", hide_index=True)

    # 🤝 MÜŞTERİLER 
    elif secilen_menu == "🤝 MÜŞTERİLER":
        st.markdown("### 🤝 Müşteri Yönetimi ve Satış Geçmişi")
        
        c_m_list, c_m_detay = st.columns([1, 1.5], gap="large")
        
        with c_m_list:
            st.subheader("Müşteri Listesi")
            df_m_goster = df_musteri.copy()
            if not df_m_goster.empty:
                df_m_goster['Toplam_Harcama'] = pd.to_numeric(df_m_goster['Toplam_Harcama'], errors='coerce').fillna(0)
                st.dataframe(df_m_goster.sort_values(by="Toplam_Harcama", ascending=False), hide_index=True, width="stretch")
                
                # MÜŞTERİ SİLME ALANI
                if st.session_state.rol == "Patron":
                    st.markdown("<br>", unsafe_allow_html=True)
                    with st.expander("❌ Müşteri Sil"):
                        sil_secim = st.selectbox("Sistemden Kaldırılacak Müşteri:", ["Seçiniz..."] + sorted(df_musteri['Musteri_Adi'].tolist()))
                        if st.button("🗑️ Müşteriyi Tamamen Sil", type="primary", width="stretch"):
                            if sil_secim != "Seçiniz...":
                                df_musteri = df_musteri[df_musteri['Musteri_Adi'] != sil_secim].reset_index(drop=True)
                                if kaydet(df_stok, df_user, df_musteri, df_satis):
                                    st.session_state.df_musteri = df_musteri
                                    st.warning(f"✅ {sil_secim} sistemden kalıcı olarak silindi.")
                                    time.sleep(1.5)
                                    st.rerun()
                            else:
                                st.error("Lütfen listeden bir müşteri seçin.")
            else:
                st.info("Henüz kayıtlı müşteri yok.")
                
        with c_m_detay:
            st.subheader("Müşteri Satış Detayı")
            m_sec = st.selectbox("Geçmişini Görmek İstediğiniz Müşteriyi Seçin:", ["Seçiniz..."] + sorted(df_musteri['Musteri_Adi'].tolist()))
            
            if m_sec != "Seçiniz...":
                sat_gecmisi = df_satis[df_satis['Musteri_Adi'] == m_sec]
                if sat_gecmisi.empty:
                    st.warning(f"{m_sec} adına yapılmış bir satış kaydı bulunamadı.")
                else:
                    toplam_bakiye = pd.to_numeric(sat_gecmisi['Toplam_Tutar'], errors='coerce').fillna(0).sum()
                    st.markdown(f"<h3 style='color:#58a6ff;'>Toplam Satış Hacmi: {toplam_bakiye:,.2f} TL</h3>", unsafe_allow_html=True)
                    st.dataframe(sat_gecmisi.sort_values(by="Tarih", ascending=False).drop(columns=['Musteri_Adi']), hide_index=True, width="stretch")

    # 👥 YÖNETİM
    elif secilen_menu == "👥 YÖNETİM":
        st.markdown("### 👥 Personel Yönetimi")
        if st.session_state.rol == "Patron":
            with st.expander("➕ Yeni Personel Ekle"):
                ca, cb, cc = st.columns(3)
                nu_ad = ca.text_input("Kullanıcı Adı")
                nu_sif = cb.text_input("Şifre")
                nu_rol = cc.selectbox("Yetki", ["Calisan", "Patron"])
                if st.button("Kaydet", width="stretch"):
                    df_user = pd.concat([df_user, pd.DataFrame([{"Kullanici_Adi": nu_ad, "Sifre": nu_sif, "Rol": nu_rol}])], ignore_index=True)
                    if kaydet(df_stok, df_user, df_musteri, df_satis): 
                        st.session_state.df_user = df_user
                        st.rerun()
                    
            st.divider()
            st.markdown("#### 🔑 Mevcut Personeller")
            for idx, row in df_user.iterrows():
                cad, cps, csl = st.columns([2, 2, 1])
                cad.markdown(f"<div style='margin-top:28px;'>**{row['Kullanici_Adi']}** ({row['Rol']})</div>", unsafe_allow_html=True)
                n_ps = cps.text_input("Yeni Şifre", value=row['Sifre'], key=f"pw_{idx}")
                
                with csl:
                    st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
                    c_up, c_del = st.columns(2)
                    if c_up.button("💾", key=f"btn_up_{idx}", help="Şifreyi Güncelle"):
                        df_user.at[idx, 'Sifre'] = n_ps
                        if kaydet(df_stok, df_user, df_musteri, df_satis): 
                            st.session_state.df_user = df_user
                            st.success("Güncellendi")
                            time.sleep(1)
                            st.rerun()
                    
                    if row['Kullanici_Adi'] != st.session_state.user:
                        if c_del.button("❌", key=f"btn_del_{idx}", help="Personeli Sil"):
                            df_user = df_user.drop(idx).reset_index(drop=True)
                            if kaydet(df_stok, df_user, df_musteri, df_satis): 
                                st.session_state.df_user = df_user
                                st.warning("Silindi")
                                time.sleep(1)
                                st.rerun()
        else: 
            st.error("Bu sayfayı görüntülemek için Patron yetkisine sahip olmalısınız.")

# --- 6. GELİŞTİRİCİ İMZASI (FOOTER) ---
st.markdown("""
<div class="footer">
    Made by <b>Ege Demircioğlu</b> | CRM Destekli V4.4 🚀
</div>
""", unsafe_allow_html=True)
