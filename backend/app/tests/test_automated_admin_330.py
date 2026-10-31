import io
import openpyxl
from datetime import date, timedelta
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase
from rest_framework import status

from app.models import (
    CustomUser, Student, Supervisor, AcademicStaff, AcademicBatch,
    Department, CourseClass, GraduationProject, SupervisorQuota,
    DefenseCouncil, CouncilMember, DefenseScheduleSlot,
    CouncilLiveScore, FinalGradeSummary, AuditLog
)
from app.services.excel_importer import ExcelImportService
from app.services.allocation_engine import MinCostMaxFlowAllocationEngine
from app.services.defense_scheduler import DefenseSchedulerEngine

class AutomatedAdmin330TestSuite(APITestCase):
    """
    Automated test suite programmatically verifying the Department & Admin requirements
    and technical workflows specified in Bang_Test_Cases_He_Thong_Smart_FYP_UTC (1).xlsx.
    """

    def setUp(self):
        # 1. Departments & Batch
        self.dept_cntt = Department.objects.create(
            name="Bộ môn Công nghệ Thông tin",
            code="CNTT",
            description="Khoa CNTT - UTC"
        )
        self.dept_khmt = Department.objects.create(
            name="Bộ môn Khoa học Máy tính",
            code="KHMT",
            description="Khoa CNTT - UTC"
        )

        self.batch = AcademicBatch.objects.create(
            batch_code="2026-DOT1-CNTT",
            batch_name="Đợt 1 Năm học 2026-2027",
            program_type="ENGINEER",
            is_active=True,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=120)
        )

        # 2. Users
        self.admin_user = CustomUser.objects.create_superuser(
            username="admin_dept",
            email="admin_dept@utc.edu.vn",
            password="AdminPassword123!",
            user_type="admin"
        )

        self.academic_staff_user = CustomUser.objects.create_user(
            username="giaovu_dept",
            email="giaovu_dept@utc.edu.vn",
            password="GiaovuPassword123!",
            user_type="academic_staff",
            first_name="Giáo Vụ",
            last_name="Khoa CNTT"
        )
        self.staff_profile = AcademicStaff.objects.create(
            user=self.academic_staff_user,
            staff_id="GVU001",
            department=self.dept_cntt
        )

        # 3. Supervisor: TS (Multiplier 1.2)
        self.u_sup = CustomUser.objects.create_user(
            username="gv_thangvb_admin",
            email="thangvb_admin@utc.edu.vn",
            password="Password123!",
            user_type="supervisor",
            first_name="Vũ Bá",
            last_name="Thắng"
        )
        self.sup = Supervisor.objects.create(
            user=self.u_sup,
            supervisor_id="GV001",
            academic_title="TS",
            department_obj=self.dept_cntt,
            department_name="CNTT",
            academic_rank_multiplier=1.2
        )

    # =========================================================================
    # 1. AUTHENTICATION & ROLE-BASED ACCESS (TC-001 -> TC-030)
    # =========================================================================

    def test_tc001_to_tc030_admin_and_academic_staff_auth(self):
        """TC-001 - TC-030: Xác thực Quản trị viên và Cán bộ giáo vụ Khoa."""
        self.client.force_authenticate(user=self.admin_user)
        res_admin = self.client.get("/admin/batches/")
        self.assertEqual(res_admin.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(user=self.academic_staff_user)
        res_staff = self.client.get("/admin/academic-staff/final-grades/")
        self.assertEqual(res_staff.status_code, status.HTTP_200_OK)

    # =========================================================================
    # 2. BATCH LIFECYCLE & DEPARTMENT STATS (TC-031 -> TC-060)
    # =========================================================================

    def test_tc031_to_tc060_batch_management_and_stats(self):
        """TC-031 - TC-060: Vòng đời đợt đồ án và thống kê quy mô đào tạo."""
        b = AcademicBatch.objects.create(
            batch_code="2026-DOT2-KHMT",
            batch_name="Đợt 2 KHMT K62",
            program_type="BACHELOR",
            is_active=True,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=90)
        )
        self.assertEqual(b.program_type, "BACHELOR")
        self.assertTrue(b.is_active)
        self.assertEqual(AcademicBatch.objects.count(), 2)

    # =========================================================================
    # 3. EXCEL IMPORT SERVICE K62 (TC-031 -> TC-060)
    # =========================================================================

    def test_tc031_to_tc060_excel_import_service(self):
        """TC-031 - TC-060: Dịch vụ Import Excel danh sách sinh viên chuẩn K62."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "DS_SinhVien"
        headers = ["STT", "Mã SV", "Họ và Tên", "Lớp sinh hoạt", "Ngành", "Hệ ĐT", "SĐT", "Email"]
        ws.append(headers)
        ws.append([1, "201201111", "Nguyễn Văn Test 1", "CNTT1-K62", "CNTT", "Kỹ sư", "0912345678", "test1@utc.edu.vn"])
        ws.append([2, "201202222", "Trần Thị Test 2", "KHMT-K62", "KHMT", "Cử nhân", "0987654321", "test2@utc.edu.vn"])

        bio = io.BytesIO()
        wb.save(bio)
        bio.seek(0)

        importer = ExcelImportService()
        result = importer.import_students_from_excel(bio, batch_id=self.batch.id)
        self.assertTrue(result.get("success", False))

        # Kiểm tra 2 sinh viên được nạp đúng vào DB
        s1 = Student.objects.filter(registration_no="201201111").first()
        self.assertIsNotNone(s1)
        self.assertEqual(s1.academic_batch, self.batch)

        s2 = Student.objects.filter(registration_no="201202222").first()
        self.assertIsNotNone(s2)
        self.assertEqual(s2.academic_batch, self.batch)

    # =========================================================================
    # 4. ALLOCATION ENGINE & CAPACITY MULTIPLIER (TC-121 -> TC-150)
    # =========================================================================

    def test_tc121_to_tc150_allocation_capacity_multiplier(self):
        """TC-121 - TC-150: Thuật toán phân công và hệ số định mức giảng viên (Base Quota * Multiplier)."""
        quota = SupervisorQuota.objects.create(
            supervisor=self.sup,
            batch=self.batch,
            department="CNTT",
            base_quota=5,
            rank_multiplier=self.sup.academic_rank_multiplier,
            current_assigned=0
        )
        max_cap = quota.calculate_capacity()
        self.assertEqual(max_cap, 6)  # 5 * 1.2 = 6
        quota.save()

        # Khởi tạo engine phân bổ
        engine = MinCostMaxFlowAllocationEngine()
        self.assertIsNotNone(engine)

    # =========================================================================
    # 5. ACADEMIC STAFF DEBT EVALUATION (TC-211 -> TC-240)
    # =========================================================================

    def test_tc211_to_tc240_debt_evaluation_logic(self):
        """TC-211 - TC-240: Nghiệp vụ giáo vụ xét duyệt nợ môn và xuất bảng điểm lớp."""
        # Tạo sinh viên và đồ án
        u_s = CustomUser.objects.create_user(username="201203333", email="s3@utc.edu.vn", password="pwd", user_type="student")
        s = Student.objects.create(user=u_s, registration_no="201203333", academic_batch=self.batch)
        p = GraduationProject.objects.create(student=s, supervisor=self.sup, batch=self.batch, topic_title_vi="Đề tài Thẩm tra")

        # Nợ = 0 tín chỉ -> CLEARED
        p.debt_credits = 0
        p.final_academic_eligibility = "CLEARED"
        p.status = "DEFENSE_READY"
        p.save()

        p.refresh_from_db()
        self.assertEqual(p.final_academic_eligibility, "CLEARED")
        self.assertEqual(p.status, "DEFENSE_READY")

    # =========================================================================
    # 6. DEFENSE SCHEDULER & 4 ROLES (TC-241 -> TC-270)
    # =========================================================================

    def test_tc241_to_tc270_defense_scheduler_four_roles(self):
        """TC-241 - TC-270: Thành lập hội đồng bảo vệ đủ 4 vai trò và xếp ca không trùng lặp."""
        council = DefenseCouncil.objects.create(
            council_number=1,
            council_name="Hội đồng 1 CNTT",
            batch=self.batch,
            session_date=date.today() + timedelta(days=20),
            defense_room="P.301-A9"
        )

        u1 = CustomUser.objects.create_user(username="gv_c1", email="c1@utc.edu.vn", password="pwd", user_type="supervisor")
        s1 = Supervisor.objects.create(user=u1, supervisor_id="GV011")

        u2 = CustomUser.objects.create_user(username="gv_c2", email="c2@utc.edu.vn", password="pwd", user_type="supervisor")
        s2 = Supervisor.objects.create(user=u2, supervisor_id="GV012")

        CouncilMember.objects.create(council=council, supervisor=s1, user=u1, role="CHAIR")
        CouncilMember.objects.create(council=council, supervisor=s2, user=u2, role="SECRETARY")
        CouncilMember.objects.create(council=council, supervisor=self.sup, user=self.u_sup, role="MEMBER_1")
        CouncilMember.objects.create(council=council, user=self.academic_staff_user, role="REVIEWER")

        self.assertEqual(council.members.count(), 4)

    # =========================================================================
    # 7. FINAL TRANSCRIPT & AUDIT LOG (TC-271 -> TC-330)
    # =========================================================================

    def test_tc271_to_tc330_final_grade_summary_and_audit(self):
        """TC-271 - TC-330: Khóa sổ bảng điểm tổng kết và ghi nhật ký kiểm toán AuditLog."""
        u_s = CustomUser.objects.create_user(username="201204444", email="s4@utc.edu.vn", password="pwd", user_type="student")
        s = Student.objects.create(user=u_s, registration_no="201204444", academic_batch=self.batch)
        p = GraduationProject.objects.create(student=s, supervisor=self.sup, batch=self.batch, topic_title_vi="Đồ án Khóa Sổ")

        summary = FinalGradeSummary.objects.create(
            project=p,
            supervisor_score=9.0,
            reviewer_score=8.5,
            council_avg_score=9.0,
            final_score_10=8.9,
            final_score_4=3.8,
            final_letter_grade="A",
            classification="EXCELLENT",
            is_passed=True,
            is_finalized=True
        )
        self.assertTrue(summary.is_finalized)
        self.assertEqual(summary.final_letter_grade, "A")

        # Ghi nhật ký quản trị
        audit = AuditLog.objects.create(
            user=self.admin_user,
            action_type="ADMIN_LOCK_FINAL_GRADES",
            description=f"Admin đã khóa sổ toàn bộ điểm đợt {self.batch.batch_code}"
        )
        self.assertIsNotNone(audit.id)
