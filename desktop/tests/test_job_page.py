from plotdas_client.models import Job
from plotdas_client.ui.job_page import JobPage


def test_job_page_renders_real_job_list_shape(qtbot):
    page = JobPage(lambda _password: [], lambda: "")
    qtbot.addWidget(page)
    job = Job.from_dict(
        {
            "job_id": "job_20260905T214745_24b99027",
            "project": "xinjing",
            "status": "running",
            "completed": 5540,
            "total": 19371,
            "failed": 4,
            "pid": 122827,
            "created_at": "2026-09-05T21:47:45+08:00",
            "current_window": {"start": "2023-03-05T21:31:00+08:00"},
        }
    )

    page._show_jobs([job])

    assert page.table.item(0, 0).text() == "job_20260905T214745_24b99027"
    assert page.table.item(0, 2).text() == "运行中"
    assert page.table.cellWidget(0, 3).value() == 5540
    assert "1 个运行中" in page.status.text()
