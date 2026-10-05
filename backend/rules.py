"""收敛判定与弦长换算。

判定：收敛绝对值不超过 3.0 mm 为合格。
换算：弦长读数不能直接当毫米用，按当量换算成收敛后再判：
    收敛(mm) = (弦长 - 基准弦长) × 当量系数
直填毫米与弦长换算走同一取舍规则（保留 3 位小数），两条路算出同一个数。
"""
import math

LIMIT_MM = 3.0

# 当量参数合法范围
FACTOR_MIN = 0.0  # 当量系数必须大于 0（开区间下界）
FACTOR_MAX = 10.0  # 当量系数上界
BASELINE_MIN_MM = 0.0
BASELINE_MAX_MM = 100000.0  # 基准弦长上界 100 m

# 弦长读数合法范围
CHORD_MIN_MM = 0.0
CHORD_MAX_MM = 100000.0

RESULT_DIGITS = 3  # 换算结果与直填毫米统一保留 3 位小数


def judge(delta_mm: float) -> tuple[str, str]:
    if abs(delta_mm) <= LIMIT_MM:
        return "合格", f"收敛 {delta_mm} mm 在 ±{LIMIT_MM} mm 以内"
    return "超限", f"收敛 {delta_mm} mm 超过 ±{LIMIT_MM} mm"


def _as_finite_number(value, label: str) -> float:
    try:
        num = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label}必须是数字")
    if not math.isfinite(num):
        raise ValueError(f"{label}必须是有限数字")
    return num


def validate_equivalent(factor, baseline_mm) -> tuple[float, float]:
    """校验当量参数；填错或越界抛出带中文原因的 ValueError。"""
    f = _as_finite_number(factor, "当量系数")
    if not (FACTOR_MIN < f <= FACTOR_MAX):
        raise ValueError(
            f"当量系数越界：须大于 {FACTOR_MIN:g} 且不超过 {FACTOR_MAX:g}，当前为 {f:g}"
        )
    b = _as_finite_number(baseline_mm, "基准弦长")
    if not (BASELINE_MIN_MM <= b <= BASELINE_MAX_MM):
        raise ValueError(
            f"基准弦长越界：须在 {BASELINE_MIN_MM:g} ~ {BASELINE_MAX_MM:g} mm 之间，当前为 {b:g}"
        )
    return f, b


def validate_chord(chord_mm) -> float:
    """校验弦长读数；填错或越界抛出带中文原因的 ValueError。"""
    c = _as_finite_number(chord_mm, "弦长读数")
    if not (CHORD_MIN_MM <= c <= CHORD_MAX_MM):
        raise ValueError(
            f"弦长读数越界：须在 {CHORD_MIN_MM:g} ~ {CHORD_MAX_MM:g} mm 之间，当前为 {c:g}"
        )
    return c


def validate_reading(delta_mm) -> float:
    """直填毫米：必须是有限数字。"""
    return _as_finite_number(delta_mm, "收敛值")


def convert_chord(chord_mm: float, factor: float, baseline_mm: float) -> float:
    """弦长 -> 收敛毫米：(弦长 - 基准弦长) × 当量系数，保留 3 位小数。"""
    return round((chord_mm - baseline_mm) * factor, RESULT_DIGITS)


def round_reading(value: float) -> float:
    """直填毫米与弦长换算同一取舍规则，保证两条路算出同一个数。"""
    return round(value, RESULT_DIGITS)
