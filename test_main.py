import unittest
from address_matcher import AddressMatcher, load_test_cases
import time
import pandas as pd


class TestAddressMatcher(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize the AddressMatcher with your data files
        cls.solution = AddressMatcher('list_ward.txt', 'list_district.txt', 'list_province.txt')
        cls.test_cases = load_test_cases('public.json')
        # cls.test_cases = load_test_cases('public-test.json')

    def test_match_address(self):
        summary_only = True
        df = []
        timer = []
        correct = 0
        for test_idx, data_point in enumerate(self.test_cases):
            address = data_point["text"]
            answer = data_point["result"]
            ok = 0
            try:
                start = time.perf_counter_ns()
                result = self.solution.process(address)
                answer = data_point["result"]
                finish = time.perf_counter_ns()
                timer.append(finish - start)

                # if answer["province"] != result["province"] or answer["district"] != result["district"] or answer["ward"] != result["ward"]:
                #     print(f"=====\n{address}")
                #     print(f"{answer}")
                #     print(f"{result}")

                ok += int(answer["province"] == result["province"])
                ok += int(answer["district"] == result["district"])
                ok += int(answer["ward"] == result["ward"])
                df.append([
                    test_idx,
                    address,
                    answer["province"],
                    result["province"],
                    int(answer["province"] == result["province"]),
                    answer["district"],
                    result["district"],
                    int(answer["district"] == result["district"]),
                    answer["ward"],
                    result["ward"],
                    int(answer["ward"] == result["ward"]),
                    ok,
                    timer[-1] / 1_000_000_000,
                ])
            except Exception as e:
                df.append([
                    test_idx,
                    address,
                    answer["province"],
                    "EXCEPTION",
                    0,
                    answer["district"],
                    "EXCEPTION",
                    0,
                    answer["ward"],
                    "EXCEPTION",
                    0,
                    0,
                    0,
                ])
                # any failure count as a zero correct
                pass
            correct += ok

            if not summary_only:
                # responsive stuff
                print(f"Test {test_idx:5d}/{len(self.test_cases):5d}")
                print(f"Correct: {ok}/3")
                print(f"Time Executed: {timer[-1] / 1_000_000_000:.4f}")

        print(f"-" * 30)
        total = len(self.test_cases) * 3
        score_scale_10 = round(correct / total * 10, 2)
        if len(timer) == 0:
            timer = [0]
        max_time_sec = round(max(timer) / 1_000_000_000, 4)
        avg_time_sec = round((sum(timer) / len(timer)) / 1_000_000_000, 4)

        df2 = pd.DataFrame(
            [[correct, total, score_scale_10, max_time_sec, avg_time_sec]],
            columns=['correct', 'total', 'score / 10', 'max_time_sec', 'avg_time_sec', ],
        )

        columns = [
            'ID',
            'text',
            'province',
            'province_student',
            'province_correct',
            'district',
            'district_student',
            'district_correct',
            'ward',
            'ward_student',
            'ward_correct',
            'total_correct',
            'time_sec',
        ]

        df = pd.DataFrame(df)
        df.columns = columns

        print(df2)


if __name__ == '__main__':
    unittest.main()
