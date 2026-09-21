from __future__ import annotations

import unittest

from eval_metrics import EvalCase, score_case


class EvalMetricsTest(unittest.TestCase):
    def test_scores_source_pages_answer_points_relations_and_anomaly(self) -> None:
        case = EvalCase(
            id="q1",
            question="造成右岸深層滑動的主要因果鏈是什麼？",
            expected_answer_points=["累積雨量", "地下水位上升", "剪力強度下降"],
            expected_source_pages=[1, 2],
            expected_relation_labels=["causes"],
            expected_anomaly=None,
        )
        response = {
            "answer": "累積雨量增加後，地下水位上升，並使剪力強度下降。",
            "retrieved_chunks": [
                {"source_page": 2, "text": "地下水位上升", "score": 0.9},
                {"source_page": 9, "text": "其他資料", "score": 0.7},
            ],
            "graph_data": {
                "edges": [
                    {"label": "causes"},
                    {"label": "supports"},
                ],
            },
            "anomalies": [],
        }

        score = score_case(case, response)

        self.assertEqual(score["source_page_hit"], 1.0)
        self.assertEqual(score["source_page_recall"], 0.5)
        self.assertEqual(score["answer_point_coverage"], 1.0)
        self.assertEqual(score["relation_hit"], 1.0)
        self.assertEqual(score["anomaly_match"], 1.0)

    def test_flags_missing_expected_anomaly(self) -> None:
        case = EvalCase(
            id="ood",
            question="股票價格多少？",
            expected_anomaly="out_of_domain",
        )

        score = score_case(case, {"answer": "", "retrieved_chunks": [], "anomalies": []})

        self.assertEqual(score["anomaly_match"], 0.0)

    def test_answer_points_normalize_common_units_and_spacing(self) -> None:
        case = EvalCase(
            id="rainfall",
            question="雨量是多少？",
            expected_answer_points=["57.5 mm", "6/2 09:00", "6/3 04:00"],
        )

        score = score_case(case, {
            "answer": "累積雨量為57.5毫米，集中於6月2日09點至6月3日04點。",
            "retrieved_chunks": [],
            "anomalies": [],
        })

        self.assertEqual(score["answer_point_coverage"], 1.0)


if __name__ == "__main__":
    unittest.main()
