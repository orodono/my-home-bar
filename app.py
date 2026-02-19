import streamlit as st
import requests
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import json
import os
import time

# --- 設定 ---
API_BASE_URL = "https://www.thecocktaildb.com/api/json/v1/1"
# あなたのスプレッドシートURL
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1Jno6oVMteh_2uiII9nKl2uDDMuloyObRuMFRNpBCvhM/edit"
DB_FILE = "cocktail_master.json"
NO_IMAGE_PLACEHOLDER = "https://via.placeholder.com/150?text=No+Image"

SPIRITS = ["Gin", "Vodka", "Rum", "Tequila", "Whiskey"]
DEFAULT_MASTER_ING = SPIRITS + ["Brandy", "Lemon Juice", "Lime Juice", "Sugar Syrup", "Tonic Water", "Soda Water", "Mint"]

st.set_page_config(page_title="Cloud Home Bar", page_icon="🍸", layout="wide")

# 20行目あたり（アプリの序盤）に追加
if "selected_inventory" not in st.session_state:
    st.session_state.selected_inventory = [] # 最初は空っぽ
# --- スプレッドシート接続設定 ---
# = st.connection("gsheets", type=GSheetsConnection)

def load_cloud_data():
    """スプレッドシートからデータを読み込む"""
    try:
        df = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="Cocktail_DB", ttl=0)
        favs = [x for x in df['favorites'].dropna().tolist() if x]
        inv = [x for x in df['inventory'].dropna().tolist() if x]
        m_ing = [x for x in df['master_ingredients'].dropna().tolist() if x]
        if not m_ing: m_ing = DEFAULT_MASTER_ING
        return favs, inv, m_ing
    except:
        return [], [], DEFAULT_MASTER_ING

def save_cloud_data(favs, inv, m_ing):
    """スプレッドシートにデータを保存"""
    max_len = max(len(favs), len(inv), len(m_ing), 1)
    data = {
        "favorites": favs + [""] * (max_len - len(favs)),
        "inventory": inv + [""] * (max_len - len(inv)),
        "master_ingredients": m_ing + [""] * (max_len - len(m_ing))
    }
    df = pd.DataFrame(data)
    conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Cocktail_DB", data=df)
    st.cache_data.clear()

# --- JSON/API 関数 ---
def load_json(file_path, default_value=None):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default_value if default_value is not None else {}

def get_image(url):
    if url and str(url) != "None": return url
    return NO_IMAGE_PLACEHOLDER

def get_match_score(drink, inventory):
    score = 0
    inv_lower = [i.lower() for i in inventory]
    for i in range(1, 16):
        ing = drink.get(f'strIngredient{i}')
        if ing and any(si in ing.lower() for si in inv_lower): score += 1
    return score

def estimate_strength(drink_data):
    if "strength" in drink_data: return drink_data["strength"]
    name = drink_data.get("strDrink", "").lower()
    if any(k in name for k in ["martini", "negroni", "shot", "old fashioned"]): return "High"
    return "Medium"

# --- UIコンポーネント ---
def render_cocktail_card(drink, key_prefix, favorites, selected_ingredients):
    with st.container(border=True):
        c1, c2 = st.columns([1, 2])
        with c1: st.image(get_image(drink.get('strDrinkThumb')), width=100)
        with c2:
            name = drink.get('strDrink')
            clean_name = name.replace("⭐ [MY] ", "")
            is_fav = clean_name in favorites
            st.markdown(f"**{'❤️ ' if is_fav else ''}{name}**")
            ings_display = []
            inv_lower = [i.lower() for i in selected_ingredients]
            for i in range(1, 6):
                ing = drink.get(f'strIngredient{i}')
                if ing:
                    if any(si in ing.lower() for si in inv_lower): ings_display.append(f":red[**{ing}**]")
                    else: ings_display.append(ing)
            st.markdown(f"🧪 {' / '.join(ings_display)}" if ings_display else "🧪 No info")
            if st.button("詳細", key=f"{key_prefix}_{drink.get('idDrink', name)}"):
                show_drink_details(drink, favorites, selected_ingredients)

@st.dialog("カクテル詳細")
def show_drink_details(detail, favorites, selected_ingredients):
    clean_name = detail['strDrink'].replace("⭐ [MY] ", "")
    col1, col2 = st.columns([1, 1.2])
    with col1: st.image(get_image(detail.get('strDrinkThumb')), use_container_width=True)
    with col2:
        st.subheader(detail['strDrink'])
        if st.button("❤️ 解除" if clean_name in favorites else "🤍 お気に入り"):
            if clean_name in favorites: favorites.remove(clean_name)
            else: favorites.append(clean_name)
            save_cloud_data(favorites, selected_inventory, master_ingredients)
            st.rerun()
    st.write("---")
    inv_lower = [i.lower() for i in selected_ingredients]
    for i in range(1, 16):
        ing = detail.get(f'strIngredient{i}')
        if ing:
            is_in = any(si in ing.lower() for si in inv_lower)
            txt = f"・ {ing} ({detail.get(f'strMeasure{i}', '適量')})"
            st.markdown(f":red[**{txt}**]" if is_in else txt)
    st.info(detail.get('strInstructions', "手順なし"))

# --- メイン処理 ---
st.title("🍸 My Home Bar: Cloud Edition")

# 1. データの管理（セッション状態を活用）
if "master_ingredients" not in st.session_state:
    f, s, m = load_cloud_data() # 最初だけ読み込み（失敗しても空リストが返る）
    st.session_state.favorites = f
    st.session_state.selected_inventory = s
    st.session_state.master_ingredients = m

favorites = st.session_state.favorites
selected_inventory = st.session_state.selected_inventory
master_ingredients = st.session_state.master_ingredients

local_db = load_json(DB_FILE, default_value={})

tab1, tab2, tab3 = st.tabs(["🔍 探す", "❤️ お気に入り", "📝 登録"])

with st.sidebar:
    st.header("Inventory")
    with st.expander("＋ 材料を追加"):
        new_ing = st.text_input("材料名")
        if st.button("追加"):
            if new_ing and new_ing not in master_ingredients:
                st.session_state.master_ingredients.append(new_ing)
                # save_cloud_data(...) # 保存は一旦お休み
                st.rerun()

    st.write("📦 **在庫タイル**")
    sorted_master = sorted(master_ingredients, key=lambda x: (x not in SPIRITS, x))
    
    ing_cols = st.columns(2)
    for idx, ing in enumerate(sorted_master):
        is_selected = ing in selected_inventory
        if ing_cols[idx % 2].button(f"{'✅' if is_selected else '➕'} {ing}", 
                                     key=f"t_{ing}", 
                                     type="primary" if is_selected else "secondary", 
                                     use_container_width=True):
            if is_selected:
                st.session_state.selected_inventory.remove(ing)
            else:
                st.session_state.selected_inventory.append(ing)
            st.rerun()
    
    st.divider()
    search_query = st.text_input("名前検索")
    alc_level = st.select_slider("度数:", options=["All", "Low/None", "Medium", "High"], value="All")

with tab1:
    if selected_inventory:
        inv_lower = [i.lower() for i in selected_inventory]
        results = []
        for d_info in local_db.values():
            match_found = False
            for i in range(1, 16):
                ing = d_info.get(f'strIngredient{i}')
                if ing and any(si in ing.lower() for si in inv_lower):
                    match_found = True; break
            if match_found: results.append(d_info)
        
        filtered = [d for d in results if (not search_query or search_query.lower() in d['strDrink'].lower()) and (alc_level == "All" or estimate_strength(d) == alc_level)]
        sorted_list = sorted(filtered, key=lambda x: (-get_match_score(x, selected_inventory), 0 if x['strDrink'] in favorites else 1))

        if not sorted_list: st.warning("DBにカクテルがありません。ローカルで全件同期したcocktail_master.jsonをGitHubに上げてください。")
        else:
            cols = st.columns(2)
            for idx, drink in enumerate(sorted_list[:24]):
                with cols[idx % 2]: render_cocktail_card(drink, "sc", favorites, selected_inventory)
    else:
        st.info("在庫を選択してください。")

with tab2:
    st.header("お気に入り")
    fav_list = [d for d in local_db.values() if d['strDrink'] in favorites]
    if fav_list:
        cols = st.columns(2)
        for idx, drink in enumerate(fav_list):
            with cols[idx % 2]: render_cocktail_card(drink, "fv", favorites, selected_inventory)

with tab3:
    st.write("マイレシピ機能はスプレッドシートの構造上、次のアップデートで対応予定です！")