import streamlit as st
import pandas as pd
from PIL import Image, ImageOps, ImageEnhance
from pyzbar.pyzbar import decode
import os
from datetime import datetime

# --- 1. GÖRSEL TASARIM VE KURUMSAL KİMLİK (CSS) ---
st.set_page_config(page_title="Pro Kasa Elite", layout="wide")

st.markdown("""
    <style>
    /* Ana Arka Plan */
    .stApp { background: radial-gradient(circle at top, #1a1f25, #0d1117); color: #c9d1d9; }
    
    /* GEREKSİZ BEYAZ BOŞLUKLARI SIFIRLAMA */
    .block-container { padding-top: 2rem !important; }
    [data-testid="stHeader"] { display: none; }

    /* STREAMLIT FORM TASARIMI (GİRİŞ EKRANI İÇİN) */
    [data-testid="stForm"] {
        background-color: #161b22;
        border: 1px solid #30363d !important;
        border-radius: 20px;
        padding: 40px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }

    /* FOOTER (İMZA) */
    .footer {
        position: fixed; left: 0; bottom: 0; width: 100%;
        background-color: rgba(13, 17, 23, 0.9); color: #8b949e;
        text-align: center; padding: 10px; font-size: 13px;
        border-top: 1px solid #30363d; backdrop-filter: blur(5px); z-index: 999;
    }

    /* METRİK KARTLARI */
    div[data-testid="stMetric"] {
        background-color: #161b22; border: 1px solid #30363d;
        border-radius: 15px; padding: 15px !important; transition: 0.3s;
    }

    /* MODERN BUTONLAR */
    .stButton>button, [data-testid="stFormSubmitButton"]>button {
        border-radius: 10px; background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
        color: white; font-weight: bold; border: none; height: 3.5em; width: 100%; transition: 0.3s;
    }
    div.stButton > button[kind="secondary"] {
        background: linear-gradient(135deg, #da3633 0%, #f85149 100%);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. VERİ YÖNETİMİ ---
def verileri_yukle():
    dosya = "veriler.xlsx"
    if not os.path.exists(dosya):
        df_s = pd.DataFrame(columns=['Barkod', 'Urun_Adi', 'Fiyat', 'Stok', 'Son_satis_sayisi', 'Son_guncelleme_tarihi'])
        df_u = pd.DataFrame([{"Kullanici_Adi": "Eyup", "Sifre": "1234", "Rol": "Patron"}])
        with pd.ExcelWriter(dosya) as writer:
            df_s.to_excel(writer, sheet_name="Sayfa1", index=False)
            df_u.to_excel(writer, sheet_name="Kullanicilar", index=False)
        return df_s, df_u
    
    with pd.ExcelFile(dosya) as xls:
        df_s = pd.read_excel(xls, "Sayfa1", dtype=str).fillna("0")
        df_u = pd.read_excel(xls, "Kullanicilar", dtype=str).fillna("")
    
    for col in ['Son_satis_sayisi', 'Son_guncelleme_tarihi']:
        if col not in df_s.columns: df_s[col] = "0"
    return df_s, df_u

def kaydet(df_stok, df_user):
    try:
        with pd.ExcelWriter("veriler.xlsx") as writer:
            df_stok.to_excel(writer, sheet_name="Sayfa1", index=False)
            df_user.to_excel(writer, sheet_name="Kullanicilar", index=False)
        return True
    except:
        st.error("🚨 Excel dosyası açık! Lütfen kapatıp tekrar deneyin.")
        return False

# --- 3. OTURUM VE HAFIZA ---
if "okunan_barkod" not in st.session_state: st.session_state.okunan_barkod = None
if "user" not in st.session_state: st.session_state.user = None

df_stok, df_user = verileri_yukle()

# --- 4. MERKEZİ GİRİŞ EKRANI ---
if st.session_state.user is None:
    _, col_login, _ = st.columns([1, 1.5, 1])
    with col_login:
        with st.form("login_form"):
            st.markdown("<h1 style='text-align:center; font-size: 60px; margin:0;'>🏪</h1>", unsafe_allow_html=True)
            st.markdown("<h1 style='text-align:center; color: #58a6ff; margin-top:0;'>Hoşgeldiniz</h1>", unsafe_allow_html=True)
            st.markdown("<p style='text-align:center; color: #8b949e; margin-bottom:20px;'>Lütfen giriş yapın</p>", unsafe_allow_html=True)
            
            k_ad = st.text_input("Kullanıcı Adı", placeholder="Kullanıcı adınız")
            k_sif = st.text_input("Şifre", type="password", placeholder="••••••••")
            
            submit = st.form_submit_button("Sisteme Giriş")
            
            if submit:
                match = df_user[(df_user['Kullanici_Adi'] == k_ad) & (df_user['Sifre'] == k_sif)]
                if not match.empty:
                    st.session_state.user, st.session_state.rol = k_ad, match.iloc[0]['Rol']
                    st.rerun()
                else:
                    st.error("Hatalı kullanıcı adı veya şifre!")
                    
    st.markdown('<div class="footer">Ege Demircioğlu tarafından yapılmıştır</div>', unsafe_allow_html=True)
    st.stop()

# --- 5. ANA PANEL ---
st.sidebar.markdown(f"### 👤 {st.session_state.user}\n**Yetki:** {st.session_state.rol}")
if st.sidebar.button("🔴 Güvenli Çıkış"):
    st.session_state.user = None; st.session_state.okunan_barkod = None; st.rerun()

t1, t2, t3 = st.tabs(["🛒 İşlemler", "📊 Envanter", "👥 Yönetim"])

with t1:
    st.markdown("### 📸 Barkod Tarayıcı")
    
    # KULLANICIYA KAMERA VE DOSYA YÜKLEME SEÇENEĞİ SUNUYORUZ
    secim = st.radio("Okutma Yöntemi:", ["📸 Canlı Kamera", "📁 Dosya Yükle"], horizontal=True)
    
    img_file = None
    if secim == "📸 Canlı Kamera":
        img_file = st.camera_input("Barkodu kameraya gösterin ve çekin")
    else:
        img_file = st.file_uploader("Galeriden barkod fotoğrafı seçin", type=['jpg','png','jpeg'])
    
    # --- YENİ: GÖRÜNTÜ İYİLEŞTİRME VE OKUMA MOTORU ---
    if img_file:
        img = Image.open(img_file)
        
        # 1. Fotoğrafı Siyah-Beyaz yap
        img_gray = ImageOps.grayscale(img)
        
        # 2. Kontrastı %200 artır (Siyah çizgileri daha siyah, beyazları daha beyaz yapar)
        enhancer = ImageEnhance.Contrast(img_gray)
        img_high_contrast = enhancer.enhance(2.0)
        
        # 3. Keskinliği artır (Bulanıklığı azaltır)
        sharpness = ImageEnhance.Sharpness(img_high_contrast)
        img_sharp = sharpness.enhance(2.0)

        # Önce orijinali, bulamazsa griyi, bulamazsa iyileştirilmişi (keskin) dene
        decoded = decode(img) or decode(img_gray) or decode(img_sharp)
        
        if decoded:
            st.session_state.okunan_barkod = decoded[0].data.decode("utf-8").strip("*")
        else:
            st.session_state.okunan_barkod = "HATA"

    if st.session_state.okunan_barkod:
        if st.session_state.okunan_barkod == "HATA":
            st.error("Barkod okunamadı! Lütfen ürünü biraz daha uzaklaştırıp netlemesini bekleyin.")
            if st.button("🔄 Sıfırla ve Tekrar Dene"): st.session_state.okunan_barkod = None; st.rerun()
        else:
            barkod = st.session_state.okunan_barkod
            filtre = df_stok['Barkod'] == barkod
            urun = df_stok[filtre]
            
            if not urun.empty:
                u = urun.iloc[0]
                st.subheader(f"📦 {u['Urun_Adi']} ({barkod})")
                
                stok_n = int(float(u['Stok']))
                m1, m2 = st.columns(2)
                m1.metric("💰 Fiyat", f"{u['Fiyat']} TL")
                m2.metric("📦 Stok", f"{stok_n} Adet", delta="- Kritik!" if stok_n < 5 else None, delta_color="inverse")
                st.caption(f"🕒 Son Güncelleme: {u['Son_guncelleme_tarihi']}")
                st.divider()
                
                now = datetime.now().strftime("%d/%m/%Y %H:%M")
                c_sat, c_ek, c_fiy = st.columns(3)
                
                with c_sat:
                    s_mik = st.number_input("Satış Adedi", 1, 1000000, 1)
                    if st.button(f"💸 {s_mik} Sat"):
                        df_stok.loc[filtre, 'Stok'] = str(stok_n - s_mik)
                        df_stok.loc[filtre, 'Son_satis_sayisi'] = str(s_mik)
                        df_stok.loc[filtre, 'Son_guncelleme_tarihi'] = now
                        if kaydet(df_stok, df_user): st.balloons(); st.rerun()
                
                with c_ek:
                    e_mik = st.number_input("Ekleme Adedi", 1, 1000000, 1)
                    if st.button(f"➕ {e_mik} Ekle"):
                        df_stok.loc[filtre, 'Stok'] = str(stok_n + e_mik)
                        df_stok.loc[filtre, 'Son_guncelleme_tarihi'] = now
                        if kaydet(df_stok, df_user): st.rerun()
                
                with c_fiy:
                    if st.session_state.rol == "Patron":
                        y_f = st.number_input("Yeni Fiyat", value=float(u['Fiyat']))
                        if st.button("🏷️ Güncelle"):
                            df_stok.loc[filtre, 'Fiyat'] = str(y_f)
                            df_stok.loc[filtre, 'Son_guncelleme_tarihi'] = now
                            if kaydet(df_stok, df_user): st.rerun()
                    else: st.info("Yetkiniz yok.")
            else:
                st.warning(f"Kayıtsız Barkod: {barkod}")
                with st.form("yeni_urun"):
                    y_ad = st.text_input("Ürün Adı")
                    y_f = st.number_input("Fiyat", min_value=0.0)
                    y_s = st.number_input("Stok", min_value=0)
                    if st.form_submit_button("💾 Kaydet"):
                        yeni = pd.DataFrame([{"Barkod": barkod, "Urun_Adi": y_ad, "Fiyat": str(y_f), "Stok": str(y_s), "Son_satis_sayisi": "0", "Son_guncelleme_tarihi": datetime.now().strftime("%d/%m/%Y %H:%M")}])
                        df_stok = pd.concat([df_stok, yeni], ignore_index=True)
                        if kaydet(df_stok, df_user): st.rerun()

with t2:
    st.subheader("📊 Tüm Ürün Listesi")
    st.dataframe(df_stok, width="stretch", hide_index=True)

with t3:
    if st.session_state.rol == "Patron":
        st.subheader("👥 Personel ve Yetki Yönetimi")
        
        with st.expander("➕ Yeni Personel Ekle"):
            ca, cb, cc = st.columns(3)
            nu_ad = ca.text_input("Kullanıcı Adı")
            nu_sif = cb.text_input("Şifre")
            nu_rol = cc.selectbox("Yetki Seviyesi", ["Calisan", "Patron"])
            if st.button("Kaydet", key="pers_kaydet"):
                y_u = pd.DataFrame([{"Kullanici_Adi": nu_ad, "Sifre": nu_sif, "Rol": nu_rol}])
                df_user = pd.concat([df_user, y_u], ignore_index=True)
                if kaydet(df_stok, df_user): st.rerun()
        
        st.divider()
        for idx, row in df_user.iterrows():
            cad, cps, csl = st.columns([2,2,1])
            cad.write(f"**{row['Kullanici_Adi']}** ({row['Rol']})")
            n_ps = cps.text_input("Yeni Şifre", key=f"pw_{idx}", placeholder="Şifre Değiştir")
            if cps.button("Güncelle", key=f"btn_up_{idx}"):
                df_user.at[idx, 'Sifre'] = n_ps
                if kaydet(df_stok, df_user): st.success("Güncellendi"); st.rerun()
            
            if row['Kullanici_Adi'] != st.session_state.user:
                if csl.button("❌ Sil", key=f"btn_del_{idx}", type="secondary"):
                    df_user = df_user.drop(idx)
                    if kaydet(df_stok, df_user): st.rerun()
    else:
        st.error("Bu bölüm sadece Patron yetkisine açıktır.")

# --- İMZA (FOOTER) ---
st.markdown('<div class="footer">Ege Demircioğlu tarafından yapılmıştır</div>', unsafe_allow_html=True)