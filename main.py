# NOTE: you CAN change this cell
# If you want to use your own database, download it here
# !gdown ...
import os
import requests
import csv
import re
import pandas as pd
import json
import time
from multiprocessing import Process, Manager

from functools import lru_cache
from collections import defaultdict
import unicodedata
from typing import List, Set
import multiprocessing

import cProfile
import memory_profiler
from memory_profiler import profile

# Remove file if it exists
if os.path.exists("test.json"):
    os.remove("test.json")

# Function to download the file from Google Drive (use an alternative method if gdown is not available)
def download_from_google_drive(url, filename):
    try:
        response = requests.get(url)
        with open(filename, 'wb') as f:
            f.write(response.content)
        print(f"Downloaded '{filename}' successfully.")
    except Exception as e:
        print(f"An error occurred while downloading the file: {e}")


class TrieNode:
    __slots__ = ['children', 'is_end_of_word', 'data']

    def __init__(self):
        self.children = {}
        self.is_end_of_word = False
        self.data = []


class Trie:
    def __init__(self):
        self.root = TrieNode()
        self.vietnamese_chars = frozenset("aáàăằắâbcdđeêềfghiíịjklmnoóòôồơpqrstuưvwxyzABCDĐEFGHIJKLMNOPQRSTUVWXYZ")
        self.variation_cache = defaultdict(set)

    @lru_cache(maxsize=1024)
    def remove_diacritics(self, text: str) -> str:
        normalized = unicodedata.normalize('NFD', text)
        return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')

    def generate_variations(self, full_name: str) -> List[str]:
        if full_name in self.variation_cache:
            return list(self.variation_cache[full_name])

        words = full_name.split()
        variations = {full_name}

        for i in range(len(words)):
            words_with_T = words[:i] + ['T' + words[i]] + words[i + 1:]
            variations.add(' '.join(words_with_T))

        self.variation_cache[full_name] = variations
        return list(variations)

    def _generate_word_variations(self, word: str) -> Set[str]:
        variations = set()
        length = len(word)

        # Missing character variations
        variations.update(word[:i] + word[i + 1:] for i in range(length))

        # Character replacement and insertion variations
        for i in range(length):
            variations.update(
                word[:i] + char + word[i + 1:]
                for char in self.vietnamese_chars
                if char != word[i]
            )
            variations.update(
                word[:i] + char + word[i:]
                for char in self.vietnamese_chars
            )

        # Add characters at start and end
        variations.update(char + word for char in self.vietnamese_chars)
        variations.update(word + char for char in self.vietnamese_chars)

        return variations

    def _insert_word(self, word: str, data: dict):
        node = self.root
        for char in word.lower():  # Case-insensitive insert
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.is_end_of_word = True
        node.data.append(data)

    def _generate_all_variations(self, full_name: str) -> set:
        initial_variations = set(self.generate_variations(full_name))
        all_variations = set()

        for variant in initial_variations:
            all_variations.add(variant)  # Original variant
            all_variations.add(self.remove_diacritics(variant))  # No diacritics version
            all_variations.update(self._generate_word_variations(variant))  # Other variations

        return all_variations

    def Provinces_insert(self, code: str, full_name: str):
        all_variations = self._generate_all_variations(full_name)
        data = {"Code": code, "FullName": full_name}
        for word in all_variations:
            self._insert_word(word, data)

    def Districts_insert(self, code: str, full_name: str, ProvinceCode: str):
        all_variations = self._generate_all_variations(full_name)
        data = {"Code": code, "FullName": full_name, "ProvinceCode": ProvinceCode}
        for word in all_variations:
            self._insert_word(word, data)

    def Wards_insert(self, code: str, full_name: str, DistrictCode: str):
        all_variations = self._generate_all_variations(full_name)
        data = {"Code": code, "FullName": full_name, "DistrictCode": DistrictCode}
        for word in all_variations:
            self._insert_word(word, data)

    def Insert_Compare(self, word: str):
        """Insert word for comparison database"""
        node = self.root
        for char in word.lower():  # Case-insensitive insert
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.is_end_of_word = True
        # Store the word directly in data instead of list for comparison
        node.data = word

    def search_cp(self, word: str) -> str:
        """Search in comparison database"""
        node = self.root
        for char in word.lower():  # Case-insensitive search
            if char not in node.children:
                return None
            node = node.children[char]

        return node.data if node.is_end_of_word else None

    def search(self, word: str) -> List[dict]:
        """Search in main database"""
        node = self.root
        for char in word.lower():  # Case-insensitive search
            if char not in node.children:
                return None
            node = node.children[char]

        return node.data if node.is_end_of_word else None

    def search_phrase(self, phrase: str) -> List[dict]:
        """Search for multi-word phrases"""
        # Filter words shorter than 2 characters
        filtered_words = [word for word in phrase.split() if len(word) > 1]
        results = []

        # Search for all possible word combinations
        for i in range(len(filtered_words)):
            for j in range(i + 1, len(filtered_words) + 1):
                phrase_to_check = ' '.join(filtered_words[i:j])
                found_data = self.search(phrase_to_check)

                if found_data:
                    if isinstance(found_data, list):
                        # Add unique items from list
                        results.extend(
                            item for item in found_data
                            if item and item not in results
                        )
                    elif found_data not in results:
                        # Add single item if not already in results
                        results.append(found_data)

        return results


class Solution:
    def __init__(self):

        # Cập nhật các URL thành URL tải xuống trực tiếp từ Google Drive
        # Download database của mình
        url_Districts = "https://drive.google.com/uc?id=1HX5_HqBTxi6WGBuv03RDD3Pp1LZfUbO_&export=download"
        url_Provinces = "https://drive.google.com/uc?id=1r7oFUXFSnVV8L_vF_k6WFkNI5M4tVp5D&export=download"
        url_Wards = "https://drive.google.com/uc?id=1AEzjEDter32zb3em-XY3lUG4V0YY4FOA&export=download"

        download_from_google_drive(url_Districts, "Districts.txt")
        download_from_google_drive(url_Provinces, "Provinces.txt")
        download_from_google_drive(url_Wards, "Wards.txt")

        self._init_paths()
        self._init_tries()
        print('Starting data load')
        self.load_data()
        print('Data load complete')

    def _init_paths(self):
        # Private test paths
        self.province_path = "list_province.txt"
        self.district_path = "list_district.txt"
        self.ward_path = "list_ward.txt"
        # Data paths
        self.Districts_path = "Districts.txt"
        self.Provinces_path = "Provinces.txt"
        self.Wards_path = "Wards.txt"

    def _init_tries(self):
        self.provinces_trie = Trie()
        self.districts_trie = Trie()
        self.wards_trie = Trie()
        self.province_cp = Trie()
        self.district_cp = Trie()
        self.ward_cp = Trie()

    def load_data(self):
        # Load main data
        provinces_data = self.read_data(self.Provinces_path)
        districts_data = self.read_data(self.Districts_path)
        wards_data = self.read_data(self.Wards_path)

        # Load comparison data
        compare_province = self.insert_from_file(self.province_path)
        compare_district = self.insert_from_file(self.district_path)
        compare_ward = self.insert_from_file(self.ward_path)

        # Process data in parallel
        with multiprocessing.Pool() as pool:
            print('Loading provinces')
            pool.starmap(self.provinces_trie.Provinces_insert,
                         [(p['Code'], p['FullName']) for p in provinces_data])

            print('Loading districts')
            pool.starmap(self.districts_trie.Districts_insert,
                         [(d['Code'], d['FullName'], d['ProvinceCode']) for d in districts_data])

            print('Loading wards')
            pool.starmap(self.wards_trie.Wards_insert,
                         [(w['Code'], w['FullName'], w['DistrictCode']) for w in wards_data])

        # Load comparison data
        print('Loading comparison data')
        for p in compare_province:
            self.province_cp.Insert_Compare(p)
        for d in compare_district:
            self.district_cp.Insert_Compare(d)
        for w in compare_ward:
            self.ward_cp.Insert_Compare(w)

    def read_data(self, file_path):
        with open(file_path, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file, delimiter=';')
            records = []
            for row in reader:
                records.append(row)
        return records

    def insert_from_file(self, filename):
        with open(filename, 'r', encoding='utf-8') as file:
            reader = [line.strip() for line in file if (clean_line := line.strip())]
        return reader

    def capitalize_first_letter(self, text):
        words = text.split()  # Tách chuỗi thành danh sách các từ
        capitalized_words = [word[0].upper() + word[1:] for word in words]  # Viết hoa chữ cái đầu của mỗi từ
        return " ".join(capitalized_words)  # Ghép lại thành chuỗi

    # Xử lý riêng Bà Rịa - Vũng Tàu
    def handle_ba_ria_vung_tau_case(self, input_phrase):
        """
        Xử lý riêng cho Bà Rịa - Vũng Tàu, nhận diện và trích xuất quận/phường có số, và tiếp tục xử lý phần còn lại.
        """
        # Xác định và chuẩn hóa tên tỉnh thành "Bà Rịa - Vũng Tàu"
        if "Bà Rịa - Vũng Tàu" not in input_phrase and "Bà Rịa-Vũng Tàu" not in input_phrase:
            return None

        # Xóa tên tỉnh thành khỏi chuỗi
        input_phrase = re.sub(r"Bà Rịa - Vũng Tàu", "", input_phrase, flags=re.IGNORECASE).strip()

        ward = None
        district = None

        # Tìm số phường nếu có (ví dụ: "P1", "Phường 1")
        ward_match = re.search(r'\b(?:Phường|P|F|P.|F.|phường|p|f)\s*(\d+)', input_phrase)
        if ward_match:
            ward = ward_match.group(1)
            input_phrase = input_phrase.replace(ward_match.group(0), "").strip()

        # Chuẩn hóa lại chuỗi còn lại
        input_phrase = re.sub(
            r"Huyện|huyện|Tỉnh|Thị xã|Thị Xã|Phường|phường|Thị trấn|Thị Trấn|Xã|xã|Quận|quận|Thành phố|Thành Phố|TP|Tnh|Tp|tp|F|f|Tỉn|tỉnh|T.p|T.P",
            " ", input_phrase).strip()
        input_phrase = re.sub(r"[!@#$%^&*()_=+{},.\/?<>:;`~|-]", " ", input_phrase).strip()
        input_phrase = re.sub(r"\d+", "", input_phrase).strip()
        input_phrase = re.sub(r"\s+", " ", input_phrase).strip()
        input_phrase = self.capitalize_first_letter(input_phrase)

        # Tìm kiếm thông tin tỉnh/thành phố, quận/huyện, và phường/xã trong Trie
        result = self.query_standard(input_phrase)

        # Gán thông tin đặc biệt cho Bà Rịa - Vũng Tàu và chỉ số quận/phường
        result["province"] = "Bà Rịa - Vũng Tàu"
        if ward:
            result["ward"] = ward

        return result

    def normalize_ho_chi_minh(self, input_phrase):
        hcm_variants = {
            'HCM': 'Hồ Chí Minh',
            'TPHCM': 'Hồ Chí Minh',
            'HồChíMinh': 'Hồ Chí Minh',
            'Thành PhôHôChíMinh': 'Hồ Chí Minh',
            'H.C.Minh': 'Hồ Chí Minh',
            'H C M': 'Hồ Chí Minh',
            'H.C.M': 'Hồ Chí Minh',
            'TP.HCM': 'Hồ Chí Minh',
            'T.P.H.C.M': 'Hồ Chí Minh'
        }

        # Thay thế các từ viết tắt trong input_phrase
        for key, value in hcm_variants.items():
            input_phrase = re.sub(r'\b' + re.escape(key) + r'\b', value, input_phrase, flags=re.IGNORECASE)

        return input_phrase

    def handle_ward_number_case(self, input_phrase):
        """
        Xử lý riêng cho Ward, nhận diện và trích xuất phường có số (vd. P13, Q7), và tiếp tục xử lý phần còn lại.
        """
        # Chuẩn hóa các từ viết tắt của Hồ Chí Minh
        input_phrase = self.normalize_ho_chi_minh(input_phrase)

        # Nếu không phải là Hồ Chí Minh thì bỏ qua
        if "Hồ Chí Minh" in input_phrase:
            return None

        ward = None
        district = None
        province = None

        ward_match = re.search(r'\b(?:Phường|P|F|P.|F.|phường|p|f)\s*(\d+)', input_phrase)
        if ward_match:
            ward = ward_match.group(1)
            input_phrase = input_phrase.replace(ward_match.group(0), "").strip()

        # Chuẩn hóa lại chuỗi cho phần còn lại
        input_phrase = re.sub(
            r"Xã|xã|Phường|phường|Quận|quận|Huyện|huyện|Thành phố|Thành Phố|thành phố|TP|Tp|tp|f|F|T.P|T.p", " ",
            input_phrase).strip()
        input_phrase = re.sub(r"[!@#$%^&*()_=+{},.\/?<>:;`~|-]", " ", input_phrase).strip()
        input_phrase = re.sub(r"\d+", "", input_phrase).strip()
        input_phrase = re.sub(r"\s+", " ", input_phrase).strip()
        input_phrase = self.capitalize_first_letter(input_phrase)

        # Tiếp tục tìm kiếm thông thường với phần còn lại của Hồ Chí Minh
        result = self.query_standard(input_phrase)  # Giả định query_standard là hàm xử lý chuẩn

        if ward:
            result["ward"] = ward

        return result

    # Hàm xử lý riêng cho Hồ Chí Minh với trường hợp quận/phường có số
    def handle_ho_chi_minh_case(self, input_phrase):
        """
        Xử lý riêng cho Hồ Chí Minh, nhận diện và trích xuất quận/phường có số (vd. P13, Q7), và tiếp tục xử lý phần còn lại.
        """
        # Chuẩn hóa các từ viết tắt của Hồ Chí Minh
        input_phrase = self.normalize_ho_chi_minh(input_phrase)

        # Nếu không phải là Hồ Chí Minh thì bỏ qua
        if "Hồ Chí Minh" not in input_phrase:
            return None

        # Kiểm tra có số phường/quận không
        ward = None
        district = None

        # Pattern cho phường (P/F + số)
        ward_match = re.search(r'\b(?:Phường|P|F|P.|F.)\s*(\d+)', input_phrase)
        if ward_match:
            ward = ward_match.group(1)  # Lấy số phường
            input_phrase = input_phrase.replace(ward_match.group(0), "").strip()  # Xóa khỏi chuỗi

        # Pattern cho quận (Q/Quận + số)
        district_match = re.search(r'\b(?:Quận|Q|quận|Q.)\s*(\d+)', input_phrase)
        if district_match:
            district = district_match.group(1)  # Lấy số quận
            input_phrase = input_phrase.replace(district_match.group(0), "").strip()  # Xóa khỏi chuỗi

        # Chuẩn hóa lại chuỗi cho phần còn lại
        input_phrase = re.sub(
            r"Xã|xã|Phường|phường|Quận|quận|Huyện|huyện|Thành phố|Thành Phố|thành phố|TP|Tp|tp|f|F|T.P|T.p", " ",
            input_phrase).strip()
        input_phrase = re.sub(r"[!@#$%^&*()_=+{},.\/?<>:;`~|-]", " ", input_phrase).strip()
        input_phrase = re.sub(r"\d+", "", input_phrase).strip()
        input_phrase = re.sub(r"\s+", " ", input_phrase).strip()
        input_phrase = self.capitalize_first_letter(input_phrase)

        # Tiếp tục tìm kiếm thông thường với phần còn lại của Hồ Chí Minh
        result = self.query_standard(input_phrase)  # Giả định query_standard là hàm xử lý chuẩn

        # Thêm thông tin về Hồ Chí Minh và kết quả phường/quận nếu có
        result["province"] = "Hồ Chí Minh"
        if district:
            result["district"] = district
        if ward:
            result["ward"] = ward

        return result

    def run_with_timeout(func, *args, timeout=0.1):
        with Manager() as manager:
            result = manager.dict()

            rep = {
                "province": '',
                "district": '',
                "ward": ''
            }

            def worker():
                result['value'] = func(*args)

            p = Process(target=worker)
            p.start()
            p.join(timeout=timeout)

            if p.is_alive():
                p.terminate()
                p.join()
                return rep

            return result.get('value', rep)

    def process_second(self, input_phrase):
        """
        Hàm chính để gọi xử lý địa chỉ ngoài Hồ Chí Minh
        """
        # Kiểm tra và gọi xử lý riêng cho Hồ Chí Minh nếu có
        hcm_result = self.handle_ho_chi_minh_case(input_phrase)
        if hcm_result:
            return hcm_result

        # Kiểm tra và gọi xử lý riêng cho "Bà Rịa - Vũng Tàu"
        brvt_result = self.handle_ba_ria_vung_tau_case(input_phrase)
        if brvt_result:
            return brvt_result

        # Xử lý các tỉnh/thành khác như bình thường nếu không phải Hồ Chí Minh
        return self.handle_ward_number_case(input_phrase)

    def process(self, input_phrase):
        """
        Hàm chính
        """
        # result = self.run_with_timeout(self.process_second, input_phrase, timeout=0.1)
        #
        # print(result)

        return self.process_second(input_phrase)

    def query_standard(self, input_phrase):

        # district_number_data =''
        ward_number_data = ''

        # Pattern cho phường (P/F + số)
        ward_match = re.search(r'\b(?:Phường|P|F|P.|F.)\s*(\d+)', input_phrase)
        if ward_match:
            ward = ward_match.group(1)  # Lấy số phường
            ward_number_data = ward
            input_phrase = input_phrase.replace(ward_match.group(0), "").strip()  # Xóa khỏi chuỗi

        input_phrase = re.sub(
            r"Huyện|huyện|Tỉnh|Thị xã|Thị Xã|Phường|phường|Thị trấn|Thị Trấn|Xã|xã|Quận|quận|Thành phố|Thành Phố|TP|Tnh|Tp|tp|F|f|Tỉn|tỉnh|T.p|T.P|Thủ đô|Huzyen|XK",
            " ", input_phrase).strip()
        input_phrase = re.sub(r"[!@#$%^&*()_=+{},.\/?<>:;`~|-]", " ", input_phrase).strip()
        input_phrase = re.sub(r"\d+", "", input_phrase).strip()
        input_phrase = re.sub(r"\s+", " ", input_phrase).strip()
        input_phrase = self.capitalize_first_letter(input_phrase)

        dict_ghitat = {
            'HN': 'Hà Nội',
            'H N': 'Hà Nội',
            'TPHN': 'Hà Nội',
            'HNội': 'Hà Nội',
            'HàNội': 'Hà Nội',
            'HàNoi': 'Hà Nội',
            'Phan Rang': 'Phan Rang-Tháp Chàm',
            'Thanh Hoá': 'Thanh Hóa',
            'HaNam': 'Hà Nam',
            'Khánh Hoà': 'Khánh Hòa',
            'Tin GJiang': 'Tiền Giang',
            'T Giang': 'Tiền Giang',
            'Quảyg Nm': 'Quảng Nam',
            'T T H': 'Thừa Thiên Huế',
            'Thừa T Huế': 'Thừa Thiên Huế',
            'TTH': 'Thừa Thiên Huế',
            'Hanh Hóa': 'Thanh Hóa',
            'Minh Thượng': 'U Minh Thượng',
            'HaOi Dương': 'Hải Dương',
            'H Nam': 'Hà Nam',
            'Hú Hoa': 'Phú Hoà',
            'Phú Hòa': 'Phú Hoà',
            'Tuy Hòa': 'Tuy Hoà',
            'TQdung Trị': 'Quảng Trị',
            'Khabnh Hòa': 'Khánh Hòa',
            'Biên Hoà': 'Biên Hòa',
            'Chiêm Hoá': 'Chiêm Hóa',
            'Hoằng Hoá': 'Hoằng Hóa',
            'HHiệp Ha': 'Hiệp Hòa',
            'Đức Hoà': 'Đức Hòa',
            'Hiệp Hoà': 'Hiệp Hòa',
            'Đông Hoà': 'Đông Hòa',
            'Ứng Hoà': 'Ứng Hòa',
            'Sơn Hoà': 'Sơn Hòa',
            'Hòa Quý': 'Hoà Quý',
            'Vĩnh Hoà': 'Vĩnh Hòa',
            'Hoà Cường Nam': 'Hòa Cường Nam',
            'Minh Hoà': 'Minh Hòa',
            'Đức Hoà': 'Đức Hòa',
            'Thái Hoà': 'Thái Hòa',
            'Thanh Hoà': 'Thanh Hòa',
            'Bích Hoà': 'Bích Hòa',
            'Hoà Thọ Đông': 'Hòa Thọ Đông',
            'Hoà Thạnh': 'Hòa Thạnh',
            'Hoà Bắc': 'Hòa Bắc',
            'Cộng Hoà': 'Cộng Hòa',
            'Hoà Lợi': 'Hòa Lợi',
            'Lương Hoà': 'Lương Hòa',
            'Hoà Trị': 'Hòa Trị',
            'Cộng Hoà': 'Cộng Hòa',
            'Thái Hoà': 'Thái Hòa',
            'Tân Hoà': 'Tân Hòa',
            'ĐồGg Van': 'Đồng Văn'
        }

        for key, value in dict_ghitat.items():
            input_phrase = re.sub(r'\b' + re.escape(key) + r'\b', value, input_phrase)

        found_phrases1 = self.provinces_trie.search_phrase(input_phrase)
        if len(found_phrases1) == 1:
            province_name = found_phrases1[0]["FullName"]
            input_phrase = input_phrase.replace(province_name, " ")

        found_phrases2 = self.districts_trie.search_phrase(input_phrase)
        if len(found_phrases2) == 1:
            district_name = found_phrases2[0]["FullName"]
            input_phrase = input_phrase.replace(district_name, " ")

        found_phrases3 = self.wards_trie.search_phrase(input_phrase)
        if len(found_phrases3) == 1:
            ward_name = found_phrases3[0]["FullName"]
            input_phrase = input_phrase.replace(ward_name, " ")

        provinces_data = []
        districts_data = []
        wards_data = []

        match len(found_phrases1):
            case 0:  # Không có thành phố
                districts_data, wards_data = self.Districts_0(found_phrases2, found_phrases3)

                # if(ward_number_data!=''):wards_data.append(ward_number_data)
                # print(f'Test Ward Data:  {wards_data}')
                result = self.ref(provinces_data, districts_data, wards_data)
                return result

            case 1:  # Có 1 thành phố
                provinces_data = found_phrases1[0]
                districts_data, wards_data = self.Districts_1(found_phrases2, found_phrases3, provinces_data)
                if wards_data:
                    # print(f'Test Ward Data:  {wards_data}')
                    if wards_data["FullName"] == provinces_data["FullName"]:
                        wards_data = []

                # if(ward_number_data!=''):wards_data.append(ward_number_data)
                result = self.ref(provinces_data, districts_data, wards_data)
                return result

            case _:  # Có nhiều thành phố, tìm quận rồi tìm ngược lên thành phố
                districts_data, wards_data = self.Districts_0(found_phrases2, found_phrases3)
                # if (district_number_data!=''):districts_data.append(district_number_data)
                if districts_data:
                    for data in found_phrases1:
                        if data["Code"] == districts_data["ProvinceCode"]:
                            districts_data = data
                            if (ward_number_data != ''): wards_data.append(ward_number_data)
                            result = self.ref(provinces_data, districts_data, wards_data)
                else:
                    provinces_data = found_phrases1[-1]  # Không có quận thì lấy cái cuối cùng trong list
                    districts_data, wards_data = self.Districts_1(found_phrases2, found_phrases3, provinces_data)
                    if wards_data:
                        # print(f'Test Ward Data:  {wards_data}')
                        if wards_data["FullName"] == provinces_data["FullName"]:
                            wards_data = []
                    result = self.ref(provinces_data, districts_data, wards_data)
                    return result

        return result

    # Không có thành phố -> tìm quận
    def Districts_0(self, found_phrases2, found_phrases3):
        districts_data = []
        wards_data = []

        match len(found_phrases2):
            case 1:
                districts_data = found_phrases2[0]
                wards_data = self.Wards_1(found_phrases3, districts_data)
                return districts_data, wards_data

            case 0:
                wards_data = self.Wards_0(found_phrases3)
                return districts_data, wards_data

            case _:
                wards_data = self.Wards_0(found_phrases3)
                if wards_data:
                    for data in found_phrases2:
                        if data["Code"] == wards_data["DistrictCode"] and data["FullName"] != wards_data["FullName"]:
                            districts_data = data
                            return districts_data, wards_data

        return districts_data, wards_data

    # Tìm được thành phố -> tìm quận
    def Districts_1(self, found_phrases2, found_phrases3, provinces_data):
        districts_data = []
        wards_data = []

        match len(found_phrases2):
            case 0:
                wards_data = self.Wards_0(found_phrases3)
                return districts_data, wards_data

            case 1:
                districts_data = found_phrases2[0]
                wards_data = self.Wards_1(found_phrases3, districts_data)
                return districts_data, wards_data

            case _:
                for data in found_phrases2:
                    if data["ProvinceCode"] == provinces_data["Code"]:
                        districts_data = data
                        wards_data = self.Wards_1(found_phrases3, districts_data)
                        return districts_data, wards_data

        return districts_data, wards_data

    # Không có quận
    def Wards_0(self, found_phrases3):
        wards_data = []

        match len(found_phrases3):
            case 0:
                return wards_data

            case _:
                wards_data = found_phrases3[0]
                return wards_data

        return wards_data

    # Tìm được quận -> tìm phường
    def Wards_1(self, found_phrases3, districts_data):
        wards_data = []

        match len(found_phrases3):
            case 0:
                return wards_data

            case 1:
                if found_phrases3[0]["FullName"] != districts_data["FullName"]:
                    wards_data = found_phrases3[0]
                return wards_data

            case _:
                for data in found_phrases3:
                    if data["DistrictCode"] == districts_data["Code"] and data["FullName"] != districts_data[
                        "FullName"]:
                        wards_data = data
                        return wards_data

        return wards_data

    def ref(self, provinces_data, districts_data, wards_data):
        province = ""
        district = ""
        ward = ""

        if provinces_data:
            found_phrases1 = self.province_cp.search_cp(provinces_data["FullName"])
            if found_phrases1:
                province = provinces_data["FullName"]

        if districts_data:
            found_phrases2 = self.district_cp.search_cp(districts_data["FullName"])
            if found_phrases2:
                district = districts_data["FullName"]

        if wards_data:
            found_phrases3 = self.ward_cp.search_cp(wards_data["FullName"])
            if found_phrases3:
                ward = wards_data["FullName"]

        result = {
            "province": province,
            "district": district,
            "ward": ward
        }

        return result

# Function to download the file from Google Drive (use an alternative method if gdown is not available)
def download_from_google_drive(url, filename):
    if os.path.exists(filename):
        os.remove(filename)
    try:
        response = requests.get(url)
        with open(filename, 'wb') as f:
            f.write(response.content)
        print(f"Downloaded '{filename}' successfully.")
    except Exception as e:
        print(f"An error occurred while downloading the file: {e}")


# NOTE: DO NOT change this cell
# This cell is for scoring
def test():

    # URL to download the file (make sure it's a direct link)
    url = "https://drive.google.com/uc?export=download&id=1PBt3U9I3EH885CDhcXspebyKI5Vw6uLB"
    download_from_google_drive(url, "test.json")

    TEAM_NAME = 'Optimal_updated_17'  # This should be your team name
    EXCEL_FILE = f'{TEAM_NAME}.xlsx'

    with open('test.json', encoding="utf8") as f:
        data = json.load(f)

    summary_only = True
    df = []
    solution = Solution()
    timer = []
    correct = 0
    for test_idx, data_point in enumerate(data):
        address = data_point["text"]

        ok = 0
        try:
            start = time.perf_counter_ns()
            result = solution.process(address)
            answer = data_point["result"]
            finish = time.perf_counter_ns()
            timer.append(finish - start)

            if answer["province"] != result["province"] or answer["district"] != result["district"] or answer["ward"] != \
                    result["ward"]:
                print(f"=====\n{address}")
                print(f"{answer}")
                print(f"{result}")

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
            print(f"Test {test_idx:5d}/{len(data):5d}")
            print(f"Correct: {ok}/3")
            print(f"Time Executed: {timer[-1] / 1_000_000_000:.4f}")


    print(f"-"*30)
    total = len(data) * 3
    score_scale_10 = round(correct / total * 10, 2)
    if len(timer) == 0:
        timer = [0]
    max_time_sec = round(max(timer) / 1_000_000_000, 4)
    avg_time_sec = round((sum(timer) / len(timer)) / 1_000_000_000, 4)

    import pandas as pd

    df2 = pd.DataFrame(
        [[correct, total, score_scale_10, max_time_sec, avg_time_sec]],
        columns=['correct', 'total', 'score / 10', 'max_time_sec', 'avg_time_sec',],
    )

    print(df2)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    test()

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
