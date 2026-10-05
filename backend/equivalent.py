"""当量换算：弦长读数必须先按当量系数换成收敛毫米，再判合格。

收敛(mm) = 弦长(mm) × 当量系数
直填毫米相当于系数为 1.0 的一路，因此“弦长路”和“毫米路”算出的必须是同一个数。
"""

# 允许维护的当量系数范围：系数必须为正，且不能放到无限大。
COEFF_MIN = 0.000001
COEFF_MAX = 1000.0
DEFAULT_COEFF = 1.0

# 弦长读数（仪器读数，非负）与最终收敛毫米的合理边界，挡住明显的录入错误。
CHORD_MIN = 0.0
CHORD_MAX = 1_000_000.0
DELTA_MIN = -100_000.0
DELTA_MAX = 100_000.0


def parse_number(value, field: str) -> float:
    """把前端传来的值解析为有限数字，失败时带中文字段名抛出 ValueError。"""
    if value is None or isinstance(value, bool):
        raise ValueError(f"{field}必须是数字")
    try:
        num = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field}必须是数字")
    if num != num or num in (float("inf"), float("-inf")):
        raise ValueError(f"{field}必须是有限数字")
    return num


def validate_coefficient(coeff: float) -> float:
    if coeff <= 0:
        raise ValueError("当量系数必须大于 0")
    if not (COEFF_MIN <= coeff <= COEFF_MAX):
        raise ValueError(
            f"当量系数越界：允许范围为 {COEFF_MIN:g}～{COEFF_MAX:g}，当前 {coeff:g}"
        )
    return coeff


def validate_chord(chord_mm: float) -> float:
    if chord_mm < CHORD_MIN or chord_mm > CHORD_MAX:
        raise ValueError(
            f"弦长读数越界：允许范围为 {CHORD_MIN:g}～{CHORD_MAX:g} mm，当前 {chord_mm:g}"
        )
    return chord_mm


def validate_delta(delta_mm: float) -> float:
    if delta_mm < DELTA_MIN or delta_mm > DELTA_MAX:
        raise ValueError(
            f"收敛毫米越界：允许范围为 {DELTA_MIN:g}～{DELTA_MAX:g} mm，当前 {delta_mm:g}"
        )
    return delta_mm


def to_delta(chord_mm: float, coefficient: float) -> float:
    """弦长按当量系数换算为收敛毫米。两路换算共用这一个函数，保证同一个数。"""
    chord = validate_chord(parse_number(chord_mm, "弦长读数"))
    coeff = validate_coefficient(parse_number(coefficient, "当量系数"))
    return round(chord * coeff, 6)


def normalize_direct_delta(delta_mm: float) -> float:
    """直填毫米路：只做范围校验并统一到相同精度。"""
    return round(validate_delta(parse_number(delta_mm, "收敛毫米")), 6)
