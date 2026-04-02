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
    .block-container { padding-top: 2rem !important; }
    [data-testid="stHeader"] { display: none; }
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
    /* 🌟 LOGO KUSURSUZ MERKEZLEME VE BÜYÜTME 🌟 */
    [data-testid="stImage"] { 
        display: flex; 
        justify-content: center !important; /* Yatayda zorla ortala */
        align-items: center !important; 
        width: 100%; /* Formun tam genişliğini kullan */
        margin-top: 15px; /* Üstten hoş bir boşluk */
        margin-bottom: -10px; 
    }
    
    [data-testid="stImage"] img { 
        border-radius: 50%; 
        width: 180px !important; /* BÜYÜTÜLDÜ (Eski: 130px) */
        height: 180px !important; /* BÜYÜTÜLDÜ (Eski: 130px) */
        object-fit: cover; 
        border: 3px solid #58a6ff; 
        box-shadow: 0 0 20px rgba(88, 166, 255, 0.5); /* Işık arttırıldı */
    }
    </style>
    """, unsafe_allow_html=True)

# 🇹🇷 TÜRKİYE SAATİ AYARI
tr_timezone = pytz.timezone('Europe/Istanbul')
def su_an():
    return datetime.now(tr_timezone).strftime("%d/%m/%Y %H:%M")

# 🍪 ÇEREZ (BENİ HATIRLA) YÖNETİCİSİ
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
    
    # Senin Excel tablonla birebir uyumlu
    if 'Son_satis_tarihi' not in df_s.columns: df_s['Son_satis_tarihi'] = ""
    if 'Son_ekleme_tarihi' not in df_s.columns: df_s['Son_ekleme_tarihi'] = ""
    
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

# VERİLERİ ÇEKİYORUZ
if "veriler_cekildi" not in st.session_state:
    df_s_temp, df_u_temp = verileri_yukle()
    st.session_state.df_stok = df_s_temp
    st.session_state.df_user = df_u_temp
    st.session_state.veriler_cekildi = True

# 🕵️‍♂️ BENİ HATIRLA (Otomatik Giriş Kontrolü - Hayalet Çerez Çözümü)
if st.session_state.user is None and not st.session_state.get("cikis_yapildi", False):
    kayitli_kullanici = cookie_manager.get(cookie="kullanici_adi")
    if kayitli_kullanici:
        match = st.session_state.df_user[st.session_state.df_user['Kullanici_Adi'] == kayitli_kullanici]
        if not match.empty:
            st.session_state.user = kayitli_kullanici
            st.session_state.rol = match.iloc[0]['Rol']
            st.rerun()

# 🚨 ÖZEL CANLI OKUYUCU EKLENTİSİ
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
            
            // HAZIR ARAYÜZ YERİNE DOĞRUDAN ÇEKİRDEK MOTORU KULLANIYORUZ
            var html5QrCode = new Html5Qrcode("reader");
            
            var config = { 
                fps: 15, 
                qrbox: {width: 250, height: 250},
                formatsToSupport: [ 
                    Html5QrcodeSupportedFormats.QR_CODE,  
                    Html5QrcodeSupportedFormats.CODE_128, 
                    Html5QrcodeSupportedFormats.CODE_39,  
                    Html5QrcodeSupportedFormats.EAN_13    
                ]
            };

            // Direkt olarak arka kamerayı (environment) başlat
            html5QrCode.start(
                { facingMode: "environment" }, 
                config,
                function(decodedText) {
                    playBeep();
                    // Okuma başarılıysa kamerayı kapat ve veriyi Python'a yolla
                    html5QrCode.stop().then(function() {
                        setComponentValue(decodedText);
                    });
                },
                function(errorMessage) {
                    // Arka plandaki okuyamama hatalarını gizle, log'u şişirmesin
                }
            ).catch(function(err) {
                // EĞER KAMERA İZNİ YOKSA VEYA HATA VERİRSE: Müşteriye net bir mesaj göster
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
            
            # 🌟 LOGOYU DİREKT FORMA KOYUYORUZ (Merkezlemeyi CSS Hallediyor)
            import os
            if os.path.exists("logo.png"):
                st.image("logo.png")
            else:
                # Logo yoksa bile aynı büyüklükte ve ortada duran bir UI hazırladık
                st.markdown("""
                    <div style='display: flex; justify-content: center; align-items: center; width: 100%; margin-top: 15px;'>
                        <div style='
                            border-radius: 50%;
                            width: 180px;
                            height: 180px;
                            background-color: #161b22;
                            border: 3px solid #58a6ff;
                            box-shadow: 0 0 20px rgba(88, 166, 255, 0.5);
                            display: flex;
                            justify-content: center;
                            align-items: center;
                            font-size: 70px;
                        '>🏪</div>
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
                    
                    if "cikis_yapildi" in st.session_state:
                        del st.session_state["cikis_yapildi"]
                    
                    if beni_hatirla:
                        cookie_manager.set("kullanici_adi", k_ad, max_age=30*24*60*60) 
                        import time
                        time.sleep(1) 
                    
                    st.rerun()
                else: st.error("Hatalı Giriş!")
    st.stop()
# --- 5. ANA PANEL (SADECE GİRİŞ YAPILINCA BURAYA GEÇER) ---
df_stok = st.session_state.df_stok
df_user = st.session_state.df_user

c_bilgi, c_yenile, c_cikis = st.columns([2, 1, 1])
with c_bilgi: st.markdown(f"👤 **{st.session_state.user}** | 🟢 Yetki: {st.session_state.rol}")

with c_yenile:
    if st.button("🔄 Verileri Yenile", width="stretch"):
        del st.session_state.veriler_cekildi; st.session_state.okunan_barkod = None; st.rerun()

with c_cikis:
    if st.button("🔴 Çıkış", width="stretch"):
        
        # 1. GÜVENLİK KONTROLÜ: Çerez gerçekten var mı diye bak, varsa sil!
        if cookie_manager.get("kullanici_adi") is not None:
            cookie_manager.delete("kullanici_adi")
            
        # 2. GARANTİ (ÇİFT DİKİŞ): Çerez yoksa bile var sayıp içini boşaltıyoruz
        cookie_manager.set("kullanici_adi", "", max_age=0) 
        
        # 3. HAFIZAYI TEMİZLE
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.session_state.cikis_yapildi = True
        
        # 4. TELEFONA ZAMAN TANI
        import time
        time.sleep(1)
        
        st.rerun()

st.divider()
t1, t2, t3 = st.tabs(["🛒 İşlemler", "📊 Envanter", "👥 Yönetim"])

# --- SEKME 1: İŞLEMLER ---
with t1:
    st.markdown("### 🛒 Hızlı Kasa ve Satış Ekranı")
    
    # EKRANI İKİYE BÖLÜYORUZ: SOLDA OKUYUCU, SAĞDA SEPET
    col_kasa, col_sepet = st.columns([1.2, 1])
    
    # --- SOL TARAF: BARKOD OKUMA VE SEPETE ATMA ---
    with col_kasa:
        if st.session_state.okunan_barkod is None:
            st.info("💡 Kameraya izin verin ve barkodu çerçeveye oturtun.")
            okunan = canli_okuyucu(key=f"kamera_{st.session_state.scanner_key}")
            if okunan:
                st.session_state.okunan_barkod = okunan
                st.session_state.scanner_key += 1 
                st.rerun() 
        else:
            barkod = st.session_state.okunan_barkod
            filtre = df_stok['Barkod'] == barkod
            urun = df_stok[filtre]
            
            if not urun.empty:
                u = urun.iloc[0]
                st.success(f"✅ BİP! Barkod Okundu")
                st.subheader(f"📦 {u['Urun_Adi']}")
                st.caption(f"Barkod: {barkod} | Mevcut Stok: {int(float(u['Stok']))} Adet")
                
               stok_n = int(float(u['Stok']))
    
    # 🌟 YENİ NEON FİYAT ETİKETİ BÜYÜSÜ 🌟
    st.markdown(f"""
        <div style='
            text-align: center; 
            padding: 15px; 
            border-radius: 12px; 
            border: 2px solid #ffffff; 
            box-shadow: 0 0 20px rgba(255, 255, 255, 0.6), inset 0 0 10px rgba(255, 255, 255, 0.2); 
            background-color: #0d1117; 
            margin: 15px 0;
        '>
            <div style='font-size: 16px; color: #a3a3a3; margin-bottom: 5px; text-transform: uppercase; letter-spacing: 1px;'>Birim Fiyat</div>
            <div style='
                font-size: 42px; 
                font-weight: 900; 
                color: #ffffff; 
                text-shadow: 0 0 10px #ffffff, 0 0 25px rgba(255, 255, 255, 0.8); 
                letter-spacing: 2px;
            '>💰 {u['Fiyat']} TL</div>
        </div>
    """, unsafe_allow_html=True)
    
    st.divider()
                
                # --- 1. SEPETE EKLEME KISMI ---
                s_mik = st.number_input("Kaç Adet Eklenecek?", min_value=1, max_value=stok_n if stok_n > 0 else 1, value=1)
                
                if st.button("🛒 Sepete Fırlat", type="primary", width="stretch"):
                    if stok_n < s_mik:
                        st.error("Yetersiz Stok!")
                    else:
                        mevcut_urun = next((item for item in st.session_state.sepet if item["Barkod"] == barkod), None)
                        if mevcut_urun:
                            mevcut_urun["Adet"] += s_mik
                        else:
                            st.session_state.sepet.append({
                                "Barkod": barkod,
                                "Urun_Adi": u['Urun_Adi'],
                                "Fiyat": float(u['Fiyat']),
                                "Adet": s_mik
                            })
                        st.session_state.okunan_barkod = None 
                        st.rerun()
                        
                if st.button("🔄 İptal Et (Yeni Barkod Okut)", width="stretch"):
                    st.session_state.okunan_barkod = None
                    st.rerun()

                # --- 2. HIZLI STOK VE FİYAT GÜNCELLEME KISMI (GERİ GELDİ!) ---
                st.markdown("<br>", unsafe_allow_html=True) # Ufak bir boşluk
                with st.expander("⚙️ Hızlı Stok / Fiyat İşlemleri"):
                    c_ek, c_fiy = st.columns(2)
                    with c_ek:
                        e_mik = st.number_input("Stok Ekle", 1, value=1, key=f"stok_ekle_{barkod}")
                        if st.button(f"➕ {e_mik} Ekle", key=f"btn_ekle_{barkod}", width="stretch"):
                            df_stok.loc[filtre, 'Stok'] = str(stok_n + e_mik)
                            df_stok.loc[filtre, 'Son_guncelleme_tarihi'] = su_an()
                            if kaydet(df_stok, df_user): 
                                st.session_state.df_stok = df_stok
                                st.success("Stok başarıyla eklendi!")
                                st.rerun()
                    with c_fiy:
                        if st.session_state.rol == "Patron":
                            y_f = st.number_input("Yeni Fiyat", value=float(u['Fiyat']), key=f"fiyat_degis_{barkod}")
                            if st.button("🏷️ Güncelle", key=f"btn_fiyat_{barkod}", width="stretch"):
                                df_stok.loc[filtre, 'Fiyat'] = str(y_f)
                                df_stok.loc[filtre, 'Son_guncelleme_tarihi'] = su_an()
                                if kaydet(df_stok, df_user): 
                                    st.session_state.df_stok = df_stok
                                    st.success("Fiyat güncellendi!")
                                    st.rerun()
                        else: 
                            st.info("Yetkiniz yok")
            else:
                st.warning(f"⚠️ Kayıtsız Barkod: {barkod}")
                st.info("Bu ürünü hemen envantere ekleyebilirsiniz:")
                with st.form("yeni_urun"):
                    y_ad = st.text_input("Ürün Adı")
                    y_f = st.number_input("Fiyat", min_value=0.0)
                    y_s = st.number_input("Stok", min_value=0)
                    if st.form_submit_button("💾 Kaydet ve Envantere Ekle"):
                        yeni = pd.DataFrame([{
                            "Barkod": barkod, "Urun_Adi": y_ad, "Fiyat": str(y_f), "Stok": str(y_s), 
                            "Son_satis_sayisi": "0", "Son_guncelleme_tarihi": su_an(),
                            "Son_satis_tarihi": "", "Son_ekleme_tarihi": su_an() 
                        }])
                        df_stok = pd.concat([df_stok, yeni], ignore_index=True)
                        if kaydet(df_stok, df_user): 
                            st.session_state.df_stok = df_stok
                            st.session_state.okunan_barkod = None
                            st.rerun()
                            
                if st.button("🔄 İptal Et (Yeni Barkod Okut)", width="stretch"):
                    st.session_state.okunan_barkod = None
                    st.rerun()

    # --- SAĞ TARAF: CANLI SEPET VE ONAY EKRANI ---
    with col_sepet:
        st.subheader("🛍️ Sepetiniz")
        
        if len(st.session_state.sepet) == 0:
            st.info("Sepetiniz şu an boş. Sol taraftan ürün okutun.")
        else:
            # Sepetteki listeyi DataFrame'e çevirip ekranda gösteriyoruz
            df_sepet = pd.DataFrame(st.session_state.sepet)
            df_sepet['Toplam (TL)'] = df_sepet['Fiyat'] * df_sepet['Adet']
            
            st.markdown("💡 *Adet sayılarına çift tıklayıp değiştirebilir, satırı seçip 'Delete' ile silebilirsiniz.*")
            
            # SİHİRLİ TABLO: Müşteri anında adet değiştirirse burası algılar
            edited_sepet = st.data_editor(
                df_sepet,
                width="stretch",
                num_rows="dynamic", # Silmeye izin ver
                hide_index=True,
                disabled=["Barkod", "Urun_Adi", "Fiyat", "Toplam (TL)"], # Sadece Adet değiştirilebilir
                key="sepet_editor"
            )
            
            # Kullanıcı tabloda değişiklik yaptıysa bunu hafızaya (sepetimize) geri kaydet
            st.session_state.sepet = edited_sepet.drop(columns=['Toplam (TL)']).to_dict('records')
            
            # GENEL TOPLAM HESAPLAMA
            genel_toplam = edited_sepet['Toplam (TL)'].sum()
            st.error(f"### 💳 Ödenecek Tutar: {genel_toplam:,.2f} TL")
            st.divider()
            
            # SATIŞI ONAYLAMA (VERİTABANINDAN DÜŞME)
            if st.button("✅ Satışı Onayla ve Tamamla", type="primary", width="stretch"):
                # Sepetteki her ürünü tek tek stoktan düşüyoruz
                for item in st.session_state.sepet:
                    b = item['Barkod']
                    satilan_adet = item['Adet']
                    
                    idx = df_stok.index[df_stok['Barkod'] == b]
                    if not idx.empty:
                        i = idx[0]
                        mevcut_stok = float(df_stok.loc[i, 'Stok'])
                        df_stok.loc[i, 'Stok'] = str(mevcut_stok - satilan_adet)
                        df_stok.loc[i, 'Son_satis_tarihi'] = su_an()
                        df_stok.loc[i, 'Son_guncelleme_tarihi'] = su_an()
                
                # Tüm stok düşüşlerini Google Sheets'e tek seferde kaydet
                if kaydet(df_stok, df_user):
                    st.session_state.df_stok = df_stok
                    st.session_state.sepet = [] # Sepeti boşalt
                    st.success("🎉 Satış Başarılı! Stoklar güncellendi.")
                    import time
                    time.sleep(1.5) # Mesajı 1.5 saniye görsünler
                    st.rerun()
            
            if st.button("🗑️ Sepeti Tamamen Boşalt", width="stretch"):
                st.session_state.sepet = []
                st.rerun()

# --- SEKME 2: ENVANTER ---
with t2:
    st.subheader("📊 Envanter ve Stok Durumu")
    
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

    # 🚨 SİHİRLİ DOKUNUŞ: Tablo ekrana basılmadan hemen önce gizli numaraları (index) sıfırlıyoruz ki Streamlit ağlamasın!
    df_goster = df_goster.reset_index(drop=True)

    if st.session_state.rol == "Patron":
        st.info("💡 **EXCEL MODU:** Hücrelere çift tıklayarak fiyat/stok değiştirebilirsiniz. Silmek için satırı seçip Delete'e basın.")
        
        edited_df = st.data_editor(
            df_goster, width="stretch", num_rows="dynamic", hide_index=True,
            disabled=["Barkod", "Son_satis_sayisi", "Son_guncelleme_tarihi", "Son_satis_tarihi", "Son_ekleme_tarihi"],
            key="envanter_editor"
        )
        
        if st.button("💾 Tüm Değişiklikleri Buluta Kaydet", type="primary", width="stretch"):
            with st.spinner("⏳ Değişiklikler buluta işleniyor ve sistem yenileniyor... Lütfen bekleyin."):
                
                import time
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
# --- SEKME 3: YÖNETİM ---
with t3:
    if st.session_state.rol == "Patron":
        st.subheader("👥 Personel Yönetimi")
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
