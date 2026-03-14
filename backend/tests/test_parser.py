from __future__ import annotations

from pathlib import Path

import backend.parser as parser_module
from backend.parser import extract_status_details, is_noise, parse_pdf, parse_text_pages


def test_extract_status_details_variants() -> None:
    government = "Status: Government Home University : Mumbai University"
    unaided_minority = (
        "Status: Un-Aided Autonomous Religious Minority - Muslim "
        "Home University : Autonomous Institute"
    )

    assert extract_status_details(government) == ("Government", "General", "Mumbai University")
    assert extract_status_details(unaided_minority) == (
        "Private (Unaided)",
        "Religious (Muslim)",
        "Autonomous Institute",
    )


def test_is_noise_skips_page_headers_and_numbers() -> None:
    assert is_noise("Government of Maharashtra")
    assert is_noise("2")
    assert not is_noise("06006 - College of Engineering Pune, Pune")


def test_parse_text_pages_handles_page_breaks_stage_split_and_ignored_categories() -> None:
    pages = [
        "\n".join(
            [
                "Cut Off List for Maharashtra & Minority Seats of CAP Round I 2025-26",
                "Government of Maharashtra",
                "06006 - College of Engineering Pune, Pune",
                "0600624210 - Computer Science and Engineering",
                "Status: Government Home University : Savitribai Phule Pune University",
                "State Level",
                "GOPENS GOBCS LOPENS",
                "9196 16679 25163",
                "(97.3737374) (95.2100000) (92.6700000)",
                "Stage",
            ]
        ),
        "\n".join(
            [
                "I",
                "TFWS EWS PWDROBCS ORPHAN",
                "7401 13724 45678",
                "(97.8600000) (96.0600000) (84.1000000)",
            ]
        ),
    ]

    result = parse_text_pages(pages, source_name="CAP_Round_I_2025-26.pdf")

    assert result.round_label == "CAP Round I"
    assert result.academic_year == "2025-26"
    assert result.output_filename == "MHT_CET_CAP_Round_I_Cutoffs_2025-26.xlsx"
    assert result.colleges_found == 1
    assert result.branches_found == 1
    assert result.ignored_categories == ["PWDROBCS"]

    row = result.rows[0]
    assert row.college_code == "06006"
    assert row.city == "Pune"
    assert row.district == "Pune"
    assert row.college_type == "Government"
    assert row.home_university == "Savitribai Phule Pune University"
    assert row.data["GOPENS"]["rank"] == 9196
    assert row.data["GOPENS"]["pct"] == 97.3737374
    assert row.data["TFWS"]["rank"] == 7401
    assert row.data["EWS"]["pct"] == 96.06
    assert "ORPHAN" not in row.data


def test_parse_text_pages_handles_realistic_stage_header_and_wrapped_category() -> None:
    pages = [
        "\n".join(
            [
                "Cut Off List for Maharashtra & Minority Seats of CAP Round I 2025-26",
                "01002 - Government College of Engineering, Amravati",
                "0100224210 - Computer Science and Engineering",
                "Status: Government Autonomous Home University : Autonomous Institute",
                "State Level",
                "Stage GOPENS GSCS TFWS PWDROBC EWS",
                "                      S",
                "I 9196 18016 7401 93506 13724",
                "(97.3737374) (94.7837750) (97.8664807) (70.2033567) (96.0638523)",
            ]
        )
    ]

    result = parse_text_pages(pages, source_name="CAP_Round_I_2025-26.pdf")

    row = result.rows[0]
    assert row.data["GOPENS"]["rank"] == 9196
    assert row.data["GSCS"]["pct"] == 94.7837750
    assert row.data["TFWS"]["rank"] == 7401
    assert row.data["EWS"]["pct"] == 96.0638523
    assert result.ignored_categories == ["PWDROBCS"]


def test_parse_text_pages_accepts_iterators() -> None:
    pages = iter(
        [
            "\n".join(
                [
                    "Cut Off List for Maharashtra & Minority Seats of CAP Round I 2025-26",
                    "01002 - Government College of Engineering, Amravati",
                    "0100224210 - Computer Science and Engineering",
                    "Status: Government Home University : SGBAU",
                    "State Level",
                    "GOPENS",
                    "9196",
                    "(97.3737374)",
                ]
            )
        ]
    )

    result = parse_text_pages(pages, source_name="CAP_Round_I_2025-26.pdf")

    assert result.rows_found == 1
    assert result.rows[0].data["GOPENS"]["rank"] == 9196


def test_parse_pdf_streams_page_extraction(monkeypatch) -> None:
    sequence: list[str] = []
    page_text = "\n".join(
        [
            "Cut Off List for Maharashtra & Minority Seats of CAP Round I 2025-26",
            "01002 - Government College of Engineering, Amravati",
            "0100224210 - Computer Science and Engineering",
            "Status: Government Home University : SGBAU",
            "State Level",
            "GOPENS",
            "9196",
            "(97.3737374)",
        ]
    )

    class FakePage:
        def __init__(self, index: int) -> None:
            self.index = index

        def extract_text(self, layout=True, x_tolerance=1, y_tolerance=3):  # noqa: ANN001
            sequence.append(f"extract-{self.index}")
            return page_text

    class FakePdf:
        def __init__(self) -> None:
            self.pages = [FakePage(index) for index in range(1, 6)]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

    monkeypatch.setattr(parser_module.pdfplumber, "open", lambda _: FakePdf())

    progress_events: list[int] = []
    result = parse_pdf(
        Path("fake.pdf"),
        progress_callback=lambda event: (
            progress_events.append(event["pages_processed"]),
            sequence.append(f"progress-{event['pages_processed']}"),
        ),
        source_name="CAP_Round_I_2025-26.pdf",
    )

    assert result.rows_found == 5
    assert progress_events == [1, 2, 3, 4, 5]
    assert sequence.index("progress-1") < sequence.index("extract-4")
    assert sequence.index("progress-3") < sequence.index("extract-4")
    assert sequence.index("extract-4") < sequence.index("progress-4")
    assert sequence.index("extract-5") < sequence.index("progress-5")
