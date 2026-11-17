"""Mini NPU Simulator — Python 3.8+ / standard library only."""

import json
import math
import time
from pathlib import Path

EPSILON = 1e-9
REPEAT = 10
SIZES = (3, 5, 13, 25)


# 같은 위치의 수를 곱하고 그 결과를 전부 더한다.
def mac(pattern, filter_data):
    score = 0.0
    for row in range(len(pattern)):
        for col in range(len(pattern[row])):
            score += pattern[row][col] * filter_data[row][col]
    return score


# 한 줄에 숫자 3개씩 입력받고 잘못 입력한 줄은 다시 받는다.
def input_matrix(name):
    matrix = []
    print(f"\n{name} 입력 (3x3, 숫자 사이 공백)")
    for row in range(3):
        while True:
            try:
                text = input(f"{row + 1}번째 줄: ")
            except EOFError:
                print("입력이 중단되었습니다.")
                return None
            values = text.split()
            if len(values) != 3:
                print("입력 형식 오류: 각 줄에 숫자 3개를 공백으로 구분해 입력하세요.")
                continue
            try:
                numbers = [float(value) for value in values]
            except ValueError:
                print("입력 오류: 숫자만 입력하세요.")
                continue
            if not all(math.isfinite(value) for value in numbers):
                print("입력 오류: 무한대나 NaN은 사용할 수 없습니다.")
                continue
            matrix.append(numbers)
            break
    return matrix


# 점수가 거의 같으면 판정 불가이다.
def decide(score_a, score_b, label_a="A", label_b="B"):
    if not math.isfinite(score_a) or not math.isfinite(score_b):
        return "UNDECIDED"
    if abs(score_a - score_b) < EPSILON:
        return "UNDECIDED"
    if score_a > score_b:
        return label_a
    return label_b


# 파일 읽기나 화면 출력 시간은 재지 않고 MAC 함수만 10회 이상 측정한다.
def measure_mac(pattern, filter_data, repeat=REPEAT):
    start = time.perf_counter()
    for _ in range(repeat):
        mac(pattern, filter_data)
    end = time.perf_counter()
    return (end - start) * 1000 / repeat


# data.json은 main.py와 같은 폴더에서 읽는다.
def load_json_data():
    path = Path(__file__).resolve().parent / "data.json"
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, UnicodeError, ValueError) as error:
        print("파일 읽기 오류:", error)
        return None
    if not isinstance(data, dict):
        print("데이터 오류: JSON 전체는 객체여야 합니다.")
        return None
    if not isinstance(data.get("filters"), dict):
        print("데이터 오류: filters가 없거나 객체가 아닙니다.")
        return None
    if not isinstance(data.get("patterns"), dict):
        print("데이터 오류: patterns가 없거나 객체가 아닙니다.")
        return None
    return data


# 'cross', '+'를 Cross로, 'x'를 X로 통일한다.
def normalize_label(label):
    if not isinstance(label, str):
        return None
    name = label.strip().lower()
    if name in ("+", "cross"):
        return "Cross"
    if name == "x":
        return "X"
    return None


# n×n 배열인지, 모든 칸이 유한한 숫자인지 검사한다.
def validate_matrix(matrix, size):
    if not isinstance(matrix, list):
        return "2차원 리스트 형식이 아닙니다"
    if len(matrix) != size:
        return f"행 개수가 {size}개가 아닙니다"
    for row_index, row in enumerate(matrix, 1):
        if not isinstance(row, list):
            return f"{row_index}번째 행이 리스트가 아닙니다"
        if len(row) != size:
            return f"{row_index}번째 행의 열 개수가 {size}개가 아닙니다"
        for col_index, number in enumerate(row, 1):
            if type(number) not in (int, float):
                return f"({row_index}, {col_index}) 위치가 숫자가 아닙니다"
            try:
                finite = math.isfinite(number)
            except (ValueError, OverflowError):
                finite = False
            if not finite:
                return f"({row_index}, {col_index}) 위치의 숫자가 유효하지 않습니다"
    return None


# size_N_idx를 해석한다. 잘못된 이름은 None과 오류 이유를 돌려준다.
def parse_case_key(key):
    parts = key.split("_")
    if len(parts) != 3 or parts[0] != "size":
        return None, "키 규칙 오류 (size_N_idx 필요)"
    if not parts[1].isascii() or not parts[1].isdecimal():
        return None, "키의 크기 N이 숫자가 아닙니다"
    if not parts[2].isascii() or not parts[2].isdecimal():
        return None, "키의 번호 idx가 숫자가 아닙니다"
    size = int(parts[1])
    if size not in (5, 13, 25) or int(parts[2]) < 1:
        return None, "지원하지 않는 크기 또는 잘못된 번호입니다"
    return size, None


# 필터 이름을 표준화하고 두 배열을 검증한다.
def get_filters(filters, size):
    source = filters.get(f"size_{size}")
    if not isinstance(source, dict):
        return None, f"size_{size} 필터가 없거나 객체가 아닙니다"
    normalized = {}
    for raw_label, matrix in source.items():
        label = normalize_label(raw_label)
        if label is None:
            return None, f"알 수 없는 필터 라벨: {raw_label}"
        if label in normalized:
            return None, f"{label} 필터 라벨이 중복됩니다"
        normalized[label] = matrix
    for label in ("Cross", "X"):
        if label not in normalized:
            return None, f"{label} 필터가 없습니다"
        error = validate_matrix(normalized[label], size)
        if error:
            return None, f"{label} 필터: {error}"
    return normalized, None


# 패턴 한 개를 검사하고 판정한다. 실패해도 다른 패턴은 계속 진행한다.
def analyze_case(key, case, filters):
    size, error = parse_case_key(key)
    if error:
        return {"pass": False, "reason": error}
    if not isinstance(case, dict):
        return {"pass": False, "reason": "패턴 데이터가 객체가 아닙니다"}
    expected = normalize_label(case.get("expected"))
    if expected is None:
        return {"pass": False, "reason": "expected 라벨이 올바르지 않습니다"}
    pattern = case.get("input")
    error = validate_matrix(pattern, size)
    if error:
        return {"pass": False, "reason": "패턴: " + error}
    normalized, error = get_filters(filters, size)
    if error:
        return {"pass": False, "reason": error}
    try:
        score_cross = mac(pattern, normalized["Cross"])
        score_x = mac(pattern, normalized["X"])
    except (ValueError, OverflowError, TypeError, IndexError) as exc:
        return {"pass": False, "reason": f"연산 오류: {exc}"}
    if not math.isfinite(score_cross) or not math.isfinite(score_x):
        return {"pass": False, "reason": "MAC 결과가 유효한 숫자가 아닙니다"}
    result = decide(score_cross, score_x, "Cross", "X")
    passed = result == expected
    if passed:
        reason = "정답 일치"
    elif result == "UNDECIDED":
        reason = "동점(허용오차) 판정으로 expected와 불일치"
    else:
        reason = "계산한 판정과 expected가 다릅니다"
    return {"pass": passed, "reason": reason, "scores": (score_cross, score_x),
            "result": result, "expected": expected}


# 예제 3×3은 성능 비교용 고정 배열이다. 자동 패턴 생성기는 만들지 않는다.
BENCHMARK_3 = [
    [0, 1, 0],
    [1, 1, 1],
    [0, 1, 0],
]


# 표의 N²는 '필터 하나에 대한 MAC 계산 한 번'의 위치별 곱셈 횟수이다.
def show_performance(filters, patterns):
    print("\n=== 성능 분석 (크기별 MAC 평균/10회) ===")
    print(f"{'크기':<10} {'평균 시간(ms)':>16} {'연산 횟수(N²)':>16}")
    print("-" * 46)
    for size in SIZES:
        if size == 3:
            pattern = BENCHMARK_3
            filter_data = BENCHMARK_3
        else:
            normalized, error = get_filters(filters, size)
            if error:
                print(f"{size}x{size:<7} {'N/A':>16} {size * size:>16} ({error})")
                continue
            # 해당 크기에서 올바른 패턴 하나를 우선 사용한다.
            pattern = None
            for key, case in patterns.items():
                case_size, key_error = parse_case_key(key)
                if key_error is None and case_size == size and isinstance(case, dict):
                    candidate = case.get("input")
                    if validate_matrix(candidate, size) is None:
                        pattern = candidate
                        break
            # 패턴이 전부 잘못되어 있다면 정상 Cross 필터를 입력 배열로 쓴다.
            if pattern is None:
                pattern = normalized["Cross"]
            filter_data = normalized["Cross"]
        average = measure_mac(pattern, filter_data)
        print(f"{size}x{size:<7} {average:>16.6f} {size * size:>16}")


# 모드 1: 직접 3×3 입력하고 A/B 판정한다.
def mode1():
    print("\n=== 사용자 입력 (3x3) ===")
    filter_a = input_matrix("필터 A")
    if filter_a is None:
        return
    filter_b = input_matrix("필터 B")
    if filter_b is None:
        return
    print("\n=== 필터 저장 확인 ===")
    print("필터 A:", filter_a)
    print("필터 B:", filter_b)
    pattern = input_matrix("패턴")
    if pattern is None:
        return
    score_a = mac(pattern, filter_a)
    score_b = mac(pattern, filter_b)
    print("\n=== MAC 결과 ===")
    print("A 점수:", score_a)
    print("B 점수:", score_b)
    result = decide(score_a, score_b)
    print("판정:", "판정 불가" if result == "UNDECIDED" else result)
    print("\n=== 성능 분석 (평균/10회) ===")
    print(f"A 평균 연산 시간: {measure_mac(pattern, filter_a):.6f} ms")
    print(f"B 평균 연산 시간: {measure_mac(pattern, filter_b):.6f} ms")
    print("연산 횟수(N², 필터당):", len(pattern) ** 2)


# 모드 2: JSON 전체 분석, PASS/FAIL, 성능표, 요약 출력.
def mode2():
    print("\n=== data.json 분석 ===")
    data = load_json_data()
    if data is None:
        return
    filters = data["filters"]
    patterns = data["patterns"]
    print("JSON 파일 읽기 성공")
    print("\n=== 필터 로드 및 검증 ===")
    for size in (5, 13, 25):
        _, error = get_filters(filters, size)
        if error:
            print(f"size_{size}: 오류 - {error}")
        else:
            print(f"size_{size}: Cross/X 필터 확인")
    print("\n=== 패턴별 MAC 분석 ===")
    passed_count = 0
    failed = []
    for key, case in patterns.items():
        outcome = analyze_case(key, case, filters)
        if "scores" in outcome:
            cross_score, x_score = outcome["scores"]
            print(f"\n--- {key} ---")
            print(f"Cross 점수: {cross_score}")
            print(f"X 점수: {x_score}")
            print(f"판정: {outcome['result']} | expected: {outcome['expected']} | "
                  f"{'PASS' if outcome['pass'] else 'FAIL'}")
        else:
            print(f"\n--- {key} ---\nFAIL: {outcome['reason']}")
        if outcome["pass"]:
            passed_count += 1
        else:
            failed.append((key, outcome["reason"]))
    show_performance(filters, patterns)
    print("\n=== 결과 요약 ===")
    print("전체 테스트:", len(patterns))
    print("통과:", passed_count)
    print("실패:", len(failed))
    if failed:
        print("실패 케이스:")
        for key, reason in failed:
            print(f"- {key}: {reason}")
    else:
        print("실패 케이스: 없음")


# 프로그램 시작 메뉴.
def main():
    while True:
        print("\n=== Mini NPU Simulator ===")
        print("1. 사용자 입력 (3x3)")
        print("2. data.json 분석")
        try:
            choice = input("선택: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n입력이 중단되어 종료합니다.")
            return
        if choice == "1":
            mode1()
            return
        if choice == "2":
            mode2()
            return
        print("오류: 1 또는 2를 입력하세요.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n입력이 중단되어 종료합니다.")
