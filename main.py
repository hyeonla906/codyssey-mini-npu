"""Mini NPU 시뮬레이터: 모드 1 → 모드 2 순서로 읽는 main.py.


1. 모드 1: 3×3 숫자를 직접 입력하고 A/B 점수를 비교
2. 모드 2: data.json을 읽어 Cross/X를 비교하고 PASS/FAIL 확인
3. 맨 아래 main(): 실행 시 1번 또는 2번 모드를 선택

중요: 파이썬은 먼저 모든 def(함수)를 등록한 뒤, 맨 아래에서 main()을 실행합니다.
그래서 mode1()/mode2()가 사용하는 함수가 아래에 정의되어 있어도 정상 실행됩니다.
"""

import json
import math
import time
from pathlib import Path

EPSILON = 1e-9  # 점수 차이가 이 값보다 작으면 판정 보류
REPEAT = 10     # MAC 계산을 10번 반복해 1회 평균 시간 계산

# ======================================================================
# [모드 1] 사용자 직접 입력 (3×3) — 이 순서대로 읽기
# ======================================================================

# [1-1] mode1(): 필터 A/B 입력 → 패턴 입력 → 점수 → 판정 → 성능
def mode1():
    filter_a = input_matrix("필터 A")
    filter_b = input_matrix("필터 B")
    print("\n=== 필터 저장 확인 ===")
    print("필터 A:", filter_a)
    print("필터 B:", filter_b)
    pattern = input_matrix("패턴")
    score_a = mac(pattern, filter_a)
    score_b = mac(pattern, filter_b)
    result = decide(score_a, score_b)
    print("\n=== MAC 결과 ===")
    print(f"A 점수: {score_a} / B 점수: {score_b}")
    print("판정:", "판정 불가" if result == "UNDECIDED" else result)
    print("\n=== 성능 분석 (MAC 10회 평균) ===")
    print(f"A 평균 시간: {measure_mac(pattern, filter_a):.6f} ms")
    print(f"B 평균 시간: {measure_mac(pattern, filter_b):.6f} ms")
    print("연산 횟수(N², 필터당):", len(pattern) ** 2)


# [1-2] input_matrix(): 3×3 숫자 배열 한 개 입력받기 (총 세 번 호출)
def input_matrix(name):
    matrix = []
    print(f"\n{name} 입력 (3줄, 숫자는 공백으로 구분)")
    for row in range(3):
        while True:
            try:
                numbers = [float(x) for x in input(f"{row + 1}번째 줄: ").split()]
            except ValueError:
                print("입력 오류: 숫자만 입력하세요.")
                continue
            if len(numbers) != 3 or not all(math.isfinite(x) for x in numbers):
                print("입력 형식 오류: 각 줄에 유효한 숫자 3개를 입력하세요.")
                continue
            matrix.append(numbers)
            break
    return matrix


# [1-3] mac(): 같은 위치의 수를 곱하고 더해 점수 계산 (모드 2도 사용)
def mac(pattern, filter_data):
    score = 0.0
    for row in range(len(pattern)):
        for col in range(len(pattern[row])):
            score += pattern[row][col] * filter_data[row][col]
    return score


# [1-4] decide(): 두 점수 비교, 동점이면 UNDECIDED (모드 2도 사용)
def decide(score_a, score_b, label_a="A", label_b="B"):
    if not math.isfinite(score_a) or not math.isfinite(score_b):
        return "UNDECIDED"
    if abs(score_a - score_b) < EPSILON:
        return "UNDECIDED"
    return label_a if score_a > score_b else label_b


# [1-5] measure_mac(): MAC 10회 실행 후 평균 시간(ms) 측정 (모드 2도 사용)
def measure_mac(pattern, filter_data):
    start = time.perf_counter()
    for _ in range(REPEAT):
        mac(pattern, filter_data)
    return (time.perf_counter() - start) * 1000 / REPEAT


# ======================================================================
# [모드 2] data.json 자동 분석 — 이 순서대로 읽기
# ======================================================================

# [2-1] mode2(): JSON 읽기 → 필터 검사 → 모든 패턴 분석 → 성능표 → 요약
def mode2():
    data = load_json_data()
    if data is None:
        return
    filters, patterns = data["filters"], data["patterns"]
    print("\n=== 필터 로드 및 검증 ===")
    for size in (5, 13, 25):
        _, error = get_filters(filters, size)
        print(f"size_{size}:", error if error else "Cross/X 필터 확인")
    print("\n=== 패턴 분석 ===")
    passed = 0
    failed = []
    for key, case in patterns.items():
        print(f"\n--- {key} ---")
        ok, reason = analyze_case(key, case, filters)
        if ok:
            passed += 1
        else:
            print("FAIL 원인:", reason)
            failed.append((key, reason))
    show_performance(filters)
    print("\n=== 결과 요약 ===")
    print("전체 테스트:", len(patterns))
    print("통과:", passed)
    print("실패:", len(failed))
    if failed:
        print("실패 케이스:")
        for key, reason in failed:
            print(f"- {key}: {reason}")
    else:
        print("실패 케이스: 없음")


# [2-2] load_json_data(): data.json 불러오기 및 기본 구조 검사
def load_json_data():
    try:
        with open(Path(__file__).with_name("data.json"), encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, UnicodeError, ValueError) as error:
        print("파일 읽기 오류:", error)
        return None
    if (not isinstance(data, dict)
            or not isinstance(data.get("filters"), dict)
            or not isinstance(data.get("patterns"), dict)):
        print("데이터 오류: filters와 patterns는 JSON 객체여야 합니다.")
        return None
    return data


# [2-3] get_filters(): 크기별 Cross/X 필터 가져오기
def get_filters(filters, size):
    source = filters.get(f"size_{size}")
    if not isinstance(source, dict):
        return None, f"size_{size} 필터가 없습니다"
    result = {}
    for key, matrix in source.items():
        label = normalize_label(key)
        if label is None or label in result:
            return None, f"필터 라벨 오류 또는 중복: {key}"
        error = validate_matrix(matrix, size)
        if error:
            return None, f"{label} 필터: {error}"
        result[label] = matrix
    if set(result) != {"Cross", "X"}:
        return None, "Cross 또는 X 필터가 빠졌습니다"
    return result, None


# [2-4] normalize_label(): + / cross / x 이름을 Cross 또는 X로 통일
def normalize_label(label):
    if not isinstance(label, str):
        return None
    return {"+": "Cross", "cross": "Cross", "x": "X"}.get(label.strip().lower())


# [2-5] validate_matrix(): N×N 배열 크기와 숫자 검사
def validate_matrix(matrix, size):
    if not isinstance(matrix, list) or len(matrix) != size:
        return f"행 개수가 {size}개가 아닙니다"
    for row_number, row in enumerate(matrix, 1):
        if not isinstance(row, list) or len(row) != size:
            return f"{row_number}번째 행의 열 개수가 {size}개가 아닙니다"
        for number in row:
            if type(number) not in (int, float):
                return f"{row_number}번째 행에 숫자가 아닌 값이 있습니다"
            try:
                if not math.isfinite(number):
                    return f"{row_number}번째 행에 유효하지 않은 숫자가 있습니다"
            except (ValueError, OverflowError):
                return f"{row_number}번째 행에 유효하지 않은 숫자가 있습니다"
    return None


# [2-6] parse_case_key(): size_13_2처럼 적힌 키에서 크기 확인
def parse_case_key(key):
    parts = key.split("_")
    if (len(parts) != 3 or parts[0] != "size"
            or parts[1] not in ("5", "13", "25")
            or not parts[2].isascii() or not parts[2].isdecimal()
            or not parts[2].strip("0")):
        return None
    return int(parts[1])


# [2-7] analyze_case(): 패턴 하나 검사 → MAC → 판정 → PASS/FAIL
def analyze_case(key, case, filters):
    size = parse_case_key(key)
    if size is None:
        return False, "패턴 키 형식 오류 (size_N_idx)"
    if not isinstance(case, dict):
        return False, "패턴 데이터가 JSON 객체가 아닙니다"
    expected = normalize_label(case.get("expected"))
    if expected is None:
        return False, "expected 라벨 오류"
    pattern = case.get("input")
    error = validate_matrix(pattern, size)
    if error:
        return False, f"패턴: {error}"
    selected, error = get_filters(filters, size)
    if error:
        return False, error
    cross_score = mac(pattern, selected["Cross"])
    x_score = mac(pattern, selected["X"])
    if not math.isfinite(cross_score) or not math.isfinite(x_score):
        return False, "MAC 결과가 유효한 숫자가 아닙니다"
    result = decide(cross_score, x_score, "Cross", "X")
    passed = result == expected
    print(f"Cross 점수: {cross_score} / X 점수: {x_score}")
    print(f"판정: {result} | expected: {expected} | {'PASS' if passed else 'FAIL'}")
    if passed:
        return True, "정답 일치"
    if result == "UNDECIDED":
        return False, "점수 차이가 epsilon 미만이라 동점, expected와 불일치"
    return False, "판정 결과가 expected와 다릅니다"


# [2-8] show_performance(): 크기별 MAC 10회 평균 시간과 N² 출력
def show_performance(filters):
    print("\n=== 성능 분석 (MAC 10회 평균) ===")
    print(f"{'크기':<10} {'평균 시간(ms)':>16} {'연산 횟수(N²)':>16}")
    for size in (3, 5, 13, 25):
        if size == 3:
            pattern = [[0, 1, 0], [1, 1, 1], [0, 1, 0]]
        else:
            selected, error = get_filters(filters, size)
            if error:
                print(f"{size}×{size}: 측정 불가 ({error})")
                continue
            pattern = selected["Cross"]
        average = measure_mac(pattern, pattern)
        print(f"{size}×{size:<7} {average:>16.6f} {size * size:>16}")


# ======================================================================
# [프로그램 시작] main() — 메뉴 선택 (맨 아래에서 호출)
# ======================================================================

# [시작] main(): 사용자 선택 1 → mode1(), 2 → mode2()
def main():
    while True:
        print("\n=== Mini NPU Simulator ===")
        print("1. 사용자 입력 (3×3)")
        print("2. data.json 분석")
        choice = input("선택: ").strip()
        if choice == "1":
            mode1()
            return
        if choice == "2":
            mode2()
            return
        print("오류: 1 또는 2를 입력하세요.")


# 이 파일을 직접 실행할 때 프로그램을 시작합니다.
if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print("\n입력이 중단되어 종료합니다.")
