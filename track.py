# -*- coding: utf-8 -*-
import math
import re
import streamlit as st
import pandas as pd

st.set_page_config(page_title="国际物流自动判断系统", layout="wide")

# ======================================================
# 侧边栏：选择大类
# ======================================================
st.sidebar.title("🌍 国际物流自动判断系统")

category = st.sidebar.radio(
    "请选择物流大类",
    [
        "US-FBM",
        "DE-FBM",
        "UK-FBM",
        "JP-FBM",
        "CA-FBA",
        "US-FBA",
        "DE-FBA",
        "UK-FBA",
        "JP-FBA",
    ]
)

st.title(f"📦 {category} 自动物流判断系统")

# 显示给用户看的“默认单位”
if category in ["US-FBM", "US-FBA", "CA-FBA"]:
    display_len_unit = "inch"
    display_wt_unit = "lb"
else:
    display_len_unit = "cm"
    display_wt_unit = "kg"

st.subheader(f"请输入包裹尺寸与重量（可带单位后缀，如 10、10cm、10in、2kg、2lb）")

# 使用 text_input，支持输入单位后缀
L_raw = st.text_input(f"长度（L），示例：10 / 10cm / 10in（默认 {display_len_unit}）", value="")
W_raw = st.text_input(f"宽度（W），示例：10 / 10cm / 10in（默认 {display_len_unit}）", value="")
H_raw = st.text_input(f"高度（H），示例：10 / 10cm / 10in（默认 {display_len_unit}）", value="")
WT_raw = st.text_input(f"实重（Weight），示例：2 / 2kg / 2lb（默认 {display_wt_unit}）", value="")

# 德国 GEL 国际大货包裹需要目的区域（仅 DE-FBM 用）
gel_dest_region = None
if category == "DE-FBM":
    gel_dest_region = st.selectbox(
        "GEL 国际大货包裹目的地区（仅影响体积重计算）",
        ["其他区域", "AT", "HR"]
    )

# ======================================================
# 工具函数：自动识别单位 & 换算
# ======================================================
def parse_length(x):
    """
    自动识别用户输入的长度单位
    支持：10, 10cm, 10 cm, 10in, 10 inch
    返回: 数值, 单位("inch"/"cm"/None)
    """
    s = str(x).lower().strip()
    nums = re.findall(r"[\d.]+", s)
    if not nums:
        raise ValueError(f"无法从输入中解析数字: {x}")
    num = float(nums[0])

    if "cm" in s:
        return num, "cm"
    if "in" in s or "inch" in s:
        return num, "inch"
    return num, None  # 未写单位，后面按国家默认


def parse_weight(x):
    """
    自动识别用户输入的重量单位
    支持：2, 2kg, 2 kg, 2lb, 2 lbs, 2 pound
    返回: 数值, 单位("kg"/"lb"/None)
    """
    s = str(x).lower().strip()
    nums = re.findall(r"[\d.]+", s)
    if not nums:
        raise ValueError(f"无法从输入中解析数字: {x}")
    num = float(nums[0])

    if "kg" in s:
        return num, "kg"
    if "lb" in s or "lbs" in s or "pound" in s:
        return num, "lb"
    return num, None


def convert_units_for_category(category, L_raw, W_raw, H_raw, WT_raw):
    """
    根据大类自动选择内部使用的单位体系，并做换算：
    - US-FBM / US-FBA / CA-FBA : inch + lb
    - 其他（DE/UK/JP FBM & FBA）: cm + kg
    """
    L, Lu = parse_length(L_raw)
    W, Wu = parse_length(W_raw)
    H, Hu = parse_length(H_raw)
    WT, WTu = parse_weight(WT_raw)

    # US 系列 & CA-FBA 使用 inch/lb
    if category in ["US-FBM", "US-FBA", "CA-FBA"]:
        # 长度 -> inch
        if Lu == "cm":
            L *= 0.393700787
        if Wu == "cm":
            W *= 0.393700787
        if Hu == "cm":
            H *= 0.393700787
        # 未写单位，按默认 inch 处理
        # 重量 -> lb
        if WTu == "kg":
            WT *= 2.20462262
        # 未写单位，按默认 lb 处理
        return L, W, H, WT, "inch", "lb"

    # 其余国家使用 cm/kg
    else:
        # 长度 -> cm
        if Lu == "inch":
            L *= 2.54
        if Wu == "inch":
            W *= 2.54
        if Hu == "inch":
            H *= 2.54
        # 重量 -> kg
        if WTu == "lb":
            WT *= 0.45359237
        return L, W, H, WT, "cm", "kg"


# 体积重和 cm³ 工具
def calc_dim_weight(L, W, H, divisor):
    return (L * W * H) / divisor

def inch_to_cm(x):
    return x * 2.54

def volume_cm3_from_inch(L, W, H):
    return inch_to_cm(L) * inch_to_cm(W) * inch_to_cm(H)


def make_result(channel, can_ship, item_type, dim_weight, charge_weight, reason=None):
    return {
        "渠道": channel,
        "可发": "是" if can_ship else "否",
        "件型": item_type if (can_ship and item_type) else ("-" if can_ship else "-"),
        "体积重": f"{dim_weight:.2f}" if dim_weight is not None else "-",
        "计费重": f"{charge_weight:.2f}" if charge_weight is not None else "-",
        "不可发原因": reason if not can_ship else "-",
    }

# ======================================================
# US-FBM：16 渠道（inch / lb）
# ======================================================
def rule_fedex_ground(L,W,H,Wt,G):
    dim = calc_dim_weight(L,W,H,250)
    charge = max(dim, Wt)
    if L<=48 and W<=30 and G<=105 and Wt<=50:
        return make_result("FEDEX-Ground", True, "标准件", dim, charge)
    if (48<L<=96 or 30<W<=96 or 105<G<=130 or 50<Wt<=150):
        return make_result("FEDEX-Ground", True, "一般超尺寸超重（AHS）", dim, charge)
    if (96<L<=108 or 130<G<=165) and Wt<=150:
        return make_result("FEDEX-Ground", True, "超尺寸（LPS）", dim, charge)
    if L>108 or G>165 or Wt>150:
        return make_result("FEDEX-Ground", False, "-", dim, charge, "超过最大限制")
    return make_result("FEDEX-Ground", False, "-", dim, charge, "不符合规则")

def rule_ups_ground(L,W,H,Wt,G):
    dim = calc_dim_weight(L,W,H,223)
    charge = max(dim, Wt)
    if L<=48 and W<=30 and G<=105 and Wt<=50:
        return make_result("UPS-Ground", True, "标准件", dim, charge)
    if (48<L<=96 or 30<W<=96 or 105<G<=130 or 50<Wt<=150):
        return make_result("UPS-Ground", True, "一般超尺寸超重（AHS）", dim, charge)
    if (96<L<=108 or 130<G<=165) and Wt<=150:
        return make_result("UPS-Ground", True, "超尺寸（LPS）", dim, charge)
    if L>108 or G>165 or Wt>150:
        return make_result("UPS-Ground", False, "-", dim, charge, "超过最大限制")
    return make_result("UPS-Ground", False, "-", dim, charge, "不符合规则")

def rule_amazon_common(L,W,H,Wt,G, channel_name):
    postal_dim = calc_dim_weight(L,W,H,250)
    gc_dim     = calc_dim_weight(L,W,H,194)
    postal_charge = max(postal_dim, Wt)
    gc_charge     = max(gc_dim, Wt)
    if (L<=37 and W<=30 and H<=24 and G<=105 
        and postal_charge<=50 and gc_charge<=50):
        return make_result(channel_name, True, "标准件", postal_dim, postal_charge)
    if (37<L<=47 or 30<W<=33 or H>24):
        return make_result(channel_name, True, "一般超尺寸超重（Non-Standard Fee）",
                           postal_dim, postal_charge)
    if (47<L<=59 or W>42 or (105<G<=126)
        or postal_charge>50 or gc_charge>50):
        return make_result(channel_name, True, "超尺寸（LPS）", postal_dim, postal_charge)
    if (L>59 or W>33 or H>33 or G>126 or postal_charge>50):
        return make_result(channel_name, False, "-", postal_dim, postal_charge, "西邮不可发")
    if (L>48 or W>30 or G>105 or gc_charge>50):
        return make_result(channel_name, False, "-", postal_dim, postal_charge, "谷仓不可发")
    return make_result(channel_name, False, "-", postal_dim, postal_charge, "不符合规则")

def rule_amazon_ground(L,W,H,Wt,G):
    return rule_amazon_common(L,W,H,Wt,G,"Amazon-Ground")

def rule_amazon_shipping(L,W,H,Wt,G):
    return rule_amazon_common(L,W,H,Wt,G,"Amazon-Shipping")

def rule_yun_ground(L,W,H,Wt,G):
    dim = 0.0
    charge = Wt
    if L<=48 and W<=30 and G<=105 and Wt<=50:
        return make_result("YUN-Ground", True, "标准件", dim, charge)
    if (48<L<=96 or 30<W<=96 or 105<G<=130 or 50<Wt<=150):
        return make_result("YUN-Ground", True, "一般超尺寸超重（AHS）", dim, charge)
    if (96<L<=108 or 130<G<=165) and Wt<=150:
        return make_result("YUN-Ground", True, "超尺寸（LPS）", dim, charge)
    if L>108 or G>165 or Wt>150:
        return make_result("YUN-Ground", False, "-", dim, charge, "超过最大限制")
    return make_result("YUN-Ground", False, "-", dim, charge, "不符合规则")

def rule_wp_ground(L,W,H,Wt,G):
    dim = calc_dim_weight(L,W,H,250)
    charge = max(dim,Wt)
    if L<=96 and G<=130 and charge<=150:
        return make_result("WP-Ground", True, "标准件", dim, charge)
    if (96<L<=108 or G>130):
        return make_result("WP-Ground", True, "超尺寸", dim, charge)
    if L>108 or charge>150:
        return make_result("WP-Ground", False, "-", dim, charge, "超过最大限制")
    return make_result("WP-Ground", False, "-", dim, charge)

def rule_usps_ground(L,W,H,Wt,G):
    dim = calc_dim_weight(L,W,H,166)
    charge = max(dim,Wt)
    vol = volume_cm3_from_inch(L,W,H)
    if L<=22 and G<=108 and Wt<=50 and charge<=70:
        return make_result("USPS-Ground Advantage", True, "标准件", dim, charge)
    if L>22 or vol>55000:
        return make_result("USPS-Ground Advantage", True, "一般超尺寸超重", dim, charge)
    if G>108 or charge>70:
        return make_result("USPS-Ground Advantage", False, "-", dim, charge, "超过限制")
    return make_result("USPS-Ground Advantage", False, "-", dim, charge)

def rule_ups_mi_small(L,W,H,Wt,G):
    vol = volume_cm3_from_inch(L,W,H)
    if L<=22 and Wt<=10:
        return make_result("UPS MI轻小", True, "标准件", vol, Wt)
    if (22<L<=27) or vol>55000:
        return make_result("UPS MI轻小", True, "一般超尺寸超重", vol, Wt)
    if L>27 or W>16 or H>16 or G>50 or Wt>10:
        return make_result("UPS MI轻小", False, "-", vol, Wt, "超过限制")
    return make_result("UPS MI轻小", False, "-", vol, Wt)

def rule_dhl_small(L,W,H,Wt,G):
    dim = calc_dim_weight(L,W,H,166)
    charge = max(dim,Wt)
    vol = volume_cm3_from_inch(L,W,H)
    if L<=22 and G<=50 and Wt<=1:
        return make_result("DHL-Local-Small", True, "标准件", dim, charge)
    if (22<L<=27) or vol>55000:
        return make_result("DHL-Local-Small", True, "一般超尺寸超重", dim, charge)
    if L>27 or G>50 or Wt>1:
        return make_result("DHL-Local-Small", False, "-", dim, charge, "超过限制")
    return make_result("DHL-Local-Small", False, "-", dim, charge)

def rule_gc_parcel(L,W,H,Wt,G):
    dim = calc_dim_weight(L,W,H,223)
    charge = max(dim,Wt)
    vol = volume_cm3_from_inch(L,W,H)
    if L<22 and W<16 and H<=16 and Wt<=25:
        return make_result("GC-Parcel", True, "标准件", dim, charge)
    if L>=22 or W>=16 or H>16 or Wt>=25 or vol>=56000:
        return make_result("GC-Parcel", False, "-", dim, charge, "超过限制")
    return make_result("GC-Parcel", False, "-", dim, charge)

def rule_fedex_smartpost(L,W,H,Wt,G):
    dim = calc_dim_weight(L,W,H,250)
    charge = max(dim,Wt)
    if (6<L<=27 and 4<W<=17 and 1<H<=17 and G<=108 and charge<=70):
        return make_result("FEDEX-Smartpost", True, "标准件", dim, charge)
    if (27<L<=60) or (W>17) or (35<Wt<=71):
        return make_result("FEDEX-Smartpost", True, "一般超尺寸超重", dim, charge)
    if L>60 or G>130 or charge>70:
        return make_result("FEDEX-Smartpost", False, "-", dim, charge, "超过限制")
    return make_result("FEDEX-Smartpost", False, "-", dim, charge)

def rule_fedex_economy(L,W,H,Wt,G):
    dim = calc_dim_weight(L,W,H,194)
    dim_base = dim
    if Wt<20 and 84<=G<107 and dim<20:
        charge = 20
    elif Wt<70 and 107<=G<130 and dim<70:
        charge = 70
    else:
        charge = max(dim,Wt)
    if L<=27 and W<=17 and H<=17 and G<=130 and Wt<=9:
        return make_result("FEDEX-Economy", True, "标准件", dim_base, charge)
    if (27<L<=48) or (17<W<=30) or (17<H<=30):
        return make_result("FEDEX-Economy", True, "一般超尺寸超重", dim_base, charge)
    if L>60 or G>130 or charge>70:
        return make_result("FEDEX-Economy", False, "-", dim_base, charge, "超过限制")
    return make_result("FEDEX-Economy", False, "-", dim_base, charge)

def rule_ups_ground_saver(L,W,H,Wt,G):
    vol = volume_cm3_from_inch(L,W,H)
    if vol>28000:
        dim = calc_dim_weight(L,W,H,125)
    else:
        dim = calc_dim_weight(L,W,H,167)
    charge = max(dim,Wt)
    if L<=22 and G<=105 and 1<charge<=9 and vol<=56000:
        return make_result("UPS-Ground Saver", True, "标准件", dim, charge)
    if (22<L<=48) or (vol>56000):
        return make_result("UPS-Ground Saver", True, "一般超尺寸", dim, charge)
    if (48<L<=108) or (W>30) or (vol>141500):
        return make_result("UPS-Ground Saver", True, "超尺寸", dim, charge)
    if L>108 or G>165 or charge>9:
        return make_result("UPS-Ground Saver", False, "-", dim, charge, "超过限制")
    return make_result("UPS-Ground Saver", False, "-", dim, charge)

def rule_ups_mi(L,W,H,Wt,G):
    vol = volume_cm3_from_inch(L,W,H)
    if L<=22 and 1<Wt<=10:
        return make_result("UPS MI", True, "标准件", vol, Wt)
    if (22<L<=27) or (vol>55000):
        return make_result("UPS MI", True, "一般超尺寸超重", vol, Wt)
    if L>27 or W>16 or H>16 or G>50 or Wt>10:
        return make_result("UPS MI", False, "-", vol, Wt, "超过限制")
    return make_result("UPS MI", False, "-", vol, Wt)

def rule_usps_priority(L,W,H,Wt,G):
    dim = calc_dim_weight(L,W,H,166)
    charge = max(dim,Wt)
    vol = volume_cm3_from_inch(L,W,H)
    if L<=22 and charge<=70:
        return make_result("USPS Priority", True, "标准件", dim, charge)
    if (L>22 or vol>55000):
        return make_result("USPS Priority", True, "一般超尺寸超重", dim, charge)
    if G>50 or charge>70:
        return make_result("USPS Priority", False, "-", dim, charge, "超过限制")
    return make_result("USPS Priority", False, "-", dim, charge)

def rule_dhl_big(L,W,H,Wt,G):
    dim = calc_dim_weight(L,W,H,166)
    charge = max(dim,Wt)
    vol = volume_cm3_from_inch(L,W,H)
    if L<=22 and charge<=25 and G<=50 and vol<=56000:
        return make_result("DHL-Local-Big", True, "标准件", dim, charge)
    if (22<L<=27) or (50<G<=84) or (vol>56000):
        return make_result("DHL-Local-Big", True, "一般超尺寸超重", dim, charge)
    if L>27 or G>84 or charge>25:
        return make_result("DHL-Local-Big", False, "-", dim, charge, "超过限制")
    return make_result("DHL-Local-Big", False, "-", dim, charge)

US_FBM_CHANNELS = [
    rule_fedex_ground,
    rule_ups_ground,
    rule_amazon_ground,
    rule_amazon_shipping,
    rule_yun_ground,
    rule_wp_ground,
    rule_usps_ground,
    rule_ups_mi_small,
    rule_dhl_small,
    rule_gc_parcel,
    rule_fedex_smartpost,
    rule_fedex_economy,
    rule_ups_ground_saver,
    rule_ups_mi,
    rule_usps_priority,
    rule_dhl_big,
]

# ======================================================
# US-FBM：根据 A/B/C 三段逻辑选择候选渠道
# ======================================================
def get_us_fbm_candidate_channels(L, W, H, Wt, G):
    """
    A）实重 8–150 且（标准件 或 大件） → 6 个 Ground 渠道
    B）实重 0–5 且 小包/信封 → 4 个小包渠道
    C）实重 1–10 且 非超包裹 → 7 个轻量渠道
    """

    channels_A = [
        rule_fedex_ground,
        rule_ups_ground,
        rule_amazon_ground,
        rule_amazon_shipping,
        rule_yun_ground,
        rule_wp_ground,
    ]

    channels_B = [
        rule_usps_ground,
        rule_ups_mi_small,
        rule_dhl_small,
        rule_gc_parcel,
    ]

    channels_C = [
        rule_fedex_smartpost,
        rule_fedex_economy,
        rule_ups_ground_saver,
        rule_ups_mi,
        rule_usps_priority,
        rule_dhl_big,
    ]

    # -------------------------
    # A 组：8–150 lb 大件
    # -------------------------
    if 8 <= Wt <= 150:
        is_standard = (L <= 48 and W <= 30 and G <= 105 and Wt <= 50)
        is_oversize = (L > 48 or G > 105)

        if is_standard or is_oversize:
            return channels_A

    # -------------------------
    # B 组：0–5 lb 小包/信封
    # -------------------------
    if 0 < Wt <= 5:
        is_small = ((L <= 22 and W <= 16 and H <= 16) or
                    (L <= 27 and W <= 17))
        if is_small:
            return channels_B

    # -------------------------
    # C 组：1–10 lb 轻重量
    # -------------------------
    if 1 <= Wt <= 10:
        not_oversize = (L <= 48 and W <= 30 and G <= 105)
        if not_oversize:
            return channels_C

    return []

# ======================================================
# DE-FBM：8 渠道（cm / kg，向上取整）
# ======================================================
def _round_de_dims(L_cm, W_cm, H_cm):
    L = math.ceil(L_cm)
    W = math.ceil(W_cm)
    H = math.ceil(H_cm)
    G = math.ceil(L + 2*(W+H))
    V = L * W * H
    return L, W, H, G, V

def rule_dhl_de_dom(L_cm,W_cm,H_cm,W_kg,_Gignored):
    L,W,H,G,V = _round_de_dims(L_cm,W_cm,H_cm)
    charge = W_kg
    if (15<L<=120 and 11<W<=60 and 1<H<=60 and G<=360 and 0<W_kg<=31.5):
        return make_result("DHL德国包裹", True, "标准件", V, charge)
    if (120<L<=200 or W>60 or H>60):
        return make_result("DHL德国包裹", True, "一般超尺寸超重", V, charge)
    if (L>200 or G>360 or W_kg>31.5):
        return make_result("DHL德国包裹", False, "-", V, charge, "超过限制")
    return make_result("DHL德国包裹", False, "-", V, charge)

def rule_dhl_de_intl(L_cm,W_cm,H_cm,W_kg,_Gignored):
    L,W,H,G,V = _round_de_dims(L_cm,W_cm,H_cm)
    charge = W_kg
    if (15<L<=120 and 11<W<=60 and 1<H<=60 and G<=300 and 0<W_kg<=31.5):
        return make_result("DHL国际包裹", True, "标准件", V, charge)
    if (120<L<=150 or W>60 or H>60):
        return make_result("DHL国际包裹", True, "一般超尺寸超重", V, charge)
    if (L>150 or G>300 or W_kg>31.5):
        return make_result("DHL国际包裹", False, "-", V, charge, "超过限制")
    return make_result("DHL国际包裹", False, "-", V, charge)

def _rule_dpd_common(L_cm,W_cm,H_cm,W_kg, channel_name):
    L,W,H,G,V = _round_de_dims(L_cm,W_cm,H_cm)
    charge = W_kg
    if (15<L<=120 and 11<W<=60 and 1<H<=60 and G<=300 and 0<W_kg<=31.5):
        return make_result(channel_name, True, "标准件", V, charge)
    if (120<L<=175 or W>60 or V>150000):
        return make_result(channel_name, True, "一般超尺寸超重", V, charge)
    if (L>175 or G>300 or W_kg>31.5):
        return make_result(channel_name, False, "-", V, charge, "超过限制")
    return make_result(channel_name, False, "-", V, charge)

def rule_dpd_de_dom(L_cm,W_cm,H_cm,W_kg,G):
    return _rule_dpd_common(L_cm,W_cm,H_cm,W_kg,"DPD德国包裹")

def rule_dpd_de_intl(L_cm,W_cm,H_cm,W_kg,G):
    return _rule_dpd_common(L_cm,W_cm,H_cm,W_kg,"DPD国际包裹")

def _rule_gls_common(L_cm,W_cm,H_cm,W_kg, channel_name):
    L,W,H,G,V = _round_de_dims(L_cm,W_cm,H_cm)
    charge = W_kg
    if (3<L<=120 and 3<W<=80 and 3<H<=60 and G<=300 and 0<W_kg<=40):
        return make_result(channel_name, True, "标准件", V, charge)
    if (120<L<=200 or H>3 or V>150000):
        return make_result(channel_name, True, "一般超尺寸超重", V, charge)
    if (L>200 or G>300 or W_kg>40 or W>80 or H>60):
        return make_result(channel_name, False, "-", V, charge, "超过限制")
    return make_result(channel_name, False, "-", V, charge)

def rule_gls_de_dom(L_cm,W_cm,H_cm,W_kg,G):
    return _rule_gls_common(L_cm,W_cm,H_cm,W_kg,"GLS德国包裹")

def rule_gls_de_intl(L_cm,W_cm,H_cm,W_kg,G):
    return _rule_gls_common(L_cm,W_cm,H_cm,W_kg,"GLS国际包裹")

def rule_gel_de_heavy(L_cm,W_cm,H_cm,W_kg,G):
    L,W,H,G,V = _round_de_dims(L_cm,W_cm,H_cm)
    Lm, Wm, Hm = L/100.0, W/100.0, H/100.0
    vol_weight = Lm*Wm*Hm*150.0
    charge = max(W_kg, vol_weight)
    if (L<=320 and W<=120 and H<=220 and vol_weight<=1000 and 0<W_kg<=60):
        return make_result("GEL德国大货包裹", True, "标准件", vol_weight, charge)
    dims_m = sorted([Lm,Wm,Hm], reverse=True)
    area_2d = dims_m[0]*dims_m[1]
    if (L>320 or H>220 or W>120 or W_kg>60 or vol_weight>1000 or area_2d>2.0):
        return make_result("GEL德国大货包裹", False, "-", vol_weight, charge, "超过限制")
    return make_result("GEL德国大货包裹", False, "-", vol_weight, charge)

def rule_gel_de_intl(L_cm,W_cm,H_cm,W_kg,G):
    L,W,H,G,V = _round_de_dims(L_cm,W_cm,H_cm)
    Lm, Wm, Hm = L/100.0, W/100.0, H/100.0
    if gel_dest_region == "AT":
        k = 200.0
    elif gel_dest_region == "HR":
        k = 300.0
    else:
        k = 167.0
    vol_weight = Lm*Wm*Hm*k
    charge = max(W_kg, vol_weight)
    if (L<=320 and W<=120 and H<=220 and vol_weight<=1000 and 0<W_kg<=60):
        return make_result("GEL国际大货包裹", True, "标准件", vol_weight, charge)
    dims_m = sorted([Lm,Wm,Hm], reverse=True)
    area_2d = dims_m[0]*dims_m[1]
    if (L>320 or H>220 or W>120 or W_kg>60 or vol_weight>1000 or area_2d>2.0):
        return make_result("GEL国际大货包裹", False, "-", vol_weight, charge, "超过限制")
    return make_result("GEL国际大货包裹", False, "-", vol_weight, charge)

DE_FBM_GROUP_DHL_DPD = [
    rule_dhl_de_dom,
    rule_dhl_de_intl,
    rule_dpd_de_dom,
    rule_dpd_de_intl,
]
DE_FBM_GROUP_GLS = [
    rule_gls_de_dom,
    rule_gls_de_intl,
]
DE_FBM_GROUP_GEL = [
    rule_gel_de_heavy,
    rule_gel_de_intl,
]

# ======================================================
# UK-FBM：7 渠道（cm / kg）
# ======================================================
def _round_uk_dims(L_cm, W_cm, H_cm):
    L = math.ceil(L_cm)
    W = math.ceil(W_cm)
    H = math.ceil(H_cm)
    G = math.ceil(L + 2*(W+H))
    V = L * W * H
    return L, W, H, G, V

def rule_uk_royal_mail(L_cm,W_cm,H_cm,W_kg,G0):
    L,W,H,G,V = _round_uk_dims(L_cm,W_cm,H_cm)
    charge = W_kg
    if (0<L<=61 and 0<W<=46 and 0<H<=46 and 0<W_kg<=20):
        return make_result("Royal Mail包裹", True, "标准件", V, charge)
    if (L>61 or W>46 or H>46 or V>31500 or W_kg>20):
        return make_result("Royal Mail包裹", False, "-", V, charge, "超过限制")
    return make_result("Royal Mail包裹", False, "-", V, charge)

def rule_uk_dpd(L_cm,W_cm,H_cm,W_kg,G0):
    L,W,H,G,V = _round_uk_dims(L_cm,W_cm,H_cm)
    charge = W_kg
    if (0<L<=100 and 0<W<=60 and 0<H<=70 and 0<W_kg<=30 and G<=230):
        return make_result("DPD英国本土", True, "标准件", V, charge)
    if (L>100 or W>60 or H>70 or G>230 or W_kg>30):
        return make_result("DPD英国本土", False, "-", V, charge, "超过限制")
    return make_result("DPD英国本土", False, "-", V, charge)

def rule_uk_evri_standard(L_cm,W_cm,H_cm,W_kg,G0):
    L,W,H,G,V = _round_uk_dims(L_cm,W_cm,H_cm)
    charge = W_kg
    if (0<L<=120 and 0<W_kg<=15 and G<=225):
        return make_result("EVRI本土标准包裹", True, "标准件", V, charge)
    if (L>120 or G>225 or W_kg>15):
        return make_result("EVRI本土标准包裹", False, "-", V, charge, "超过限制")
    return make_result("EVRI本土标准包裹", False, "-", V, charge)

def rule_uk_evri_bulk(L_cm,W_cm,H_cm,W_kg,G0):
    L,W,H,G,V = _round_uk_dims(L_cm,W_cm,H_cm)
    charge = W_kg
    if (0<L<=180 and 0<W_kg<=30 and G<=420):
        return make_result("EVRI本土大货", True, "标准件", V, charge)
    if (L>180 or G>420 or W_kg>30):
        return make_result("EVRI本土大货", False, "-", V, charge, "超过限制")
    return make_result("EVRI本土大货", False, "-", V, charge)

def rule_uk_gc_parcel(L_cm,W_cm,H_cm,W_kg,G0):
    L,W,H,G,V = _round_uk_dims(L_cm,W_cm,H_cm)
    charge = W_kg
    if (0<L<=60 and 0<W_kg<=15 and 0<W<=46 and 0<H<=46):
        return make_result("UK GC PARCEL", True, "标准件", V, charge)
    if (L>60 or W>46 or H>46 or W_kg>15 or V>31000):
        return make_result("UK GC PARCEL", False, "-", V, charge, "超过限制")
    return make_result("UK GC PARCEL", False, "-", V, charge)

def rule_uk_yodael(L_cm,W_cm,H_cm,W_kg,G0):
    L,W,H,G,V = _round_uk_dims(L_cm,W_cm,H_cm)
    charge = W_kg
    sum_wh = W + H
    if (L<=90 and W_kg<=3 and V<=31000):
        return make_result("YODAEL UK本地包裹", True, "48H小包", V, charge)
    if (L<=90 and W_kg<=17 and V<=113000 and sum_wh<=150):
        return make_result("YODAEL UK本地包裹", True, "48H大包", V, charge)
    if (L<=120 and W_kg<=30 and V<=230000 and sum_wh<=170):
        return make_result("YODAEL UK本地包裹", True, "48H大货", V, charge)
    if (L<=170 and W_kg<=30 and V<=280000 and sum_wh<=250):
        return make_result("YODAEL UK本地包裹", True, "48H超大货", V, charge)
    if (L<=90 and W_kg<=17 and V<=113000 and sum_wh<=150):
        return make_result("YODAEL UK本地包裹", True, "24H大包", V, charge)
    if (L<=120 and W_kg<=30 and V<=230000 and sum_wh<=170):
        return make_result("YODAEL UK本地包裹", True, "24H大货", V, charge)
    return make_result("YODAEL UK本地包裹", False, "-", V, charge, "超过限制")

def rule_uk_xdp(L_cm,W_cm,H_cm,W_kg,G0):
    L,W,H,G,V = _round_uk_dims(L_cm,W_cm,H_cm)
    vol_weight = V / 5000.0
    charge = max(W_kg, vol_weight)
    if (L<=320 and W_kg<=50):
        return make_result("XDP本地包裹", True, "Economy Parcels", vol_weight, charge)
    if (L<=400 and W_kg<=150):
        return make_result("XDP本地包裹", True, "Two man", vol_weight, charge)
    return make_result("XDP本地包裹", False, "-", vol_weight, charge, "超过限制")

UK_FBM_CHANNELS = [
    rule_uk_royal_mail,
    rule_uk_dpd,
    rule_uk_evri_standard,
    rule_uk_evri_bulk,
    rule_uk_gc_parcel,
    rule_uk_yodael,
    rule_uk_xdp,
]

# ======================================================
# JP-FBM：2 渠道（cm / kg）
# ======================================================
def _round_jp_dims(L_cm, W_cm, H_cm):
    L = math.ceil(L_cm)
    W = math.ceil(W_cm)
    H = math.ceil(H_cm)
    G = math.ceil(L + 2*(W+H))
    V = L * W * H
    return L, W, H, G, V

def rule_jp_small_express(L_cm, W_cm, H_cm, W_kg, G0):
    L, W, H, G, V = _round_jp_dims(L_cm, W_cm, H_cm)
    charge = W_kg
    if (21 <= L and 15 <= W and 0 < H <= 3 and 0 < W_kg <= 1 and 0 < G <= 60):
        return make_result("JP-小型快递", True, "标准件", V, charge)
    return make_result("JP-小型快递", False, "-", V, charge, "不符合标准件")

def rule_jp_express_cargo(L_cm, W_cm, H_cm, W_kg, G0):
    L, W, H, G, V = _round_jp_dims(L_cm, W_cm, H_cm)
    charge = W_kg
    if G <= 60 and W_kg <= 2:
        return make_result("JP-快递货物", True, "价格阶梯1", V, charge)
    if G <= 80 and W_kg <= 5:
        return make_result("JP-快递货物", True, "价格阶梯2", V, charge)
    if G <= 100 and W_kg <= 10:
        return make_result("JP-快递货物", True, "价格阶梯3", V, charge)
    if G <= 140 and W_kg <= 20:
        return make_result("JP-快递货物", True, "价格阶梯4", V, charge)
    if G <= 160 and W_kg <= 30:
        return make_result("JP-快递货物", True, "价格阶梯5", V, charge)
    if G <= 170 and W_kg <= 50:
        return make_result("JP-快递货物", True, "价格阶梯6", V, charge)
    if G <= 180 and W_kg <= 50:
        return make_result("JP-快递货物", True, "价格阶梯7", V, charge)
    if G <= 200 and W_kg <= 50:
        return make_result("JP-快递货物", True, "价格阶梯8", V, charge)
    if G <= 220 and W_kg <= 50:
        return make_result("JP-快递货物", True, "价格阶梯9", V, charge)
    if G <= 240 and W_kg <= 50:
        return make_result("JP-快递货物", True, "价格阶梯10", V, charge)
    if G <= 260 and W_kg <= 50:
        return make_result("JP-快递货物", True, "价格阶梯11", V, charge)
    return make_result("JP-快递货物", False, "-", V, charge, "超过规格")

JP_FBM_CHANNELS = [
    rule_jp_small_express,
    rule_jp_express_cargo,
]

# ======================================================
# CA-FBA：加拿大 FBA（inch / lb，永远可发，只计算附加费）
# ======================================================
def rule_ca_fba(L_in, W_in, H_in, W_lb, G_in):
    girth = L_in + 2 * (W_in + H_in)
    volume = L_in * W_in * H_in
    triggered = []
    total_fee = 0.0

    # 这里根据你提供的 CA-FBA 表格实现
    if L_in > 60:
        triggered.append("A")
        total_fee += 17
    if L_in > 106:
        triggered.append("B")
        total_fee += 150
    if W_in > 30:
        triggered.append("E")
        total_fee += 17
    if girth > 130:
        triggered.append("H")
        total_fee += 60
    if girth > 165:
        triggered.append("I")
        total_fee += 150
    if W_lb > 70:
        triggered.append("K")
        total_fee += 17
    if W_lb > 150:
        triggered.append("L")
        total_fee += 150

    if not triggered:
        item_type = "标准件（无附加费）"
        desc = "-"
    else:
        item_type = "触发附加费"
        desc = f"触发档位: {','.join(triggered)}；附加费合计 USD {total_fee:.2f}"

    return {
        "渠道": "CA-FBA",
        "可发": "是",
        "件型": item_type,
        "体积重": f"{volume:.2f}",
        "计费重": f"{W_lb:.2f}",
        "不可发原因": desc,
    }

CA_FBA_CHANNELS = [rule_ca_fba]

# ======================================================
# JP-FBA：日本 FBA（cm / kg，重量档位）
# ======================================================
def rule_jp_fba(L_cm, W_cm, H_cm, W_kg, G0):
    weight_val = round(W_kg, 2)

    if weight_val > 50:
        return {
            "渠道": "JP-FBA",
            "可发": "否",
            "件型": "-",
            "体积重": "-",
            "计费重": f"{weight_val:.2f}",
            "不可发原因": "重量 > 50kg，无法发货",
        }

    surcharge = 0.0
    level = None

    if weight_val > 25:
        surcharge = 432.0
        level = "J"
    if weight_val > 30:
        surcharge = 1233.0
        level = "K"

    if level is None:
        item_type = "标准件（无附加费）"
        reason = "-"
    else:
        if level == "J":
            reason = f"重量超过 25kg，附加费 {surcharge:.2f} JBP"
        else:
            reason = f"重量超过 30kg，附加费 {surcharge:.2f} JBP"
        item_type = f"触发附加费（档位{level}）"

    return {
        "渠道": "JP-FBA",
        "可发": "是",
        "件型": item_type,
        "体积重": "-",
        "计费重": f"{weight_val:.2f}",
        "不可发原因": reason,
    }

JP_FBA_CHANNELS = [rule_jp_fba]

# ======================================================
# US-FBA：美国 FBA（inch / lb）
# ======================================================
def rule_us_fba(L_in, W_in, H_in, W_lb, G_in):
    """
    美国 FBA 四档：
    - 小号：L<=15, W<=12, H<=0.75, 计费重<=1lb，不看周长
    - 大号标准：L<=18, W<=14, H<=8, G<=130, 计费重<=20lb
    - 大件：L<=59, W<=33, H<=33, G<=130, 计费重<=50lb
    - 超大件：其余全部
    """
    dim = calc_dim_weight(L_in, W_in, H_in, 139.0)
    charge = max(dim, W_lb)

    if L_in <= 15 and W_in <= 12 and H_in <= 0.75 and charge <= 1:
        return {
            "渠道": "US-FBA",
            "可发": "是",
            "件型": "FBA-小号",
            "体积重": f"{dim:.2f}",
            "计费重": f"{charge:.2f}",
            "不可发原因": "-",
        }

    if (L_in <= 18 and W_in <= 14 and H_in <= 8
            and G_in <= 130 and charge <= 20):
        return {
            "渠道": "US-FBA",
            "可发": "是",
            "件型": "FBA-大号标准",
            "体积重": f"{dim:.2f}",
            "计费重": f"{charge:.2f}",
            "不可发原因": "-",
        }

    if (L_in <= 59 and W_in <= 33 and H_in <= 33
            and G_in <= 130 and charge <= 50):
        return {
            "渠道": "US-FBA",
            "可发": "是",
            "件型": "FBA-大件",
            "体积重": f"{dim:.2f}",
            "计费重": f"{charge:.2f}",
            "不可发原因": "-",
        }

    return {
        "渠道": "US-FBA",
        "可发": "是",
        "件型": "FBA-超大件",
        "体积重": f"{dim:.2f}",
        "计费重": f"{charge:.2f}",
        "不可发原因": "-",
    }

US_FBA_CHANNELS = [rule_us_fba]

# ======================================================
# DE-FBA / UK-FBA：英德 FBA（cm / kg）
# ======================================================
def rule_eu_fba_common(L_cm, W_cm, H_cm, W_kg, G0, channel_name):
    G = L_cm + 2 * (W_cm + H_cm)
    dim = (L_cm * W_cm * H_cm) / 5000.0
    charge = max(dim, W_kg)

    if (L_cm <= 61 and W_cm <= 46 and H_cm <= 46
            and W_kg <= 1.76 and charge <= 25.82
            and G <= 360):
        tier = "FBA-小号大件"
    elif (L_cm <= 120 and W_cm <= 60 and H_cm <= 60
          and W_kg <= 23 and charge <= 86.4
          and G <= 360):
        tier = "FBA-大号标准"
    elif (L_cm <= 175 and W_cm <= 60 and H_cm <= 60
          and W_kg <= 31.5 and charge <= 126
          and G <= 360):
        tier = "FBA-大件"
    else:
        tier = "FBA-超大件"

    return {
        "渠道": channel_name,
        "可发": "是",
        "件型": tier,
        "体积重": f"{dim:.2f}",
        "计费重": f"{charge:.2f}",
        "不可发原因": "-",
    }

def rule_de_fba(L_cm, W_cm, H_cm, W_kg, G0):
    return rule_eu_fba_common(L_cm, W_cm, H_cm, W_kg, G0, "DE-FBA")

def rule_uk_fba(L_cm, W_cm, H_cm, W_kg, G0):
    return rule_eu_fba_common(L_cm, W_cm, H_cm, W_kg, G0, "UK-FBA")

DE_FBA_CHANNELS = [rule_de_fba]
UK_FBA_CHANNELS = [rule_uk_fba]


# ======================================================
# 全渠道临界值库（只要等于这些临界数字就要提示）
# ======================================================

THRESHOLD_MAP = {
    # ============================
    # US-FBM（inch / lb）
    # ============================
    "US-FBM": {
        "L": [22, 27, 37, 47, 48, 59, 60, 96, 108],
        "W": [16, 17, 30, 33, 42, 96],
        "H": [16, 17, 24, 33],
        "G": [50, 84, 105, 108, 126, 130, 141500, 165],
        "WT": [1, 5, 9, 10, 20, 25, 35, 50, 70, 150],
        "DIM": [],
    },

    # ============================
    # US-FBA（inch / lb）
    # ============================
    "US-FBA": {
        "L": [15, 18, 59],
        "W": [12, 14, 33],
        "H": [0.75, 8, 33],
        "G": [130],
        "WT": [1, 20, 50],
        "DIM": [1, 20, 50],
    },

    # ============================
    # CA-FBA（inch / lb）
    # ============================
    "CA-FBA": {
        "L": [60, 106],
        "W": [30],
        "H": [],
        "G": [130, 165],
        "WT": [70, 150],
        "DIM": [],
    },

    # ============================
    # DE-FBM（cm / kg）
    # ============================
    "DE-FBM": {
        "L": [120, 150, 175, 200, 320],
        "W": [60, 80, 120],
        "H": [60, 220],
        "G": [300, 360],
        "WT": [31.5, 40, 60],
        "DIM": [150000, 1000],   # V or vol_weight
    },

    # ============================
    # UK-FBM（cm / kg）
    # ============================
    "UK-FBM": {
        "L": [60, 61, 90, 100, 120, 170, 180, 320, 400],
        "W": [46, 60, 70],
        "H": [46, 70],
        "G": [225, 230, 250, 420],
        "WT": [3, 15, 20, 30, 50, 150],
        "DIM": [31000, 113000, 230000, 280000],
    },

    # ============================
    # JP-FBM（cm / kg）
    # ============================
    "JP-FBM": {
        "L": [21],
        "W": [15],
        "H": [3],
        "G": [60, 80, 100, 140, 160, 170, 180, 200, 220, 240, 260],
        "WT": [1, 2, 5, 10, 20, 30, 50],
        "DIM": [],
    },

    # ============================
    # DE-FBA / UK-FBA（cm / kg）
    # ============================
    "DE-FBA": {
        "L": [61, 120, 175],
        "W": [46, 60],
        "H": [46, 60],
        "G": [360],
        "WT": [1.76, 23, 31.5],
        "DIM": [25.82, 86.4, 126],
    },
    "UK-FBA": {
        "L": [61, 120, 175],
        "W": [46, 60],
        "H": [46, 60],
        "G": [360],
        "WT": [1.76, 23, 31.5],
        "DIM": [25.82, 86.4, 126],
    },

    # ============================
    # JP-FBA（cm / kg）
    # ============================
    "JP-FBA": {
        "L": [],
        "W": [],
        "H": [],
        "G": [],
        "WT": [25, 30, 50],
        "DIM": [],
    },
}


# ======================================================
# 通用临界提醒函数（适配所有国家和渠道）
# ======================================================
def check_threshold_all(category, L, W, H, WT, G):
    msgs = []

    if category not in THRESHOLD_MAP:
        return msgs

    rules = THRESHOLD_MAP[category]

    # 体积重公式（用现有计算规则）
    DIM = (L * W * H)

    # US-FBA / CA-FBA / 其他有专属 divisor 的自己判断
    # 但临界值判断不需要绝对匹配原本的体积重，只要“等于临界值”提示即可
    charge_dim = DIM

    def add_msg(name, value, limits):
        for lim in limits:
            if abs(value - lim) < 1e-6:
                msgs.append(f"⚠ {name} 正好等于临界值 {lim}")

    add_msg("长度", L, rules["L"])
    add_msg("宽度", W, rules["W"])
    add_msg("高度", H, rules["H"])
    add_msg("周长 Girth", G, rules["G"])
    add_msg("重量", WT, rules["WT"])
    add_msg("体积相关指标", charge_dim, rules["DIM"])

    return msgs





# ======================================================
# 根据大类 + 重量选择渠道列表
# ======================================================
def get_channels(category, weight_value, L=None, W=None, H=None, G=None):
    if category == "US-FBM":
        return get_us_fbm_candidate_channels(L, W, H, weight_value, G), None
    if category == "DE-FBM":
        w = weight_value   # kg
        if w <= 0:
            return [], "请先输入大于 0 的重量（kg）"
        if w <= 31.5:
            return DE_FBM_GROUP_DHL_DPD, None
        elif w <= 40:
            return DE_FBM_GROUP_GLS, None
        elif w <= 60:
            return DE_FBM_GROUP_GEL, None
        else:
            return [], "实重 > 60kg，建议使用 DHL Freight（卡板服务）。"

    if category == "UK-FBM":
        return UK_FBM_CHANNELS, None

    if category == "JP-FBM":
        return JP_FBM_CHANNELS, None

    if category == "CA-FBA":
        return CA_FBA_CHANNELS, None

    if category == "US-FBA":
        return US_FBA_CHANNELS, None

    if category == "DE-FBA":
        return DE_FBA_CHANNELS, None

    if category == "UK-FBA":
        return UK_FBA_CHANNELS, None

    if category == "JP-FBA":
        return JP_FBA_CHANNELS, None

    return [], "未知大类。"


# ======================================================
# 自动判断按钮 + 推荐渠道
# ======================================================
if st.button("自动判断所有渠道"):
    try:
        length, width, height, weight, base_len_unit, base_wt_unit = convert_units_for_category(
            category, L_raw, W_raw, H_raw, WT_raw
        )
    except Exception as e:
        st.error("请输入合法的数字或带单位的数值，例如：10、10cm、10in、2kg、2lb")
    else:
        girth = length + 2 * (width + height)

        st.write(
            f"**系统用于判断的内部尺寸：** "
            f"L = {length:.2f} {base_len_unit}，"
            f"W = {width:.2f} {base_len_unit}，"
            f"H = {height:.2f} {base_len_unit}，"
            f"Weight = {weight:.2f} {base_wt_unit}，"
            f"Girth = {girth:.2f} {base_len_unit}"
        )
# ===== 全品类临界提醒 =====
        threshold_msgs = check_threshold_all(category, length, width, height, weight, girth)
        for m in threshold_msgs:
            st.warning(m)

        channels, msg = get_channels(
            category,
            weight,
            length,
            width,
            height,
            girth
        )


        if msg:
            st.info(msg)

        if len(channels) == 0:
            st.warning("当前大类下没有可计算的渠道（可能未配置或重量超范围）。")
        else:
            results = []
            for func in channels:
                result = func(length, width, height, weight, girth)
                results.append(result)

            df = pd.DataFrame(results)
            df["推荐"] = ""

            # 推荐渠道：在可发渠道里选计费重最小，其次体积重最小
            df_ok = df[df["可发"] == "是"].copy()
            if not df_ok.empty:
                df_ok["_计费重_num"] = pd.to_numeric(df_ok["计费重"], errors="coerce")
                df_ok["_体积重_num"] = pd.to_numeric(df_ok["体积重"], errors="coerce")
                df_ok = df_ok.sort_values(
                    by=["_计费重_num", "_体积重_num"],
                    ascending=[True, True]
                )
                best_channel = df_ok.iloc[0]["渠道"]
                df.loc[df["渠道"] == best_channel, "推荐"] = "⭐ 推荐"

                st.subheader("⭐ 推荐渠道")
                st.dataframe(df[df["推荐"] == "⭐ 推荐"])

            st.subheader("✅ 可发渠道")
            st.dataframe(df[df["可发"] == "是"])

            st.subheader("❌ 不可发渠道")
            st.dataframe(df[df["可发"] == "否"])
