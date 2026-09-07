from PySide6.QtCore import Qt

from plotdas_client.ui.metadata_widget import MetadataWidget


def _tree_text(widget: MetadataWidget) -> list[tuple[str, str]]:
    result = []

    def visit(item) -> None:
        result.append((item.text(0), item.text(1)))
        for index in range(item.childCount()):
            visit(item.child(index))

    for index in range(widget.topLevelItemCount()):
        visit(widget.topLevelItem(index))
    return result


def test_metadata_is_grouped_and_human_readable(qtbot):
    widget = MetadataWidget()
    qtbot.addWidget(widget)
    widget.set_metadata(
        {
            "project": "xinjing",
            "status": "success",
            "requested_start_time": "2026-09-06T10:00:00",
            "requested_end_time": "2026-09-06T10:01:30",
            "sampling_rate": 500,
            "sample_count": 45000,
            "filter_type": "bandpass",
            "source_files": ["/data/a.h5", "/data/b.h5"],
            "image_path": "/output/xinjing/a.png",
        }
    )

    text = _tree_text(widget)
    assert ("状态", "成功") in text
    assert ("采样率", "500 Hz") in text
    assert ("采样点数", "45,000") in text
    assert ("滤波类型", "带通滤波") in text
    assert ("请求开始时间", "2026-09-06 10:00:00") in text
    assert ("持续时间", "1 分 30 秒") in text
    assert ("图片文件", "/output/xinjing/a.png") in text
    assert ("第 1 项", "/data/a.h5") in text
    assert {"基本信息", "数据范围", "处理参数", "文件与版本"}.issubset({label for label, _ in text})


def test_nested_and_unknown_metadata_remain_visible(qtbot):
    widget = MetadataWidget()
    qtbot.addWidget(widget)
    widget.set_metadata({"custom_block": {"foo_bar": True}})

    text = _tree_text(widget)
    assert ("其他信息", "") in text
    assert ("Custom Block", "") in text
    assert ("Foo Bar", "是") in text


def test_metadata_sections_can_be_selected(qtbot):
    widget = MetadataWidget()
    qtbot.addWidget(widget)
    widget.set_visible_sections(["基本信息"])
    widget.set_metadata({"project": "xinjing", "sampling_rate": 500, "custom": "value"})

    text = _tree_text(widget)
    assert ("项目", "xinjing") in text
    assert ("采样率", "500 Hz") not in text
    assert ("Custom", "value") not in text


def test_long_values_are_not_elided_and_receive_wrapped_height(qtbot):
    widget = MetadataWidget()
    qtbot.addWidget(widget)
    long_path = "/cluster/datapool4/liaoxl/" + "very-long-directory/" * 8 + "data.h5"
    widget.resize(360, 400)
    widget.set_metadata({"source_file": long_path})
    widget.show()
    qtbot.waitExposed(widget)

    section = widget.topLevelItem(0)
    item = section.child(0)
    index = widget.indexFromItem(item, 1)
    hint = widget.sizeHintForIndex(index)

    assert widget.textElideMode() == Qt.TextElideMode.ElideNone
    assert item.text(1) == long_path
    assert hint.height() > widget.fontMetrics().height()
