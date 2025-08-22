import os
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from filelock import FileLock

# ====== 設定 ======
st.set_page_config(page_title="どこから来ましたか？", layout="centered")

# 書き込み可能な場所に保存（Cloudでも安全）
DATA_DIR = os.environ.get("STREAMLIT_DATA_DIR", "/tmp")
os.makedirs(DATA_DIR, exist_ok=True)
CSV_FILE = os.path.join(DATA_DIR, "locations.csv")
LOCK_FILE = os.path.join(DATA_DIR, "locations.csv.lock")

ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "santi111")  # 本番はsecretsに入れる

st.title("📍 あなたはどこから来ましたか？（関東マップ）")

# ====== ファイル初期化 ======
try:
    if not os.path.exists(CSV_FILE):
        with FileLock(LOCK_FILE, timeout=10):
            pd.DataFrame(columns=["place", "lat", "lon"]).to_csv(CSV_FILE, index=False)
except Exception as e:
    st.error("初期化時にエラーが発生しました。")
    st.exception(e)
    st.stop()

# ====== Geocoder 準備（レート制限 & タイムアウト）======
@st.cache_resource
def get_geocoder():
    # user_agent にメールを入れるとブロックされにくい（Nominatimのポリシー）
    return Nominatim(user_agent="location_app (youremail@example.com)", timeout=10)

geocoder = get_geocoder()
geocode = RateLimiter(geocoder.geocode, min_delay_seconds=1.0, swallow_exceptions=False)

# ====== 入力フォーム ======
with st.form("location_form"):
    place = st.text_input("都道府県・市区町村・駅名など（例：埼玉県さいたま市、渋谷駅）")
    submitted = st.form_submit_button("地図に追加する")

    if submitted and place:
        try:
            location = geocode(place + ", Japan")
            if location:
                df_new = pd.DataFrame(
                    {"place": [place], "lat": [location.latitude], "lon": [location.longitude]}
                )
                with FileLock(LOCK_FILE, timeout=10):
                    # ヘッダ有無をファイル存在で制御
                    write_header = not os.path.exists(CSV_FILE) or os.path.getsize(CSV_FILE) == 0
                    df_new.to_csv(CSV_FILE, mode="a", header=write_header, index=False)
                st.success(f"✅ {place} を地図に追加しました！")
            else:
                st.warning("場所が見つかりませんでした。別の表記でもお試しください。")
        except Exception as e:
            st.error("エラーが発生しました。詳細は下記をご確認ください。")
            st.exception(e)  # 原因特定に有用
            st.stop()

# ====== CSV読み込み ======
try:
    with FileLock(LOCK_FILE, timeout=10):
        if os.path.exists(CSV_FILE) and os.path.getsize(CSV_FILE) > 0:
            df = pd.read_csv(CSV_FILE)
        else:
            df = pd.DataFrame(columns=["place", "lat", "lon"])
except Exception as e:
    st.error("CSV読み込み時にエラーが発生しました。")
    st.exception(e)
    st.stop()

# ====== 地図描画 ======
m = folium.Map(location=[35.6895, 139.6917], zoom_start=8)  # 関東中心
for _, row in df.iterrows():
    try:
        folium.Marker([float(row["lat"]), float(row["lon"])], tooltip=str(row["place"])).add_to(m)
    except Exception:
        # 破損行があっても全体は描画する
        continue

st.subheader("🗾 みんなの出発地マップ")
st_folium(m, width=700, height=500)

# ====== 管理者向けリセット ======
with st.expander("🔒 管理者設定（データリセット）"):
    admin = st.text_input("管理者パスワード", type="password")
    if st.button("データをリセット", type="primary") and admin == ADMIN_PASSWORD:
        try:
            with FileLock(LOCK_FILE, timeout=10):
                pd.DataFrame(columns=["place", "lat", "lon"]).to_csv(CSV_FILE, index=False)
            st.warning("🧹 データをリセットしました。")
        except Exception as e:
            st.error("リセットでエラーが発生しました。")
            st.exception(e)
