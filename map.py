import os
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from filelock import FileLock

from geopy.geocoders import Nominatim
from geopy.geocoders import OpenCage, Photon
from geopy.extra.rate_limiter import RateLimiter
from geopy.exc import GeocoderUnavailable, GeocoderTimedOut

# ====== 基本設定 ======
st.set_page_config(page_title="どこから来ましたか？", layout="centered")
DATA_DIR = os.environ.get("STREAMLIT_DATA_DIR", "/tmp")
os.makedirs(DATA_DIR, exist_ok=True)
CSV_FILE = os.path.join(DATA_DIR, "locations.csv")
LOCK_FILE = os.path.join(DATA_DIR, "locations.csv.lock")
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "santi111")

st.title("📍 あなたはどこから来ましたか？（関東マップ）")

# ====== ファイル初期化 ======
if not os.path.exists(CSV_FILE):
    with FileLock(LOCK_FILE, timeout=10):
        pd.DataFrame(columns=["place", "lat", "lon"]).to_csv(CSV_FILE, index=False)

# ====== ジオコーダ・フォールバック実装 ======
@st.cache_resource
def build_geocoders():
    geocoders = []

    # 1) OpenCage（推奨）
    oc_key = st.secrets.get("OPENCAGE_API_KEY")
    if oc_key:
        geocoders.append(
            OpenCage(api_key=oc_key, timeout=10)
        )

    # 2) Photon（キー不要・比較的寛容）
    geocoders.append(
        Photon(user_agent="kanto-map-survey (contact: youremail@example.com)", timeout=10)
    )

    # 3) Nominatim（最後の手段）
    geocoders.append(
        Nominatim(user_agent="kanto-map-survey (contact: youremail@example.com)", timeout=10)
    )
    return geocoders

GEOCODERS = build_geocoders()

def robust_geocode(query: str):
    # 各プロバイダに順番に当て、RateLimiter付きで軽いバックオフ
    last_exc = None
    for g in GEOCODERS:
        geocode = RateLimiter(
            g.geocode,
            min_delay_seconds=1.0,             # 速すぎる連投を回避
            max_retries=2,                     # 軽いリトライ
            error_wait_seconds=2.0,            # 失敗時の待機
            swallow_exceptions=False
        )
        try:
            return geocode(query)
        except (GeocoderUnavailable, GeocoderTimedOut, ConnectionError) as e:
            last_exc = e
            continue  # 次のプロバイダへ
        except Exception as e:
            # 予期せぬ例外もフォールバック継続
            last_exc = e
            continue
    # すべて失敗
    if last_exc:
        raise last_exc
    return None

# ====== 入力フォーム ======
with st.form("location_form"):
    place = st.text_input("都道府県・市区町村・駅名など（例：埼玉県さいたま市、渋谷駅）")
    submitted = st.form_submit_button("地図に追加する")
    if submitted and place:
        try:
            location = robust_geocode(place + ", Japan")
            if location:
                df_new = pd.DataFrame(
                    {"place": [place], "lat": [location.latitude], "lon": [location.longitude]}
                )
                with FileLock(LOCK_FILE, timeout=10):
                    write_header = not os.path.exists(CSV_FILE) or os.path.getsize(CSV_FILE) == 0
                    df_new.to_csv(CSV_FILE, mode="a", header=write_header, index=False)
                st.success(f"✅ {place} を地図に追加しました！")
            else:
                st.warning("場所が見つかりませんでした。別の表記（駅名→市区町村など）でもお試しください。")
        except Exception as e:
            st.error("ジオコーディングに失敗しました（外部サービス未到達/制限の可能性）。")
            st.exception(e)

# ====== CSV読み込み ======
with FileLock(LOCK_FILE, timeout=10):
    if os.path.exists(CSV_FILE) and os.path.getsize(CSV_FILE) > 0:
        df = pd.read_csv(CSV_FILE)
    else:
        df = pd.DataFrame(columns=["place", "lat", "lon"])

# ====== 地図描画 ======
m = folium.Map(location=[35.6895, 139.6917], zoom_start=8)
for _, row in df.iterrows():
    try:
        folium.Marker([float(row["lat"]), float(row["lon"])], tooltip=str(row["place"])).add_to(m)
    except Exception:
        continue

st.subheader("🗾 みんなの出発地マップ")
st_folium(m, width=700, height=500)

# ====== 管理者リセット ======
with st.expander("🔒 管理者設定（データリセット）"):
    admin = st.text_input("管理者パスワード", type="password")
    if st.button("データをリセット", type="primary") and admin == ADMIN_PASSWORD:
        with FileLock(LOCK_FILE, timeout=10):
            pd.DataFrame(columns=["place", "lat", "lon"]).to_csv(CSV_FILE, index=False)
        st.warning("🧹 データをリセットしました。")
