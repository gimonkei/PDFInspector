import fitz


class PDFDocumentError(Exception):
    """PDF操作に失敗したときの基底例外。"""


class PDFOpenError(PDFDocumentError):
    """PDFを開けなかったときの例外。"""


class PDFPasswordRequiredError(PDFOpenError):
    """パスワード保護されたPDFを開いたときの例外。"""


class PDFSaveError(PDFDocumentError):
    """PDFを保存できなかったときの例外。"""


class PDFDocument:

    def __init__(self):
        self.doc = None
        self.path = ""

    def open(self, path):
        try:
            document = fitz.open(path)
        except Exception as error:
            raise PDFOpenError(
                "PDFを開けませんでした。\n"
                "ファイルが破損しているか、PDF形式ではない可能性があります。"
            ) from error

        if document.needs_pass:
            document.close()
            raise PDFPasswordRequiredError(
                "このPDFはパスワードで保護されています。\n"
                "現在のバージョンではパスワード付きPDFを開けません。"
            )

        self.close()
        self.doc = document
        self.path = path

    def close(self):
        if self.doc:
            self.doc.close()

        self.doc = None
        self.path = ""

    def has_document(self):
        return self.doc is not None

    def save(self):
        if self.doc is None:
            raise PDFSaveError("保存するPDFが開かれていません。")

        if not self.path:
            raise PDFSaveError("保存先が設定されていません。")

        try:
            self.doc.save(
                self.path,
                incremental=True,
                encryption=fitz.PDF_ENCRYPT_KEEP
            )
        except Exception as error:
            raise PDFSaveError(
                "PDFを上書き保存できませんでした。\n"
                "ファイルが別のアプリで使用中か、書き込み権限がない可能性があります。"
            ) from error

    def save_as(self, path):
        if self.doc is None:
            raise PDFSaveError("保存するPDFが開かれていません。")

        try:
            self.doc.save(path)
        except Exception as error:
            raise PDFSaveError(
                "PDFを保存できませんでした。\n"
                "保存先の書き込み権限や空き容量を確認してください。"
            ) from error

        self.path = path

    @property
    def page_count(self):
        if self.doc is None:
            return 0

        return len(self.doc)

    def get_page(self, index):
        if self.doc is None:
            return None

        if index < 0 or index >= len(self.doc):
            return None

        return self.doc.load_page(index)

    def get_all_pages(self):
        if self.doc is None:
            return []

        return [
            self.doc.load_page(i)
            for i in range(len(self.doc))
        ]

    @staticmethod
    def _display_point_to_pdf(page, x, y):
        point = fitz.Point(float(x), float(y))
        if page.rotation:
            point = point * page.derotation_matrix
        return point

    def add_checkmark(self, page_index, x, y, size=15.0, color="#dc0000", line_width=2.2):
        page = self.get_page(page_index)
        if page is None:
            return None

        size = max(float(size), 6.0)
        display_points = [
            (x - size * 0.48, y),
            (x - size * 0.12, y + size * 0.38),
            (x + size * 0.55, y - size * 0.48),
        ]
        points = []
        for px, py in display_points:
            point = self._display_point_to_pdf(page, px, py)
            points.append((float(point.x), float(point.y)))

        rgb = self._parse_annotation_color(color, fallback=(0.86, 0.0, 0.0))
        annot = page.add_ink_annot([points])
        annot.set_colors(stroke=rgb)
        annot.set_border(width=max(float(line_width), 0.5))
        annot.set_info(
            title="PDFInspector",
            subject="チェック",
            content="チェック",
        )
        annot.update()
        return annot

    def add_freetext_comment(
        self,
        page_index,
        x,
        y,
        text,
        font_size=11.0,
    ):
        page = self.get_page(page_index)
        if page is None:
            return None

        content = str(text).strip()
        if not content:
            return None

        point = self._display_point_to_pdf(page, x, y)
        lines = content.splitlines() or [content]
        longest = max(len(line) for line in lines)
        width = max(90.0, longest * float(font_size) * 0.72 + 14.0)
        height = max(24.0, len(lines) * float(font_size) * 1.55 + 10.0)
        rect = fitz.Rect(
            point.x,
            point.y,
            point.x + width,
            point.y + height,
        )
        annot = page.add_freetext_annot(
            rect,
            content,
            fontsize=float(font_size),
            fontname="helv",
            text_color=(1.0, 0.0, 0.0),
            fill_color=None,
            border_color=None,
            align=0,
        )
        annot.set_info(
            title="PDFInspector",
            subject="コメント",
            content=content,
        )
        annot.update()
        return annot

    def add_date_stamp(
        self,
        page_index,
        x,
        y,
        top,
        date_text,
        bottom,
        color="black",
        size=72.0,
        line_width=1.5,
    ):
        page = self.get_page(page_index)
        if page is None:
            return

        center = self._display_point_to_pdf(page, x, y)
        size = max(float(size), 42.0)
        radius = size / 2.0
        rgb = {
            "black": (0.0, 0.0, 0.0),
            "blue": (0.0, 0.27, 0.86),
            "red": (0.86, 0.0, 0.0),
        }.get(color, (0.0, 0.0, 0.0))

        shape = page.new_shape()
        shape.draw_circle(center, radius)
        y1 = center.y - radius + size * 0.34
        y2 = center.y - radius + size * 0.66
        shape.draw_line((center.x - radius, y1), (center.x + radius, y1))
        shape.draw_line((center.x - radius, y2), (center.x + radius, y2))
        shape.finish(color=rgb, width=max(float(line_width), 0.5))
        shape.commit()

        font_size = max(6.0, size * 0.13)
        text_rects = [
            fitz.Rect(center.x - radius, center.y - radius, center.x + radius, y1),
            fitz.Rect(center.x - radius, y1, center.x + radius, y2),
            fitz.Rect(center.x - radius, y2, center.x + radius, center.y + radius),
        ]
        values = [str(top), str(date_text), str(bottom)]
        for rect, value in zip(text_rects, values):
            try:
                page.insert_textbox(
                    rect,
                    value,
                    fontsize=font_size,
                    fontname="japan",
                    color=rgb,
                    align=fitz.TEXT_ALIGN_CENTER,
                )
            except Exception:
                page.insert_textbox(
                    rect,
                    value,
                    fontsize=font_size,
                    fontname="helv",
                    color=rgb,
                    align=fitz.TEXT_ALIGN_CENTER,
                )


    def add_arrow(
        self,
        page_index,
        start_x,
        start_y,
        end_x,
        end_y,
        color="red",
        line_width=2.0,
    ):
        """Write a standard PDF line annotation with an arrow tip."""
        page = self.get_page(page_index)
        if page is None:
            return None

        start = self._display_point_to_pdf(page, start_x, start_y)
        end = self._display_point_to_pdf(page, end_x, end_y)
        rgb = self._parse_annotation_color(color, fallback=(0.86, 0.0, 0.0))

        annot = page.add_line_annot(start, end)
        annot.set_colors(stroke=rgb)
        annot.set_border(width=max(float(line_width), 0.5))

        try:
            annot.set_line_ends(
                fitz.PDF_ANNOT_LE_NONE,
                fitz.PDF_ANNOT_LE_OPEN_ARROW,
            )
        except Exception:
            # Older PyMuPDF builds may not expose line-end constants. The
            # line annotation remains valid and visible without this option.
            pass

        annot.set_info(
            title="PDFInspector",
            subject="矢印",
            content="矢印",
        )
        annot.update()
        return annot

    @staticmethod
    def _parse_annotation_color(value, fallback=(0.86, 0.0, 0.0)):
        named = {
            "black": (0.0, 0.0, 0.0),
            "blue": (0.0, 0.27, 0.86),
            "red": (0.86, 0.0, 0.0),
            "yellow": (1.0, 1.0, 0.0),
            "green": (0.0, 0.65, 0.0),
            "white": (1.0, 1.0, 1.0),
        }
        text = str(value).strip().lower()
        if text in named:
            return named[text]
        if text.startswith("#") and len(text) == 7:
            try:
                return (
                    int(text[1:3], 16) / 255.0,
                    int(text[3:5], 16) / 255.0,
                    int(text[5:7], 16) / 255.0,
                )
            except ValueError:
                pass
        return fallback

    def add_shape(
        self,
        shape_type,
        page_index,
        x,
        y,
        width,
        height,
        color="red",
        line_width=2.0,
        text="",
        font_size=11.0,
        text_color="#000000",
        fill_enabled=False,
        fill_opacity=0.25,
        fill_color="#ffff00",
    ):
        """Write a standard PDF square or circle annotation."""
        page = self.get_page(page_index)
        if page is None:
            return None

        top_left = self._display_point_to_pdf(page, x, y)
        bottom_right = self._display_point_to_pdf(
            page,
            x + width,
            y + height,
        )
        rect = fitz.Rect(top_left, bottom_right).normalize()
        rgb = self._parse_annotation_color(color, fallback=(0.86, 0.0, 0.0))

        fill_rgb = self._parse_annotation_color(
            fill_color,
            fallback=rgb,
        )

        if bool(fill_enabled):
            if shape_type == "ellipse":
                fill_annot = page.add_circle_annot(rect)
            else:
                fill_annot = page.add_rect_annot(rect)
            fill_annot.set_colors(fill=fill_rgb)
            fill_annot.set_border(width=0)
            fill_annot.set_opacity(
                min(max(float(fill_opacity), 0.0), 1.0)
            )
            fill_annot.set_info(
                title="PDFInspector",
                subject="図形塗りつぶし",
                content="図形塗りつぶし",
            )
            fill_annot.update()

        if shape_type == "ellipse":
            annot = page.add_circle_annot(rect)
            subject = "円・楕円"
        else:
            annot = page.add_rect_annot(rect)
            subject = "矩形"

        annot.set_colors(stroke=rgb)
        annot.set_border(width=max(float(line_width), 0.5))
        annot.set_info(
            title="PDFInspector",
            subject=subject,
            content=subject,
        )
        annot.update()

        content = str(text).strip()
        if content:
            text_rgb = self._parse_annotation_color(
                text_color,
                fallback=rgb,
            )
            self._add_shape_freetext(
                page,
                rect,
                content,
                text_rgb,
                font_size,
            )

        return annot


    def _add_shape_freetext(
        self,
        page,
        rect,
        text,
        text_rgb,
        font_size,
    ):
        margin = max(float(font_size) * 0.35, 4.0)
        text_rect = fitz.Rect(
            rect.x0 + margin,
            rect.y0 + margin,
            rect.x1 - margin,
            rect.y1 - margin,
        )
        if text_rect.width <= 1.0 or text_rect.height <= 1.0:
            return None
        annot = page.add_freetext_annot(
            text_rect,
            str(text),
            fontsize=max(float(font_size), 4.0),
            fontname="helv",
            text_color=text_rgb,
            fill_color=None,
            border_color=None,
            align=1,
        )
        annot.set_info(
            title="PDFInspector",
            subject="図形内テキスト",
            content=str(text),
        )
        annot.update()
        return annot

    def add_cloud(
        self,
        page_index,
        x,
        y,
        width,
        height,
        color="red",
        line_width=2.0,
        cloud_radius=8.0,
        text="",
        font_size=11.0,
        text_color="#000000",
        fill_enabled=False,
        fill_opacity=0.25,
        fill_color="#ffff00",
    ):
        """Write a cloud border as a standard PDF ink annotation."""
        page = self.get_page(page_index)
        if page is None:
            return None

        width = max(float(width), 8.0)
        height = max(float(height), 8.0)
        radius = max(
            4.0,
            min(float(cloud_radius), min(width, height) / 4.0),
        )

        left = float(x)
        top = float(y)
        right = left + width
        bottom = top + height
        center_x = (left + right) * 0.5
        center_y = (top + bottom) * 0.5

        def edge_points(start, end):
            dx = end[0] - start[0]
            dy = end[1] - start[1]
            length = max((dx * dx + dy * dy) ** 0.5, 0.001)
            count = max(1, int(round(length / (radius * 1.55))))
            return [
                (
                    start[0] + dx * index / count,
                    start[1] + dy * index / count,
                )
                for index in range(count + 1)
            ]

        points = (
            edge_points((left, top), (right, top))
            + edge_points((right, top), (right, bottom))[1:]
            + edge_points((right, bottom), (left, bottom))[1:]
            + edge_points((left, bottom), (left, top))[1:]
        )

        sampled = []
        subdivisions = 5

        for index, current in enumerate(points):
            following = points[(index + 1) % len(points)]
            midpoint_x = (current[0] + following[0]) * 0.5
            midpoint_y = (current[1] + following[1]) * 0.5
            vx = midpoint_x - center_x
            vy = midpoint_y - center_y
            distance = max((vx * vx + vy * vy) ** 0.5, 0.001)
            control_x = midpoint_x + vx / distance * radius * 0.62
            control_y = midpoint_y + vy / distance * radius * 0.62

            for step in range(subdivisions):
                t = step / subdivisions
                inv = 1.0 - t
                px = (
                    inv * inv * current[0]
                    + 2.0 * inv * t * control_x
                    + t * t * following[0]
                )
                py = (
                    inv * inv * current[1]
                    + 2.0 * inv * t * control_y
                    + t * t * following[1]
                )
                point = self._display_point_to_pdf(page, px, py)
                sampled.append((float(point.x), float(point.y)))

        if sampled:
            sampled.append(sampled[0])

        rgb = self._parse_annotation_color(color, fallback=(0.86, 0.0, 0.0))

        fill_rgb = self._parse_annotation_color(
            fill_color,
            fallback=rgb,
        )

        if bool(fill_enabled) and sampled:
            fill_annot = page.add_polygon_annot(sampled[:-1])
            fill_annot.set_colors(fill=fill_rgb)
            fill_annot.set_border(width=0)
            fill_annot.set_opacity(
                min(max(float(fill_opacity), 0.0), 1.0)
            )
            fill_annot.set_info(
                title="PDFInspector",
                subject="クラウド塗りつぶし",
                content="クラウド塗りつぶし",
            )
            fill_annot.update()

        annot = page.add_ink_annot([sampled])
        annot.set_colors(stroke=rgb)
        annot.set_border(width=max(float(line_width), 0.5))
        annot.set_info(
            title="PDFInspector",
            subject="クラウド",
            content="クラウド",
        )
        annot.update()

        content = str(text).strip()
        if content:
            top_left = self._display_point_to_pdf(page, x, y)
            bottom_right = self._display_point_to_pdf(page, x + width, y + height)
            rect = fitz.Rect(top_left, bottom_right).normalize()
            text_rgb = self._parse_annotation_color(
                text_color,
                fallback=rgb,
            )
            self._add_shape_freetext(
                page,
                rect,
                content,
                text_rgb,
                font_size,
            )

        return annot

    def rotate_page(self, index, angle):
        if self.doc is None:
            return

        if index < 0 or index >= len(self.doc):
            return

        page = self.doc.load_page(index)
        current = page.rotation
        page.set_rotation((current + angle) % 360)

    def rotate_all_pages(self, angle):
        if self.doc is None:
            return

        for i in range(len(self.doc)):
            self.rotate_page(i, angle)
