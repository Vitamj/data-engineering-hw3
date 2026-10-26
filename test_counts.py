import io
import json
import unittest

from counts import chunks, map_chunk


class CountTests(unittest.TestCase):
    def test_chunk_boundaries_do_not_split_or_drop_records(self):
        records = [b'{"a":1}', b'{"long_name":"\xd0\xbf\xd1\x80\xd0\xb8\xd0\xb2\xd0\xb5\xd1\x82"}', b'{"a":3}']
        source = io.BytesIO(b"\n".join(records) + b"\n")
        self.assertEqual([row for batch in chunks(source, size=7) for row in batch], records)

    def test_mapper_deduplicates_skills_and_filters_variant(self):
        rows = [
            {"name": "Go-разработчик", "skills": ["SQL", " sql ", "Docker", "Go"], "currency": "RUR", "salary_from": 100},
            {"name": "Java-разработчик", "skills": ["SQL"], "currency": "RUR", "salary_from": 100},
        ]
        result, meta = map_chunk([json.dumps(row).encode() for row in rows])
        self.assertEqual(meta, {"vacancies": 1, "with_skills": 1, "rub_salary": 1})
        self.assertEqual(sum(result[0].values()), 3)
        self.assertEqual(sum(result[1].values()), 3)
        self.assertEqual(sum(result[2].values()), 1)

    def test_invalid_json_does_not_produce_partial_success(self):
        with self.assertRaises(json.JSONDecodeError):
            map_chunk([b'{"name":"Go developer","skills":["go"]}', b'{broken'])


if __name__ == "__main__":
    unittest.main()
