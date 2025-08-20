import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from filelock import FileLock
import os

CSV_FILE = "locations.csv"
LOCK_FILE = "locations.csv.lock"

# --- ファイルの初期化 ---
if not os.path.exists(CSV_FILE):
    with FileLock(LOCK_FILE):
        pd.DataFrame(columns=["place", "lat", "lon"]).to_csv(CSV_FILE, index=False)

st.set_page_config(page_title="どこから来ましたか？", layout="centered")
st.title("📍 あなたはどこから来ましたか？（関東マップ）")

# --- 入力フォーム ---
with st.form("location_form"):
    place = st.text_input("都道府県・市区町村・駅名など（例：埼玉県さいたま市、渋谷駅）")
    submitted = st.form_submit_button("地図に追加する")

    if submitted and place:
        geolocator = Nominatim(user_agent="location_app")
        try:
            location = geolocator.geocode(place + ", Japan")
            if location:
                df_new = pd.DataFrame({
                    "place": [place],
                    "lat": [location.latitude],
                    "lon": [location.longitude]
                })
                with FileLock(LOCK_FILE):
                    df_new.to_csv(CSV_FILE, mode="a", header=False, index=False)
                st.success(f"✅ {place} を地図に追加しました！")
            else:
                st.error("場所が見つかりませんでした。もう一度入力してください。")
        except Exception as e:
            st.error("エラーが発生しました。時間をおいて再試行してください。")
            st.stop()

# --- CSVファイル読み込み（ロック付き） ---
with FileLock(LOCK_FILE):
    df = pd.read_csv(CSV_FILE)

# --- 地図の描画 ---
m = folium.Map(location=[35.6895, 139.6917], zoom_start=8)  # 関東中心

for _, row in df.iterrows():
    folium.Marker([row['lat'], row['lon']], tooltip=row['place']).add_to(m)

st.subheader("🗾 みんなの出発地マップ")
st_folium(m, width=700, height=500)

# --- 管理者向けリセット機能 ---
with st.expander("🔒 管理者設定（データリセット）"):
    admin = st.text_input("管理者パスワード", type="password")
    if st.button("データをリセット", type="primary") and admin == "santi111":
        with FileLock(LOCK_FILE):
            pd.DataFrame(columns=["place", "lat", "lon"]).to_csv(CSV_FILE, index=False)
        st.warning("🧹 データをリセットしました。")
