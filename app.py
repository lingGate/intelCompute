# -*- coding: utf-8 -*-
"""
项目独立核算系统 v17.0
- 新增【数据备份与恢复】页面，一键导出/导入全套数据
"""

import streamlit as st
import pandas as pd
import numpy as np
import re, math
import io

st.set_page_config(page_title="项目独立核算系统", layout="wide")
TAX_FACTOR = 1/1.13

# ========== 初始化 ==========
def init_state():
    if "params" not in st.session_state:
        st.session_state.params = {"辅料率":0.10,"工费率":0.40,"管理费率":0.07,"利润率":0.20,"税率":0.13}
    if "units" not in st.session_state:
        st.session_state.units = ["公斤","米","平米","个","套","根","支","块","件","张","卷"]
    if "formulas" not in st.session_state:
        st.session_state.formulas = {
            ("表3-2", 1): {"类别":"铝板","方式":"板材","密度":2.70,"表达式":""},
            ("表3-2", 2): {"类别":"角铝","方式":"板材","密度":2.70,"表达式":""},
            ("表3-2", 3): {"类别":"PC板","方式":"板材","密度":1.20,"表达式":""},
            ("表3-3", 1): {"类别":"304不锈钢管","方式":"自动识别","密度":7.93,"表达式":""},
            ("表3-3", 2): {"类别":"201不锈钢管","方式":"自动识别","密度":7.93,"表达式":""},
            ("表3-3", 3): {"类别":"铝管","方式":"自动识别","密度":2.70,"表达式":""},
        }
    
    if "t31" not in st.session_state:
        st.session_state.t31 = pd.DataFrame(columns=["序号","材料名称","分类","型号","颜色","制造商","单位米重","平均价","系数","平均价*系数","元/kg","元/m","项目","备注"])
    if "t32" not in st.session_state:
        st.session_state.t32 = pd.DataFrame(columns=["序号","材料名称","品种","颜色","单位","制造商","厚度(mm)","计价单位","单位重量","平均价","系数","平均价*系数","元/kg","元/平米","备注"])
    if "t33" not in st.session_state:
        st.session_state.t33 = pd.DataFrame(columns=["序号","材料名称","品种","颜色","单位","制造商","厚度(mm)","计价单位","单位重量","平均价","系数","平均价*系数","元/kg","元/m","备注"])
    if "t34" not in st.session_state:
        st.session_state.t34 = pd.DataFrame(columns=["序号","材料名称","单位","制造商","规格","颜色","平均价","系数","平均价*系数","材料价格","备注"])
    if "t35" not in st.session_state:
        st.session_state.t35 = pd.DataFrame(columns=["序号","材料名称","单位","规格","型号","颜色","平均价","系数","平均价*系数","材料价格","备注"])
        
    if "t1" not in st.session_state:
        st.session_state.t1 = pd.DataFrame(columns=[
            "产品编号","产品名称","型号","规格","加工方式","序号","材料名称","规格尺寸","颜色","材质厚度","单位",
            "数量","单价","合计","材料分类","匹配状态","备注(费率)"])
            
    if "qty_map" not in st.session_state: st.session_state.qty_map = {}
    if "material_actual" not in st.session_state: st.session_state.material_actual = {}
    if "batch_rates" not in st.session_state: st.session_state.batch_rates = {}
    if "current_batch" not in st.session_state: st.session_state.current_batch = "A-001"

init_state()

# ========== 辅助函数 ==========
def parse_perimeter(spec):
    if not spec or pd.isna(spec): return 0
    spec = str(spec).strip().replace("×","*").replace("x","*").replace("X","*")
    m = re.search(r'(\d+(?:\.\d+)?)\s*[*]\s*(\d+(?:\.\d+)?)', spec)
    if m:
        A = float(m.group(1)); B = float(m.group(2))
        return (A + B) * 2 / 1000
    m = re.search(r'(\d+(?:\.\d+)?)', spec)
    if m:
        D = float(m.group(1))
        return math.pi * D / 1000
    return 0

# ========== 表3计算公式 ==========
def calc_t31(df):
    df = df.copy()
    for c in ["单位米重","平均价","系数"]: df[c] = pd.to_numeric(df[c], errors="coerce")
    df["系数"] = df["系数"].fillna(TAX_FACTOR).replace(0, TAX_FACTOR)
    df["平均价*系数"] = df["平均价"].fillna(0) * df["系数"]
    df["元/kg"] = df["平均价*系数"]
    df["元/m"] = df["单位米重"].fillna(0) * df["元/kg"]
    return df

def calc_t32(df):
    df = df.copy()
    for c in ["厚度(mm)","单位重量","平均价","系数","元/kg"]:
        if c not in df.columns: df[c] = float('nan')
        df[c] = pd.to_numeric(df[c], errors="coerce")
            
    df["系数"] = df["系数"].fillna(TAX_FACTOR).replace(0, TAX_FACTOR)
    df["平均价*系数"] = df["平均价"].fillna(0) * df["系数"]
    
    w_list, p_list = [], []
    for _, r in df.iterrows():
        thick = r.get("厚度(mm)")
        seq = r.get("序号")
        try: seq = int(seq)
        except: seq = None
        
        cfg = st.session_state.formulas.get(("表3-2", seq)) if seq else None
        density = cfg["密度"] if cfg else 0
        
        w = r.get("单位重量")
        if pd.isna(w) or w == 0:
            if pd.notna(thick) and thick > 0 and density > 0:
                w = density * thick
            else:
                w = 0
                
        if w > 0:
            base_price_kg = r.get("元/kg")
            if pd.isna(base_price_kg) or base_price_kg == 0:
                base_price_kg = r["平均价*系数"]
            p_m2 = base_price_kg * w
            w_list.append(round(w, 4)); p_list.append(round(p_m2, 4))
        else:
            w_list.append(0); p_list.append(r["平均价*系数"])
            
    df["单位重量"] = w_list
    df["元/平米"] = p_list
    df["元/kg"] = df["元/kg"].fillna(df["平均价*系数"])
    return df

def calc_t33(df):
    df = df.copy()
    for c in ["厚度(mm)","单位重量","平均价","系数","元/kg"]:
        if c not in df.columns: df[c] = float('nan')
        df[c] = pd.to_numeric(df[c], errors="coerce")
            
    df["系数"] = df["系数"].fillna(TAX_FACTOR).replace(0, TAX_FACTOR)
    df["平均价*系数"] = df["平均价"].fillna(0) * df["系数"]
    
    w_list, m_list = [], []
    for _, r in df.iterrows():
        thick = r.get("厚度(mm)")
        spec = r.get("品种", "")
        seq = r.get("序号")
        try: seq = int(seq)
        except: seq = None
        
        cfg = st.session_state.formulas.get(("表3-3", seq)) if seq else None
        density = cfg["密度"] if cfg else 0
        
        w = r.get("单位重量")
        if pd.isna(w) or w == 0:
            if pd.notna(thick) and thick > 0 and density > 0:
                perimeter = parse_perimeter(spec)
                if perimeter > 0:
                    w = density * perimeter * thick
                else:
                    w = 0
            else:
                w = 0
                
        if w > 0:
            base_price_kg = r.get("元/kg")
            if pd.isna(base_price_kg) or base_price_kg == 0:
                base_price_kg = r["平均价*系数"]
            p_m = base_price_kg * w
            w_list.append(round(w, 4)); m_list.append(round(p_m, 4))
        else:
            w_list.append(0); m_list.append(r["平均价*系数"])
            
    df["单位重量"] = w_list
    df["元/m"] = m_list
    df["元/kg"] = df["元/kg"].fillna(df["平均价*系数"])
    return df

def calc_t34(df):
    df = df.copy()
    for c in ["平均价","系数"]: df[c] = pd.to_numeric(df[c], errors="coerce")
    df["系数"] = df["系数"].fillna(TAX_FACTOR).replace(0, TAX_FACTOR)
    df["平均价*系数"] = df["平均价"].fillna(0) * df["系数"]
    df["材料价格"] = df["平均价*系数"]
    return df

def calc_t35(df): return calc_t34(df)

# ========== 价格匹配 ==========
def build_price_index():
    index = {}
    def add(name, unit, price, spec="", model="", color="", thickness=""):
        if not name or pd.isna(name) or pd.isna(price) or float(price) <= 0: return
        key = (str(name).strip(), str(unit).strip())
        index.setdefault(key, [])
        index[key].append({"规格":str(spec).strip() if pd.notna(spec) else "", "型号":str(model).strip() if pd.notna(model) else "", "颜色":str(color).strip() if pd.notna(color) else "", "厚度":str(thickness).strip() if pd.notna(thickness) else "", "单价":float(price)})
    
    for _, r in calc_t31(st.session_state.t31).iterrows():
        add(r.get("材料名称"), "公斤", r.get("元/kg"), model=r.get("型号"), color=r.get("颜色"))
        add(r.get("材料名称"), "米", r.get("元/m"), model=r.get("型号"), color=r.get("颜色"))
    for _, r in calc_t32(st.session_state.t32).iterrows():
        add(r.get("材料名称"), "公斤", r.get("元/kg"), spec=r.get("品种"), color=r.get("颜色"), thickness=r.get("厚度(mm)"))
        add(r.get("材料名称"), "平米", r.get("元/平米"), spec=r.get("品种"), color=r.get("颜色"), thickness=r.get("厚度(mm)"))
    for _, r in calc_t33(st.session_state.t33).iterrows():
        add(r.get("材料名称"), "公斤", r.get("元/kg"), spec=r.get("品种"), color=r.get("颜色"), thickness=r.get("厚度(mm)"))
        add(r.get("材料名称"), "米", r.get("元/m"), spec=r.get("品种"), color=r.get("颜色"), thickness=r.get("厚度(mm)"))
    for _, r in calc_t34(st.session_state.t34).iterrows():
        add(r.get("材料名称"), r.get("单位") or "个", r.get("材料价格"), spec=r.get("规格"), color=r.get("颜色"))
    for _, r in calc_t35(st.session_state.t35).iterrows():
        add(r.get("材料名称"), r.get("单位") or "个", r.get("材料价格"), spec=r.get("规格"), model=r.get("型号"), color=r.get("颜色"))
    return index

def match_price(index, name, unit, spec="", model="", color="", thickness=""):
    name_str = str(name).strip(); unit_str = str(unit).strip()
    key = (name_str, unit_str)
    if key not in index:
        found = False
        for k in index.keys():
            if k[0] == name_str: key = k; found = True; break
        if not found: return None, "未找到材料名称"
    cands = index[key]
    if len(cands) == 1: return cands[0]["单价"], "唯一匹配"
    def score(c):
        s = 0
        search_text = f"{spec} {model} {color} {thickness}".lower().replace(" ", "")
        if c["规格"] and c["规格"].lower().replace(" ", "") in search_text: s += 1
        if c["型号"] and c["型号"].lower().replace(" ", "") in search_text: s += 2
        if c["颜色"] and c["颜色"].lower().replace(" ", "") in search_text: s += 1
        if c["厚度"] and c["厚度"].lower().replace(" ", "") in search_text: s += 1
        return s
    scored = sorted(cands, key=score, reverse=True)
    return (scored[0]["单价"], f"匹配特征") if score(scored[0]) > 0 else (scored[0]["单价"], "按名称强制匹配")

# ========== 通用渲染 ==========
def render_t3(df, calc_func, auto_cols, key):
    calc_df = calc_func(df.copy())
    col_config = {c: st.column_config.NumberColumn(c, disabled=True, format="%.4f") for c in auto_cols}
    col_config["系数"] = st.column_config.NumberColumn("系数", format="%.6f")
    col_config["单位米重"] = st.column_config.NumberColumn("单位米重(kg/m)", format="%.4f")
    col_config["单位重量"] = st.column_config.NumberColumn("单位重量", format="%.4f")
    col_config["计价单位"] = st.column_config.SelectboxColumn("计价单位", options=["元/公斤","元/平米","元/m"], required=False)
    if "元/kg" in calc_df.columns:
        col_config["元/kg"] = st.column_config.NumberColumn("元/kg (可手改)", format="%.4f")
        
    edited = st.data_editor(calc_df, num_rows="dynamic", use_container_width=True, column_config=col_config, key=key)
    return edited.reset_index(drop=True)

def default_coef_widget(table_state, key_prefix):
    c1, c2 = st.columns([1, 3])
    with c1: default_coef = st.number_input("默认系数", value=TAX_FACTOR, step=0.000001, format="%.6f", key=f"dc_{key_prefix}")
    with c2:
        if st.button("一键应用系数", key=f"apply_{key_prefix}"):
            if not table_state.empty: table_state["系数"] = default_coef; st.success("已应用")
    return default_coef

# ========== 侧边栏 ==========
st.sidebar.title("项目独立核算系统")
page = st.sidebar.radio("导航", [
    "① 表3-1 型材类","② 表3-2 按平米类","③ 表3-3 按米类",
    "④ 表3-4 其他类","⑤ 表3-5 LED类","⑥ 表1 单价分析",
    "⑦ 表2 完工成本汇总","⑧ 材料系数计算","⑨ 单位维护",
    "⑩ Excel导入","⑪ 公式配置", "⑫ 数据备份与恢复"
])

# ========== 表3页面 ==========
if page == "① 表3-1 型材类":
    st.title("表3-1 型材类材料价格明细")
    df = st.session_state.t31.copy()
    dc = default_coef_widget(df, "31")
    if not df.empty and "系数" in df.columns: df["系数"] = pd.to_numeric(df["系数"], errors="coerce").fillna(dc).replace(0, dc)
    st.session_state.t31 = render_t3(df, calc_t31, ["平均价*系数","元/kg","元/m"], "e_t31")

elif page == "② 表3-2 按平米类":
    st.title("表3-2 按平米计算类材料价格明细")
    df = st.session_state.t32.copy()
    dc = default_coef_widget(df, "32")
    if not df.empty and "系数" in df.columns: df["系数"] = pd.to_numeric(df["系数"], errors="coerce").fillna(dc).replace(0, dc)
    st.session_state.t32 = render_t3(df, calc_t32, ["单位重量","平均价*系数","元/平米"], "e_t32")

elif page == "③ 表3-3 按米类":
    st.title("表3-3 按米计算类材料价格明细")
    df = st.session_state.t33.copy()
    dc = default_coef_widget(df, "33")
    if not df.empty and "系数" in df.columns: df["系数"] = pd.to_numeric(df["系数"], errors="coerce").fillna(dc).replace(0, dc)
    st.session_state.t33 = render_t3(df, calc_t33, ["单位重量","平均价*系数","元/m"], "e_t33")

elif page == "④ 表3-4 其他类":
    st.title("表3-4 其他类材料价格明细")
    df = st.session_state.t34.copy()
    dc = default_coef_widget(df, "34")
    if not df.empty and "系数" in df.columns: df["系数"] = pd.to_numeric(df["系数"], errors="coerce").fillna(dc).replace(0, dc)
    st.session_state.t34 = render_t3(df, calc_t34, ["平均价*系数","材料价格"], "e_t34")

elif page == "⑤ 表3-5 LED类":
    st.title("表3-5 LED类材料价格明细")
    df = st.session_state.t35.copy()
    dc = default_coef_widget(df, "35")
    if not df.empty and "系数" in df.columns: df["系数"] = pd.to_numeric(df["系数"], errors="coerce").fillna(dc).replace(0, dc)
    st.session_state.t35 = render_t3(df, calc_t35, ["平均价*系数","材料价格"], "e_t35")

# ========== ⑥ 表1 单价分析 ==========
elif page == "⑥ 表1 单价分析":
    st.title("表1 单件产品单价分析")
    
    batch_id = st.text_input("批次号", st.session_state.current_batch, key="t1_batch")
    st.session_state.current_batch = batch_id
    if batch_id not in st.session_state.batch_rates:
        st.session_state.batch_rates[batch_id] = {"辅料率":0.10,"工费率":0.40,"管理费率":0.07,"利润率":0.20,"税率":0.13}
    rates = st.session_state.batch_rates[batch_id]

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: r_aux = st.number_input("辅料率", value=rates["辅料率"], step=0.01, format="%.4f", key="r_aux")
    with c2: r_labor = st.number_input("工费率", value=rates["工费率"], step=0.01, format="%.4f", key="r_labor")
    with c3: r_mgmt = st.number_input("管理费率", value=rates["管理费率"], step=0.01, format="%.4f", key="r_mgmt")
    with c4: r_profit = st.number_input("利润率", value=rates["利润率"], step=0.01, format="%.4f", key="r_profit")
    with c5: r_tax = st.number_input("税率", value=rates["税率"], step=0.01, format="%.4f", key="r_tax")

    if st.button("保存本批次费率"):
        st.session_state.batch_rates[batch_id] = {"辅料率":r_aux,"工费率":r_labor,"管理费率":r_mgmt,"利润率":r_profit,"税率":r_tax}
        st.success(f"已保存 {batch_id} 费率")
    rates = st.session_state.batch_rates[batch_id]

    st.markdown("---")
    st.subheader("BOM明细录入")
    col_m1, col_m2 = st.columns([1, 3])
    with col_m1:
        current_mode = st.selectbox("当前产品加工方式", ["混合外加工", "完全自加工", "完全外加工"])
    with col_m2:
        if current_mode in ["完全自加工", "完全外加工"]:
            category_options = ["自加工净材料", "自加工含工费净材料"]
            st.info(f"由于选择了【{current_mode}】，材料分类仅允许选择自加工类材料。")
        else:
            category_options = ["乙供净材料","乙供含工费净材料","甲供净材料","甲供含工费净材料","自加工净材料","自加工含工费净材料"]
            st.info("当前为混合外加工，开放全部六种材料分类。")

    price_index = build_price_index()
    material_names = sorted(set([k[0] for k in price_index.keys()]))
    
    df = st.session_state.t1.copy()
    for c in ["产品编号","产品名称","型号","规格","加工方式","序号","材料名称","规格尺寸","颜色","材质厚度","单位","数量","单价","合计","材料分类","匹配状态","备注(费率)"]:
        if c not in df.columns: df[c] = ""
    if df.empty: df = pd.DataFrame([{c: "" for c in df.columns}])

    edited = st.data_editor(df, num_rows="dynamic", use_container_width=True,
        column_config={
            "加工方式": st.column_config.SelectboxColumn("加工方式", options=["混合外加工", "完全自加工", "完全外加工"], required=True),
            "材料名称": st.column_config.SelectboxColumn("材料名称", options=material_names, required=False) if material_names else st.column_config.TextColumn("材料名称"),
            "单位": st.column_config.SelectboxColumn("单位", options=st.session_state.units, required=False),
            "数量": st.column_config.NumberColumn("数量", min_value=0.0, format="%.4f"),
            "单价": st.column_config.NumberColumn("单价", disabled=True, format="%.4f"),
            "合计": st.column_config.NumberColumn("合计", disabled=True, format="%.4f"),
            "匹配状态": st.column_config.TextColumn("匹配状态", disabled=True),
            "材料分类": st.column_config.SelectboxColumn("材料分类", options=category_options, required=False),
        }, key="e_t1")

    if not edited.empty:
        prices, statuses = [], []
        for _, r in edited.iterrows():
            name = r.get("材料名称"); unit = r.get("单位")
            spec = r.get("规格尺寸",""); model = r.get("型号","")
            color = r.get("颜色",""); thick = r.get("材质厚度","")
            if not name or not unit: prices.append(0); statuses.append("未填写"); continue
            p, s = match_price(price_index, name, unit, spec, model, color, thick)
            if p is None: prices.append(0); statuses.append("❌ 新材料")
            else: prices.append(p); statuses.append(f"✅ {s}")
        
        edited["单价"] = pd.Series(prices, index=edited.index)
        edited["匹配状态"] = pd.Series(statuses, index=edited.index)
        safe_qty = pd.to_numeric(edited["数量"], errors="coerce").fillna(0)
        edited["合计"] = safe_qty * edited["单价"]

    费用名称 = ["辅料及损耗","材料小计","人工费","管理费","利润","税金","价格合计"]
    材料行 = edited[~edited["材料名称"].isin(费用名称)].copy()
    
    def get_sum(cat_name):
        sub = 材料行[材料行["材料分类"] == cat_name]
        return pd.to_numeric(sub["合计"], errors="coerce").fillna(0).sum()

    Y = get_sum("乙供净材料")
    YH = get_sum("乙供含工费净材料")
    J = get_sum("甲供净材料")
    JH = get_sum("甲供含工费净材料")
    Z = get_sum("自加工净材料")
    ZH = get_sum("自加工含工费净材料")

    F = rates["辅料率"]; G = rates["工费率"]; M = rates["管理费率"]; P = rates["利润率"]; T = rates["税率"]

    if current_mode == "完全自加工" or current_mode == "完全外加工":
        辅料 = Z * F
    else:
        辅料 = (Y + J) * F

    材料小计 = (Z + ZH if current_mode != "混合外加工" else Y + YH) + 辅料

    if current_mode == "完全自加工":
        人工费 = (Z + 辅料) * G
        管理费 = (材料小计 + 人工费) * M
        利润 = 0
        税金 = (材料小计 + 人工费 + 管理费) * T
    elif current_mode == "完全外加工":
        人工费 = (Z + 辅料) * G
        管理费 = (材料小计 + 人工费) * M
        利润 = (材料小计 + 人工费) * P
        税金 = (材料小计 + 人工费 + 管理费 + 利润) * T
    else: # 混合外加工
        人工费 = (Y + J + 辅料) * G
        管理费 = (材料小计 + 人工费) * M
        利润 = (材料小计 + 人工费) * P
        税金 = (材料小计 + 人工费 + 管理费 + 利润) * T

    价格合计 = 材料小计 + 人工费 + 管理费 + 利润 + 税金

    if st.button("💾 把费用行写入表1"):
        edited = edited[~edited["材料名称"].isin(费用名称)].copy()
        new_rows = pd.DataFrame([
            {"材料名称":"辅料及损耗","备注(费率)":f"{rates['辅料率']*100:.2f}%","合计":round(辅料,2)},
            {"材料名称":"材料小计","备注(费率)":"","合计":round(材料小计,2)},
            {"材料名称":"人工费","备注(费率)":f"{rates['工费率']*100:.2f}%","合计":round(人工费,2)},
            {"材料名称":"管理费","备注(费率)":f"{rates['管理费率']*100:.2f}%","合计":round(管理费,2)},
            {"材料名称":"利润","备注(费率)":f"{rates['利润率']*100:.2f}%","合计":round(利润,2)},
            {"材料名称":"税金","备注(费率)":f"{rates['税率']*100:.2f}%","合计":round(税金,2)},
            {"材料名称":"价格合计","备注(费率)":"","合计":round(价格合计,2)},
        ])
        st.session_state.t1 = pd.concat([edited, new_rows], ignore_index=True)
        st.success("费用行已写入")
        st.rerun()

    st.session_state.t1 = edited

    st.subheader("费用汇总预览")
    summary = pd.DataFrame([
        {"项目":"辅料及损耗", "金额":round(辅料,2), "费率":f"{rates['辅料率']*100:.2f}%"},
        {"项目":"材料小计(含辅料)", "金额":round(材料小计,2)},
        {"项目":"人工费", "金额":round(人工费,2), "费率":f"{rates['工费率']*100:.2f}%"},
        {"项目":"管理费", "金额":round(管理费,2), "费率":f"{rates['管理费率']*100:.2f}%"},
        {"项目":"利润", "金额":round(利润,2), "费率":f"{rates['利润率']*100:.2f}%"},
        {"项目":"税金", "金额":round(税金,2), "费率":f"{rates['税率']*100:.2f}%"},
        {"项目":"价格合计", "金额":round(价格合计,2)},
    ])
    st.dataframe(summary, use_container_width=True, hide_index=True)

# ========== ⑦ 表2 完工成本汇总 ==========
elif page == "⑦ 表2 完工成本汇总":
    st.title("表2 完工产品成本汇总表")

    t1 = st.session_state.t1
    if t1.empty or "价格合计" not in t1["材料名称"].values:
        st.warning("请先在⑥表1中录入BOM，并点击写入费用行。"); st.stop()

    batch_id = st.session_state.current_batch
    p = st.session_state.batch_rates.get(batch_id, {"辅料率":0.10,"工费率":0.40,"管理费率":0.07,"利润率":0.20,"税率":0.13})

    valid_products = t1[t1["产品编号"].notna() & (t1["产品编号"] != "")]
    if valid_products.empty: st.warning("表1中没有有效的产品编号"); st.stop()
    
    products = valid_products[["产品编号","产品名称","型号","规格","加工方式"]].drop_duplicates(subset=["产品编号"]).reset_index(drop=True)

    st.subheader("第一步：确认产品数量")
    qty_list = [st.session_state.qty_map.get(pid, 100) for pid in products["产品编号"]]
    qty_df = pd.DataFrame({"产品编号": products["产品编号"], "产品名称": products["产品名称"], "加工方式": products["加工方式"], "数量": qty_list})
    
    with st.form("qty_form"):
        qty_edited = st.data_editor(qty_df, num_rows="fixed", use_container_width=True,
            column_config={
                "产品编号": st.column_config.TextColumn("产品编号", disabled=True),
                "产品名称": st.column_config.TextColumn("产品名称", disabled=True),
                "加工方式": st.column_config.TextColumn("加工方式", disabled=True),
                "数量": st.column_config.NumberColumn("数量 (按回车确认输入)", min_value=0, step=1, format="%d")
            })
        submit_btn = st.form_submit_button("✅ 保存数量并生成表2")

    if submit_btn:
        for _, r in qty_edited.iterrows():
            st.session_state.qty_map[r["产品编号"]] = r["数量"]
        st.success("数量已保存，金额已更新！")

    st.subheader("第二步：成本汇总结果")
    def calc_prices_for_product(pid):
        sub = t1[t1["产品编号"] == pid]
        mode = sub["加工方式"].iloc[0] if "加工方式" in sub.columns and len(sub) > 0 else "混合外加工"
        if pd.isna(mode) or mode == "": mode = "混合外加工"

        材料行名 = ["辅料及损耗","材料小计","人工费","管理费","利润","税金","价格合计"]
        sub_mat = sub[~sub["材料名称"].isin(材料行名)]
        
        def get_sum(cat_name):
            mat = sub_mat[sub_mat["材料分类"] == cat_name]
            return pd.to_numeric(mat["合计"], errors="coerce").fillna(0).sum()

        Y = get_sum("乙供净材料")
        YH = get_sum("乙供含工费净材料")
        J = get_sum("甲供净材料")
        JH = get_sum("甲供含工费净材料")
        Z = get_sum("自加工净材料")
        ZH = get_sum("自加工含工费净材料")

        F=p["辅料率"];G=p["工费率"];M=p["管理费率"];P=p["利润率"];T=p["税率"]

        if mode == "完全自加工":
            纯材料 = Z + ZH
            辅料 = Z * F
            材料小计 = 纯材料 + 辅料
            人工费 = (Z + 辅料) * G
            管理费 = (材料小计 + 人工费) * M
            税金 = (材料小计 + 人工费 + 管理费) * T
            自加工价格 = 材料小计 + 人工费 + 管理费 + 税金
            return {"材料单价": round(纯材料,2), "加工商定价": 0, "甲供价格(含税)": 0, "自加工价格(含税)": round(自加工价格,2), "完工合计单价": round(自加工价格,2)}

        elif mode == "完全外加工":
            纯材料 = Z + ZH
            辅料 = Z * F
            材料小计 = 纯材料 + 辅料
            人工费 = (Z + 辅料) * G
            管理费 = (材料小计 + 人工费) * M
            利润 = (材料小计 + 人工费) * P
            税金 = (材料小计 + 人工费 + 管理费 + 利润) * T
            外加工价格 = 材料小计 + 人工费 + 管理费 + 利润 + 税金
            return {"材料单价": round(纯材料,2), "加工商定价": round(外加工价格,2), "甲供价格(含税)": 0, "自加工价格(含税)": 0, "完工合计单价": round(外加工价格,2)}

        else: # 混合外加工
            纯材料 = Y + YH
            辅料 = (Y + J) * F
            材料小计 = 纯材料 + 辅料
            人工费 = (Y + J + 辅料) * G
            管理费 = (材料小计 + 人工费) * M
            利润 = (材料小计 + 人工费) * P
            税金 = (材料小计 + 人工费 + 管理费 + 利润) * T
            加工商定价 = 材料小计 + 人工费 + 管理费 + 利润 + 税金

            甲供价格 = (J + JH) * 1.13 * (1 + M)
            自加工价格 = (Z + ZH) * 1.13 * (1 + G) * (1 + M)

            完工合计单价 = 加工商定价 + 甲供价格 + 自加工价格
            return {"材料单价": round(纯材料,2), "加工商定价": round(加工商定价,2), "甲供价格(含税)": round(甲供价格,2), "自加工价格(含税)": round(自加工价格,2), "完工合计单价": round(完工合计单价,2)}

    rows = []
    for i, r in products.iterrows():
        pid = r["产品编号"]; qty = st.session_state.qty_map.get(pid, 0)
        pr = calc_prices_for_product(pid)
        rows.append({"序号": i+1, "标识名称": r["产品名称"], "型号": r["型号"], "尺寸": r["规格"], "加工方式": r["加工方式"], "数量": qty, **pr, "合计金额": round(qty * pr["完工合计单价"], 2)})
    
    t2 = pd.DataFrame(rows)
    st.dataframe(t2, use_container_width=True, hide_index=True)
    st.metric("批次总金额", f"{t2['合计金额'].sum():,.2f}")

    if st.button("导出表2到Excel"):
        t2.to_excel("表2_成本汇总.xlsx", index=False)
        st.success("已导出 表2_成本汇总.xlsx")

# ========== ⑧ 材料系数 ==========
elif page == "⑧ 材料系数计算":
    st.title("材料系数计算")
    t1 = st.session_state.t1
    if t1.empty: st.warning("请先在⑥表1中录入BOM"); st.stop()
    费用行名 = ["辅料及损耗","材料小计","人工费","管理费","利润","税金","价格合计"]
    mat_only = t1[~t1["材料名称"].isin(费用行名) & t1["材料名称"].notna() & (t1["材料名称"] != "")]
    mat_sum = mat_only.groupby("材料名称").agg(预算金额=("合计","sum")).reset_index()
    mat_sum["数量"] = 1
    mat_sum["调整后预算金额"] = mat_sum["预算金额"] * mat_sum["数量"]
    mat_sum["实际金额"] = mat_sum["材料名称"].map(lambda x: st.session_state.material_actual.get(x, 0))
    edited = st.data_editor(mat_sum, num_rows="dynamic", use_container_width=True,
        column_config={"预算金额": st.column_config.NumberColumn("预算金额", disabled=True, format="%.2f"), "数量": st.column_config.NumberColumn("数量", min_value=0.0, format="%.2f"), "调整后预算金额": st.column_config.NumberColumn("调整后预算金额", disabled=True, format="%.2f"), "实际金额": st.column_config.NumberColumn("实际金额", min_value=0.0, format="%.2f")}, key="e_mat")
    edited["系数"] = edited.apply(lambda r: r["调整后预算金额"]/r["实际金额"] if r["实际金额"] and r["实际金额"] != 0 else 0, axis=1)
    for _, r in edited.iterrows():
        if pd.notna(r["实际金额"]): st.session_state.material_actual[r["材料名称"]] = r["实际金额"]
    st.dataframe(edited[["材料名称","调整后预算金额","实际金额","系数"]], use_container_width=True, hide_index=True)

# ========== ⑨ 单位维护 ==========
elif page == "⑨ 单位维护":
    st.title("单位维护")
    edited = st.data_editor(pd.DataFrame({"单位": st.session_state.units}), num_rows="dynamic", use_container_width=True)
    if st.button("保存单位"):
        st.session_state.units = [u for u in edited["单位"].tolist() if u and pd.notna(u)]
        st.success("已保存")

# ========== ⑩ Excel导入 ==========
elif page == "⑩ Excel导入":
    st.title("Excel导入")
    uploaded = st.file_uploader("上传Excel文件", type=["xlsx","xls"])
    if uploaded is None: st.info("支持：表3-1至3-5、表1 等sheet"); st.stop()
    xl = pd.ExcelFile(uploaded)
    sheet_map = {"表3-1":"t31","型材":"t31","3-1":"t31","表3-2":"t32","平米":"t32","3-2":"t32","表3-3":"t33","按米":"t33","3-3":"t33","表3-4":"t34","其他":"t34","3-4":"t34","表3-5":"t35","LED":"t35","3-5":"t35","表1":"t1","单价分析":"t1","BOM":"t1"}
    
    schema = {
        "t31":["序号","材料名称","分类","型号","颜色","制造商","单位米重","平均价","系数","平均价*系数","元/kg","元/m","项目","备注"],
        "t32":["序号","材料名称","品种","颜色","单位","制造商","厚度(mm)","计价单位","单位重量","平均价","系数","平均价*系数","元/kg","元/平米","备注"],
        "t33":["序号","材料名称","品种","颜色","单位","制造商","厚度(mm)","计价单位","单位重量","平均价","系数","平均价*系数","元/kg","元/m","备注"],
        "t34":["序号","材料名称","单位","制造商","规格","颜色","平均价","系数","平均价*系数","材料价格","备注"],
        "t35":["序号","材料名称","单位","规格","型号","颜色","平均价","系数","平均价*系数","材料价格","备注"],
        "t1":["产品编号","产品名称","型号","规格","加工方式","序号","材料名称","规格尺寸","颜色","材质厚度","单位","数量","单价","合计","材料分类","匹配状态","备注(费率)"]
    }
    
    def merge_import(existing, df, target):
        df2 = pd.DataFrame()
        for c in schema[target]: df2[c] = df[c] if c in df.columns else ""
        return pd.concat([existing, df2], ignore_index=True)
    
    if st.button("一键导入所有sheet"):
        for sn in xl.sheet_names:
            at = next((tgt for kw, tgt in sheet_map.items() if kw in sn), None)
            if at:
                df = pd.read_excel(uploaded, sheet_name=sn)
                df.columns = [str(c).strip() for c in df.columns]
                st.session_state[at] = merge_import(st.session_state[at], df, at)
        st.success("已自动导入所有匹配的Sheet")

# ========== ⑪ 公式配置 ==========
elif page == "⑪ 公式配置":
    st.title("公式配置")
    rows = [{"表名":t, "序号":s, "类别":c["类别"], "方式":c["方式"], "密度":c["密度"], "表达式":c.get("表达式","")} for (t,s),c in st.session_state.formulas.items()]
    edited = st.data_editor(pd.DataFrame(rows), num_rows="dynamic", use_container_width=True,
        column_config={
            "表名": st.column_config.SelectboxColumn("表名", options=["表3-2","表3-3"], required=True),
            "方式": st.column_config.SelectboxColumn("方式", options=["板材","方管","圆管","自动识别","自定义"], required=True),
            "密度": st.column_config.NumberColumn("密度(g/cm³)", format="%.3f"),
        })
    if st.button("保存公式配置"):
        st.session_state.formulas = {(r["表名"], int(r["序号"])): {"类别":r["类别"], "方式":r["方式"], "密度":float(r["密度"]), "表达式":r.get("表达式","")} for _, r in edited.iterrows() if pd.notna(r["序号"])}
        st.success("已保存")

# ========== ⑫ 数据备份与恢复 ==========
elif page == "⑫ 数据备份与恢复":
    st.title("数据备份与恢复")
    st.caption("将当前系统中的所有表格打包下载为 Excel 备份文件。如果程序重启或更新，可在此处一键恢复。")

    st.markdown("### 1. 一键导出数据备份")
    if st.button("📦 生成当前数据备份文件"):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # 导出表3-1到3-5
            if not st.session_state.t31.empty:
                st.session_state.t31.to_excel(writer, sheet_name="表3-1型材类", index=False)
            if not st.session_state.t32.empty:
                st.session_state.t32.to_excel(writer, sheet_name="表3-2按平米类", index=False)
            if not st.session_state.t33.empty:
                st.session_state.t33.to_excel(writer, sheet_name="表3-3按米类", index=False)
            if not st.session_state.t34.empty:
                st.session_state.t34.to_excel(writer, sheet_name="表3-4其他类", index=False)
            if not st.session_state.t35.empty:
                st.session_state.t35.to_excel(writer, sheet_name="表3-5LED类", index=False)
            
            # 导出表1
            if not st.session_state.t1.empty:
                st.session_state.t1.to_excel(writer, sheet_name="表1单价分析", index=False)
        
        st.success("✅ 备份文件已生成，请点击下方按钮下载！")
        st.download_button(
            label="📥 点击下载备份文件 (Excel)",
            data=output.getvalue(),
            file_name="项目核算系统_数据备份.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    st.markdown("---")
    st.markdown("### 2. 一键恢复数据")
    st.caption("上传之前生成的备份 Excel 文件，系统会自动识别 Sheet 并覆盖当前所有数据。")
    
    uploaded_backup = st.file_uploader("请上传备份文件", type=["xlsx"])
    if uploaded_backup is not None:
        if st.button("⚠️ 确认覆盖恢复"):
            try:
                xl = pd.ExcelFile(uploaded_backup)
                
                # 匹配并覆盖
                map_backup = {
                    "表3-1型材类": "t31",
                    "表3-2按平米类": "t32",
                    "表3-3按米类": "t33",
                    "表3-4其他类": "t34",
                    "表3-5LED类": "t35",
                    "表1单价分析": "t1"
                }
                
                restored = []
                for sheet_name in xl.sheet_names:
                    if sheet_name in map_backup:
                        target_key = map_backup[sheet_name]
                        df = pd.read_excel(uploaded_backup, sheet_name=sheet_name)
                        df.columns = [str(c).strip() for c in df.columns]
                        st.session_state[target_key] = df
                        restored.append(sheet_name)
                
                if restored:
                    st.success(f"✅ 数据恢复成功！已还原：{', '.join(restored)}")
                    st.info("请点击左侧导航查看数据是否已还原。")
                else:
                    st.error("❌ 上传的 Excel 中没有找到有效的表名（如：表3-1型材类），请确保是使用系统导出的备份文件。")
            except Exception as e:
                st.error(f"恢复失败：{e}")