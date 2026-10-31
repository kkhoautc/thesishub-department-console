from django.urls import path
from .views import (
    AdminRegisterAPIView,
    AdminLoginAPIView,
    AdminCookieTokenRefreshAPIView,
    AdminCookieLogoutAPIView,
    AdminUserManagementAPIView,
    AdminImportExcelAPIView,
    AdminDownloadTemplateAPIView,
    AdminExportUsersExcelAPIView,
    AdminResetUserPasswordAPIView,
    AdminSecurityCenterAPIView,
    AdminAuditLogListAPIView,
    AdminAuditLogStatsAPIView,
    HealthCheckAPIView,
    DatabaseHealthCheckAPIView,
    AcademicBatchListCreateAPIView,
    AcademicBatchDetailAPIView,
    ExcelStudentImportAPIView,
    ExcelStudentExportAPIView,
    SupervisorQuotaListUpdateAPIView,
    AutoSupervisorAllocationAPIView,
    ManualSupervisorAllocationAPIView,
    FinalizeAndNotifyAllocationAPIView,
    DefenseCouncilListCreateAPIView,
    AutoReviewerAllocationAPIView,
    GraduationProjectsAdminListAPIView,
    ExportToTrinhWordAPIView,
    ExportBienBanExcelAPIView,
    # New Views for Full 6-Phase Workflow
    DepartmentListCreateAPIView,
    DepartmentDetailAPIView,
    SupervisorProfileUpdateAPIView,
    FinalizeAllocationAPIView,
    PublishAllocationAPIView,
    TopicApprovalAPIView,
    DownloadProjectOutlineAPIView,
    ExcelEligibilityImportAPIView,
    EligibilityDecisionAPIView,
    ExcelFinalAcademicImportAPIView,
    DeferralDecisionAPIView,
    AutoDefenseScheduleAPIView,
    ManualReviewerOverrideAPIView,
    FinalizeCouncilScoresAPIView,
    CouncilMinutesPdfExportAPIView,
    CloseBatchAPIView,
    ExportFinalSummaryExcelAPIView,
    SupervisorListAPIView,
    AcademicStaffFinalGradesAPIView,
    AcademicStaffExportClassGradesExcelAPIView,
    AcademicStaffExportEligibilityReportExcelAPIView,
    AcademicStaffCompleteBatchAPIView,
    AdminSeedDataAPIView,
)

urlpatterns = [
    # Health checks
    path("health/", HealthCheckAPIView.as_view(), name="health-check"),
    path("health/database/", DatabaseHealthCheckAPIView.as_view(), name="health-db-check"),

    # Admin Authentication & Registration
    path("admin/register/", AdminRegisterAPIView.as_view(), name="admin-register"),
    path("supervisor/login/", AdminLoginAPIView.as_view(), name="admin-login"),
    path("admin/login/", AdminLoginAPIView.as_view(), name="admin-login-direct"),
    path("token/refresh/", AdminCookieTokenRefreshAPIView.as_view(), name="admin-token-refresh"),
    path("token/logout/", AdminCookieLogoutAPIView.as_view(), name="admin-token-logout"),

    # Admin Seed Data (Khôi phục & nạp dữ liệu mẫu)
    path("admin/seed-data/", AdminSeedDataAPIView.as_view(), name="admin-seed-data"),

    # Admin User Management & Advanced Credentials
    path("admin/users/", AdminUserManagementAPIView.as_view(), name="admin-users-list"),
    path("admin/users/import-excel/", AdminImportExcelAPIView.as_view(), name="admin-users-import-excel"),
    path("admin/users/template/", AdminDownloadTemplateAPIView.as_view(), name="admin-users-template"),
    path("admin/users/export/", AdminExportUsersExcelAPIView.as_view(), name="admin-users-export"),
    path("admin/users/<int:pk>/", AdminUserManagementAPIView.as_view(), name="admin-user-detail"),
    path("admin/users/<int:pk>/reset-password/", AdminResetUserPasswordAPIView.as_view(), name="admin-users-reset-password"),

    # Giai đoạn 1: Thiết lập quan hệ Khoa - Bộ môn - Giảng viên
    path("admin/departments/", DepartmentListCreateAPIView.as_view(), name="admin-departments-list"),
    path("admin/departments/<int:pk>/", DepartmentDetailAPIView.as_view(), name="admin-departments-detail"),
    path("admin/supervisors/", SupervisorListAPIView.as_view(), name="admin-supervisors-list"),
    path("supervisors/", SupervisorListAPIView.as_view(), name="supervisors-list"),
    path("admin/supervisors/<int:pk>/profile/", SupervisorProfileUpdateAPIView.as_view(), name="admin-supervisors-update-profile"),

    # Admin Security Center & Audit Logs
    path("admin/security-center/", AdminSecurityCenterAPIView.as_view(), name="admin-security-center"),
    path("audit-logs/", AdminAuditLogListAPIView.as_view(), name="admin-audit-logs-list"),
    path("audit-logs/stats/", AdminAuditLogStatsAPIView.as_view(), name="admin-audit-logs-stats"),

    # Academic Batches & Course Classes (Giai đoạn 1)
    path("batch/create/", AcademicBatchListCreateAPIView.as_view(), name="batch-create"),
    path("batches/create/", AcademicBatchListCreateAPIView.as_view(), name="batches-create"),
    path("batch/", AcademicBatchListCreateAPIView.as_view(), name="batch-list-create"),
    path("batches/", AcademicBatchListCreateAPIView.as_view(), name="batches-list-create"),
    path("admin/batches/create/", AcademicBatchListCreateAPIView.as_view(), name="admin-batches-create"),
    path("admin/batches/", AcademicBatchListCreateAPIView.as_view(), name="admin-batches-list"),
    path("admin/batches/<int:pk>/", AcademicBatchDetailAPIView.as_view(), name="admin-batches-detail"),
    path("admin/batches/<int:pk>/close/", CloseBatchAPIView.as_view(), name="admin-batches-close"),

    # Student Excel Import & Export (Giai đoạn 1)
    path("student/import/", ExcelStudentImportAPIView.as_view(), name="student-import"),
    path("students/import/", ExcelStudentImportAPIView.as_view(), name="students-import"),
    path("student/import-excel/", ExcelStudentImportAPIView.as_view(), name="student-import-excel"),
    path("students/import-excel/", ExcelStudentImportAPIView.as_view(), name="students-import-excel"),
    path("admin/students/import/", ExcelStudentImportAPIView.as_view(), name="admin-students-import"),
    path("admin/student/import-excel/", ExcelStudentImportAPIView.as_view(), name="admin-student-import-excel"),
    path("admin/student/import/", ExcelStudentImportAPIView.as_view(), name="admin-student-import"),
    path("admin/students/import-excel/", ExcelStudentImportAPIView.as_view(), name="admin-students-import-excel"),
    path("admin/students/export-excel/", ExcelStudentExportAPIView.as_view(), name="admin-students-export-excel"),
    path("students/export-excel/", ExcelStudentExportAPIView.as_view(), name="students-export-excel"),
    path("admin/batches/<int:batch_id>/export-students/", ExcelStudentExportAPIView.as_view(), name="admin-batches-export-students"),

    # Supervisor Quotas & Allocation (Giai đoạn 2)
    path("admin/quotas/", SupervisorQuotaListUpdateAPIView.as_view(), name="admin-quotas"),
    path("admin/allocations/auto-match/", AutoSupervisorAllocationAPIView.as_view(), name="admin-allocations-auto-match"),
    path("admin/allocations/manual/", ManualSupervisorAllocationAPIView.as_view(), name="admin-allocations-manual"),
    path("admin/allocations/finalize/", FinalizeAllocationAPIView.as_view(), name="admin-allocations-finalize"),
    path("admin/allocations/publish/", PublishAllocationAPIView.as_view(), name="admin-allocations-publish"),

    # Graduation Projects, Phê duyệt đề tài & Đề cương (Giai đoạn 3)
    path("admin/projects/", GraduationProjectsAdminListAPIView.as_view(), name="admin-projects-list"),
    path("admin/projects/<int:pk>/topic-approval/", TopicApprovalAPIView.as_view(), name="admin-projects-topic-approval"),
    path("admin/projects/<int:pk>/download-outline/", DownloadProjectOutlineAPIView.as_view(), name="admin-projects-download-outline"),

    # Xét điều kiện làm đồ án & Force Approve (Giai đoạn 4)
    path("admin/eligibility/import-excel/", ExcelEligibilityImportAPIView.as_view(), name="admin-eligibility-import-excel"),
    path("admin/eligibility/export-excel/", AcademicStaffExportEligibilityReportExcelAPIView.as_view(), name="admin-eligibility-export-excel"),
    path("admin/projects/<int:pk>/eligibility-decision/", EligibilityDecisionAPIView.as_view(), name="admin-projects-eligibility-decision"),
    path("admin/projects/<int:pk>/force-approve/", EligibilityDecisionAPIView.as_view(), name="admin-projects-force-approve"),
    path("projects/<int:pk>/eligibility-decision/", EligibilityDecisionAPIView.as_view(), name="projects-eligibility-decision"),
    path("projects/<int:pk>/force-approve/", EligibilityDecisionAPIView.as_view(), name="projects-force-approve"),
    path("admin/students/<int:pk>/force-approve/", EligibilityDecisionAPIView.as_view(), name="admin-students-force-approve"),
    path("students/<int:pk>/force-approve/", EligibilityDecisionAPIView.as_view(), name="students-force-approve"),
    path("app/projects/<int:pk>/force-approve/", EligibilityDecisionAPIView.as_view(), name="app-projects-force-approve"),
    path("app/students/<int:pk>/force-approve/", EligibilityDecisionAPIView.as_view(), name="app-students-force-approve"),

    # Defense Readiness, Deferral Branch, Councils & Scheduling (Giai đoạn 6 & Bảo lưu)
    path("admin/final-academic/import-excel/", ExcelFinalAcademicImportAPIView.as_view(), name="admin-final-academic-import-excel"),
    path("admin/projects/<int:pk>/deferral-decision/", DeferralDecisionAPIView.as_view(), name="admin-projects-deferral-decision"),
    path("admin/councils/", DefenseCouncilListCreateAPIView.as_view(), name="admin-councils"),
    path("admin/councils/<int:pk>/", DefenseCouncilListCreateAPIView.as_view(), name="admin-councils-detail"),
    path("admin/councils/<int:pk>/finalize-scores/", FinalizeCouncilScoresAPIView.as_view(), name="admin-councils-finalize-scores"),
    path("admin/reviewers/auto-assign/", AutoReviewerAllocationAPIView.as_view(), name="admin-reviewers-auto-assign"),
    path("admin/defense/override-reviewer/", ManualReviewerOverrideAPIView.as_view(), name="admin-defense-override-reviewer"),
    path("admin/defense/auto-schedule/", AutoDefenseScheduleAPIView.as_view(), name="admin-defense-auto-schedule"),

    # Document Generation (Word, Excel, PDF) & Xuất cuối kỳ
    path("admin/councils/<int:council_id>/export-minutes-pdf/", CouncilMinutesPdfExportAPIView.as_view(), name="admin-councils-export-minutes-pdf"),
    path("admin/export/to-trinh-word/", ExportToTrinhWordAPIView.as_view(), name="admin-export-to-trinh-word"),
    path("admin/export/bien-ban-excel/", ExportBienBanExcelAPIView.as_view(), name="admin-export-bien-ban-excel"),
    path("admin/export/final-summary-excel/", ExportFinalSummaryExcelAPIView.as_view(), name="admin-export-final-summary-excel"),

    # Phân hệ Giáo vụ (Academic Staff Module)
    path("admin/academic-staff/final-grades/", AcademicStaffFinalGradesAPIView.as_view(), name="admin-academic-staff-final-grades"),
    path("admin/academic-staff/export-class-grades-excel/", AcademicStaffExportClassGradesExcelAPIView.as_view(), name="admin-academic-staff-export-class-grades"),
    path("admin/academic-staff/complete-batch/", AcademicStaffCompleteBatchAPIView.as_view(), name="admin-academic-staff-complete-batch"),
]
