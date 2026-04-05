import unittest

from PySide6.QtWidgets import QApplication, QLineEdit, QScrollArea, QVBoxLayout, QWidget

from render_helpers import PageElementBuilder


class _DummyHost(QWidget, PageElementBuilder):
    def __init__(self):
        super().__init__()
        self.scroll = QScrollArea()
        self.page = QWidget()
        self.page_layout = QVBoxLayout(self.page)
        self.page_layout.setContentsMargins(0, 0, 0, 0)
        self.settings = {"images_enabled": True}
        self.engine = None
        self.address = QLineEdit()
        self.current_url = "about:blank"
        self._reset_layout_stack()

    def open_link(self, url: str):
        self.current_url = url

    def _set_status(self, message: str, timeout_ms: int = 0):
        return None


class RenderHelpersLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_block_uses_layout_box_model_before_qss(self):
        host = _DummyHost()

        host.begin_block(
            "div",
            css={
                "margin-left": "3px",
                "margin-top": "13px",
                "padding-left": "5px",
                "padding-top": "7px",
                "padding-right": "9px",
                "padding-bottom": "11px",
                "background-color": "#fff",
            },
        )

        wrapper = host.page_layout.itemAt(0).widget()
        self.assertEqual(wrapper.layout().contentsMargins().left(), 3)
        self.assertEqual(wrapper.layout().contentsMargins().top(), 13)

        container = wrapper.layout().itemAt(0).widget()
        margins = container.layout().contentsMargins()
        self.assertEqual((margins.left(), margins.top(), margins.right(), margins.bottom()), (5, 7, 9, 11))
        self.assertNotIn("margin-left", container.styleSheet())
        self.assertNotIn("padding-left", container.styleSheet())
        self.assertIn("background-color", container.styleSheet())

    def test_inline_text_margin_is_wrapped_not_styled(self):
        host = _DummyHost()

        host.add_text(
            "hello",
            base_style={
                "margin-left": "4px",
                "margin-top": "6px",
                "color": "red",
            },
        )

        line_widget = host.page_layout.itemAt(0).widget()
        wrapper = line_widget.layout().itemAt(0).widget()
        label = wrapper.layout().itemAt(0).widget()

        margins = wrapper.layout().contentsMargins()
        self.assertEqual((margins.left(), margins.top()), (4, 6))
        self.assertNotIn("margin-left", label.styleSheet())
        self.assertNotIn("margin-top", label.styleSheet())
        self.assertIn("color: red;", label.styleSheet())
        self.assertTrue(line_widget.layout().hasHeightForWidth())

    def test_table_row_uses_horizontal_layout_for_cells(self):
        host = _DummyHost()

        host.begin_block("table", css={"display": "table"})
        host.begin_block("tr", css={"display": "table-row"})
        host.begin_block("td", css={"display": "table-cell"})
        host.add_text("Alpha")
        host.end_block("td")
        host.begin_block("td", css={"display": "table-cell"})
        host.add_text("Beta")
        host.end_block("td")
        host.end_block("tr")
        host.end_block("table")

        table_container = host.page_layout.itemAt(0).widget()
        row_container = table_container.layout().itemAt(0).widget()
        row_layout = row_container.layout()

        self.assertEqual(row_layout.count(), 2)
        self.assertEqual(row_layout.itemAt(0).widget().property("tag"), "td")
        self.assertEqual(row_layout.itemAt(1).widget().property("tag"), "td")
