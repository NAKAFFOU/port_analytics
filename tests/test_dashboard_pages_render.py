"""Renders the full Streamlit app (streamlit.testing.v1.AppTest) once per
exposed page and asserts no exception was raised — the "rendu sans
exception des 6 pages" check from the data-integrity/6-page restructuring.
"""

from streamlit.testing.v1 import AppTest

from src.db.seed_demo import seed_demo
from src.pipeline.runner import run_analytical_pipeline
from src.dashboard.i18n import TEXT

PAGE_KEYS = ["executive", "services", "revenue", "charges", "trend_result", "trend_charges"]


def _seed() -> None:
    seed_demo(granularity="annual")
    run_analytical_pipeline()


def test_exactly_six_pages_are_exposed():
    for language in ("en", "fr"):
        pages = TEXT[language]["pages"]
        assert set(pages.keys()) == set(PAGE_KEYS)


def test_all_six_pages_render_without_exception():
    _seed()
    for page_key in PAGE_KEYS:
        at = AppTest.from_file("src/dashboard/app.py", default_timeout=60)
        at.run()
        assert not at.exception, f"initial run raised for default page: {at.exception}"

        page_label = TEXT["en"]["pages"][page_key]
        page_radio = at.sidebar.radio[1]
        assert page_label in page_radio.options
        page_radio.set_value(page_label).run()
        assert not at.exception, f"{page_key} raised: {at.exception}"
