"""Mini NPU Simulator: 3×3 수동 입력과 JSON 패턴 분석."""

import json
import math
import time
from pathlib import Path

# 판정에 사용할 허용오차와 성능 측정 반복 횟수.
EPSILON = 1e-9
REPEAT = 10


# MAC 연산: 패턴과 필터의 같은 위치를 곱하고 합계를 구한다.
def mac(pattern, filter_data):
    score = 0.0
    # 행과 열을 차례로 확인하며 곱셈 결과를 점수에 더한다.
    for row in range(len(pattern)):
        for col in range(len(pattern[row])):
            score += pattern[row][col] * filter_data[row][col]
    return score


# 3×3 숫자 입력: 한 줄에 숫자 3개씩 받아 2차원 리스트로 만든다.
def input_matrix(name):
    matrix = []
    print(f"\n{name} 입력 (3줄, 숫자는 공백으로 구분)")
    for row in range(3):
        while True:
            try:
                # 공백으로 나눈 입력값을 모두 실수(float)로 변환한다.
                numbers = [float(x) for x in input(f"{row + 1}번째 줄: ").split()]
            except ValueError:
                print("입력 오류: 숫자만 입력하세요.")
                continue
            # 숫자가 3개가 아니거나 무한대·NaN이 있으면 같은 줄을 다시 입력받는다.
            if len(numbers) != 3 or not all(math.isfinite(x) for x in numbers):
                print("입력 형식 오류: 각 줄에 유효한 숫자 3개를 입력하세요.")
                continue
            matrix.append(numbers)
            break
    return matrix


# 점수 비교: 거의 같은 점수라면 어느 쪽도 선택하지 않는다.
def decide(score_a, score_b, label_a="A", label_b="B"):
    # 올바른 숫자가 아니거나 점수 차이가 허용오차 미만이면 판정을 보류한다.
    if not math.isfinite(score_a) or not math.isfinite(score_b):
        return "UNDECIDED"
    if abs(score_a - score_b) < EPSILON:
        return "UNDECIDED"
    return label_a if score_a > score_b else label_b


# MAC 계산을 10번 실행하여 한 번당 평균 소요 시간(ms)을 구한다.
def measure_mac(pattern, filter_data):
    start = time.perf_counter()
    for _ in range(REPEAT):
        mac(pattern, filter_data)
    # 초 단위 측정값에 1000을 곱해 밀리초로 변환한다.
    return (time.perf_counter() - start) * 1000 / REPEAT


# data.json을 불러오고 filters·patterns의 기본 자료형을 확인한다.
def load_json_data():
    try:
        # main.py와 같은 폴더에 있는 파일을 UTF-8로 읽는다.
        with open(Path(__file__).with_name("data.json"), encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, UnicodeError, ValueError) as error:
        print("파일 읽기 오류:", error)
        return None
    # JSON 최상위와 필수 항목이 딕셔너리인지 검사한다.
    if (not isinstance(data, dict)
            or not isinstance(data.get("filters"), dict)
            or not isinstance(data.get("patterns"), dict)):
        print("데이터 오류: filters와 patterns는 JSON 객체여야 합니다.")
        return None
    return data


# 서로 다르게 적힌 라벨을 Cross 또는 X로 통일한다.
def normalize_label(label):
    if not isinstance(label, str):
        return None
    # 좌우 공백과 대소문자 차이를 없앤 뒤 표준 라벨로 바꾼다.
    return {"+": "Cross", "cross": "Cross", "x": "X"}.get(label.strip().lower())


# 패턴이나 필터가 지정한 N×N 크기이고 숫자로 구성됐는지 확인한다.
def validate_matrix(matrix, size):
    if not isinstance(matrix, list) or len(matrix) != size:
        return f"행 개수가 {size}개가 아닙니다"
    # 각 행의 열 개수를 확인하고, 내부 값이 정상적인 숫자인지 검사한다.
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


# 패턴 키(size_5_1 등)가 규칙에 맞는지 확인하고 크기 N을 추출한다.
def parse_case_key(key):
    parts = key.split("_")
    # size_N_idx 형식, 지원 크기, 양의 번호인지 확인한다.
    if (len(parts) != 3 or parts[0] != "size"
            or parts[1] not in ("5", "13", "25")
            or not parts[2].isascii() or not parts[2].isdecimal()
            or not parts[2].strip("0")):
        return None
    return int(parts[1])


# JSON의 크기별 필터를 확인하고 Cross/X 두 종류로 정리한다.
def get_filters(filters, size):
    source = filters.get(f"size_{size}")
    if not isinstance(source, dict):
        return None, f"size_{size} 필터가 없습니다"
    result = {}
    for key, matrix in source.items():
        label = normalize_label(key)
        # 이름이 잘못됐거나 같은 필터가 중복 등록됐다면 실패 처리한다.
        if label is None or label in result:
            return None, f"필터 라벨 오류 또는 중복: {key}"
        error = validate_matrix(matrix, size)
        if error:
            return None, f"{label} 필터: {error}"
        result[label] = matrix
    # Cross와 X가 모두 있어야 점수 비교를 진행할 수 있다.
    if set(result) != {"Cross", "X"}:
        return None, "Cross 또는 X 필터가 빠졌습니다"
    return result, None


# 패턴 한 건을 검사한 뒤 MAC 점수와 예상 정답을 비교한다.
def analyze_case(key, case, filters):
    size = parse_case_key(key)
    if size is None:
        return False, "패턴 키 형식 오류 (size_N_idx)"
    if not isinstance(case, dict):
        return False, "패턴 데이터가 JSON 객체가 아닙니다"
    # expected 라벨과 입력 패턴의 구조가 올바른지 먼저 확인한다.
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

    # 검증된 패턴을 Cross/X 필터에 각각 대입해 점수를 계산한다.
    cross_score = mac(pattern, selected["Cross"])
    x_score = mac(pattern, selected["X"])
    if not math.isfinite(cross_score) or not math.isfinite(x_score):
        return False, "MAC 결과가 유효한 숫자가 아닙니다"

    # epsilon 정책으로 얻은 판정을 expected와 비교하여 PASS/FAIL을 정한다.
    result = decide(cross_score, x_score, "Cross", "X")
    passed = result == expected
    print(f"Cross 점수: {cross_score} / X 점수: {x_score}")
    print(f"판정: {result} | expected: {expected} | {'PASS' if passed else 'FAIL'}")
    if passed:
        return True, "정답 일치"
    if result == "UNDECIDED":
        return False, "점수 차이가 epsilon 미만이라 동점, expected와 불일치"
    return False, "판정 결과가 expected와 다릅니다"


# 3×3·5×5·13×13·25×25의 평균 MAC 시간과 연산 횟수를 출력한다.
def show_performance(filters):
    print("\n=== 성능 분석 (MAC 10회 평균) ===")
    print(f"{'크기':<10} {'평균 시간(ms)':>16} {'연산 횟수(N²)':>16}")
    for size in (3, 5, 13, 25):
        if size == 3:
            # JSON에 3×3 필터가 없으므로 기본 십자가 배열을 사용한다.
            pattern = [[0, 1, 0], [1, 1, 1], [0, 1, 0]]
        else:
            selected, error = get_filters(filters, size)
            if error:
                # 유효한 필터가 없는 크기는 N/A 대신 오류를 표시하고 건너뛴다.
                print(f"{size}×{size}: 측정 불가 ({error})")
                continue
            pattern = selected["Cross"]
        average = measure_mac(pattern, pattern)
        # :>16은 오른쪽 정렬, :.6f는 소수점 여섯 자리까지 출력한다.
        print(f"{size}×{size:<7} {average:>16.6f} {size * size:>16}")


# 모드 1: 사용자가 직접 입력한 3×3 패턴을 두 필터와 비교한다.
def mode1():
    filter_a = input_matrix("필터 A")
    filter_b = input_matrix("필터 B")
    print("\n=== 필터 저장 확인 ===")
    print("필터 A:", filter_a)
    print("필터 B:", filter_b)
    pattern = input_matrix("패턴")

    # 입력받은 배열로 A/B 점수를 구한 후 더 높은 쪽을 판정한다.
    score_a = mac(pattern, filter_a)
    score_b = mac(pattern, filter_b)
    result = decide(score_a, score_b)
    print("\n=== MAC 결과 ===")
    print(f"A 점수: {score_a} / B 점수: {score_b}")
    print("판정:", "판정 불가" if result == "UNDECIDED" else result)
    print("\n=== 성능 분석 (MAC 10회 평균) ===")
    # 파일 읽기·출력 시간을 제외하고 MAC 함수 호출 시간만 측정한다.
    print(f"A 평균 시간: {measure_mac(pattern, filter_a):.6f} ms")
    print(f"B 평균 시간: {measure_mac(pattern, filter_b):.6f} ms")
    print("연산 횟수(N², 필터당):", len(pattern) ** 2)


# 모드 2: JSON 패턴 전체를 판정하고 실패 원인과 성능표를 출력한다.
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
    # patterns에 들어 있는 각 케이스를 순서대로 검사한다.
    for key, case in patterns.items():
        print(f"\n--- {key} ---")
        ok, reason = analyze_case(key, case, filters)
        if ok:
            passed += 1
        else:
            # 실패한 식별자와 이유를 목록에 저장하여 마지막에 요약한다.
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


# 메인 메뉴: 1번(직접 입력) 또는 2번(JSON 분석)을 선택해 실행한다.
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
        # 메뉴 범위를 벗어난 선택만 다시 입력받는다.
        print("오류: 1 또는 2를 입력하세요.")


# main.py를 직접 실행했을 때만 메뉴를 시작한다.
if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print("\n입력이 중단되어 종료합니다.")
