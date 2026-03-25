import streamlit as st
import pandas as pd
import json
import gspread
from datetime import datetime
from streamlit_barcode_reader import barcode_reader  # YENİ CANLI OKUMA MOTORUMUZ 🚀

# --- 1. GÖRSEL TASARIM VE KURUMSAL KİMLİK (CSS) ---
st.set_page_config(page_title="Pro Kasa Elite Cloud", layout="wide")

st.markdown("""
    <style>
    .stApp { background: radial-gradient(circle at top, #1a1f25, #0d1117); color: #c9d1d9; }
    .block-container { padding-top: 2rem !important; }
    [data-testid="stHeader"] { display: none; }
    [data-testid="stForm"] {
        background-color: #161b22; border: 1px solid #30363d !important;
        border-radius: 20px; padding: 40px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);
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
    .stButton>button, [data-testid="stFormSubmitButton"]>button {
        border-radius: 10px; background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
        color: white; font-weight: bold; border: none; height: 3.5em; width: 100%; transition: 0.3s;
    }
    div.stButton > button[kind="secondary"] {
        background: linear-gradient(135deg, #da3633 0%, #f85149 100%);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. GOOGLE SHEETS BAĞLANTISI VE VERİ YÖNETİMİ ---
@st.cache_resource
def get_gspread_client():
    try:
        creds_json = st.secrets["gcp_credentials"]
        creds_dict = json.loads(creds_json)
        gc = gspread.service_account_from_dict(creds_dict)
        return gc
    except Exception as e:
        st.error("🚨 Google bağlantı anahtarı (Secrets) hatalı veya eksik!")
        st.stop()

gc = get_gspread_client()

# ⚠️ LİNKİ BURAYA YAPIŞTIR:
SHEET_URL = "https://docs.google.com/spreadsheets/d/1BxOPA_JDtFYLZqxOVK3GCW1ZBh2dINF5HnqD0TbZ4h8/edit?gid=0#gid=0" 

def verileri_yukle():
    try:
        sh = gc.open_by_url(SHEET_URL)
        
        worksheet_s = sh.worksheet("Sayfa1")
        records_s = worksheet_s.get_all_records()
        if not records_s:
            df_s = pd.DataFrame(columns=['Barkod', 'Urun_Adi', 'Fiyat', 'Stok', 'Son_satis_sayisi', 'Son_guncelleme_tarihi'])
        else:
            df_s = pd.DataFrame(records_s).astype(str)
            
        worksheet_u = sh.worksheet("Kullanicilar")
        records_u = worksheet_u.get_all_records()
        if not records_u:
            df_u = pd.DataFrame([{"Kullanici_Adi": "Eyup", "Sifre": "1234", "Rol": "Patron"}])
            worksheet_u.update([df_u.columns.values.tolist()] + df_u.values.tolist())
        else:
            df_u = pd.DataFrame(records_u).astype(str)
            
        return df_s, df_u
    except Exception as e:
        st.error(f"🚨 Tabloya ulaşılamadı! Linki ve paylaşım yetkisini kontrol edin. Detay: {e}")
        st.stop()

def kaydet(df_stok, df_user):
    try:
        sh = gc.open_by_url(SHEET_URL)
        
        df_stok_temiz = df_stok.astype(str).fillna("")
        df_user_temiz = df_user.astype(str).fillna("")
        
        liste_stok = [df_stok_temiz.columns.values.tolist()] + df_stok_temiz.values.tolist()
        liste_user = [df_user_temiz.columns.values.tolist()] + df_user_temiz.values.tolist()
        
        worksheet_s = sh.worksheet("Sayfa1")
        worksheet_s.clear()
        worksheet_s.update(values=liste_stok)
        
        worksheet_u = sh.worksheet("Kullanicilar")
        worksheet_u.clear()
        worksheet_u.update(values=liste_user)
        return True
    except Exception as e:
        st.error(f"🚨 Google API Hatası: Veri kaydedilemedi. Detay: {e}")
        return False

# --- 3. OTURUM VE AKILLI HAFIZA ---
if "okunan_barkod" not in st.session_state: st.session_state.okunan_barkod = None
if "user" not in st.session_state: st.session_state.user = None

if "veriler_cekildi" not in st.session_state:
    df_s_temp, df_u_temp = verileri_yukle()
    st.session_state.df_stok = df_s_temp
    st.session_state.df_user = df_u_temp
    st.session_state.veriler_cekildi = True

df_stok = st.session_state.df_stok
df_user = st.session_state.df_user

# --- 4. MERKEZİ GİRİŞ EKRANI ---
if st.session_state.user is None:
    _, col_login, _ = st.columns([1, 1.5, 1])
    with col_login:
        with st.form("login_form"):
            st.markdown("<h1 style='text-align:center; font-size: 60px; margin:0;'>🏪☁️</h1>", unsafe_allow_html=True)
            st.markdown("<h1 style='text-align:center; color: #58a6ff; margin-top:0;'>Hoşgeldiniz</h1>", unsafe_allow_html=True)
            st.markdown("<p style='text-align:center; color: #8b949e; margin-bottom:20px;'>Pro Kasa Elite Cloud'a Giriş Yapın</p>", unsafe_allow_html=True)
            
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
                    
    st.markdown('<div class="footer">Ege Demircioğlu tarafından yapılmıştır (Cloud Edition)</div>', unsafe_allow_html=True)
    st.stop()

# --- 5. ANA PANEL (MOBİL UYUMLU ÜST BAR VE YENİLE BUTONU) ---
c_bilgi, c_yenile, c_cikis = st.columns([2, 1, 1])
with c_bilgi:
    st.markdown(f"### 👤 **{st.session_state.user}** | 🟢 Yetki: {st.session_state.rol}")
with c_yenile:
    if st.button("🔄 Verileri Yenile", use_container_width=True):
        if "veriler_cekildi" in st.session_state:
            del st.session_state.veriler_cekildi
        st.session_state.okunan_barkod = None
        st.rerun()
with c_cikis:
    if st.button("🔴 Çıkış", use_container_width=True):
        st.session_state.clear()
        st.rerun()

st.divider()

t1, t2, t3 = st.tabs(["🛒 İşlemler", "📊 Envanter", "👥 Yönetim"])

# --- SEKME 1: İŞLEMLER (YENİ NESİL CANLI KAMERA) ---
with t1:
    st.markdown("### 📸 Canlı Barkod Tarayıcı")
    st.info("💡 Kamerayı barkoda doğru tutun, saniyeler içinde otomatik olarak algılanacaktır. (Fotoğraf çekmenize gerek yok)")
    
    # Yeni Canlı Okuyucu Motorunu Çağırıyoruz
    okunan_deger = barcode_reader()
    
    if okunan_deger:
        st.session_state.okunan_barkod = okunan_deger
        
    if st.session_state.okunan_barkod:
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
                    if s_mik > stok_n:
                        st.error(f"⚠️ Yetersiz stok! Elinizde sadece {stok_n} adet var.")
                    else:
                        df_stok.loc[filtre, 'Stok'] = str(stok_n - s_mik)
                        df_stok.loc[filtre, 'Son_satis_sayisi'] = str(s_mik)
                        df_stok.loc[filtre, 'Son_guncelleme_tarihi'] = now
                        if kaydet(df_stok, df_user): 
                            st.session_state.df_stok = df_stok
                            st.session_state.okunan_barkod = None
                            st.balloons(); st.rerun()
            
            with c_ek:
                e_mik = st.number_input("Ekleme Adedi", 1, 1000000, 1)
                if st.button(f"➕ {e_mik} Ekle"):
                    df_stok.loc[filtre, 'Stok'] = str(stok_n + e_mik)
                    df_stok.loc[filtre, 'Son_guncelleme_tarihi'] = now
                    if kaydet(df_stok, df_user): 
                        st.session_state.df_stok = df_stok
                        st.session_state.okunan_barkod = None
                        st.rerun()
            
            with c_fiy:
                if st.session_state.rol == "Patron":
                    y_f = st.number_input("Yeni Fiyat", value=float(u['Fiyat']))
                    if st.button("🏷️ Güncelle"):
                        df_stok.loc[filtre, 'Fiyat'] = str(y_f)
                        df_stok.loc[filtre, 'Son_guncelleme_tarihi'] = now
                        if kaydet(df_stok, df_user): 
                            st.session_state.df_stok = df_stok
                            st.rerun()
                else: st.info("Yetkiniz yok.")
            
            st.divider()
            if st.button("🔄 Yeni Ürün Okut"):
                st.session_state.okunan_barkod = None
                st.rerun()
                
        else:
            st.warning(f"Kayıtsız Barkod: {barkod}")
            with st.form("yeni_urun"):
                y_ad = st.text_input("Ürün Adı")
                y_f = st.number_input("Fiyat", min_value=0.0)
                y_s = st.number_input("Stok", min_value=0)
                if st.form_submit_button("💾 Buluta Kaydet"):
                    yeni = pd.DataFrame([{"Barkod": barkod, "Urun_Adi": y_ad, "Fiyat": str(y_f), "Stok": str(y_s), "Son_satis_sayisi": "0", "Son_guncelleme_tarihi": datetime.now().strftime("%d/%m/%Y %H:%M")}])
                    df_stok = pd.concat([df_stok, yeni], ignore_index=True)
                    if kaydet(df_stok, df_user): 
                        st.session_state.df_stok = df_stok
                        st.session_state.okunan_barkod = None
                        st.rerun()
            
            if st.button("🔄 İptal ve Yeniden Okut"):
                st.session_state.okunan_barkod = None
                st.rerun()

# --- SEKME 2: ENVANTER VE HIZLI DÜZENLEME ---
with t2:
    st.subheader("📊 Canlı Envanter ve Arama")
    
    arama = st.text_input("🔍 Ürün Adı veya Barkod ile Ara:", "")
    if arama:
        mask = df_stok['Urun_Adi'].str.contains(arama, case=False, na=False) | df_stok['Barkod'].str.contains(arama, case=False, na=False)
        df_goster = df_stok[mask]
    else:
        df_goster = df_stok

    st.dataframe(df_goster, width="stretch", hide_index=True)
    st.info("Bu liste cihazın hafızasından gelmektedir. En güncel hali için 'Verileri Yenile' butonunu kullanabilirsiniz.")

    if st.session_state.rol == "Patron":
        st.divider()
        st.markdown("#### ⚡ Hızlı Düzenleme Paneli (Patron Özel)")
        
        urun_listesi = ["Seçiniz..."] + df_stok['Urun_Adi'].tolist()
        secilen_urun_adi = st.selectbox("Düzenlemek istediğiniz ürünü seçin:", urun_listesi)
        
        if secilen_urun_adi != "Seçiniz...":
            idx = df_stok.index[df_stok['Urun_Adi'] == secilen_urun_adi].tolist()[0]
            urun_verisi = df_stok.loc[idx]
            
            with st.form(key=f"hizli_guncelleme_{idx}"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    yeni_isim = st.text_input("Ürün Adı", value=str(urun_verisi['Urun_Adi']))
                with c2:
                    yeni_fiyat = st.number_input("Yeni Fiyat (TL)", value=float(urun_verisi['Fiyat']))
                with c3:
                    yeni_stok = st.number_input("Yeni Stok", value=int(float(urun_verisi['Stok'])))
                
                if st.form_submit_button("💾 Değişiklikleri Buluta Kaydet"):
                    df_stok.at[idx, 'Urun_Adi'] = str(yeni_isim)
                    df_stok.at[idx, 'Fiyat'] = str(yeni_fiyat)
                    df_stok.at[idx, 'Stok'] = str(yeni_stok)
                    df_stok.at[idx, 'Son_guncelleme_tarihi'] = datetime.now().strftime("%d/%m/%Y %H:%M")
                    
                    if kaydet(df_stok, df_user):
                        st.session_state.df_stok = df_stok
                        st.success(f"✅ Ürün başarıyla güncellendi!")
                        st.rerun()

# --- SEKME 3: YÖNETİM ---
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
                if kaydet(df_stok, df_user): 
                    st.session_state.df_user = df_user
                    st.rerun()
        
        st.divider()
        for idx, row in df_user.iterrows():
            cad, cps, csl = st.columns([2,2,1])
            cad.write(f"**{row['Kullanici_Adi']}** ({row['Rol']})")
            n_ps = cps.text_input("Yeni Şifre", key=f"pw_{idx}", placeholder="Şifre Değiştir")
            if cps.button("Güncelle", key=f"btn_up_{idx}"):
                df_user.at[idx, 'Sifre'] = n_ps
                if kaydet(df_stok, df_user): 
                    st.session_state.df_user = df_user
                    st.success("Güncellendi"); st.rerun()
            
            if row['Kullanici_Adi'] != st.session_state.user:
                if csl.button("❌ Sil", key=f"btn_del_{idx}", type="secondary"):
                    df_user = df_user.drop(idx)
                    if kaydet(df_stok, df_user): 
                        st.session_state.df_user = df_user
                        st.rerun()
    else:
        st.error("Bu bölüm sadece Patron yetkisine açıktır.")

# --- İMZA (FOOTER) ---
st.markdown('<div class="footer">Ege Demircioğlu tarafından yapılmıştır (Cloud Edition)</div>', unsafe_allow_html=True)
