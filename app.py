import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(page_title="Real-Time Price Intelligence System", page_icon="🛍️", layout="wide")

def clean_and_score(raw_df):
    df = raw_df.copy()
    for col in ["actual_price", "discounted_price", "rating", "discount_percentage", "rating_count"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "", regex=False).str.replace(r"[^0-9.\-]", "", regex=True), errors="coerce")
    df["rating_count"] = df.get("rating_count", pd.Series(0, index=df.index)).fillna(0)
    df = df.dropna(subset=["product_name", "actual_price", "discounted_price", "rating"]).copy()
    df = df[(df["actual_price"] > 0) & (df["discounted_price"] >= 0)].copy()
    if df["discount_percentage"].dropna().max() <= 1.0:
        df["discount_percentage"] = (df["discount_percentage"] * 100).round(2)
    calc_d = ((df["actual_price"] - df["discounted_price"]) / df["actual_price"] * 100).round(2)
    df["discount_percentage"] = df["discount_percentage"].fillna(calc_d).round(2)
    df["price_savings"] = (df["actual_price"] - df["discounted_price"]).clip(lower=0).round(2)
    def mm(s):
        return pd.Series(0.0, index=s.index) if s.max() == s.min() else (s - s.min()) / (s.max() - s.min()) * 100
    df["discount_score"] = df["discount_percentage"].clip(0, 100).round(2)
    df["savings_score"] = mm(df["price_savings"]).round(2)
    df["rating_score"] = (df["rating"].clip(0, 5) / 5 * 100).round(2)
    df["popularity_score"] = mm(df["rating_count"].clip(lower=0)).round(2)
    df["deal_score"] = (0.30 * df["discount_score"] + 0.25 * df["savings_score"] + 0.25 * df["rating_score"] + 0.20 * df["popularity_score"]).round(2)
    df["deal_category"] = pd.cut(df["deal_score"], bins=[-0.01, 39.999, 59.999, 74.999, 100], labels=["Low", "Average", "Good", "Excellent"]).astype(str)
    return df

@st.cache_data
def load_default_data():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(base_dir, "dashboard_data.csv")
    if os.path.exists(p):
        return clean_and_score(pd.read_csv(p))
    return pd.DataFrame()

st.markdown("### 🛍️ Real-Time Price Intelligence System  `Live Portfolio App`")
st.caption("Multi-Factor Deal Scoring, Price Comparison & Smart Product Recommendation")

tab1, tab2, tab3 = st.tabs(["📊 Live Dashboard", "🧮 Scoring Formula", "🚀 Permanent Link & Portfolio Guide"])

with tab1:
    st.sidebar.header("📂 Dataset Source")
    up_file = st.sidebar.file_uploader("Upload Amazon CSV File", type=["csv"])
    df = clean_and_score(pd.read_csv(up_file)) if up_file is not None else load_default_data()

    st.sidebar.header("🔍 Product Filters")
    if "kw" not in st.session_state:
        st.session_state.kw = "HDMI"
    c_q1, c_q2, c_q3, c_q4, c_q5 = st.sidebar.columns(5)
    if c_q1.button("HDMI"): st.session_state.kw = "HDMI"
    if c_q2.button("Mouse"): st.session_state.kw = "Mouse"
    if c_q3.button("Cable"): st.session_state.kw = "Cable"
    if c_q4.button("Audio"): st.session_state.kw = "Headphones"
    if c_q5.button("All"): st.session_state.kw = ""

    keyword = st.sidebar.text_input("Search product keyword", value=st.session_state.kw)
    max_p = int(df["discounted_price"].max()) if not df.empty else 20000
    default_b = 1000 if st.session_state.kw == "HDMI" else max_p
    max_budget = st.sidebar.slider("Maximum budget (₹)", min_value=100, max_value=max(10000, max_p), value=min(default_b, max(10000, max_p)), step=100)
    min_rating = st.sidebar.slider("Minimum rating (★)", 0.0, 5.0, 4.0, 0.1)
    cat_tier = st.sidebar.selectbox("Deal Category Tier", ["ALL", "Excellent", "Good", "Average", "Low"])
    sort_by = st.sidebar.selectbox("Sort Recommendations By", ["Best Deal Score First (Default)", "Discounted Price: Low to High", "Highest Discount % First", "Highest Rupee Savings (₹)", "Highest Customer Rating (★)"])

    filtered = df[(df["discounted_price"] <= max_budget) & (df["rating"] >= min_rating)].copy()
    if cat_tier != "ALL":
        filtered = filtered[filtered["deal_category"] == cat_tier]
    if keyword.strip():
        filtered = filtered[filtered["product_name"].astype(str).str.contains(keyword.strip(), case=False, na=False)]
    filtered = filtered.drop_duplicates(subset=["product_name"])

    if sort_by == "Discounted Price: Low to High": filtered = filtered.sort_values("discounted_price", ascending=True)
    elif sort_by == "Highest Discount % First": filtered = filtered.sort_values("discount_percentage", ascending=False)
    elif sort_by == "Highest Rupee Savings (₹)": filtered = filtered.sort_values("price_savings", ascending=False)
    elif sort_by == "Highest Customer Rating (★)": filtered = filtered.sort_values(["rating", "deal_score"], ascending=[False, False])
    else: filtered = filtered.sort_values(["deal_score", "rating"], ascending=[False, False])

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Matching Products", f"{len(filtered):,}", f"Out of {len(df)} catalog items")
    k2.metric("Average Discount", f"{filtered['discount_percentage'].mean():.1f}%" if not filtered.empty else "—", "Across filtered results")
    k3.metric("Best Deal Score", f"{filtered['deal_score'].max():.2f}" if not filtered.empty else "—", "Weighted 0-100 scale")
    k4.metric("Max Rupee Savings", f"₹{filtered['price_savings'].max():,.0f}" if not filtered.empty else "—", "Actual minus discounted")

    if filtered.empty:
        st.warning("🔍 No matching products found. Try clearing the keyword filter or raising your maximum budget (₹).")
    else:
        best = filtered.sort_values(["deal_score", "rating"], ascending=[False, False]).iloc[0]
        st.markdown(f"""
        <div style="background: linear-gradient(90deg, #1e1b4b, #312e81, #0f172a); color: white; padding: 20px; border-radius: 16px; margin-bottom: 20px;">
            <span style="background: rgba(251,191,36,0.2); color: #fde68a; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 600;">🏆 Best Matching Product Recommendation</span>
            <h3 style="color: white; margin-top: 10px; margin-bottom: 6px;">{best["product_name"]}</h3>
            <p style="font-size: 14px; color: #e0e7ff; margin-bottom: 12px;">
                Price: <b style="color:white;">₹{best["discounted_price"]:,.0f}</b> <del style="color:#a5b4fc;">₹{best["actual_price"]:,.0f}</del> &nbsp;|&nbsp; 
                Savings: <b style="color:#6ee7b7;">₹{best["price_savings"]:,.0f} ({best["discount_percentage"]:.1f}% OFF)</b> &nbsp;|&nbsp; 
                Rating: <b style="color:#fcd34d;">★ {best["rating"]:.1f} / 5 ({int(best["rating_count"]):,} reviews)</b> &nbsp;|&nbsp; 
                Deal Score: <b style="color:#34d399; font-size:18px;">{best["deal_score"]:.2f} ({best["deal_category"]})</b>
            </p>
        </div>
        """, unsafe_allow_html=True)

        b1, b2, b3, b4 = st.columns(4)
        b1.progress(min(100, int(best["discount_score"])), text=f"Discount (30%): {best['discount_score']:.0f}/100")
        b2.progress(min(100, int(best["savings_score"])), text=f"Savings (25%): {best['savings_score']:.0f}/100")
        b3.progress(min(100, int(best["rating_score"])), text=f"Rating (25%): {best['rating_score']:.0f}/100")
        b4.progress(min(100, int(best["popularity_score"])), text=f"Popularity (20%): {best['popularity_score']:.0f}/100")

        st.subheader("📋 Product Recommendations")
        cols = ["product_name", "actual_price", "discounted_price", "price_savings", "discount_percentage", "rating", "deal_score", "deal_category"]
        st.dataframe(filtered[cols], hide_index=True)

        st.subheader("📊 Visual Analytics")
        ch1, ch2, ch3 = st.columns(3)
        order = ["Excellent", "Good", "Average", "Low"]
        cmap = {"Excellent": "#10b981", "Good": "#3b82f6", "Average": "#f59e0b", "Low": "#ef4444"}
        with ch1:
            cat_counts = filtered["deal_category"].value_counts().reindex(order, fill_value=0).reset_index()
            cat_counts.columns = ["Deal Category", "Products"]
            fig1 = px.bar(cat_counts, x="Deal Category", y="Products", color="Deal Category", color_discrete_map=cmap, title="Deal Category Distribution")
            st.plotly_chart(fig1, key="c1")
        with ch2:
            fig2 = px.histogram(filtered, x="discount_percentage", nbins=10, title="Distribution of Product Discounts")
            st.plotly_chart(fig2, key="c2")
        with ch3:
            fig3 = px.scatter(filtered, x="rating", y="deal_score", color="deal_category", color_discrete_map=cmap, hover_data=["product_name"], title="Product Rating vs. Deal Score")
            st.plotly_chart(fig3, key="c3")

with tab2:
    st.subheader("Multi-Factor Deal Scoring & Data Cleaning Pipeline")
    st.info("Deal Score = 0.30 × Discount Score + 0.25 × MinMax(Savings) + 0.25 × (Rating/5 × 100) + 0.20 × MinMax(Reviews)")
    st.markdown("- **Excellent Deal:** Score ≥ 75\n- **Good Deal:** Score 60 – 74.99\n- **Average Deal:** Score 40 – 59.99\n- **Low Deal:** Score < 40")

with tab3:
    st.subheader("🚀 Permanent Hosting & Resume Bullets")
    st.code("""Real-Time Price Intelligence & Product Recommendation System | Python, Pandas, Seaborn, Streamlit
• Engineered an automated e-commerce data cleaning pipeline in Python/Pandas to parse raw pricing, strip currency/delimiter artifacts, and reconcile discount percentage scales across catalog records.
• Designed a 4-factor weighted Deal Scoring algorithm (30% Discount, 25% Min-Max Price Savings, 25% Normalized Customer Rating, 20% Review Popularity) to classify products into 4 actionable deal tiers.
• Built and deployed an interactive web dashboard enabling real-time keyword search, budget/rating filtering, deduplicated product ranking, and visual analytics.""", language="text")