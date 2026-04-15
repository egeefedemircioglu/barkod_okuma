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
    
    /* ÜSTTEKİ ŞERİDİ VE GICIK İKONLARI KÖKÜNDEN SİLİYORUZ */
    [data-testid="stHeader"] { display: none !important; }
    .block-container { padding-top: 2rem !important; max-width: 95% !important; }
    
    /* SOL MENÜYÜ GÖRSEL OLARAK AYIRMAK İÇİN UFAK BİR DOKUNUŞ */
    div[data-testid="column"]:nth-of-type(1) {
        border-right: 2px solid #30363d;
        padding-right: 20px;
    }
    
    .footer {
        position: fixed; left: 0; bottom: 0; width: 100%;
        background-color: rgba(13, 17, 23, 0.9); color: #8b949e;
        text-align: center; padding: 10px; font-size: 13px;
        border-top: 1px solid #30363d; backdrop-filter: blur(5px); z-index: 999;
    }
    div[data-testid="stMetric"] {
        background-color: #161b22; border: 1px solid #30363d;
        border-radius: 15px; padding: 15px !important; transition: 0.3s;
    }
    .stButton>button {
        border-radius: 10px; background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
        color: white; font-weight: bold; border: none; height: 3.5em; width: 100%; transition: 0.3s;
    }
    /* Menü butonlarının arasını açar */
    div.row-widget.stRadio > div { gap: 15px; font-size: 18px; }
    </style>
    """, unsafe_allow_html=True)

# 🇹🇷 TÜRKİYE SAATİ AYARI
tr_timezone = pytz.timezone('Europe/Istanbul')
def su_an():
    return datetime.now(tr_timezone).strftime("%d/%m/%Y %H:%M")

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
    
    return df_s, df_u

def kaydet(df_stok, df_user):
    sh = gc.open_by_url(SHEET_URL)
    df_stok_temiz = df_stok.astype(str).fillna("")
    df_user_temiz = df_user.astype(str).fillna("")
    sh.worksheet("Sayfa1").clear()
    sh.worksheet("Sayfa1").update(values=[df_stok_temiz.columns.values.tolist()] + df_stok_temiz.values.tolist())
    sh.worksheet("Kullanicilar").clear()
    sh.worksheet("Kullanicilar").update(values=[df_user_temiz.columns.values.tolist()] + df_user_temiz.values.tolist())
    return True

# --- 3. OTURUM VE HAFIZA KURULUMU ---
if "user" not in st.session_state: st.session_state.user = None
if "rol" not in st.session_state: st.session_state.rol = None
if "okunan_barkod" not in st.session_state: st.session_state.okunan_barkod = None
if "scanner_key" not in st.session_state: st.session_state.scanner_key = 0
if "sepet" not in st.session_state: st.session_state.sepet = []
if "tabanca_input" not in st.session_state: st.session_state.tabanca_input = ""

if "veriler_cekildi" not in st.session_state:
    df_s_temp, df_u_temp = verileri_yukle()
    st.session_state.df_stok = df_s_temp
    st.session_state.df_user = df_u_temp
    st.session_state.veriler_cekildi = True

if st.session_state.user is None and not st.session_state.get("cikis_yapildi", False):
    kayitli_kullanici = cookie_manager.get(cookie="kullanici_adi")
    if kayitli_kullanici:
        match = st.session_state.df_user[st.session_state.df_user['Kullanici_Adi'] == kayitli_kullanici]
        if not match.empty:
            st.session_state.user = kayitli_kullanici
            st.session_state.rol = match.iloc[0]['Rol']
            st.rerun()

if not os.path.exists("scanner_plugin"): os.mkdir("scanner_plugin")
with open("scanner_plugin/index.html", "w", encoding="utf-8") as f:
    f.write("""
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://unpkg.com/html5-qrcode" type="text/javascript"></script>
    </head>
    <body style="margin: 0; padding: 0; background-color: #161b22;">
        <div id="reader" style="width: 100%; border-radius: 15px; border: 2px solid #30363d; background: #0d1117; min-height: 250px;"></div>
        <script>
            function playBeep() {
                try {
                    var context = new (window.AudioContext || window.webkitAudioContext)();
                    var osc = context.createOscillator();
                    var gain = context.createGain();
                    osc.connect(gain); gain.connect(context.destination);
                    osc.type = "sine"; osc.frequency.value = 880; 
                    gain.gain.value = 0.1; osc.start(); osc.stop(context.currentTime + 0.15); 
                } catch(e) {}
            }
            function sendToPython(type, data) { window.parent.postMessage(Object.assign({ isStreamlitMessage: true, type: type }, data), "*"); }
            function init() { sendToPython("streamlit:componentReady", {apiVersion: 1}); }
            function setComponentValue(value) { sendToPython("streamlit:setComponentValue", {value: value}); }
            
            var html5QrCode = new Html5Qrcode("reader");
            var config = { 
                fps: 15, 
                qrbox: {width: 250, height: 250},
                formatsToSupport: [ Html5QrcodeSupportedFormats.QR_CODE, Html5QrcodeSupportedFormats.CODE_128, Html5QrcodeSupportedFormats.CODE_39, Html5QrcodeSupportedFormats.EAN_13 ]
            };
            html5QrCode.start(
                { facingMode: "environment" }, config,
                function(decodedText) {
                    playBeep();
                    html5QrCode.stop().then(function() { setComponentValue(decodedText); });
                },
                function(errorMessage) {}
            ).catch(function(err) {
                document.getElementById("reader").innerHTML = 
                    "<div style='color:white; text-align:center; padding:30px; font-family:sans-serif;'>" +
                    "<h3 style='color:#ff4a4a; margin-top:0;'>Kamera Açılamadı 🚫</h3>" +
                    "<p style='font-size:14px;'>Lütfen telefon ayarlarından veya tarayıcıdan kameraya izin verin.</p>" +
                    "<button onclick='location.reload()' style='margin-top:15px; padding:10px 20px; border-radius:8px; background:#58a6ff; color:white; border:none; font-weight:bold;'>Yeniden Dene</button>" +
                    "</div>";
            });
            window.addEventListener("message", function(e) {
                if (e.data.type === "streamlit:render") { sendToPython("streamlit:setFrameHeight", {height: 350}); }
            });
            init();
        </script>
    </body>
    </html>
    """)
canli_okuyucu = components.declare_component("canli_okuyucu", path="scanner_plugin")

# --- 4. GİRİŞ EKRANI ---
if st.session_state.user is None:
    _, col_login, _ = st.columns([1, 1.5, 1])
    with col_login:
        with st.form("login_form"):
            import os
            if os.path.exists("logo.png"):
                st.image("logo.png")
            else:
                st.markdown("""
                    <div style='display: flex; justify-content: center; align-items: center; width: 100%; margin-top: 15px;'>
                        <div style='border-radius: 50%; width: 180px; height: 180px; background-color: #161b22; border: 3px solid #58a6ff; box-shadow: 0 0 20px rgba(88, 166, 255, 0.5); display: flex; justify-content: center; align-items: center; font-size: 70px;'>🏪</div>
                    </div>
                    """, unsafe_allow_html=True)
            
            st.markdown("<h1 style='text-align:center; color: #58a6ff; margin-top: 5px;'>Hoşgeldiniz</h1>", unsafe_allow_html=True)
            k_ad = st.text_input("Kullanıcı Adı")
            k_sif = st.text_input("Şifre", type="password")
            beni_hatirla = st.checkbox("Beni Hatırla 🍪")
            
            if st.form_submit_button("Giriş"):
                match = st.session_state.df_user[(st.session_state.df_user['Kullanici_Adi'] == k_ad) & (st.session_state.df_user['Sifre'] == k_sif)]
                if not match.empty:
                    st.session_state.user = k_ad
                    st.session_state.rol = match.iloc[0]['Rol']
                    if "cikis_yapildi" in st.session_state: del st.session_state["cikis_yapildi"]
                    if beni_hatirla:
                        cookie_manager.set("kullanici_adi", k_ad, max_age=30*24*60*60) 
                        time.sleep(1) 
                    st.rerun()
                else: st.error("Hatalı Giriş!")
    st.stop()

# --- 5. ANA FONKSİYONLAR ---
df_stok = st.session_state.df_stok
df_user = st.session_state.df_user

def tabanca_tetiklendi():
    barkod = st.session_state.get("tabanca_input", "") 
    if barkod:
        st.session_state.okunan_barkod = barkod
        filtre = st.session_state.df_stok['Barkod'] == barkod
        if not st.session_state.df_stok[filtre].empty:
            u = st.session_state.df_stok[filtre].iloc[0]
            mevcut = next((item for item in st.session_state.sepet if item["Barkod"] == barkod), None)
            if mevcut:
                mevcut["Adet"] += 1
            else:
                st.session_state.sepet.append({"Barkod": barkod, "Urun_Adi": u['Urun_Adi'], "Fiyat": float(u['Fiyat']), "Adet": 1})
        st.session_state.tabanca_input = ""

def imleci_hapset():
    st.html(
        """
        <script>
        const doc = window.parent.document;
        setTimeout(() => {
            const inputs = doc.querySelectorAll('input[type="text"]');
            for(let i=0; i<inputs.length; i++) {
                if(inputs[i].getAttribute('aria-label') === '🔫 Barkod Numarası:') {
                    inputs[i].focus();
                    break;
                }
            }
        }, 100);
        </script>
        """
    )

if 'Marka' not in df_stok.columns:
    df_stok['Marka'] = "Genel"


# --- 🌟 MİMARİ: EKRANI SÜTUNLARA BÖLÜYORUZ (TASLAĞA GÖRE) 🌟 ---
# c_menu (Sol Menü), c_icerik (Sağdaki devasa alan)
c_menu, c_icerik = st.columns([1.2, 8], gap="large")

# --- SOL SABİT MENÜ SÜTUNU ---
with c_menu:
    st.markdown("<h2 style='color:#58a6ff; text-align:center;'>MENÜ</h2>", unsafe_allow_html=True)
    st.divider()
    
    secilen_menu = st.radio("Menü Seçimi", ["🛒 İŞLEMLER", "📊 ENVANTER", "👥 YÖNETİM"], label_visibility="collapsed")
    
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    st.divider()
    st.markdown(f"👤 **{st.session_state.user}**\n\n🟢 Yetki: {st.session_state.rol}")
    st.divider()

    if st.button("🔄 Verileri Yenile", use_container_width=True):
        if "veriler_cekildi" in st.session_state:
            del st.session_state.veriler_cekildi
        st.session_state.okunan_barkod = None
        st.rerun()

    if st.button("🔴 Çıkış Yap", use_container_width=True):
        if cookie_manager.get("kullanici_adi") is not None: cookie_manager.delete("kullanici_adi")
        cookie_manager.set("kullanici_adi", "", max_age=0) 
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.session_state.cikis_yapildi = True
        time.sleep(1)
        st.rerun()


# --- ANA İÇERİK SÜTUNU ---
with c_icerik:
    
    # 🛒 İŞLEMLER SEKME İÇERİĞİ
    if secilen_menu == "🛒 İŞLEMLER":
        # Taslaktaki gibi Orta Sütun (Okuma/Fiyat) ve Sağ Sütun (Sepet)
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
                        st.session_state.okunan_barkod = okunan
                        st.session_state.scanner_key += 1 
                        st.rerun() 

            if st.session_state.okunan_barkod:
                barkod = st.session_state.okunan_barkod
                filtre = df_stok['Barkod'] == barkod
                urun = df_stok[filtre]
                
                if not urun.empty:
                    u = urun.iloc[0]
                    stok_n = int(float(u['Stok']))
                    
                    st.subheader(f"📦 {u['Urun_Adi']} | 🔖 {barkod}")
                    
                    # 🌟 FİYAT VE STOK YAN YANA (Kompakt Tasarım)
                    c_fiyat, c_stok = st.columns([1.5, 1])
                    with c_fiyat:
                        st.markdown(f"""
                            <div style='text-align: center; padding: 10px; border-radius: 10px; border: 2px solid #ffffff; background-color: #0d1117;'>
                                <div style='font-size: 12px; color: #a3a3a3; text-transform: uppercase;'>Birim Fiyat</div>
                                <div style='font-size: 48px; font-weight: 900; color: #ffffff;'>💰 {u['Fiyat']} TL</div>
                            </div>
                        """, unsafe_allow_html=True)

                    with c_stok:
                        s_renk = "#2ea043" if stok_n > 10 else "#f85149"
                        st.markdown(f"""
                            <div style='text-align: center; padding: 10px; border-radius: 10px; border: 2px solid {s_renk}; background-color: #0d1117;'>
                                <div style='font-size: 12px; color: #a3a3a3; text-transform: uppercase;'>Mevcut Stok</div>
                                <div style='font-size: 36px; font-weight: 900; color: {s_renk};'>{stok_n}</div>
                            </div>
                        """, unsafe_allow_html=True)
                    st.divider()

                    # Marka / Grup alanı
                    mevcut_markalar = sorted(list(df_stok['Marka'].astype(str).unique()))
                    if "Genel" not in mevcut_markalar: mevcut_markalar.append("Genel")
                    
                    m_deger = str(u.get('Marka', 'Genel'))
                    m_index = mevcut_markalar.index(m_deger) if m_deger in mevcut_markalar else mevcut_markalar.index("Genel")
                    
                    c_m1, c_m2 = st.columns(2)
                    m_secim = c_m1.selectbox("Mevcutlardan Seç:", mevcut_markalar, index=m_index, key=f"marka_sel_{barkod}")
                    m_yeni = c_m2.text_input("Veya Yeni Marka Yaz:", key=f"marka_yaz_{barkod}", placeholder="Örn: VİKO")
                    
                    yeni_m = m_yeni.strip().upper() if m_yeni.strip() != "" else m_secim
                    
                    if yeni_m != m_deger:
                        if st.button(f"🏷️ Grubu '{yeni_m}' Yap", key=f"m_save_{barkod}", width="stretch"):
                            df_stok.loc[filtre, 'Marka'] = yeni_m
                            df_stok.loc[filtre, 'Son_guncelleme_tarihi'] = su_an()
                            if kaydet(df_stok, df_user):
                                st.session_state.df_stok = df_stok
                                st.success(f"✅ Ürün {yeni_m} grubuna taşındı!")
                                st.rerun()
                    st.divider()
                    
                    if cihaz_modu == "📱 Mobil (Kamera)":
                        s_mik = st.number_input("Kaç Adet Eklenecek?", min_value=1, max_value=stok_n if stok_n > 0 else 1, value=1)
                        if st.button("🛒 Sepete Fırlat", type="primary", width="stretch"):
                            if stok_n < s_mik: st.error("Yetersiz Stok!")
                            else:
                                mevcut_urun = next((item for item in st.session_state.sepet if item["Barkod"] == barkod), None)
                                if mevcut_urun: mevcut_urun["Adet"] += s_mik
                                else: st.session_state.sepet.append({"Barkod": barkod, "Urun_Adi": u['Urun_Adi'], "Fiyat": float(u['Fiyat']), "Adet": s_mik})
                                st.session_state.okunan_barkod = None 
                                st.rerun()
                                
                    if st.button("🔄 Ekranı Temizle", width="stretch"):
                        st.session_state.okunan_barkod = None
                        st.rerun()

                    st.markdown("<br>", unsafe_allow_html=True) 
                    with st.expander("⚙️ Hızlı Stok / Fiyat İşlemleri"):
                        c_ek, c_fiy = st.columns(2)
                        with c_ek:
                            e_mik = st.number_input("Stok Ekle", 1, value=1, key=f"stok_ekle_{barkod}")
                            if st.button(f"➕ {e_mik} Ekle", key=f"btn_ekle_{barkod}", width="stretch"):
                                df_stok.loc[filtre, 'Stok'] = str(stok_n + e_mik)
                                df_stok.loc[filtre, 'Son_guncelleme_tarihi'] = su_an()
                                if kaydet(df_stok, df_user): 
                                    st.session_state.df_stok = df_stok
                                    st.success("Stok başarıyla eklendi!"); st.rerun()
                        with c_fiy:
                            if st.session_state.rol == "Patron":
                                y_f = st.number_input("Yeni Fiyat", value=float(u['Fiyat']), key=f"fiyat_degis_{barkod}")
                                if st.button("🏷️ Güncelle", key=f"btn_fiyat_{barkod}", width="stretch"):
                                    df_stok.loc[filtre, 'Fiyat'] = str(y_f)
                                    df_stok.loc[filtre, 'Son_guncelleme_tarihi'] = su_an()
                                    if kaydet(df_stok, df_user): 
                                        st.session_state.df_stok = df_stok
                                        st.success("Fiyat güncellendi!"); st.rerun()
                            else: st.info("Yetkiniz yok")
                else:
                    st.warning(f"⚠️ Kayıtsız Barkod: {barkod}")
                    st.info("Bu ürünü hemen envantere ekleyebilirsiniz:")
                    with st.form("yeni_urun"):
                        y_ad = st.text_input("Ürün Adı")
                        y_marka = st.text_input("Marka / Grup (Örn: KALDE)", value="Genel")
                        y_f = st.number_input("Fiyat", min_value=0.0)
                        y_s = st.number_input("Stok", min_value=0)
                        if st.form_submit_button("💾 Kaydet ve Envantere Ekle"):
                            yeni = pd.DataFrame([{"Barkod": barkod, "Urun_Adi": y_ad, "Marka": y_marka.upper(), "Fiyat": str(y_f), "Stok": str(y_s), "Son_satis_sayisi": "0", "Son_guncelleme_tarihi": su_an(), "Son_satis_tarihi": "", "Son_ekleme_tarihi": su_an()}])
                            df_stok = pd.concat([df_stok, yeni], ignore_index=True)
                            if kaydet(df_stok, df_user): 
                                st.session_state.df_stok = df_stok
                                st.session_state.okunan_barkod = None
                                st.rerun()
                            
                    if st.button("🔄 İptal Et (Yeni Barkod Okut)", width="stretch"):
                        st.session_state.okunan_barkod = None
                        st.rerun()

        with col_sepet:
            st.markdown("### 🛍️ Sepet Alanı")
            st.divider()
            
            if len(st.session_state.sepet) == 0:
                st.info("Sepetiniz şu an boş. Sol taraftan ürün okutun.")
            else:
                df_sepet = pd.DataFrame(st.session_state.sepet)
                df_sepet['Toplam (TL)'] = df_sepet['Fiyat'] * df_sepet['Adet']
                
                edited_sepet = st.data_editor(
                    df_sepet, width="stretch", num_rows="dynamic", hide_index=True,
                    disabled=["Barkod", "Urun_Adi", "Fiyat", "Toplam (TL)"],
                    key="sepet_editor"
                )
                st.session_state.sepet = edited_sepet.drop(columns=['Toplam (TL)']).to_dict('records')
                
                genel_toplam = edited_sepet['Toplam (TL)'].sum()
                
                st.markdown(f"""
                    <div style='background-color: #161b22; padding: 20px; border-radius: 12px; border: 2px solid #58a6ff; margin-top: 15px; margin-bottom: 15px; box-shadow: 0 0 15px rgba(88, 166, 255, 0.2);'>
                        <h2 style='margin: 0; color: #ffffff; text-align: center; font-size: 32px;'>
                            Genel Toplam<br><span style='color: #58a6ff;'>{genel_toplam:,.2f} TL</span>
                        </h2>
                    </div>
                """, unsafe_allow_html=True)
                
                if st.button("💳 Satışı Onayla ve Tamamla", type="primary", width="stretch"):
                    with st.spinner("⏳ Stoklar düşülüyor, işlem onaylanıyor..."):
                        time.sleep(1.5) 
                        
                        for item in st.session_state.sepet:
                            b = item['Barkod']
                            satilan_adet = item['Adet']
                            idx = df_stok.index[df_stok['Barkod'] == b]
                            if not idx.empty:
                                i = idx[0]
                                mevcut_stok = float(df_stok.loc[i, 'Stok'])
                                df_stok.loc[i, 'Stok'] = str(max(0, mevcut_stok - satilan_adet))
                                eski_satis = int(float(df_stok.loc[i, 'Son_satis_sayisi'])) if str(df_stok.loc[i, 'Son_satis_sayisi']).strip() != "" else 0
                                df_stok.loc[i, 'Son_satis_sayisi'] = str(eski_satis + satilan_adet)
                                df_stok.loc[i, 'Son_satis_tarihi'] = su_an()
                                df_stok.loc[i, 'Son_guncelleme_tarihi'] = su_an()
                
                        if kaydet(df_stok, df_user):
                            st.session_state.df_stok = df_stok
                            st.session_state.sepet = [] 
                            st.session_state.okunan_barkod = None
                            st.success("✅ İŞLEM ONAYLANDI! Sistem yeni okuma için hazır.")
                            time.sleep(1.5)
                            st.rerun()
                
                if st.button("🗑️ Sepeti Tamamen Boşalt", width="stretch"):
                    st.session_state.sepet = []
                    st.rerun()

    # 📊 ENVANTER SEKME İÇERİĞİ
    elif secilen_menu == "📊 ENVANTER":
        st.markdown("### 📊 Envanter ve Stok Durumu")
        
        if st.session_state.rol == "Patron":
            with st.expander("🚀 MARKAYA GÖRE TOPLU FİYAT GÜNCELLEME (ZAM/İNDİRİM)"):
                c_m1, c_m2, c_m3 = st.columns([2, 1, 1])
                
                mevcut_markalar_panel = [m for m in df_stok['Marka'].unique() if m.strip() != ""]
                if not mevcut_markalar_panel: mevcut_markalar_panel = ["Genel"]
                
                secilen_marka = c_m1.selectbox("İşlem Yapılacak Marka:", mevcut_markalar_panel)
                islem_tipi = c_m2.selectbox("İşlem Tipi:", ["Zam (+)", "İndirim (-)"])
                yuzde = c_m3.number_input("Yüzde Oranı (%)", min_value=0.0, value=10.0, step=1.0)
                
                if st.button(f"⚡ {secilen_marka} Grubuna %{yuzde} {islem_tipi} Uygula", type="primary", width="stretch"):
                    with st.spinner("Fiyatlar hesaplanıyor ve buluta yazılıyor..."):
                        mask = df_stok['Marka'] == secilen_marka
                        carpan = (1 + (yuzde / 100)) if islem_tipi == "Zam (+)" else (1 - (yuzde / 100))
                        
                        eski_fiyatlar = pd.to_numeric(df_stok.loc[mask, 'Fiyat'], errors='coerce').fillna(0)
                        yeni_fiyatlar = (eski_fiyatlar * carpan).round(2)
                        df_stok.loc[mask, 'Fiyat'] = yeni_fiyatlar.astype(str)
                        df_stok.loc[mask, 'Son_guncelleme_tarihi'] = su_an()
                        
                        if kaydet(df_stok, df_user):
                            st.session_state.df_stok = df_stok
                            st.success(f"✅ Başarılı! {secilen_marka} grubundaki {mask.sum()} ürünün fiyatı güncellendi.")
                            time.sleep(2)
                            st.rerun()
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
                df_goster, 
                width="stretch", 
                num_rows="dynamic", 
                hide_index=True,
                disabled=["Barkod", "Son_satis_sayisi", "Son_guncelleme_tarihi", "Son_satis_tarihi", "Son_ekleme_tarihi"],
                key="envanter_editor"
            )
            
            secili_satirlar = edited_df[edited_df['Seç'] == True]
            
            if not secili_satirlar.empty:
                secilen_adet = len(secili_satirlar)
                st.markdown(f"""
                    <div style='background-color: #1f2937; padding: 15px; border-radius: 10px; border-left: 5px solid #3b82f6; margin-bottom: 15px;'>
                        <strong style='color: #60a5fa;'>🎯 {secilen_adet} Adet Ürün Seçildi.</strong> Bu ürünleri bir gruba bağlayabilir veya gruptan çıkarabilirsiniz:
                    </div>
                """, unsafe_allow_html=True)
                
                c_top1, c_top2, c_top3, c_top4 = st.columns([2, 1.5, 1.5, 1.2])
                
                marka_listesi = sorted(list(df_stok['Marka'].astype(str).unique()))
                if "Genel" not in marka_listesi: marka_listesi.append("Genel")
                
                hedef_marka_sec = c_top1.selectbox("Mevcut Gruplardan Seç:", marka_listesi, key="toplu_m_sec")
                hedef_marka_yaz = c_top2.text_input("Veya Yeni Grup Yaz:", placeholder="Örn: EGE YILDIZ", key="toplu_m_yaz")
                
                uygulanacak_marka = hedef_marka_yaz.strip().upper() if hedef_marka_yaz.strip() != "" else hedef_marka_sec
                
                with c_top3:
                    st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
                    if st.button(f"🔄 Gruba Bağla", type="primary", use_container_width=True):
                        with st.spinner(f"{secilen_adet} ürün taşınıyor..."):
                            tasinacak_barkodlar = secili_satirlar['Barkod'].tolist()
                            mask_tasima = df_stok['Barkod'].isin(tasinacak_barkodlar)
                            
                            df_stok.loc[mask_tasima, 'Marka'] = uygulanacak_marka
                            df_stok.loc[mask_tasima, 'Son_guncelleme_tarihi'] = su_an()
                            
                            if kaydet(df_stok, df_user):
                                st.session_state.df_stok = df_stok
                                st.success(f"✅ {secilen_adet} ürün '{uygulanacak_marka}' grubuna bağlandı.")
                                time.sleep(1.5); st.rerun()

                with c_top4:
                    st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
                    if st.button("❌ Gruptan Çıkar", use_container_width=True):
                        with st.spinner("Ürünler gruptan temizleniyor..."):
                            tasinacak_barkodlar = secili_satirlar['Barkod'].tolist()
                            mask_tasima = df_stok['Barkod'].isin(tasinacak_barkodlar)
                            
                            df_stok.loc[mask_tasima, 'Marka'] = "Genel"
                            df_stok.loc[mask_tasima, 'Son_guncelleme_tarihi'] = su_an()
                            
                            if kaydet(df_stok, df_user):
                                st.session_state.df_stok = df_stok
                                st.warning(f"🗑️ {secilen_adet} ürün gruptan çıkarıldı (Genel yapıldı).")
                                time.sleep(1.5); st.rerun()
                st.divider()

            if st.button("💾 Tablodaki Manuel Değişiklikleri Kaydet", width="stretch"):
                with st.spinner("⏳ Değişiklikler buluta işleniyor ve sistem yenileniyor... Lütfen bekleyin."):
                    time.sleep(2) 
                    
                    orijinal_barkodlar = df_goster['Barkod'].tolist()
                    kalan_barkodlar = edited_df['Barkod'].tolist()
                    silinenler = [b for b in orijinal_barkodlar if b not in kalan_barkodlar]
                    
                    df_stok = df_stok[~df_stok['Barkod'].isin(silinenler)]
                    
                    for _, row in edited_df.iterrows():
                        b = row['Barkod']
                        idx = df_stok.index[df_stok['Barkod'] == b]
                        if not idx.empty:
                            i = idx[0]
                            df_stok.loc[i, 'Urun_Adi'] = str(row['Urun_Adi'])
                            df_stok.loc[i, 'Marka'] = str(row.get('Marka', 'Genel')).upper() 
                            df_stok.loc[i, 'Fiyat'] = str(row['Fiyat'])
                            df_stok.loc[i, 'Stok'] = str(row['Stok'])
                            df_stok.loc[i, 'Son_guncelleme_tarihi'] = su_an()
                            
                    if kaydet(df_stok, df_user):
                        st.session_state.df_stok = df_stok
                        st.success("✅ Değişiklikler başarıyla kaydedildi! Tablo güncelleniyor...")
                        time.sleep(1) 
                        st.rerun() 
        else:
            st.info("💡 Sadece ürünleri görüntüleme yetkiniz var.")
            st.dataframe(df_goster, width="stretch", hide_index=True)

    # 👥 YÖNETİM SEKME İÇERİĞİ
    elif secilen_menu == "👥 YÖNETİM":
        st.markdown("### 👥 Personel Yönetimi")
        if st.session_state.rol == "Patron":
            with st.expander("➕ Personel Ekle"):
                ca, cb, cc = st.columns(3)
                nu_ad, nu_sif, nu_rol = ca.text_input("Ad"), cb.text_input("Şifre"), cc.selectbox("Yetki", ["Calisan", "Patron"])
                if st.button("Kaydet"):
                    df_user = pd.concat([df_user, pd.DataFrame([{"Kullanici_Adi": nu_ad, "Sifre": nu_sif, "Rol": nu_rol}])], ignore_index=True)
                    if kaydet(df_stok, df_user): st.session_state.df_user = df_user; st.rerun()
                    
            st.divider()
            st.markdown("#### 🔑 Mevcut Personeller")
            for idx, row in df_user.iterrows():
                cad, cps, csl = st.columns([2,2,1])
                cad.write(f"**{row['Kullanici_Adi']}** ({row['Rol']})")
                n_ps = cps.text_input("Yeni Şifre", key=f"pw_{idx}")
                if cps.button("Güncelle", key=f"btn_up_{idx}"):
                    df_user.at[idx, 'Sifre'] = n_ps
                    if kaydet(df_stok, df_user): 
                        st.session_state.df_user = df_user
                        st.success("Güncellendi"); st.rerun()
                
                if row['Kullanici_Adi'] != st.session_state.user:
                    if csl.button("❌ Sil", key=f"btn_del_{idx}"):
                        df_user = df_user.drop(idx)
                        if kaydet(df_stok, df_user): 
                            st.session_state.df_user = df_user; st.rerun()
        else: st.error("Yetkiniz yok.")

# --- 6. GELİŞTİRİCİ İMZASI (FOOTER) ---
st.markdown("""
<div class="footer">
    Made by <b>Ege Demircioğlu</b> | Powered by <b>Gemini</b> 🚀
</div>
""", unsafe_allow_html=True)
