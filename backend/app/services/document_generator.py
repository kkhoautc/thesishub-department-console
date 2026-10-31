import io
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
import openpyxl
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from django.utils import timezone
from app.models import (
    DefenseCouncil,
    CouncilMember,
    GraduationProject,
    FinalGradeSummary,
    CouncilLiveScore,
    AcademicBatch,
    CourseClass,
    Student
)

class DocumentGenerationService:

    @staticmethod
    def generate_to_trinh_docx(council_id):
        """
        Sinh file Word .docx Tờ trình thành lập Hội đồng chấm đồ án tốt nghiệp
        theo thể thức văn bản hành chính chuẩn của Trường ĐH Giao thông Vận tải (UTC).
        """
        council = DefenseCouncil.objects.select_related('batch').get(id=council_id)
        members = list(
            CouncilMember.objects.filter(council=council)
            .select_related('user', 'supervisor')
            .order_by('id')
        )

        doc = Document()

        for section in doc.sections:
            section.top_margin = Inches(0.8)
            section.bottom_margin = Inches(0.8)
            section.left_margin = Inches(1.0)
            section.right_margin = Inches(0.8)

        # Header Table
        header_table = doc.add_table(rows=1, cols=2)
        header_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        header_table.autofit = False

        cell_left = header_table.cell(0, 0)
        cell_right = header_table.cell(0, 1)
        cell_left.width = Inches(3.2)
        cell_right.width = Inches(3.8)

        p_left = cell_left.paragraphs[0]
        p_left.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_l1 = p_left.add_run("TRƯỜNG ĐẠI HỌC GIAO THÔNG VẬN TẢI\n")
        run_l1.font.name = "Times New Roman"
        run_l1.font.size = Pt(11)
        run_l1.font.bold = True
        run_l2 = p_left.add_run("KHOA CÔNG NGHỆ THÔNG TIN\n")
        run_l2.font.name = "Times New Roman"
        run_l2.font.size = Pt(11)
        run_l2.font.bold = True
        run_l3 = p_left.add_run("--------------------")
        run_l3.font.name = "Times New Roman"
        run_l3.font.size = Pt(9)

        p_right = cell_right.paragraphs[0]
        p_right.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_r1 = p_right.add_run("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\n")
        run_r1.font.name = "Times New Roman"
        run_r1.font.size = Pt(11)
        run_r1.font.bold = True
        run_r2 = p_right.add_run("Độc lập – Tự do – Hạnh phúc\n")
        run_r2.font.name = "Times New Roman"
        run_r2.font.size = Pt(12)
        run_r2.font.bold = True
        run_r3 = p_right.add_run("--------------------")
        run_r3.font.name = "Times New Roman"
        run_r3.font.size = Pt(9)

        today = timezone.now()
        p_date = doc.add_paragraph()
        p_date.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run_d = p_date.add_run(f"Hà Nội, ngày {today.day:02d} tháng {today.month:02d} năm {today.year}\n")
        run_d.font.name = "Times New Roman"
        run_d.font.size = Pt(12)
        run_d.font.italic = True

        p_title = doc.add_paragraph()
        p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_t1 = p_title.add_run("TỜ TRÌNH\n")
        run_t1.font.name = "Times New Roman"
        run_t1.font.size = Pt(14)
        run_t1.font.bold = True
        run_t2 = p_title.add_run(f"V/v: Thành lập hội đồng chấm đồ án tốt nghiệp {council.council_name}\n")
        run_t2.font.name = "Times New Roman"
        run_t2.font.size = Pt(12)
        run_t2.font.bold = True

        p_kinhgui = doc.add_paragraph()
        p_kinhgui.paragraph_format.left_indent = Inches(0.5)
        run_kg = p_kinhgui.add_run("Kính gửi:   - Ban Giám hiệu\n                 - Phòng Đào tạo Đại học\n                 - Khoa Đào tạo quốc tế\n")
        run_kg.font.name = "Times New Roman"
        run_kg.font.size = Pt(12)
        run_kg.font.bold = True

        p_body = doc.add_paragraph()
        p_body.paragraph_format.first_line_indent = Inches(0.5)
        run_b1 = p_body.add_run(
            f"Căn cứ vào kế hoạch đào tạo năm học của Trường ĐH GTVT và tiến độ thực hiện đồ án tốt nghiệp đợt {council.batch.batch_name}, "
            f"Khoa Công nghệ Thông tin kính đề nghị Nhà trường cho phép thành lập Hội đồng chấm đồ án tốt nghiệp ({council.council_name}) "
            f"dành cho sinh viên hệ chính quy.\n\n"
            f"Đề xuất danh sách thành viên Hội đồng chấm đồ án tốt nghiệp (mô hình 1 Chủ tịch - 2 Thư ký - 2 Ủy viên) gồm các Thầy/Cô sau:\n"
        )
        run_b1.font.name = "Times New Roman"
        run_b1.font.size = Pt(12)

        table = doc.add_table(rows=1, cols=4)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        hdr_cells = table.rows[0].cells
        headers = ["STT", "Họ và tên", "Đơn vị công tác / Bộ môn", "Trách nhiệm trong HĐ"]

        for i, text in enumerate(headers):
            hdr_cells[i].text = text
            hdr_cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            for r in hdr_cells[i].paragraphs[0].runs:
                r.font.name = "Times New Roman"
                r.font.size = Pt(11)
                r.font.bold = True

        for idx, m in enumerate(members, start=1):
            row_cells = table.add_row().cells
            title = m.supervisor.academic_title if (m.supervisor and m.supervisor.academic_title) else ""
            full_name = f"{title} {m.user.get_full_name()}".strip()
            unit = m.external_institution if m.role == "EXTERNAL_MEMBER" and m.external_institution else (m.supervisor.department_name if m.supervisor else "Khoa CNTT")
            
            row_cells[0].text = str(idx)
            row_cells[1].text = full_name
            row_cells[2].text = unit or "Bộ môn CNTT"
            row_cells[3].text = m.get_role_display()

            for c in row_cells:
                for r in c.paragraphs[0].runs:
                    r.font.name = "Times New Roman"
                    r.font.size = Pt(11)

        p_end = doc.add_paragraph()
        p_end.paragraph_format.first_line_indent = Inches(0.5)
        run_e = p_end.add_run(
            f"\nThời gian bảo vệ: Ngày {council.session_date.strftime('%d/%m/%Y') if council.session_date else '...'} ({council.get_session_time_display()})\n"
            f"Địa điểm: {council.defense_room or 'Phòng bảo vệ Khoa CNTT'}\n\n"
            f"Kính mong Ban Giám hiệu xem xét và phê duyệt./."
        )
        run_e.font.name = "Times New Roman"
        run_e.font.size = Pt(12)

        sig_table = doc.add_table(rows=1, cols=2)
        sig_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        c_left = sig_table.cell(0, 0)
        c_right = sig_table.cell(0, 1)

        p_s_left = c_left.paragraphs[0]
        p_s_left.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_sl = p_s_left.add_run("PHÒNG ĐÀO TẠO ĐẠI HỌC\n\n\n\n\n(Ký và ghi rõ họ tên)")
        r_sl.font.name = "Times New Roman"
        r_sl.font.size = Pt(12)
        r_sl.font.bold = True

        p_s_right = c_right.paragraphs[0]
        p_s_right.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_sr = p_s_right.add_run("TRƯỞNG KHOA CNTT\n\n\n\n\nTS. Hoàng Văn Thông")
        r_sr.font.name = "Times New Roman"
        r_sr.font.size = Pt(12)
        r_sr.font.bold = True

        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer

    @staticmethod
    def generate_outline_docx(project_id):
        """
        Giai đoạn 3 (Bước 23): Sinh Phiếu giao đề tài & Đề cương đồ án tốt nghiệp chuẩn UTC.
        """
        proj = GraduationProject.objects.select_related(
            'student__user', 'student__course_class', 'supervisor__user', 'batch'
        ).get(id=project_id)

        doc = Document()
        for section in doc.sections:
            section.top_margin = Inches(0.8)
            section.bottom_margin = Inches(0.8)
            section.left_margin = Inches(1.0)
            section.right_margin = Inches(0.8)

        # Header
        header_table = doc.add_table(rows=1, cols=2)
        header_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        c_left = header_table.cell(0, 0)
        c_right = header_table.cell(0, 1)

        p_l = c_left.paragraphs[0]
        p_l.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_l1 = p_l.add_run("TRƯỜNG ĐẠI HỌC GTVT\nKHOA CÔNG NGHỆ THÔNG TIN\n----------------")
        r_l1.font.bold = True
        r_l1.font.name = "Times New Roman"

        p_r = c_right.paragraphs[0]
        p_r.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_r1 = p_r.add_run("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\nĐộc lập – Tự do – Hạnh phúc\n----------------")
        r_r1.font.bold = True
        r_r1.font.name = "Times New Roman"

        p_title = doc.add_paragraph()
        p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_t = p_title.add_run("\nPHIẾU GIAO ĐỀ TÀI ĐỒ ÁN TỐT NGHIỆP\n")
        r_t.font.name = "Times New Roman"
        r_t.font.size = Pt(15)
        r_t.font.bold = True

        student = proj.student
        sup = proj.supervisor
        p_info = doc.add_paragraph()
        p_info.paragraph_format.first_line_indent = Inches(0.3)
        runs_data = [
            f"1. Họ và tên sinh viên: {student.user.get_full_name()}\n",
            f"   Mã số sinh viên: {student.registration_no}       Lớp: {student.course_class.class_name if student.course_class else ''}\n",
            f"   Chương trình đào tạo: {student.get_education_program_display()}\n",
            f"2. Giảng viên hướng dẫn: {sup.academic_title or ''} {sup.user.get_full_name()} ({sup.department_name or 'Khoa CNTT'})\n",
            f"3. Tên đề tài tốt nghiệp:\n",
            f"   - Tên tiếng Việt: {proj.topic_title_vi}\n",
            f"   - Tên tiếng Anh: {proj.topic_title_en or '(Đang cập nhật)'}\n",
            f"4. Trạng thái phê duyệt: KHOA ĐÃ PHÊ DUYỆT (Approved)\n",
            f"5. Nhiệm vụ và yêu cầu của đề tài:\n",
            f"   - Nghiên cứu khảo sát bài toán thực tế và xây dựng kiến trúc hệ thống.\n",
            f"   - Lập trình cài đặt thử nghiệm, kiểm thử tính năng hoàn thiện.\n",
            f"   - Soạn thảo báo cáo đề cương và thuyết minh đồ án theo đúng quy chuẩn học vụ UTC.\n",
            f"6. Ngày giao nhiệm vụ: {proj.created_at.strftime('%d/%m/%Y')}\n"
        ]
        for line in runs_data:
            r = p_info.add_run(line)
            r.font.name = "Times New Roman"
            r.font.size = Pt(12)

        # Signatures
        sig_table = doc.add_table(rows=1, cols=3)
        sig_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        for idx, (role, title) in enumerate([("SINH VIÊN", "Ký và ghi rõ họ tên"), ("GIẢNG VIÊN HƯỚNG DẪN", "Ký và ghi rõ họ tên"), ("TRƯỞNG BỘ MÔN", "Ký và ghi rõ họ tên")]):
            cell = sig_table.cell(0, idx)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r1 = p.add_run(f"{role}\n\n\n\n\n{title}")
            r1.font.bold = True
            r1.font.name = "Times New Roman"
            r1.font.size = Pt(11)

        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer

    @staticmethod
    def generate_bien_ban_excel(council_id):
        """
        Sinh file Excel Biên bản chấm điểm Hội đồng bảo vệ đồ án tốt nghiệp.
        """
        council = DefenseCouncil.objects.select_related('batch').get(id=council_id)
        projects = list(
            GraduationProject.objects.filter(council=council)
            .select_related('student__user', 'supervisor__user', 'reviewer__user')
            .order_by('student__registration_no')
        )

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"Hội đồng {council.council_number}"

        # Font & Styles
        font_title = Font(name="Times New Roman", size=14, bold=True)
        font_header = Font(name="Times New Roman", size=11, bold=True, color="FFFFFF")
        font_data = Font(name="Times New Roman", size=11)
        fill_header = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_left = Alignment(horizontal="left", vertical="center")
        thin_border = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='thin', color='CBD5E1')
        )

        # Title
        ws.merge_cells("A1:N1")
        cell_t1 = ws["A1"]
        cell_t1.value = f"TRƯỜNG ĐẠI HỌC GIAO THÔNG VẬN TẢI - KHOA CÔNG NGHỆ THÔNG TIN"
        cell_t1.font = Font(name="Times New Roman", size=11, bold=True)
        cell_t1.alignment = align_center

        ws.merge_cells("A2:N2")
        cell_t2 = ws["A2"]
        cell_t2.value = f"BIÊN BẢN CHẤM ĐIỂM BẢO VỆ ĐỒ ÁN TỐT NGHIỆP - {council.council_name.upper()}"
        cell_t2.font = font_title
        cell_t2.alignment = align_center

        headers = [
            ("STT", 6),
            ("MSSV", 14),
            ("Họ và Tên", 22),
            ("Lớp / Ngành", 14),
            ("Tên đề tài tốt nghiệp", 38),
            ("GV Hướng Dẫn", 20),
            ("GV Phản Biện", 20),
            ("Điểm GVHD", 12),
            ("Điểm GVPB", 12),
            ("Điểm HĐ (TB)", 14),
            ("Điểm Hệ 10", 12),
            ("Điểm Hệ 4", 12),
            ("Điểm Chữ", 11),
            ("Kết luận", 13)
        ]

        row_idx = 5
        for col_idx, (hdr_text, col_width) in enumerate(headers, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=hdr_text)
            cell.font = font_header
            cell.fill = fill_header
            cell.alignment = align_center
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = col_width

        for stt, proj in enumerate(projects, start=1):
            row_idx += 1
            student = proj.student
            user = student.user
            full_name = user.get_full_name()
            sup_name = proj.supervisor.user.get_full_name() if proj.supervisor else ""
            rev_name = proj.reviewer.user.get_full_name() if proj.reviewer else ""

            summary = getattr(proj, 'final_grade_summary', None)
            if not summary:
                summary, _ = FinalGradeSummary.objects.get_or_create(project=proj)
                summary.supervisor_score = proj.supervisor_score
                summary.reviewer_score = proj.reviewer_score
                scores = list(CouncilLiveScore.objects.filter(project=proj))
                if scores:
                    summary.council_avg_score = round(sum(s.total_score for s in scores) / len(scores), 2)
                summary.calculate_and_save()

            row_data = [
                stt,
                student.registration_no,
                full_name,
                student.department or "CNTT",
                proj.topic_title_vi,
                sup_name,
                rev_name,
                summary.supervisor_score if summary.supervisor_score is not None else "",
                summary.reviewer_score if summary.reviewer_score is not None else "",
                summary.council_avg_score if summary.council_avg_score is not None else "",
                summary.final_score_10 if summary.final_score_10 is not None else "",
                summary.final_score_4 if summary.final_score_4 is not None else "",
                summary.final_letter_grade or "",
                "Đạt" if summary.is_passed else "Không đạt"
            ]

            for c_idx, val in enumerate(row_data, start=1):
                c = ws.cell(row=row_idx, column=c_idx, value=val)
                c.font = font_data
                c.border = thin_border
                if c_idx in [1, 2, 8, 9, 10, 11, 12, 13, 14]:
                    c.alignment = align_center
                elif c_idx in [3, 4, 5, 6, 7]:
                    c.alignment = align_left

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer

    @staticmethod
    def generate_final_summary_excel(batch_id):
        """
        Giai đoạn 6 (Bước 45): Xuất dữ liệu cuối kỳ (ký).
        Bao gồm toàn bộ đề tài, điểm số và danh sách sinh viên BẢO LƯU đồ án.
        """
        batch = AcademicBatch.objects.get(id=batch_id)
        projects = list(
            GraduationProject.objects.filter(batch=batch)
            .select_related('student__user', 'supervisor__user', 'final_grade_summary')
            .order_by('student__registration_no')
        )

        wb = openpyxl.Workbook()
        ws_all = wb.active
        ws_all.title = "Tổng kết cuối kỳ"

        # Sheet 1: Tất cả sinh viên
        ws_all.cell(row=1, column=1, value=f"BÁO CÁO DỮ LIỆU TỔNG KẾT ĐỒ ÁN TỐT NGHIỆP - {batch.batch_name.upper()}").font = Font(name="Times New Roman", size=14, bold=True)
        headers = ["STT", "MSSV", "Họ và tên", "Chương trình", "Tên đề tài", "GVHD", "Điểm TK (Hệ 10)", "Điểm Hệ 4", "Điểm Chữ", "Kết luận", "Ghi chú / Bảo lưu"]

        for idx, h in enumerate(headers, start=1):
            c = ws_all.cell(row=3, column=idx, value=h)
            c.font = Font(name="Times New Roman", size=11, bold=True, color="FFFFFF")
            c.fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
            c.alignment = Alignment(horizontal="center", vertical="center")
            ws_all.column_dimensions[get_column_letter(idx)].width = 20

        ws_all.column_dimensions["E"].width = 35
        ws_all.column_dimensions["K"].width = 25

        row_idx = 3
        for stt, proj in enumerate(projects, start=1):
            row_idx += 1
            std = proj.student
            summary = getattr(proj, 'final_grade_summary', None)
            is_deferred = (proj.deferral_status == "APPROVED")
            
            verdict = "Bảo lưu" if is_deferred else ("Đạt" if (summary and summary.is_passed) else "Không đạt")
            note = f"Đơn bảo lưu: {proj.deferral_reason}" if is_deferred else (proj.ineligibility_reason or "")

            row_data = [
                stt,
                std.registration_no,
                std.user.get_full_name(),
                std.get_education_program_display(),
                proj.topic_title_vi,
                proj.supervisor.user.get_full_name() if proj.supervisor else "",
                summary.final_score_10 if (summary and not is_deferred) else "",
                summary.final_score_4 if (summary and not is_deferred) else "",
                summary.final_letter_grade if (summary and not is_deferred) else "",
                verdict,
                note
            ]

            for c_idx, val in enumerate(row_data, start=1):
                c = ws_all.cell(row=row_idx, column=c_idx, value=val)
                c.font = Font(name="Times New Roman", size=11)
                if is_deferred:
                    c.fill = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
                if c_idx in [1, 2, 4, 7, 8, 9, 10]:
                    c.alignment = Alignment(horizontal="center", vertical="center")

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer

    @staticmethod
    def generate_class_grades_excel(batch_id, course_class_id=None):
        """
        Chức năng cuối kỳ cho Giáo vụ:
        Xuất danh sách điểm đồ án tốt nghiệp chi tiết theo từng lớp (CourseClass).
        Nếu có course_class_id: xuất file cho lớp đó.
        Nếu không có: xuất file có nhiều sheet (mỗi sheet 1 lớp) + 1 sheet tổng hợp toàn đợt.
        """
        batch = AcademicBatch.objects.get(id=batch_id)

        if course_class_id:
            classes = list(CourseClass.objects.filter(id=course_class_id, batch=batch))
        else:
            classes = list(CourseClass.objects.filter(batch=batch).order_by("class_code"))

        wb = openpyxl.Workbook()
        # Remove default sheet
        wb.remove(wb.active)

        font_univ = Font(name="Times New Roman", size=11, bold=True)
        font_title = Font(name="Times New Roman", size=13, bold=True)
        font_subtitle = Font(name="Times New Roman", size=11, italic=True)
        font_header = Font(name="Times New Roman", size=10, bold=True, color="FFFFFF")
        font_data = Font(name="Times New Roman", size=10)
        font_bold = Font(name="Times New Roman", size=10, bold=True)
        fill_header = PatternFill(start_color="003366", end_color="003366", fill_type="solid")
        fill_deferred = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
        fill_failed = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
        fill_passed = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")

        align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_left = Alignment(horizontal="left", vertical="center")
        align_right = Alignment(horizontal="right", vertical="center")
        thin_border = Border(
            left=Side(style="thin", color="CBD5E1"),
            right=Side(style="thin", color="CBD5E1"),
            top=Side(style="thin", color="CBD5E1"),
            bottom=Side(style="thin", color="CBD5E1")
        )

        headers = [
            ("STT", 6),
            ("Mã SV", 13),
            ("Họ và Tên", 22),
            ("Hệ ĐT", 12),
            ("Tên đề tài tốt nghiệp", 38),
            ("GV Hướng Dẫn", 20),
            ("GV Phản Biện", 20),
            ("Hội Đồng", 14),
            ("Điểm GVHD", 11),
            ("Điểm GVPB", 11),
            ("Điểm HĐ", 11),
            ("Điểm Hệ 10", 11),
            ("Điểm Hệ 4", 10),
            ("Điểm Chữ", 10),
            ("Xếp loại", 14),
            ("Kết luận", 12),
            ("Ghi chú", 22)
        ]

        def render_sheet_content(ws, title_text, subtitle_text, projects_list):
            # Banner
            ws.merge_cells("A1:G1")
            c_u1 = ws["A1"]
            c_u1.value = "TRƯỜNG ĐẠI HỌC GIAO THÔNG VẬN TẢI\nKHOA CÔNG NGHỆ THÔNG TIN"
            c_u1.font = font_univ
            c_u1.alignment = align_center

            ws.merge_cells("H1:Q1")
            c_u2 = ws["H1"]
            c_u2.value = "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\nĐộc lập - Tự do - Hạnh phúc"
            c_u2.font = font_univ
            c_u2.alignment = align_center

            # Title
            ws.merge_cells("A3:Q3")
            c_t = ws["A3"]
            c_t.value = title_text
            c_t.font = font_title
            c_t.alignment = align_center

            ws.merge_cells("A4:Q4")
            c_sub = ws["A4"]
            c_sub.value = subtitle_text
            c_sub.font = font_subtitle
            c_sub.alignment = align_center

            # Header Row
            row_idx = 6
            for col_idx, (hdr_text, col_w) in enumerate(headers, start=1):
                cell = ws.cell(row=row_idx, column=col_idx, value=hdr_text)
                cell.font = font_header
                cell.fill = fill_header
                cell.alignment = align_center
                col_letter = get_column_letter(col_idx)
                ws.column_dimensions[col_letter].width = col_w

            passed_count = 0
            failed_count = 0
            deferred_count = 0
            scores_10_list = []

            for stt, proj in enumerate(projects_list, start=1):
                row_idx += 1
                std = proj.student
                user = std.user
                full_name = user.get_full_name() or user.username
                sup_name = proj.supervisor.user.get_full_name() if proj.supervisor else ""
                rev_name = proj.reviewer.user.get_full_name() if proj.reviewer else ""
                council_name = proj.council.council_name if proj.council else ""

                summary = getattr(proj, "final_grade_summary", None)
                if not summary and (proj.supervisor_score is not None or proj.reviewer_score is not None):
                    summary, _ = FinalGradeSummary.objects.get_or_create(project=proj)
                    summary.supervisor_score = proj.supervisor_score
                    summary.reviewer_score = proj.reviewer_score
                    scores = list(CouncilLiveScore.objects.filter(project=proj))
                    if scores:
                        summary.council_avg_score = round(sum(s.total_score for s in scores) / len(scores), 2)
                    summary.calculate_and_save()

                is_deferred = (proj.deferral_status == "APPROVED")
                if is_deferred:
                    deferred_count += 1
                    verdict = "Bảo lưu"
                    note = f"Đơn bảo lưu: {proj.deferral_reason or 'Đã duyệt'}"
                elif summary and summary.is_passed:
                    passed_count += 1
                    verdict = "Đạt"
                    note = proj.ineligibility_reason or ""
                    if summary.final_score_10 is not None:
                        scores_10_list.append(summary.final_score_10)
                else:
                    failed_count += 1
                    verdict = "Không đạt"
                    note = proj.ineligibility_reason or ""
                    if summary and summary.final_score_10 is not None:
                        scores_10_list.append(summary.final_score_10)

                row_data = [
                    stt,
                    std.registration_no,
                    full_name,
                    std.get_education_program_display(),
                    proj.topic_title_vi,
                    sup_name,
                    rev_name,
                    council_name,
                    summary.supervisor_score if summary and summary.supervisor_score is not None else "",
                    summary.reviewer_score if summary and summary.reviewer_score is not None else "",
                    summary.council_avg_score if summary and summary.council_avg_score is not None else "",
                    summary.final_score_10 if (summary and not is_deferred and summary.final_score_10 is not None) else "",
                    summary.final_score_4 if (summary and not is_deferred and summary.final_score_4 is not None) else "",
                    summary.final_letter_grade if (summary and not is_deferred) else "",
                    summary.classification if (summary and not is_deferred) else "",
                    verdict,
                    note
                ]

                for c_idx, val in enumerate(row_data, start=1):
                    c = ws.cell(row=row_idx, column=c_idx, value=val)
                    c.font = font_data
                    c.border = thin_border
                    if is_deferred:
                        c.fill = fill_deferred
                    elif verdict == "Đạt":
                        if c_idx in [12, 13, 14, 16]:
                            c.fill = fill_passed
                    elif verdict == "Không đạt":
                        if c_idx in [12, 13, 14, 16]:
                            c.fill = fill_failed

                    if c_idx in [1, 2, 4, 8, 9, 10, 11, 12, 13, 14, 15, 16]:
                        c.alignment = align_center
                    elif c_idx in [3, 5, 6, 7, 17]:
                        c.alignment = align_left

            # Summary stats block
            total_students = len(projects_list)
            avg_score = round(sum(scores_10_list) / len(scores_10_list), 2) if scores_10_list else 0.0
            pass_rate = round((passed_count / total_students) * 100, 1) if total_students > 0 else 0.0

            row_idx += 2
            ws.merge_cells(f"A{row_idx}:Q{row_idx}")
            c_stat = ws[f"A{row_idx}"]
            c_stat.value = (
                f"THỐNG KÊ: Tổng số: {total_students} sinh viên | "
                f"Đạt: {passed_count} ({pass_rate}%) | "
                f"Không đạt: {failed_count} | "
                f"Bảo lưu: {deferred_count} | "
                f"Điểm TB khóa/lớp: {avg_score} / 10"
            )
            c_stat.font = font_bold
            c_stat.alignment = align_left

            # Signatures block
            row_idx += 2
            today = timezone.now()
            ws.merge_cells(f"M{row_idx}:Q{row_idx}")
            c_date = ws[f"M{row_idx}"]
            c_date.value = f"Hà Nội, ngày {today.day} tháng {today.month} năm {today.year}"
            c_date.font = font_subtitle
            c_date.alignment = align_center

            row_idx += 1
            ws.merge_cells(f"B{row_idx}:E{row_idx}")
            c_s1 = ws[f"B{row_idx}"]
            c_s1.value = "NGƯỜI LẬP BẢNG\n(Giáo vụ Khoa CNTT)\n\n\n\n\n(Ký và ghi rõ họ tên)"
            c_s1.font = font_bold
            c_s1.alignment = align_center

            ws.merge_cells(f"G{row_idx}:J{row_idx}")
            c_s2 = ws[f"G{row_idx}"]
            c_s2.value = "TRƯỞNG BỘ MÔN\n\n\n\n\n\n(Ký và ghi rõ họ tên)"
            c_s2.font = font_bold
            c_s2.alignment = align_center

            ws.merge_cells(f"L{row_idx}:P{row_idx}")
            c_s3 = ws[f"L{row_idx}"]
            c_s3.value = "TRƯỞNG KHOA CÔNG NGHỆ THÔNG TIN\n\n\n\n\n\n(Ký và ghi rõ họ tên)"
            c_s3.font = font_bold
            c_s3.alignment = align_center

        # If specific class or multiple classes:
        if course_class_id and classes:
            target_cls = classes[0]
            ws = wb.create_sheet(title=f"Lớp {target_cls.class_code[:25]}")
            projs = list(
                GraduationProject.objects.filter(batch=batch, student__course_class=target_cls)
                .select_related("student__user", "supervisor__user", "reviewer__user", "council", "final_grade_summary")
                .order_by("student__registration_no")
            )
            title = f"BẢNG TỔNG HỢP ĐIỂM ĐỒ ÁN TỐT NGHIỆP - LỚP {target_cls.class_code.upper()}"
            sub = f"Đợt: {batch.batch_name} | Lớp: {target_cls.class_name} | Chương trình: {target_cls.get_program_type_display()}"
            render_sheet_content(ws, title, sub, projs)
        else:
            # Sheet 1: Tổng hợp toàn đợt
            ws_all = wb.create_sheet(title="Toàn đợt")
            all_projs = list(
                GraduationProject.objects.filter(batch=batch)
                .select_related("student__user", "supervisor__user", "reviewer__user", "council", "final_grade_summary", "student__course_class")
                .order_by("student__course_class__class_code", "student__registration_no")
            )
            title_all = f"BẢNG TỔNG HỢP ĐIỂM ĐỒ ÁN TỐT NGHIỆP TOÀN ĐỢT - {batch.batch_name.upper()}"
            sub_all = f"Học kỳ / Năm học: {batch.batch_name} ({batch.batch_code}) | Tất cả các lớp"
            render_sheet_content(ws_all, title_all, sub_all, all_projs)

            # Sheet per class
            for c in classes:
                clean_title = f"Lớp {c.class_code}"[:30].replace("/", "-").replace("\\", "-")
                ws_c = wb.create_sheet(title=clean_title)
                c_projs = [p for p in all_projs if p.student.course_class_id == c.id]
                title_c = f"BẢNG TỔNG HỢP ĐIỂM ĐỒ ÁN TỐT NGHIỆP - LỚP {c.class_code.upper()}"
                sub_c = f"Đợt: {batch.batch_name} | Lớp học phần: {c.class_name} | Hệ: {c.get_program_type_display()}"
                render_sheet_content(ws_c, title_c, sub_c, c_projs)

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer

    @staticmethod
    def generate_eligibility_report_excel(batch_id):
        """
        Giai đoạn 4: Xuất Báo cáo Hậu kiểm điều kiện học vụ bảo vệ ĐATN (Quy chế Nợ = 0 TC).
        Báo cáo phân loại rõ ràng:
        - Đủ điều kiện bảo vệ (Nợ = 0 TC)
        - Bảo lưu đồ án (Nợ > 0 TC)
        """
        batch = AcademicBatch.objects.get(id=batch_id)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Hau_kiem_hoc_vu"

        font_univ = Font(name="Times New Roman", size=10, bold=True)
        font_title = Font(name="Times New Roman", size=13, bold=True)
        font_subtitle = Font(name="Times New Roman", size=11, italic=True)
        font_header = Font(name="Times New Roman", size=10, bold=True, color="FFFFFF")
        font_data = Font(name="Times New Roman", size=10)
        font_bold = Font(name="Times New Roman", size=10, bold=True)
        fill_header = PatternFill(start_color="003366", end_color="003366", fill_type="solid")
        fill_deferred = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
        fill_passed = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
        fill_special = PatternFill(start_color="E0E7FF", end_color="E0E7FF", fill_type="solid")

        align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_left = Alignment(horizontal="left", vertical="center")
        align_right = Alignment(horizontal="right", vertical="center")
        thin_border = Border(
            left=Side(style="thin", color="CBD5E1"),
            right=Side(style="thin", color="CBD5E1"),
            top=Side(style="thin", color="CBD5E1"),
            bottom=Side(style="thin", color="CBD5E1")
        )

        headers = [
            ("STT", 6),
            ("Mã SV", 13),
            ("Họ và Tên", 22),
            ("Lớp học phần", 16),
            ("Hệ ĐT", 14),
            ("Tên đề tài tốt nghiệp", 38),
            ("GV Hướng Dẫn", 22),
            ("Điểm QT (GVHD)", 14),
            ("GPA Tích Lũy", 12),
            ("Tín Chỉ Nợ", 12),
            ("Kết Quả Hậu Kiểm", 22),
            ("Trạng Thái Đồ Án", 16),
            ("Ghi Chú", 30)
        ]

        # Banner
        ws.merge_cells("A1:E1")
        c_u1 = ws["A1"]
        c_u1.value = "TRƯỜNG ĐẠI HỌC GIAO THÔNG VẬN TẢI\nKHOA CÔNG NGHỆ THÔNG TIN"
        c_u1.font = font_univ
        c_u1.alignment = align_center

        ws.merge_cells("F1:M1")
        c_u2 = ws["F1"]
        c_u2.value = "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\nĐộc lập - Tự do - Hạnh phúc"
        c_u2.font = font_univ
        c_u2.alignment = align_center

        # Title
        ws.merge_cells("A3:M3")
        c_t = ws["A3"]
        c_t.value = "BÁO CÁO HẬU KIỂM ĐIỀU KIỆN HỌC VỤ BẢO VỆ ĐỒ ÁN TỐT NGHIỆP"
        c_t.font = font_title
        c_t.alignment = align_center

        ws.merge_cells("A4:M4")
        c_sub = ws["A4"]
        c_sub.value = f"Đợt: {batch.batch_name} ({batch.batch_code}) | Tiêu chuẩn: Sinh viên nợ tích lũy 0 TC đủ ĐK bảo vệ - Nợ > 0 TC bảo lưu"
        c_sub.font = font_subtitle
        c_sub.alignment = align_center

        # Header Row
        row_idx = 6
        for col_idx, (hdr_text, col_w) in enumerate(headers, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=hdr_text)
            cell.font = font_header
            cell.fill = fill_header
            cell.alignment = align_center
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = col_w

        projects_list = list(
            GraduationProject.objects.filter(batch=batch)
            .select_related("student__user", "student__course_class", "supervisor__user")
            .order_by("student__course_class__class_code", "student__registration_no")
        )

        eligible_count = 0
        deferred_count = 0
        force_count = 0

        for stt, proj in enumerate(projects_list, start=1):
            row_idx += 1
            std = proj.student
            user = std.user
            full_name = user.get_full_name() or user.username
            class_name = std.course_class.class_name if std.course_class else ""
            sup_name = proj.supervisor.user.get_full_name() if proj.supervisor else ""

            is_force = (proj.initial_eligibility == "FORCE_APPROVED")
            is_deferred = (proj.deferral_status == "APPROVED" or proj.debt_credits > 0 or proj.status == "DEFERRED")
            is_eligible = (proj.debt_credits == 0 and not is_deferred) or proj.is_eligible_for_defense or is_force

            if is_force:
                force_count += 1
                result_text = "ĐẶC CÁCH BẢO VỆ"
                fill_color = fill_special
            elif is_eligible:
                eligible_count += 1
                result_text = "ĐỦ ĐIỀU KIỆN BẢO VỆ"
                fill_color = fill_passed
            else:
                deferred_count += 1
                result_text = "BẢO LƯU ĐỒ ÁN"
                fill_color = fill_deferred

            row_data = [
                stt,
                std.registration_no,
                full_name,
                class_name,
                std.get_education_program_display(),
                proj.topic_title_vi,
                sup_name,
                proj.supervisor_score if proj.supervisor_score is not None else "Chưa có",
                proj.gpa_score if proj.gpa_score is not None else "",
                proj.debt_credits,
                result_text,
                proj.get_status_display(),
                proj.ineligibility_reason or proj.deferral_reason or ""
            ]

            for col_idx, val in enumerate(row_data, start=1):
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.font = font_data
                cell.border = thin_border
                if col_idx in (1, 2, 4, 5, 8, 9, 10, 11, 12):
                    cell.alignment = align_center
                else:
                    cell.alignment = align_left
                if col_idx == 11:
                    cell.fill = fill_color
                    cell.font = font_bold

        # Statistics block
        row_idx += 2
        total_st = len(projects_list)
        ws.cell(row=row_idx, column=2, value="TỔNG SỐ SINH VIÊN:").font = font_bold
        ws.cell(row=row_idx, column=3, value=f"{total_st} sinh viên").font = font_bold

        row_idx += 1
        ws.cell(row=row_idx, column=2, value="ĐỦ ĐIỀU KIỆN BẢO VỆ (NỢ 0 TC):").font = font_bold
        c_el = ws.cell(row=row_idx, column=3, value=f"{eligible_count} sinh viên ({round((eligible_count/total_st)*100, 1) if total_st else 0}%)")
        c_el.font = font_bold
        c_el.fill = fill_passed

        row_idx += 1
        ws.cell(row=row_idx, column=2, value="BẢO LƯU ĐỒ ÁN (NỢ > 0 TC):").font = font_bold
        c_df = ws.cell(row=row_idx, column=3, value=f"{deferred_count} sinh viên ({round((deferred_count/total_st)*100, 1) if total_st else 0}%)")
        c_df.font = font_bold
        c_df.fill = fill_deferred

        if force_count > 0:
            row_idx += 1
            ws.cell(row=row_idx, column=2, value="ĐẶC CÁCH (FORCE APPROVE):").font = font_bold
            ws.cell(row=row_idx, column=3, value=f"{force_count} sinh viên").font = font_bold

        # Signatures
        row_idx += 3
        now_dt = timezone.now()
        date_str = f"Hà Nội, ngày {now_dt.day} tháng {now_dt.month} năm {now_dt.year}"
        ws.cell(row=row_idx, column=9, value=date_str).font = font_subtitle
        row_idx += 1
        ws.cell(row=row_idx, column=2, value="GIÁO VỤ KHOA CNTT").font = font_bold
        ws.cell(row=row_idx, column=9, value="TRƯỞNG KHOA CNTT").font = font_bold
        row_idx += 1
        ws.cell(row=row_idx, column=2, value="(Ký và ghi rõ họ tên)").font = font_subtitle
        ws.cell(row=row_idx, column=9, value="(Ký và ghi rõ họ tên)").font = font_subtitle

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer

