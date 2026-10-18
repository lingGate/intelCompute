# -*- coding: utf-8 -*-
"""
项目独立核算系统 v14.1 (完整无错版)
- 严格拆解材料分类，套用文字公式计算费用
- 增加表3材料“已使用”状态高亮
- 补全⑦-⑪页面逻辑
"""

import streamlit as st
import pandas as pd
import numpy as np
import re, math

st.set_page_config(page_title="项目独立核算系统", layout="wide")
TAX_FACTOR = 1/1.13

# ========== 初始化 ==========
def init_state():
    if "params" not in st.session_state:
        st.session_state.params = {
            "辅料率": 0.10, "工费率": 0.40,
            "管理费率": 0.07, "利润率": 0.20, "税率": 0.13}
    if "units" not in st.session_state:
        st.session_state.units = ["公斤","米","平米","个","套","根","支","块","件","张","卷"]
    if "formulas" not in st.session_state:
        st.session_state.formulas = {
            ("表3-2", 1): {"类别":"铝板","方式":"板材","密度":2.70,"表达式":""},
            ("表3-2", 2): {"类别":"角铝","方式":"板材","密度":2.70,"表达式":""},
            ("表3-2", 3): {"类别":"PC板","方式":"板材","密度":1.20,"表达式":""},
            ("表3-3", 1): {"类别":"304不锈钢管","方式":"自动识别","密度":7.93,"表达式":""},
            ("表3-3", 2): {"类别":"铝管","方式":"自动识别","密度":2.70,"表达式":""},
            ("表3-3", 3): {"类别":"镀锌管","方式":"自动识别","密度":7.85,"表达式":""},
        }
    if "t31" not in st.session_state:
        st.session_state.t31 = pd.DataFrame(columns=[
            "序号","材料名称","分类","型号","颜色","制造商","单位米重",
            "平均价","系数","平均价*系数","元/kg","元/m","项目","备注"])
    if "t32" not in st.session_state:
        st.session_state.t32 = pd.DataFrame(columns=[
            "序号","材料名称","品种","颜色","单位","制造商","厚度(mm)","计价单位",
            "单位重量","平均价","系数","平均价*系数","元/kg","元/平米","备注"])
    if "t33" not in st.session_state:
        st.session_state.t33 = pd.DataFrame(columns=[
            "序号","材料名称","品种","颜色","单位","制造商","厚度(mm)","计价单位",
            "单位重量","平均价","系数","平均价*系数","元/kg","元/m","备注"])
    if "t34" not in st.session_state:
        st.session_state.t34 = pd.DataFrame(columns=[
            "序号","材料名称","单位","制造商","规格","颜色",
            "平均价","系数","平均价*系数","材料价格","备注"])
    if "t35" not in st.session_state:
        st.session_state.t35 = pd.DataFrame(columns=[
            "序号","材料名称","单位","规格","型号","颜色",
            "平均价","系数","平均价*系数","材料价格","备注"])
    if "t1" not in st.session_state:
        st.session_state.t1 = pd.DataFrame(columns=[
            "产品编号","产品名称","型号","规格","加工方式","序号",
            "材料名称","规格尺寸","颜色","材质厚度","单位",
            "数量","单价","合计","材料分类","匹配状态"])
    if "qty_map" not in st.session_state:
        st.session_state.qty_map = {}
    if "batch_rates" not in st.session_state:
        st.session_state.batch_rates = {}
    if "current_batch" not in st.session_state:
        st.session_state.current_batch = "A-001"

init_state()

# ========== 工具函数 ==========
def parse_spec(spec):
    result = {"A":0, "B":0, "D":0}
    if not spec or pd.isna(spec): return result
    spec = str(spec).strip().replace("×","*").replace("x","*").replace("X","*")
    m = re.search(r'(\d+(?:\.\d+)?)\s*[*]\s*(\d+(?:\.\d+)?)', spec)
    if m:
        result["A"] = float(m.group(1)); result["B"] = float(m.group(2))
        return result
    m = re.search(r'(\d+(?:\.\d+)?)', spec)
    if m:
        result["D"] = float(m.group(1))
    return result

def calc_unit_weight(calc_type, density, spec, thickness, custom_expr=""):
    if not thickness or pd.isna(thickness) or thickness <= 0: return 0
    if not density or density <= 0: return 0
    parsed = parse_spec(spec)
    A, B, D = parsed["A"], parsed["B"], parsed["D"]
    if calc_type == "板材": return round(density * thickness, 4)
    elif calc_type == "方管":
        if A > 0 and B > 0: return round((A + B) * 2 * thickness * density / 1000, 4)
    elif calc_type == "圆管":
        if D > 0: return round(math.pi * D * thickness * density / 1000, 4)
    elif calc_type in ("自动识别","混合"):
        if A > 0 and B > 0: return round((A + B) * 2 * thickness * density / 1000, 4)
        elif D > 0: return round(math.pi * D * thickness * density / 1000, 4)
    return 0

def get_used_materials():
    if st.session_state.t1.empty: return set()
    fee_names = ["辅料及损耗","材料小计","人工费","管理费","利润","税金","合计","价格合计"]
    mats = st.session_state.t1[~st.session_state.t1["材料名称"].isin(fee_names)]
    return set(mats["材料名称"].dropna().unique())

# ========== 计算表3 ==========
def calc_t31(df):
    df = df.copy()
    for c in ["单位米重","平均价","系数"]:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")
    df["系数"] = df["系数"].fillna(TAX_FACTOR).replace(0, TAX_FACTOR)
    df["平均价*系数"] = df["平均价"].fillna(0) * df["系数"]
    df["元/kg"] = df["平均价*系数"]
    df["元/m"] = df["单位米重"].fillna(0) * df["元/kg"]
    return df

def calc_t32(df):
    df = df.copy()
    for c in ["厚度(mm)","单位重量","平均价","系数"]:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")
    df["系数"] = df["系数"].fillna(TAX_FACTOR).replace(0, TAX_FACTOR)
    df["平均价*系数"] = df["平均价"].fillna(0) * df["系数"]
    df["元/kg"] = df["平均价*系数"]
    w_list, p_list = [], []
    for _, r in df.iterrows():
        pu = r.get("计价单位", "元/公斤")
        if pd.isna(pu) or pu == "元/公斤":
            try: seq = int(r.get("序号"))
            except: seq = None
            cfg = st.session_state.formulas.get(("表3-2", seq)) if seq else None
            w = calc_unit_weight(cfg["方式"], cfg["密度"], r.get("品种",""), r.get("厚度(mm)"), cfg.get("表达式","")) if cfg else 0
            if w > 0: w_list.append(w); p_list.append(round(w * r["元/kg"], 4)); continue
        w_list.append(0); p_list.append(r["平均价*系数"])
    df["单位重量"] = w_list; df["元/平米"] = p_list
    return df

def calc_t33(df):
    df = df.copy()
    for c in ["厚度(mm)","单位重量","平均价","系数"]:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")
    df["系数"] = df["系数"].fillna(TAX_FACTOR).replace(0, TAX_FACTOR)
    df["平均价*系数"] = df["平均价"].fillna(0) * df["系数"]
    df["元/kg"] = df["平均价*系数"]
    w_list, m_list = [], []
    for _, r in df.iterrows():
        pu = r.get("计价单位", "元/公斤")
        if pd.isna(pu) or pu == "元/公斤":
            try: seq = int(r.get("序号"))
            except: seq = None
            cfg = st.session_state.formulas.get(("表3-3", seq)) if seq else None
            w = calc_unit_weight(cfg["方式"], cfg["密度"], r.get("品种",""), r.get("厚度(mm)"), cfg.get("表达式","")) if cfg else 0
            if w > 0: w_list.append(w); m_list.append(round(w * r["元/kg"], 4)); continue
        w_list.append(0); m_list.append(r["平均价*系数"])
    df["单位重量"] = w_list; df["元/m"] = m_list
    return df

def calc_t34(df):
    df = df.copy()
    for c in ["平均价","系数"]:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")
    df["系数"] = df["系数"].fillna(TAX_FACTOR).replace(0, TAX_FACTOR)
    df["平均价*系数"] = df["平均价"].fillna(0) * df["系数"]
    df["材料价格"] = df["平均价*系数"]
    return df

def calc_t35(df): return calc_t34(df)

# ========== 表3渲染 ==========
def render_t3(df, calc_func, auto_cols, key, used_mats):
    df = calc_func(df)
    df["使用状态"] = df["材料名称"].apply(lambda x: "✅ 已使用" if x in used_mats else "")
    
    col_config = {c: st.column_config.NumberColumn(c, disabled=True, format="%.4f") for c in auto_cols}
    col_config["系数"] = st.column_config.NumberColumn("系数", format="%.6f")
    col_config["单位米重"] = st.column_config.NumberColumn("单位米重(kg/m)", format="%.4f")
    col_config["单位重量"] = st.column_config.NumberColumn("单位重量", format="%.4f")
    col_config["计价单位"] = st.column_config.SelectboxColumn("计价单位", options=["元/公斤","元/平米","元/m"])
    col_config["使用状态"] = st.column_config.TextColumn("使用状态", disabled=True)

    edited = st.data_editor(df, num_rows="dynamic", use_container_width=True, column_config=col_config, key=key)
    return calc_func(edited)

# ========== 侧边栏 ==========
st.sidebar.title("项目独立核算系统")
page = st.sidebar.radio("导航", [
    "① 表3-1 型材类","② 表3-2 按平米类","③ 表3-3 按米类",
    "④ 表3-4 其他类","⑤ 表3-5 LED类","⑥ 表1 单价分析",
    "⑦ 表2 完工成本汇总","⑧ 材料系数计算","⑨ 单位维护",
    "⑩ Excel导入","⑪ 公式配置"
])

used_mats = get_used_materials()

# ========== ①-⑤ 表3 ==========
if page == "① 表3-1 型材类":
    st.title("表3-1 型材类材料价格明细")
    df = st.session_state.t31.copy()
    dc = st.number_input("默认系数", value=TAX_FACTOR, step=0.000001, format="%.6f", key="dc_31")
    if not df.empty:
        df["系数"] = pd.to_numeric(df["系数"], errors="coerce").fillna(dc).replace(0, dc)
    st.session_state.t31 = render_t3(df, calc_t31, ["平均价*系数","元/kg","元/m"], "e_t31", used_mats)
    st.success(f"共 {len(st.session_state.t31)} 行")

elif page == "② 表3-2 按平米类":
    st.title("表3-2 按平米计算类材料价格明细")
    df = st.session_state.t32.copy()
    dc = st.number_input("默认系数", value=TAX_FACTOR, step=0.000001, format="%.6f", key="dc_32")
    if not df.empty:
        df["系数"] = pd.to_numeric(df["系数"], errors="coerce").fillna(dc).replace(0, dc)
    st.session_state.t32 = render_t3(df, calc_t32, ["单位重量","平均价*系数","元/kg","元/平米"], "e_t32", used_mats)
    st.success(f"共 {len(st.session_state.t32)} 行")

elif page == "③ 表3-3 按米类":
    st.title("表3-3 按米计算类材料价格明细")
    df = st.session_state.t33.copy()
    dc = st.number_input("默认系数", value=TAX_FACTOR, step=0.000001, format="%.6f", key="dc_33")
    if not df.empty:
        df["系数"] = pd.to_numeric(df["系数"], errors="coerce").fillna(dc).replace(0, dc)
    st.session_state.t33 = render_t3(df, calc_t33, ["单位重量","平均价*系数","元/kg","元/m"], "e_t33", used_mats)
    st.success(f"共 {len(st.session_state.t33)} 行")

elif page == "④ 表3-4 其他类":
    st.title("表3-4 其他类材料价格明细")
    df = st.session_state.t34.copy()
    dc = st.number_input("默认系数", value=TAX_FACTOR, step=0.000001, format="%.6f", key="dc_34")
    if not df.empty:
        df["系数"] = pd.to_numeric(df["系数"], errors="coerce").fillna(dc).replace(0, dc)
    st.session_state.t34 = render_t3(df, calc_t34, ["平均价*系数","材料价格"], "e_t34", used_mats)
    st.success(f"共 {len(st.session_state.t34)} 行")

elif page == "⑤ 表3-5 LED类":
    st.title("表3-5 LED类材料价格明细")
    df = st.session_state.t35.copy()
    dc = st.number_input("默认系数", value=TAX_FACTOR, step=0.000001, format="%.6f", key="dc_35")
    if not df.empty:
        df["系数"] = pd.to_numeric(df["系数"], errors="coerce").fillna(dc).replace(0, dc)
    st.session_state.t35 = render_t3(df, calc_t35, ["平均价*系数","材料价格"], "e_t35", used_mats)
    st.success(f"共 {len(st.session_state.t35)} 行")

# ========== ⑥ 表1 ==========
elif page == "⑥ 表1 单价分析":
    st.title("表1 单件产品单价分析")
    
    c0, _ = st.columns([2, 3])
    with c0: batch_id = st.text_input("批次号", st.session_state.current_batch, key="t1_batch")
    st.session_state.current_batch = batch_id
    if batch_id not in st.session_state.batch_rates:
        st.session_state.batch_rates[batch_id] = {"辅料率":0.10,"工费率":0.40,"管理费率":0.07,"利润率":0.20,"税率":0.13}
    rates = st.session_state.batch_rates[batch_id]

    st.caption(f"当前批次：**{batch_id}**")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: r_aux = st.number_input("辅料率", value=rates["辅料率"], step=0.01, format="%.2f", key="r_aux")
    with c2: r_labor = st.number_input("工费率", value=rates["工费率"], step=0.01, format="%.2f", key="r_labor")
    with c3: r_mgmt = st.number_input("管理费率", value=rates["管理费率"], step=0.01, format="%.2f", key="r_mgmt")
    with c4: r_profit = st.number_input("利润率", value=rates["利润率"], step=0.01, format="%.2f", key="r_profit")
    with c5: r_tax = st.number_input("税率", value=rates["税率"], step=0.01, format="%.2f", key="r_tax")
    
    if st.button("保存本批次费率"):
        st.session_state.batch_rates[batch_id] = {"辅料率":r_aux,"工费率":r_labor,"管理费率":r_mgmt,"利润率":r_profit,"税率":r_tax}
        st.success("已保存")
    rates = st.session_state.batch_rates[batch_id]

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.text_input("产品编号", "P001", key="t1_pid")
    with c2: st.text_input("产品名称", "客服中心提示牌", key="t1_pname")
    with c3: st.text_input("型号", "IDT-17A", key="t1_model")
    with c4: st.text_input("规格", "(约12m)*500*100", key="t1_spec")
    with c5: method = st.selectbox("加工方式", ["混合加工", "完全外加工", "完全自加工"], key="t1_method")

    df = st.session_state.t1.copy()
    for c in ["产品编号","产品名称","型号","规格","加工方式","序号","材料名称","规格尺寸","颜色","材质厚度","单位","数量","单价","合计","材料分类","匹配状态"]:
        if c not in df.columns: df[c] = ""

    all_mats = pd.concat([
        calc_t31(st.session_state.t31), calc_t32(st.session_state.t32), 
        calc_t33(st.session_state.t33), calc_t34(st.session_state.t34), 
        calc_t35(st.session_state.t35)
    ])
    material_names = sorted(all_mats["材料名称"].dropna().unique().tolist())

    edited = st.data_editor(df, num_rows="dynamic", use_container_width=True,
        column_config={
            "材料名称": st.column_config.SelectboxColumn("材料名称", options=material_names),
            "单位": st.column_config.SelectboxColumn("单位", options=st.session_state.units),
            "数量": st.column_config.NumberColumn("数量", min_value=0.0, format="%.4f"),
            "单价": st.column_config.NumberColumn("单价", disabled=True, format="%.4f"),
            "合计": st.column_config.NumberColumn("合计", disabled=True, format="%.2f"),
            "匹配状态": st.column_config.TextColumn("匹配状态", disabled=True),
            "材料分类": st.column_config.SelectboxColumn("材料分类", options=["自加工净材料","自加工含工费净材料","甲供净材料","甲供含工费净材料","乙供净材料","乙供含工费净材料"]),
        }, key="e_t1")

    if not edited.empty:
        prices = []
        for _, r in edited.iterrows():
            name = r.get("材料名称")
            match = all_mats[all_mats["材料名称"] == name]
            p = 0
            if not match.empty:
                row = match.iloc[0]
                if "元/平米" in match.columns and pd.notna(row.get("元/平米")): p = row["元/平米"]
                elif "元/m" in match.columns and pd.notna(row.get("元/m")): p = row["元/m"]
                elif "材料价格" in match.columns and pd.notna(row.get("材料价格")): p = row["材料价格"]
            prices.append(p)
        edited["单价"] = prices
        edited["数量"] = pd.to_numeric(edited["数量"], errors="coerce").fillna(0)
        edited["合计"] = edited["数量"] * edited["单价"]
    
    st.session_state.t1 = edited
    st.markdown("---")
    st.subheader("费用计算")

    fee_names = ["辅料及损耗","材料小计","人工费","管理费","利润","税金","合计","价格合计","加工商定价","甲供单价","自加工单价"]
    if not edited.empty:
        mat_only = edited[~edited["材料名称"].isin(fee_names)]
        ca = mat_only.groupby("材料分类")["合计"].sum().to_dict()
        Y  = float(ca.get("乙供净材料", 0))
        YH = float(ca.get("乙供含工费净材料", 0))
        J  = float(ca.get("甲供净材料", 0))
        JH = float(ca.get("甲供含工费净材料", 0))
        Z  = float(ca.get("自加工净材料", 0))
        ZH = float(ca.get("自加工含工费净材料", 0))
    else:
        Y=YH=J=JH=Z=ZH=0

    F=rates["辅料率"]; G=rates["工费率"]; M=rates["管理费率"]; P=rates["利润率"]; T=rates["税率"]
    
    if method == "混合加工":
        辅料 = (Y + J) * F
        工费 = (Y + J + 辅料) * G
        管理费 = (Y + YH + 辅料 + 工费) * M
        利润 = (Y + YH + 辅料 + 工费 + 管理费) * P
        税金 = (Y + YH + 辅料 + 工费 + 管理费 + 利润) * T
        加工商定价 = Y + YH + 辅料 + 工费 + 管理费 + 利润 + 税金
        
        甲供单价 = J * 1.13 * (1 + M)
        自加工单价 = Z * 1.13 * (1 + G) * (1 + M)
        完工合计 = 加工商定价 + 甲供单价 + 自加工单价
        
    elif method == "完全外加工":
        辅料 = Y * F
        工费 = (Y + 辅料) * G
        管理费 = (Y + YH + 辅料 + 工费) * M
        利润 = (Y + YH + 辅料 + 工费 + 管理费) * P
        税金 = (Y + YH + 辅料 + 工费 + 管理费 + 利润) * T
        加工商定价 = Y + YH + 辅料 + 工费 + 管理费 + 利润 + 税金
        甲供单价 = 0
        自加工单价 = 0
        完工合计 = 加工商定价
        
    elif method == "完全自加工":
        辅料 = Z * F
        工费 = (Z + 辅料) * G
        管理费 = (Z + ZH + 辅料 + 工费) * M
        利润 = 0
        税金 = (Z + ZH + 辅料 + 工费 + 管理费) * T
        加工商定价 = 0
        甲供单价 = 0
        自加工单价 = Z + ZH + 辅料 + 工费 + 管理费 + 税金
        完工合计 = 自加工单价

    summary = pd.DataFrame([
        {"项目":"材料小计", "金额":round(Y+YH+J+JH+Z+ZH,2)},
        {"项目":"辅料及损耗", "金额":round(辅料,2), "费率":f"{F*100:.0f}%"},
        {"项目":"人工费", "金额":round(工费,2), "费率":f"{G*100:.0f}%"},
        {"项目":"管理费", "金额":round(管理费,2), "费率":f"{M*100:.0f}%"},
        {"项目":"利润", "金额":round(利润,2), "费率":f"{P*100:.0f}%"},
        {"项目":"税金", "金额":round(税金,2), "费率":f"{T*100:.0f}%"},
        {"项目":"合计", "金额":round(完工合计,2)}
    ])
    st.dataframe(summary, use_container_width=True, hide_index=True)
    
    if st.button("将费用行写入表1"):
        edited = edited[~edited["材料名称"].isin(fee_names)].copy()
        new_rows = pd.DataFrame([
            {"材料名称":"辅料及损耗","合计":round(辅料,2)},
            {"材料名称":"材料小计","合计":round(Y+YH+J+JH+Z+ZH,2)},
            {"材料名称":"人工费","合计":round(工费,2)},
            {"材料名称":"管理费","合计":round(管理费,2)},
            {"材料名称":"利润","合计":round(利润,2)},
            {"材料名称":"税金","合计":round(税金,2)},
            {"材料名称":"加工商定价","合计":round(加工商定价,2)},
            {"材料名称":"甲供单价","合计":round(甲供单价,2)},
            {"材料名称":"自加工单价","合计":round(自加工单价,2)},
            {"材料名称":"合计","合计":round(完工合计,2)}
        ])
        st.session_state.t1 = pd.concat([edited, new_rows], ignore_index=True)
        st.rerun()

# ========== ⑦ 表2 ==========
elif page == "⑦ 表2 完工成本汇总":
    st.title("表2 完工产品成本核算汇总表")
    t1 = st.session_state.t1
    if t1.empty:
        st.warning("请先在⑥表1中录入BOM并写入费用行")
        st.stop()
    
    # 提取所有产品
    fee_names = ["辅料及损耗","材料小计","人工费","管理费","利润","税金","合计","价格合计","加工商定价","甲供单价","自加工单价"]
    mat_rows = t1[~t1["材料名称"].isin(fee_names)]
    products = mat_rows[["产品编号","产品名称","型号","规格","加工方式"]].drop_duplicates().reset_index(drop=True)
    
    st.subheader("数量录入")
    qty_df = pd.DataFrame({
        "产品编号": products["产品编号"], "产品名称": products["产品名称"],
        "数量": [st.session_state.qty_map.get(pid, 100) for pid in products["产品编号"]]})
    qty_edited = st.data_editor(qty_df, num_rows="dynamic", use_container_width=True, key="qty_editor")
    for _, r in qty_edited.iterrows():
        st.session_state.qty_map[r["产品编号"]] = r["数量"]

    rows = []
    for i, r in products.iterrows():
        pid = r["产品编号"]; qty = st.session_state.qty_map.get(pid, 0)
        sub = t1[t1["产品编号"] == pid]
        
        # 从表1写入的行中提取数据
        def get_val(name):
            row = sub[sub["材料名称"] == name]
            if not row.empty: return float(pd.to_numeric(row["合计"], errors="coerce").fillna(0).iloc[0])
            return 0.0

        材料单价 = sub[~sub["材料名称"].isin(fee_names)]["合计"].sum()
        加工商定价 = get_val("加工商定价")
        甲供单价 = get_val("甲供单价")
        自加工单价 = get_val("自加工单价")
        完工合计 = get_val("合计")
        
        rows.append({
            "序号": i+1, "标识名称": r["产品名称"], "型号": r["型号"], "尺寸": r["规格"],
            "加工方式": r["加工方式"], "数量": qty, "材料单价": round(材料单价,2),
            "加工商定价": round(加工商定价,2), "甲供价格(含税)": round(甲供单价,2), 
            "自加工价格(含税)": round(自加工单价,2), "完工合计单价": round(完工合计,2),
            "合计金额": round(qty * 完工合计, 2), "备注": ""
        })
        
    t2 = pd.DataFrame(rows)
    st.subheader("表2 成本汇总")
    st.dataframe(t2, use_container_width=True, hide_index=True)
    st.metric("批次总金额", f"{t2['合计金额'].sum():,.2f}")

    if st.button("导出表2"):
        t2.to_excel("表2_成本汇总.xlsx", index=False)
        st.success("已导出")

# ========== ⑧ 材料系数计算 ==========
elif page == "⑧ 材料系数计算":
    st.title("材料系数计算")
    t1 = st.session_state.t1
    if t1.empty:
        st.warning("⚠️ 目前表1为空。请先到【⑥ 表1 单价分析】中录入材料BOM，系统才能根据材料汇总计算系数。")
        st.stop()
    fee_names = ["辅料及损耗","材料小计","人工费","管理费","利润","税金","合计","价格合计","加工商定价","甲供单价","自加工单价"]
    mat_only = t1[~t1["材料名称"].isin(fee_names)]
    
    mat_sum = mat_only.groupby("材料名称").agg(预算金额=("合计","sum")).reset_index()
    mat_sum["数量"] = 1
    mat_sum["调整后预算金额"] = mat_sum["预算金额"] * mat_sum["数量"]
    mat_sum["实际金额"] = mat_sum["材料名称"].map(lambda x: st.session_state.material_actual.get(x, 0))
    edited = st.data_editor(mat_sum, num_rows="dynamic", use_container_width=True,
        column_config={
            "预算金额": st.column_config.NumberColumn("预算金额", disabled=True, format="%.2f"),
            "数量": st.column_config.NumberColumn("数量", min_value=0.0, format="%.2f"),
            "调整后预算金额": st.column_config.NumberColumn("调整后预算金额", disabled=True, format="%.2f"),
            "实际金额": st.column_config.NumberColumn("实际金额", min_value=0.0, format="%.2f"),
        }, key="e_mat")
    def calc_coef(row):
        a = row["实际金额"]; b = row["调整后预算金额"]
        return b/a if a and a != 0 else 0
    edited["系数"] = edited.apply(calc_coef, axis=1)
    for _, r in edited.iterrows():
        if pd.notna(r["实际金额"]):
            st.session_state.material_actual[r["材料名称"]] = r["实际金额"]
    st.dataframe(edited[["材料名称","调整后预算金额","实际金额","系数"]], use_container_width=True, hide_index=True)
    if st.button("导出材料系数"):
        edited.to_excel("材料系数.xlsx", index=False)
        st.success("已导出")

# ========== ⑨ 单位维护 ==========
elif page == "⑨ 单位维护":
    st.title("单位维护")
    units_df = pd.DataFrame({"单位": st.session_state.units})
    edited = st.data_editor(units_df, num_rows="dynamic", use_container_width=True, key="e_units")
    if st.button("保存单位"):
        new_units = [u for u in edited["单位"].tolist() if u and pd.notna(u)]
        st.session_state.units = new_units
        st.success(f"已保存 {len(new_units)} 个单位")

# ========== ⑩ Excel导入 ==========
elif page == "⑩ Excel导入":
    st.title("Excel导入")
    uploaded = st.file_uploader("上传Excel文件", type=["xlsx","xls"])
    if uploaded is None:
        st.stop()
    xl = pd.ExcelFile(uploaded)
    st.write("检测到sheet：", xl.sheet_names)

    sheet_map = {
        "表3-1":"t31","型材":"t31","3-1":"t31",
        "表3-2":"t32","平米":"t32","3-2":"t32",
        "表3-3":"t33","按米":"t33","3-3":"t33",
        "表3-4":"t34","其他":"t34","3-4":"t34",
        "表3-5":"t35","LED":"t35","3-5":"t35",
        "表1":"t1","单价分析":"t1","BOM":"t1",
    }
    target_names = {"t31":"表3-1","t32":"表3-2","t33":"表3-3","t34":"表3-4","t35":"表3-5","t1":"表1"}
    schema = {
        "t31":["序号","材料名称","分类","型号","颜色","制造商","单位米重","平均价","系数","平均价*系数","元/kg","元/m","项目","备注"],
        "t32":["序号","材料名称","品种","颜色","单位","制造商","厚度(mm)","计价单位","单位重量","平均价","系数","平均价*系数","元/kg","元/平米","备注"],
        "t33":["序号","材料名称","品种","颜色","单位","制造商","厚度(mm)","计价单位","单位重量","平均价","系数","平均价*系数","元/kg","元/m","备注"],
        "t34":["序号","材料名称","单位","制造商","规格","颜色","平均价","系数","平均价*系数","材料价格","备注"],
        "t35":["序号","材料名称","单位","规格","型号","颜色","平均价","系数","平均价*系数","材料价格","备注"],
        "t1":["产品编号","产品名称","型号","规格","加工方式","序号","材料名称","规格尺寸","颜色","材质厚度","单位","数量","单价","合计","材料分类","匹配状态"],
    }
    def merge_import(existing, df, target):
        s = schema[target]
        df2 = pd.DataFrame()
        for c in s: df2[c] = df[c] if c in df.columns else ""
        return pd.concat([existing, df2], ignore_index=True)

    if st.button("一键导入所有sheet"):
        imported = []
        for sn in xl.sheet_names:
            at = None
            for kw, tgt in sheet_map.items():
                if kw in sn: at = tgt; break
            if at:
                df = pd.read_excel(uploaded, sheet_name=sn)
                df.columns = [str(c).strip() for c in df.columns]
                st.session_state[at] = merge_import(st.session_state[at], df, at)
                imported.append(f"{sn} → {target_names[at]}")
        st.success("已导入：\n" + "\n".join(imported))

# ========== ⑪ 公式配置 ==========
elif page == "⑪ 公式配置":
    st.title("公式配置")
    rows = []
    for (table, seq), cfg in st.session_state.formulas.items():
        rows.append({"表名":table,"序号":seq,"类别":cfg["类别"],"方式":cfg["方式"],"密度":cfg["密度"],"表达式":cfg.get("表达式","")})
    edited = st.data_editor(pd.DataFrame(rows), num_rows="dynamic", use_container_width=True, key="e_formula")
    if st.button("保存公式配置"):
        nf = {}
        for _, r in edited.iterrows():
            if pd.isna(r["表名"]) or pd.isna(r["序号"]): continue
            try: seq = int(r["序号"])
            except: continue
            nf[(r["表名"], seq)] = {"类别":r["类别"],"方式":r["方式"],"密度":float(r["密度"]),"表达式": r.get("表达式","")}
        st.session_state.formulas = nf
        st.success("已保存")