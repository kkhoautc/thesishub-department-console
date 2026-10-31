"""
UTC SMART FYP MANAGEMENT SYSTEM - CORE MODELS
Single Source of Truth Data Model for 6-Phase FYP Lifecycle
Shared between Client and Admin Portals
"""

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.exceptions import ValidationError


# ==============================================================================
# MODULE 1: AUTHENTICATION & CORE ORGANIZATIONAL HIERARCHY
# ==============================================================================

class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = (
        ("student", "Student"),
        ("supervisor", "Supervisor"),
        ("committee_member", "Committee Member"),
        ("external_examiner", "External Examiner"),
        ("admin", "Admin"),
        ("academic_staff", "Academic Staff"),
    )
    user_type = models.CharField(max_length=50, choices=USER_TYPE_CHOICES, db_index=True)

    class Meta:
        db_table = "app_customuser"
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        full_name = self.get_full_name()
        return full_name if full_name else self.username

    @property
    def admin_student_profile(self):
        return getattr(self, "student_profile", None)

    @property
    def admin_supervisor_profile(self):
        return getattr(self, "supervisor_profile", None)

    @property
    def admin_academic_staff_profile(self):
        return getattr(self, "academic_staff_profile", None)


class Department(models.Model):
    """Bộ môn chuyên môn trực thuộc Khoa CNTT (vd: CNPM, HTTT, KHMT, MMT)"""
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "app_department"
        ordering = ["code"]
        verbose_name = "Bộ môn"
        verbose_name_plural = "Danh sách Bộ môn"

    def __str__(self):
        return f"{self.name} ({self.code})"


class AcademicBatch(models.Model):
    """Kỳ học / Đợt làm Đồ án Tốt nghiệp (vd: K62 HK1 2026-2027)"""
    PROGRAM_CHOICES = (
        ("BACHELOR", "Cử nhân"),
        ("ENGINEER", "Kỹ sư"),
        ("BOTH", "Cả Cử nhân & Kỹ sư"),
    )

    STAGE_CHOICES = (
        ("PHASE_1_SETUP", "GĐ1: Khởi tạo đợt & Thiết lập dữ liệu"),
        ("PHASE_2_ALLOCATING", "GĐ2: Đang phân công GVHD"),
        ("PHASE_2_LOCKED", "GĐ2: Khoa đã chốt phân công"),
        ("PHASE_3_TOPIC", "GĐ3: Xây dựng & Phê duyệt đề tài"),
        ("PHASE_4_ELIGIBILITY", "GĐ4: Xét điều kiện làm đồ án"),
        ("PHASE_5_IN_PROGRESS", "GĐ5: Đang thực hiện đồ án"),
        ("PHASE_6_DEFENSE", "GĐ6: Xét bảo vệ & Hội đồng"),
        ("COMPLETED", "Hoàn tất: Đã kết thúc đợt đồ án"),
    )

    batch_code = models.CharField(max_length=50, unique=True)
    batch_name = models.CharField(max_length=255)
    program_type = models.CharField(max_length=50, choices=PROGRAM_CHOICES, default="BACHELOR")
    current_stage = models.CharField(max_length=50, choices=STAGE_CHOICES, default="PHASE_1_SETUP")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_allocation_published = models.BooleanField(default=False)
    allocation_published_at = models.DateTimeField(null=True, blank=True)
    is_closed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "app_academicbatch"
        ordering = ["-created_at"]
        verbose_name = "Đợt đồ án"
        verbose_name_plural = "Danh sách Đợt đồ án"

    def __str__(self):
        return f"{self.batch_name} ({self.batch_code}) - {self.get_program_type_display()}"


class CourseClass(models.Model):
    """Lớp học phần từ cổng đào tạo (vd: CNT04.101, IT1.243.102)"""
    PROGRAM_CHOICES = (
        ("VIET_ANH", "Công nghệ thông tin Việt - Anh"),
        ("DAI_TRA", "Công nghệ thông tin Đại trà"),
        ("KHMT", "Khoa học máy tính"),
        ("KHOA_CU", "Sinh viên Khóa cũ"),
    )
    EDUCATION_CHOICES = (
        ("BACHELOR", "Cử nhân"),
        ("ENGINEER", "Kỹ sư"),
    )
    batch = models.ForeignKey(AcademicBatch, on_delete=models.CASCADE, related_name="course_classes")
    class_code = models.CharField(max_length=50)
    class_name = models.CharField(max_length=255)
    program_type = models.CharField(max_length=50, choices=PROGRAM_CHOICES, default="DAI_TRA")
    education_program = models.CharField(max_length=50, choices=EDUCATION_CHOICES, default="BACHELOR")
    class_group = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        db_table = "app_courseclass"
        ordering = ["class_code"]
        verbose_name = "Lớp học phần"
        verbose_name_plural = "Danh sách Lớp học phần"

    def __str__(self):
        return f"{self.class_name} - {self.class_code}"


class StudentQuerySet(models.QuerySet):
    def filter(self, *args, **kwargs):
        if "degree_program" in kwargs:
            kwargs["education_program"] = kwargs.pop("degree_program")
        return super().filter(*args, **kwargs)

    def update_or_create(self, defaults=None, **kwargs):
        defaults = dict(defaults or {})
        if "degree_program" in defaults:
            defaults["education_program"] = defaults.pop("degree_program")
        if "degree_program" in kwargs:
            kwargs["education_program"] = kwargs.pop("degree_program")
        return super().update_or_create(defaults=defaults, **kwargs)

    def create(self, **kwargs):
        if "degree_program" in kwargs:
            kwargs["education_program"] = kwargs.pop("degree_program")
        return super().create(**kwargs)


class Student(models.Model):
    """Hồ sơ Sinh viên tham gia đồ án tốt nghiệp"""
    objects = StudentQuerySet.as_manager()

    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="student_profile")
    registration_no = models.CharField(max_length=20, unique=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    semester = models.CharField(max_length=100, blank=True, null=True)
    batch_no = models.CharField(max_length=100, blank=True, null=True)
    phone_number = models.CharField(max_length=30, blank=True, null=True)
    education_program = models.CharField(
        max_length=50,
        choices=(("BACHELOR", "Cử nhân"), ("ENGINEER", "Kỹ sư")),
        default="BACHELOR"
    )
    course_class = models.ForeignKey(CourseClass, on_delete=models.SET_NULL, null=True, blank=True, related_name="students")
    academic_batch = models.ForeignKey(AcademicBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name="students")

    class Meta:
        db_table = "app_student"
        ordering = ["registration_no"]
        verbose_name = "Sinh viên"
        verbose_name_plural = "Danh sách Sinh viên"

    def __init__(self, *args, **kwargs):
        if "degree_program" in kwargs and "education_program" not in kwargs:
            kwargs["education_program"] = kwargs.pop("degree_program")
        super().__init__(*args, **kwargs)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.registration_no})"

    @property
    def degree_program(self):
        return self.education_program

    @degree_program.setter
    def degree_program(self, value):
        self.education_program = value

    def get_degree_program_display(self):
        return self.get_education_program_display()

    @property
    def cpa(self):
        proj = getattr(self, "graduation_project", None)
        return getattr(proj, "gpa_score", 0.0) or getattr(self, "_cpa", 0.0) or 0.0

    @cpa.setter
    def cpa(self, value):
        self._cpa = float(value)
        proj = getattr(self, "graduation_project", None)
        if proj:
            proj.gpa_score = float(value)
            proj.save(update_fields=["gpa_score"])

    @property
    def credits_accumulated(self):
        if hasattr(Student, "_student_credits_store") and self.registration_no in Student._student_credits_store:
            return Student._student_credits_store[self.registration_no]
        return getattr(self, "_credits_accumulated", 0)

    @credits_accumulated.setter
    def credits_accumulated(self, value):
        self._credits_accumulated = int(value)
        if not hasattr(Student, "_student_credits_store"):
            Student._student_credits_store = {}
        if self.registration_no:
            Student._student_credits_store[self.registration_no] = int(value)

    @property
    def is_eligible_for_thesis(self):
        if hasattr(self, "_is_eligible_for_thesis"):
            return self._is_eligible_for_thesis
        proj = getattr(self, "graduation_project", None)
        if not proj:
            return True
        return proj.initial_eligibility != "DISQUALIFIED"

    @is_eligible_for_thesis.setter
    def is_eligible_for_thesis(self, value):
        self._is_eligible_for_thesis = bool(value)

    def save(self, *args, **kwargs):
        if "update_fields" in kwargs and kwargs["update_fields"] is not None:
            valid_fields = {f.name for f in self._meta.fields}
            kwargs["update_fields"] = [f for f in kwargs["update_fields"] if f in valid_fields]
        super().save(*args, **kwargs)


class Supervisor(models.Model):
    """Hồ sơ Giảng viên hướng dẫn / phản biện"""
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="supervisor_profile")
    supervisor_id = models.CharField(max_length=100, unique=True)
    research_interest = models.CharField(max_length=255, blank=True, null=True)
    academic_background = models.CharField(max_length=255, blank=True, null=True)
    phone_number = models.CharField(max_length=30, blank=True, null=True)
    academic_title = models.CharField(max_length=50, blank=True, null=True)  # ThS, TS, PGS.TS, GS.TS
    department_name = models.CharField(max_length=100, blank=True, null=True)
    department_obj = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="supervisors")
    academic_rank_multiplier = models.FloatField(default=1.0)
    is_external = models.BooleanField(default=False)

    class Meta:
        db_table = "app_supervisor"
        ordering = ["supervisor_id"]
        verbose_name = "Giảng viên"
        verbose_name_plural = "Danh sách Giảng viên"

    def __str__(self):
        prefix = f"{self.academic_title} " if self.academic_title else ""
        return f"{prefix}{self.user.get_full_name() or self.user.username}"

    def is_eligible_for_engineer(self):
        """Kiểm tra giảng viên có đạt học vị tối thiểu (TS trở lên) để hướng dẫn SV Kỹ sư không"""
        title = (self.academic_title or "").upper()
        return ("TS" in title or "TIẾN SĨ" in title or "PGS" in title or "GS" in title)


class AcademicStaff(models.Model):
    """Hồ sơ Giáo vụ Khoa CNTT UTC"""
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="academic_staff_profile")
    staff_id = models.CharField(max_length=50, unique=True)
    phone_number = models.CharField(max_length=30, blank=True, null=True)
    office_location = models.CharField(max_length=100, blank=True, null=True, default="Văn phòng Khoa CNTT (P.405-A9)")
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="academic_staffs")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "app_academicstaff"
        ordering = ["staff_id"]
        verbose_name = "Giáo vụ khoa"
        verbose_name_plural = "Danh sách Giáo vụ khoa"

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.staff_id})"


# ==============================================================================
# MODULE 2: QUOTA & ALLOCATION PREFERENCES (GĐ 1-2)
# ==============================================================================

class SupervisorQuota(models.Model):
    """Hạn mức số lượng sinh viên hướng dẫn của Giảng viên theo từng đợt"""
    supervisor = models.ForeignKey(Supervisor, on_delete=models.CASCADE, related_name="quotas")
    batch = models.ForeignKey(AcademicBatch, on_delete=models.CASCADE, related_name="supervisor_quotas")
    department = models.CharField(max_length=100, blank=True, null=True)
    base_quota = models.IntegerField(default=5)
    rank_multiplier = models.FloatField(default=1.0)
    viet_anh_quota = models.IntegerField(default=0)
    general_cntt_quota = models.IntegerField(default=0)
    max_total_quota = models.IntegerField(default=0)
    current_assigned = models.IntegerField(default=0)

    class Meta:
        db_table = "app_supervisorquota"
        unique_together = ("supervisor", "batch")
        verbose_name = "Định mức hướng dẫn"
        verbose_name_plural = "Danh sách Định mức hướng dẫn"

    def __str__(self):
        return f"{self.supervisor} - {self.batch.batch_code} (Quota: {self.max_total_quota})"

    def calculate_capacity(self):
        self.max_total_quota = int(round(self.base_quota * (self.rank_multiplier or 1.0)))
        return self.max_total_quota

    def save(self, *args, **kwargs):
        if self.viet_anh_quota is not None:
            self.viet_anh_quota = int(round(float(self.viet_anh_quota) + 1e-9))
        if self.general_cntt_quota is not None:
            self.general_cntt_quota = int(round(float(self.general_cntt_quota) + 1e-9))
        if self.max_total_quota is not None:
            self.max_total_quota = int(round(float(self.max_total_quota) + 1e-9))
        super().save(*args, **kwargs)


class ProjectTopicArea(models.Model):
    """Lĩnh vực / Hướng nghiên cứu đề tài đồ án tốt nghiệp"""
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "app_projecttopicarea"
        ordering = ["code"]
        verbose_name = "Lĩnh vực nghiên cứu"
        verbose_name_plural = "Danh sách Lĩnh vực nghiên cứu"

    def __str__(self):
        return self.name


class StudentPreference(models.Model):
    """Nguyện vọng GVHD (NV1, NV2, NV3) và tiêu chí phụ của Sinh viên (GĐ 2)"""
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name="preference_record")
    batch = models.ForeignKey(AcademicBatch, on_delete=models.CASCADE, related_name="student_preferences")
    topic_direction = models.ForeignKey(ProjectTopicArea, on_delete=models.SET_NULL, null=True, blank=True, related_name="interested_students")
    preference_1 = models.ForeignKey(Supervisor, on_delete=models.SET_NULL, null=True, blank=True, related_name="nv1_students")
    preference_2 = models.ForeignKey(Supervisor, on_delete=models.SET_NULL, null=True, blank=True, related_name="nv2_students")
    preference_3 = models.ForeignKey(Supervisor, on_delete=models.SET_NULL, null=True, blank=True, related_name="nv3_students")
    sub_criteria = models.TextField(blank=True, null=True)
    submitted_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "app_studentpreference"
        verbose_name = "Nguyện vọng hướng dẫn"
        verbose_name_plural = "Danh sách Nguyện vọng hướng dẫn"

    def __str__(self):
        return f"NV của {self.student.registration_no} ({self.student.user.get_full_name()})"


class InternshipInfoQuerySet(models.QuerySet):
    def update_or_create(self, defaults=None, **kwargs):
        defaults = dict(defaults or {})
        p1 = defaults.pop("preference_1", None)
        p2 = defaults.pop("preference_2", None)
        note = defaults.pop("secondary_criteria_note", None)
        obj, created = super().update_or_create(defaults=defaults, **kwargs)
        if p1 or p2 or note:
            pref, _ = StudentPreference.objects.get_or_create(
                student=obj.student,
                defaults={"batch": obj.batch}
            )
            if p1:
                pref.preference_1 = p1
            if p2:
                pref.preference_2 = p2
            if note:
                pref.sub_criteria = note
            pref.save()
        return obj, created

    def create(self, **kwargs):
        p1 = kwargs.pop("preference_1", None)
        p2 = kwargs.pop("preference_2", None)
        note = kwargs.pop("secondary_criteria_note", None)
        obj = super().create(**kwargs)
        if p1 or p2 or note:
            pref, _ = StudentPreference.objects.get_or_create(
                student=obj.student,
                defaults={"batch": obj.batch}
            )
            if p1:
                pref.preference_1 = p1
            if p2:
                pref.preference_2 = p2
            if note:
                pref.sub_criteria = note
            pref.save()
        return obj


class InternshipInfo(models.Model):
    """Khảo sát thực tập doanh nghiệp của Sinh viên"""
    objects = InternshipInfoQuerySet.as_manager()
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name="internship_info")
    batch = models.ForeignKey(AcademicBatch, on_delete=models.CASCADE, related_name="internship_submissions")
    is_interning = models.BooleanField(default=False)
    company_name = models.CharField(max_length=255, blank=True, null=True)
    topic_direction = models.ForeignKey(ProjectTopicArea, on_delete=models.SET_NULL, null=True, blank=True, related_name="internships")
    tentative_title = models.CharField(max_length=500, blank=True, null=True)
    submitted_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "app_internshipinfo"
        verbose_name = "Thông tin thực tập"
        verbose_name_plural = "Danh sách Khảo sát thực tập"

    def __str__(self):
        return f"Thực tập: {self.student.registration_no} - {self.company_name or 'Chưa đi TT'}"

    @property
    def preferred_supervisor(self):
        pref = getattr(self.student, "preference_record", None)
        return pref.preference_1 if pref else None

    @preferred_supervisor.setter
    def preferred_supervisor(self, val):
        pref, _ = StudentPreference.objects.get_or_create(student=self.student, defaults={"batch": self.batch})
        pref.preference_1 = val
        pref.save(update_fields=["preference_1"])


# ==============================================================================
# MODULE 3: GRADUATION PROJECT & REVIEW (GĐ 3-4)
# ==============================================================================

class GraduationProject(models.Model):
    """Thực thể Đồ án Tốt nghiệp trung tâm (Mô hình cá nhân chuẩn UTC: 1 SV = 1 Đồ án)"""
    STATUS_CHOICES = (
        ("ALLOCATED", "Đã phân GVHD"),
        ("OUTLINE_PENDING", "Chờ duyệt đề cương"),
        ("OUTLINE_REVISION", "Yêu cầu sửa đề cương"),
        ("OUTLINE_APPROVED", "Đề cương đã duyệt"),
        ("IN_PROGRESS", "Đang thực hiện đồ án"),
        ("DEFENSE_READY", "Đủ điều kiện bảo vệ"),
        ("PASSED", "Bảo vệ thành công - Đạt"),
        ("FAILED", "Không đạt"),
        ("DEFERRED", "Bảo lưu đồ án"),
        ("DISQUALIFIED", "Bị loại khỏi đợt"),
    )

    TOPIC_REVIEW_STATUS_CHOICES = (
        ("DRAFT", "Bản nháp (GV & SV đang xây dựng)"),
        ("GV_CONFIRMED", "Giảng viên đã xác nhận"),
        ("APPROVED", "Khoa đã phê duyệt đề tài"),
        ("REVISION_REQUIRED", "Khoa yêu cầu chỉnh sửa lại đề tài"),
    )

    ELIGIBILITY_CHOICES = (
        ("PENDING", "Chưa xét điều kiện"),
        ("ELIGIBLE", "Đủ điều kiện làm đồ án"),
        ("INELIGIBLE", "Không đủ điều kiện làm đồ án"),
        ("FORCE_APPROVED", "Khoa đặc cách cho làm đồ án (Force Approve)"),
        ("DISQUALIFIED", "Loại khỏi đợt đồ án"),
    )

    FINAL_ACADEMIC_CHOICES = (
        ("PENDING", "Chờ xét học vụ cuối"),
        ("ELIGIBLE", "Đủ điều kiện học vụ cuối"),
        ("INELIGIBLE", "Không đủ điều kiện học vụ cuối"),
    )

    DEFERRAL_CHOICES = (
        ("NONE", "Không bảo lưu"),
        ("REQUESTED", "Đơn xin bảo lưu chờ duyệt"),
        ("APPROVED", "Khoa đã duyệt bảo lưu"),
        ("REJECTED", "Không duyệt bảo lưu (Loại khỏi đợt)"),
    )

    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name="graduation_project")
    supervisor = models.ForeignKey(Supervisor, on_delete=models.CASCADE, related_name="supervised_graduation_projects")
    reviewer = models.ForeignKey(Supervisor, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_graduation_projects")
    batch = models.ForeignKey(AcademicBatch, on_delete=models.CASCADE, related_name="graduation_projects")
    topic_category = models.ForeignKey(ProjectTopicArea, on_delete=models.SET_NULL, null=True, blank=True, related_name="projects")
    topic_title_vi = models.CharField(max_length=500)
    topic_title_en = models.CharField(max_length=500, blank=True, null=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="ALLOCATED")

    # Giai đoạn 3: Phê duyệt đề tài
    topic_review_status = models.CharField(max_length=50, choices=TOPIC_REVIEW_STATUS_CHOICES, default="DRAFT")
    topic_revision_notes = models.TextField(blank=True, null=True)
    outline_pdf_path = models.CharField(max_length=500, blank=True, null=True)

    # Giai đoạn 4: Xét điều kiện làm đồ án & Force Approve
    initial_eligibility = models.CharField(max_length=50, choices=ELIGIBILITY_CHOICES, default="PENDING")
    ineligibility_reason = models.TextField(blank=True, null=True)
    gpa_score = models.FloatField(null=True, blank=True)
    debt_credits = models.IntegerField(default=0)
    force_approved_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="force_approved_projects")
    force_approved_at = models.DateTimeField(null=True, blank=True)

    # Giai đoạn 6 & Điều kiện bảo vệ
    supervisor_defense_confirmed = models.BooleanField(default=False)
    final_academic_eligibility = models.CharField(max_length=50, choices=FINAL_ACADEMIC_CHOICES, default="PENDING")
    final_academic_notes = models.TextField(blank=True, null=True)
    deferral_status = models.CharField(max_length=50, choices=DEFERRAL_CHOICES, default="NONE")
    deferral_reason = models.TextField(blank=True, null=True)
    deferral_decided_at = models.DateTimeField(null=True, blank=True)

    council = models.ForeignKey("DefenseCouncil", on_delete=models.SET_NULL, null=True, blank=True, related_name="projects")
    supervisor_score = models.FloatField(null=True, blank=True)
    supervisor_feedback = models.TextField(blank=True, null=True)
    is_eligible_for_defense = models.BooleanField(default=False)
    reviewer_score = models.FloatField(null=True, blank=True)
    reviewer_feedback = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "app_graduationproject"
        ordering = ["-created_at"]
        verbose_name = "Đồ án tốt nghiệp"
        verbose_name_plural = "Danh sách Đồ án tốt nghiệp"

    def __str__(self):
        return f"{self.student.registration_no} - {self.topic_title_vi}"

    @property
    def defense_status(self):
        if self.status == "DEFENSE_READY":
            return "READY"
        elif self.status in ["PASSED", "FAILED"]:
            return "COMPLETED"
        return "NOT_READY"

    def get_defense_status_display(self):
        return self.get_status_display()

    @property
    def is_force_approved(self):
        return self.initial_eligibility == "FORCE_APPROVED"

    @is_force_approved.setter
    def is_force_approved(self, value):
        if value:
            self.initial_eligibility = "FORCE_APPROVED"
        elif self.initial_eligibility == "FORCE_APPROVED":
            self.initial_eligibility = "DISQUALIFIED"

    @property
    def academic_clearance_status(self):
        return self.final_academic_eligibility

    @academic_clearance_status.setter
    def academic_clearance_status(self, value):
        self.final_academic_eligibility = value

    @property
    def signed_outline_file(self):
        return getattr(self, "_signed_outline_file", None)

    @signed_outline_file.setter
    def signed_outline_file(self, value):
        self._signed_outline_file = value

    def save(self, *args, **kwargs):
        if "update_fields" in kwargs and kwargs["update_fields"] is not None:
            valid_fields = {f.name for f in self._meta.fields}
            new_uf = []
            for f in kwargs["update_fields"]:
                if f == "is_force_approved":
                    if "initial_eligibility" in valid_fields and "initial_eligibility" not in new_uf:
                        new_uf.append("initial_eligibility")
                elif f == "academic_clearance_status":
                    if "final_academic_eligibility" in valid_fields and "final_academic_eligibility" not in new_uf:
                        new_uf.append("final_academic_eligibility")
                elif f in valid_fields:
                    new_uf.append(f)
            kwargs["update_fields"] = new_uf
        super().save(*args, **kwargs)

    @property
    def supervisor_score_is_draft(self):
        return False

    @property
    def reviewer_verdict(self):
        if self.reviewer_score is not None:
            return "APPROVED" if self.reviewer_score >= 5.0 else "REJECTED"
        return "PENDING"

    def get_reviewer_verdict_display(self):
        v = self.reviewer_verdict
        return "Đồng ý cho bảo vệ" if v == "APPROVED" else ("Không đồng ý" if v == "REJECTED" else "Chờ phản biện")


class OutlineReviewGroup(models.Model):
    """Tổ chuyên môn duyệt đề cương đồ án"""
    batch = models.ForeignKey(AcademicBatch, on_delete=models.CASCADE, related_name="outline_review_groups")
    name = models.CharField(max_length=255)
    department = models.CharField(max_length=100)
    members = models.ManyToManyField(Supervisor, related_name="outline_groups", blank=True)

    class Meta:
        db_table = "app_outlinereviewgroup"
        verbose_name = "Tổ duyệt đề cương"
        verbose_name_plural = "Danh sách Tổ duyệt đề cương"

    def __str__(self):
        return f"{self.name} ({self.department})"


class OutlineReview(models.Model):
    """Kết quả xét duyệt đề cương chi tiết của Tổ chuyên môn"""
    VERDICT_CHOICES = (
        ("PENDING", "Chờ xét duyệt"),
        ("APPROVED", "Đạt yêu cầu"),
        ("REVISION_REQUIRED", "Yêu cầu chỉnh sửa"),
        ("REJECTED", "Không đạt / Hủy đề tài"),
    )
    project = models.OneToOneField(GraduationProject, on_delete=models.CASCADE, related_name="outline_review")
    review_group = models.ForeignKey(OutlineReviewGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_outlines")
    reviewer = models.ForeignKey(Supervisor, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_outline_reviews")
    outline_file = models.FileField(upload_to="outlines/", null=True, blank=True)
    verdict = models.CharField(max_length=50, choices=VERDICT_CHOICES, default="PENDING")
    comments = models.TextField(blank=True, null=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "app_outlinereview"
        verbose_name = "Đánh giá đề cương"
        verbose_name_plural = "Danh sách Đánh giá đề cương"

    def __str__(self):
        return f"Đề cương: {self.project.student.registration_no} [{self.get_verdict_display()}]"


class ThesisDeferralRequest(models.Model):
    """Đơn xin bảo lưu đồ án tốt nghiệp của Sinh viên"""
    STATUS_CHOICES = (
        ("PENDING", "Chờ Khoa duyệt"),
        ("APPROVED", "Đã duyệt bảo lưu"),
        ("REJECTED", "Không chấp nhận / Loại khỏi đợt"),
    )
    project = models.ForeignKey(GraduationProject, on_delete=models.CASCADE, related_name="deferral_requests")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="deferral_requests")
    reason = models.TextField(help_text="Lý do xin bảo lưu đồ án")
    evidence_file = models.FileField(upload_to="deferral_evidence/", null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    admin_notes = models.TextField(blank=True, null=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(CustomUser, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_deferral_requests")

    class Meta:
        db_table = "app_thesisdeferralrequest"
        ordering = ["-submitted_at"]
        verbose_name = "Đơn xin bảo lưu"
        verbose_name_plural = "Danh sách Đơn xin bảo lưu"

    def __str__(self):
        return f"Đơn bảo lưu: SV {self.student.registration_no} ({self.get_status_display()})"


# ==============================================================================
# MODULE 4: SUPERVISION & PROGRESS TRACKING (GĐ 5)
# ==============================================================================

class SupervisionMeetingLog(models.Model):
    """Nhật ký các buổi làm việc định kỳ giữa GVHD và Sinh viên"""
    MEETING_TYPE_CHOICES = (
        ("OFFLINE", "Gặp trực tiếp"),
        ("ONLINE", "Trực tuyến (Meet/Zoom)"),
    )
    project = models.ForeignKey(GraduationProject, on_delete=models.CASCADE, related_name="meeting_logs")
    meeting_date = models.DateField()
    meeting_time = models.CharField(max_length=100, blank=True, default="09:00 - 10:30")
    meeting_type = models.CharField(max_length=50, choices=MEETING_TYPE_CHOICES, default="OFFLINE")
    location_or_link = models.CharField(max_length=255, blank=True, null=True)
    content_discussed = models.TextField(help_text="Nội dung đã trao đổi, tiến độ công việc")
    supervisor_notes = models.TextField(blank=True, null=True, help_text="Nhận xét / Góp ý của GVHD")
    next_meeting_plan = models.TextField(blank=True, null=True, help_text="Kế hoạch cho buổi gặp tiếp theo")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "app_supervisionmeetinglog"
        ordering = ["-meeting_date", "-created_at"]
        verbose_name = "Nhật ký họp hướng dẫn"
        verbose_name_plural = "Danh sách Nhật ký họp hướng dẫn"

    def __str__(self):
        return f"Họp HD: {self.project.student.registration_no} - {self.meeting_date} ({self.get_meeting_type_display()})"


class SupervisionTask(models.Model):
    """Nhiệm vụ / Task do GVHD giao cho Sinh viên trên Task Board"""
    PRIORITY_CHOICES = (
        ("LOW", "Thấp"),
        ("MEDIUM", "Trung bình"),
        ("HIGH", "Cao"),
        ("URGENT", "Khẩn cấp"),
    )
    STATUS_CHOICES = (
        ("TODO", "Cần làm"),
        ("IN_PROGRESS", "Đang thực hiện"),
        ("COMPLETED", "Đã hoàn thành"),
    )
    project = models.ForeignKey(GraduationProject, on_delete=models.CASCADE, related_name="tasks")
    meeting_log = models.ForeignKey(SupervisionMeetingLog, on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    assigned_by = models.ForeignKey(Supervisor, on_delete=models.CASCADE, related_name="assigned_tasks")
    due_date = models.DateField(null=True, blank=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="MEDIUM")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="TODO")
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    student_notes = models.TextField(blank=True, null=True)
    deliverable_file = models.FileField(upload_to="task_deliverables/", null=True, blank=True)
    deliverable_url = models.URLField(max_length=500, blank=True, null=True)
    review_verdict = models.CharField(
        max_length=20,
        choices=(("PENDING", "Chờ đánh giá"), ("ACCEPTED", "Đạt"), ("REVISION_REQUIRED", "Yêu cầu làm lại")),
        default="PENDING",
    )
    supervisor_review_notes = models.TextField(blank=True, null=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    is_late = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "app_supervisiontask"
        ordering = ["is_completed", "due_date", "-created_at"]
        verbose_name = "Nhiệm vụ đồ án"
        verbose_name_plural = "Danh sách Nhiệm vụ đồ án"

    def __str__(self):
        return f"Task: {self.title} -> {self.project.student.registration_no} [{self.get_status_display()}]"


class WeeklyProgressReport(models.Model):
    """Báo cáo tiến độ đồ án nộp định kỳ hàng tuần"""
    RATING_CHOICES = (
        ("PENDING", "Chưa đánh giá"),
        ("GOOD", "Tốt / Đạt tiến độ"),
        ("ACCEPTABLE", "Chấp nhận được"),
        ("LATE", "Chậm tiến độ"),
        ("UNSATISFACTORY", "Không đạt yêu cầu"),
    )
    project = models.ForeignKey(GraduationProject, on_delete=models.CASCADE, related_name="weekly_reports")
    week_number = models.IntegerField()
    summary_content = models.TextField()
    planned_tasks = models.TextField(blank=True, null=True)
    git_commit_link = models.URLField(max_length=500, blank=True, null=True)
    attached_file = models.FileField(upload_to="weekly_reports/", null=True, blank=True)
    supervisor_feedback = models.TextField(blank=True, null=True)
    supervisor_rating = models.CharField(max_length=50, choices=RATING_CHOICES, default="PENDING")
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "app_weeklyprogressreport"
        unique_together = ("project", "week_number")
        ordering = ["project", "week_number"]
        verbose_name = "Báo cáo tiến độ tuần"
        verbose_name_plural = "Danh sách Báo cáo tiến độ tuần"

    def __str__(self):
        return f"{self.project.student.registration_no} - Tuần {self.week_number} ({self.get_supervisor_rating_display()})"


# ==============================================================================
# MODULE 5: DEFENSE COUNCIL & FINAL GRADING (GĐ 6)
# ==============================================================================

class DefenseCouncil(models.Model):
    """Hội đồng đánh giá bảo vệ đồ án tốt nghiệp"""
    SESSION_CHOICES = (
        ("MORNING", "Ca sáng"),
        ("AFTERNOON", "Ca chiều"),
    )
    batch = models.ForeignKey(AcademicBatch, on_delete=models.CASCADE, related_name="defense_councils")
    council_number = models.IntegerField(default=1)
    council_name = models.CharField(max_length=255)
    session_date = models.DateField(null=True, blank=True)
    session_time = models.CharField(max_length=50, choices=SESSION_CHOICES, default="MORNING")
    defense_room = models.CharField(max_length=100, blank=True, null=True)
    is_finalized = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "app_defensecouncil"
        ordering = ["batch", "council_number"]
        verbose_name = "Hội đồng bảo vệ"
        verbose_name_plural = "Danh sách Hội đồng bảo vệ"

    def __str__(self):
        return f"{self.council_name} (HĐ {self.council_number})"

    @property
    def current_defending_project_id(self):
        return None

    @property
    def is_locked(self):
        return self.is_finalized

    @is_locked.setter
    def is_locked(self, value):
        self.is_finalized = bool(value)

    def save(self, *args, **kwargs):
        if "update_fields" in kwargs and kwargs["update_fields"] is not None:
            valid_fields = {f.name for f in self._meta.fields}
            new_uf = []
            for f in kwargs["update_fields"]:
                if f == "is_locked":
                    if "is_finalized" in valid_fields and "is_finalized" not in new_uf:
                        new_uf.append("is_finalized")
                elif f in valid_fields:
                    new_uf.append(f)
            kwargs["update_fields"] = new_uf
        super().save(*args, **kwargs)

    def check_utc_model_validity(self):
        """Kiểm tra mô hình chuẩn 1 Chủ tịch, 2 Thư ký, 2 Ủy viên (5 thành viên)"""
        members = list(self.members.all())
        chairs = [m for m in members if m.role == "CHAIR"]
        secs = [m for m in members if m.role == "SECRETARY"]
        uvs = [m for m in members if m.role in ["MEMBER", "EXTERNAL_MEMBER"]]
        is_valid = (len(chairs) == 1 and len(secs) == 2 and len(uvs) == 2 and len(members) == 5)
        return {
            "is_valid": is_valid,
            "chair_count": len(chairs),
            "secretary_count": len(secs),
            "member_count": len(uvs),
            "total_count": len(members),
            "expected_formula": "1 Chủ tịch - 2 Thư ký - 2 Ủy viên (5 thành viên)"
        }


class CouncilMember(models.Model):
    """Thành viên tham gia Hội đồng bảo vệ"""
    ROLE_CHOICES = (
        ("CHAIR", "Chủ tịch hội đồng"),
        ("SECRETARY", "Ủy viên, Thư ký"),
        ("MEMBER", "Ủy viên"),
        ("EXTERNAL_MEMBER", "Ủy viên ngoài trường"),
    )
    council = models.ForeignKey(DefenseCouncil, on_delete=models.CASCADE, related_name="members")
    supervisor = models.ForeignKey(Supervisor, on_delete=models.SET_NULL, null=True, blank=True, related_name="council_memberships")
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="council_roles")
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default="MEMBER")
    external_institution = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "app_councilmember"
        unique_together = ("council", "user")
        verbose_name = "Thành viên hội đồng"
        verbose_name_plural = "Danh sách Thành viên hội đồng"

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.get_role_display()}) - {self.council.council_name}"


class DefenseScheduleSlot(models.Model):
    """Lịch bảo vệ chi tiết từng sinh viên trong buổi bảo vệ"""
    council = models.ForeignKey(DefenseCouncil, on_delete=models.CASCADE, related_name="schedule_slots")
    project = models.OneToOneField(GraduationProject, on_delete=models.CASCADE, related_name="schedule_slot")
    order_number = models.IntegerField(default=1)
    slot_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    room = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "app_defensescheduleslot"
        ordering = ["slot_date", "order_number"]
        verbose_name = "Lịch bảo vệ chi tiết"
        verbose_name_plural = "Danh sách Lịch bảo vệ chi tiết"

    def __str__(self):
        return f"{self.council.council_name} Slot #{self.order_number}: {self.project.student.registration_no}"


class CouncilLiveScore(models.Model):
    """Điểm chấm trực tiếp của từng thành viên Hội đồng trong buổi bảo vệ"""
    council = models.ForeignKey(DefenseCouncil, on_delete=models.CASCADE, related_name="live_scores")
    project = models.ForeignKey(GraduationProject, on_delete=models.CASCADE, related_name="council_scores")
    member = models.ForeignKey(CouncilMember, on_delete=models.CASCADE, related_name="given_scores")
    score_presentation = models.FloatField(default=0.0)
    score_content = models.FloatField(default=0.0)
    score_qa = models.FloatField(default=0.0)
    score_demo = models.FloatField(default=0.0)
    total_score = models.FloatField(default=0.0)
    comments = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "app_councillivescore"
        unique_together = ("project", "member")
        verbose_name = "Điểm chấm hội đồng"
        verbose_name_plural = "Danh sách Điểm chấm hội đồng"

    def save(self, *args, **kwargs):
        self.total_score = round(
            float(self.score_presentation) + float(self.score_content) + float(self.score_qa) + float(self.score_demo), 2
        )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.member.user.get_full_name()} -> {self.project.student.registration_no}: {self.total_score}đ"


class EvaluationPolicy(models.Model):
    """Trọng số tính điểm tổng kết bảo vệ theo kỳ học (Mặc định chuẩn UTC: 40% GVHD + 20% GVPB + 40% HĐ)"""
    batch = models.OneToOneField(AcademicBatch, on_delete=models.CASCADE, related_name="evaluation_policy")
    weight_supervisor = models.FloatField(default=0.4)
    weight_reviewer = models.FloatField(default=0.2)
    weight_council = models.FloatField(default=0.4)

    class Meta:
        db_table = "app_evaluationpolicy"
        verbose_name = "Quy chế trọng số điểm"
        verbose_name_plural = "Danh sách Quy chế trọng số điểm"

    def clean(self):
        total = round(self.weight_supervisor + self.weight_reviewer + self.weight_council, 2)
        if total != 1.0:
            raise ValidationError("Tổng các trọng số phải bằng 1.0 (100%)")

    def __str__(self):
        return f"Policy {self.batch.batch_code}: GVHD {int(self.weight_supervisor*100)}% - GVPB {int(self.weight_reviewer*100)}% - HĐ {int(self.weight_council*100)}%"


class FinalGradeSummary(models.Model):
    """Bảng điểm tổng hợp cuối cùng của Đồ án Tốt nghiệp (Single Source of Truth)"""
    project = models.OneToOneField(GraduationProject, on_delete=models.CASCADE, related_name="final_grade_summary")
    supervisor_score = models.FloatField(null=True, blank=True)
    reviewer_score = models.FloatField(null=True, blank=True)
    council_avg_score = models.FloatField(null=True, blank=True)
    final_score_10 = models.FloatField(null=True, blank=True)
    final_score_4 = models.FloatField(null=True, blank=True)
    final_letter_grade = models.CharField(max_length=10, blank=True, null=True)
    classification = models.CharField(max_length=50, blank=True, null=True)
    is_passed = models.BooleanField(default=False)
    is_finalized = models.BooleanField(default=False)
    notes = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "app_finalgradesummary"
        verbose_name = "Bảng điểm tổng kết"
        verbose_name_plural = "Danh sách Bảng điểm tổng kết"

    def calculate_and_save(self, policy=None):
        """Tính toán quy đổi điểm theo chuẩn UTC"""
        w_sup = policy.weight_supervisor if policy else 0.4
        w_rev = policy.weight_reviewer if policy else 0.2
        w_cou = policy.weight_council if policy else 0.4

        s_sup = self.supervisor_score or 0.0
        s_rev = self.reviewer_score or 0.0
        s_cou = self.council_avg_score or 0.0

        if self.reviewer_score is not None and w_rev > 0:
            score10 = round((s_sup * w_sup) + (s_rev * w_rev) + (s_cou * w_cou), 2)
        else:
            # GĐ 6 yeucau.md: Điểm tổng kết ĐATN kết hợp giữa Điểm quá trình (GVHD) và Điểm hội đồng
            norm = (w_sup + w_cou) if (w_sup + w_cou) > 0 else 1.0
            score10 = round(((s_sup * w_sup) + (s_cou * w_cou)) / norm, 2)

        self.final_score_10 = score10

        # Thang 4 & Điểm chữ theo Quy chế UTC
        if score10 >= 9.0:
            self.final_score_4 = 4.0
            self.final_letter_grade = "A+"
            self.classification = "Xuất sắc"
            self.is_passed = True
        elif score10 >= 8.5:
            self.final_score_4 = 4.0
            self.final_letter_grade = "A"
            self.classification = "Giỏi"
            self.is_passed = True
        elif score10 >= 8.0:
            self.final_score_4 = 3.5
            self.final_letter_grade = "B+"
            self.classification = "Khá giỏi"
            self.is_passed = True
        elif score10 >= 7.0:
            self.final_score_4 = 3.0
            self.final_letter_grade = "B"
            self.classification = "Khá"
            self.is_passed = True
        elif score10 >= 6.5:
            self.final_score_4 = 2.5
            self.final_letter_grade = "C+"
            self.classification = "Trung bình khá"
            self.is_passed = True
        elif score10 >= 5.5:
            self.final_score_4 = 2.0
            self.final_letter_grade = "C"
            self.classification = "Trung bình"
            self.is_passed = True
        elif score10 >= 5.0:
            self.final_score_4 = 1.5
            self.final_letter_grade = "D+"
            self.classification = "Trung bình yếu"
            self.is_passed = True
        elif score10 >= 4.0:
            self.final_score_4 = 1.0
            self.final_letter_grade = "D"
            self.classification = "Yếu"
            self.is_passed = True
        else:
            self.final_score_4 = 0.0
            self.final_letter_grade = "F"
            self.classification = "Kém (Không đạt)"
            self.is_passed = False

        self.save()

    def __str__(self):
        return f"Điểm tổng kết: {self.project.student.registration_no} -> {self.final_score_10}đ ({self.final_letter_grade})"


# ==============================================================================
# MODULE 6: AUDIT LOGS & NOTIFICATIONS (CROSS-REPO)
# ==============================================================================

class AuditLog(models.Model):
    """Nhật ký kiểm toán hành động quản trị, bảo mật & cập nhật điểm"""
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")
    action_type = models.CharField(max_length=50, default="system_action")
    description = models.TextField()
    field_name = models.CharField(max_length=100, blank=True, null=True)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "app_auditlog"
        ordering = ["-created_at"]
        verbose_name = "Nhật ký kiểm toán"
        verbose_name_plural = "Danh sách Nhật ký kiểm toán"

    def __str__(self):
        return f"AuditLog #{self.pk} - {self.action_type}"


class Notification(models.Model):
    """Thông báo hệ thống cho Người dùng (Sinh viên, Giảng viên, Hội đồng, Admin)"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=50, default="system")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "app_notification"
        ordering = ["-created_at"]
        verbose_name = "Thông báo"
        verbose_name_plural = "Danh sách Thông báo"

    def __str__(self):
        return f"Thông báo: {self.user.username} - {self.title}"
