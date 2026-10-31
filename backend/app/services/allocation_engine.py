import collections
from django.db import transaction
from django.utils import timezone
from app.models import (
    Student,
    Supervisor,
    SupervisorQuota,
    InternshipInfo,
    StudentPreference,
    GraduationProject,
    AcademicBatch,
    ProjectTopicArea,
    AuditLog
)

class MinCostMaxFlowAllocationEngine:
    """
    Min-Cost Max-Flow (MCMF) Matching Engine for Supervisor Allocation.
    Tuân thủ quy trình nghiệp vụ Giai đoạn 2:
    1. Hard Constraint: Nếu SV thuộc CT Kỹ sư (ENGINEER), GVHD bắt buộc phải đạt học vị tối thiểu (TS trở lên).
    2. Soft Constraint: Tối ưu theo nguyện vọng NV1 (-120), NV2 (-70), NV3 (-40), độ phù hợp chuyên môn bộ môn (-30).
    3. Capacity: Tính toán theo hệ số học vị (GS/PGS/TS/ThS).
    """

    class Edge:
        def __init__(self, to, cap, flow, cost, rev):
            self.to = to
            self.cap = cap
            self.flow = flow
            self.cost = cost
            self.rev = rev

    @classmethod
    def allocate_supervisors_for_batch(cls, batch_id):
        try:
            batch = AcademicBatch.objects.get(id=batch_id)
        except AcademicBatch.DoesNotExist:
            return {"success": False, "error": f"Không tìm thấy đợt đồ án ID {batch_id}."}

        # 1. Fetch all students in batch
        students = list(Student.objects.filter(academic_batch=batch).select_related('course_class', 'user'))
        if not students:
            return {
                "success": True,
                "matched_count": 0,
                "unassigned_count": 0,
                "matched": [],
                "unassigned": [],
                "message": "Không có sinh viên nào trong đợt này."
            }

        # 2. Fetch all supervisor quotas in batch
        quotas = list(SupervisorQuota.objects.filter(batch=batch).select_related('supervisor__user'))
        if not quotas:
            return {
                "success": False,
                "error": "Chưa thiết lập định mức Quota cho giảng viên trong đợt này."
            }

        for q in quotas:
            if q.max_total_quota is None:
                q.calculate_capacity()
                q.save(update_fields=["max_total_quota"])

        # Fetch student preferences (NV1, NV2, NV3) or legacy internship info
        preferences = {pref.student_id: pref for pref in StudentPreference.objects.filter(batch=batch).select_related(
            'topic_direction', 'preference_1', 'preference_2', 'preference_3'
        )}
        surveys = {info.student_id: info for info in InternshipInfo.objects.filter(batch=batch).select_related(
            'topic_direction'
        )}

        # Bộ môn và độ tương thích chuyên môn
        dept_topic_affinity = {
            "CNPM": ["SOFTWARE_DEV", "SOFTWARE_TESTING", "GAME_DEV"],
            "MHTTT": ["NETWORK_INFRA", "CYBER_SECURITY", "SOFTWARE_DEV"],
            "Mạng&HTTT": ["NETWORK_INFRA", "CYBER_SECURITY", "SOFTWARE_DEV"],
            "KHMT": ["AI_DATA", "ALGORITHMS", "GAME_DEV", "SOFTWARE_DEV"],
            "Thỉnh giảng": ["AI_DATA", "SOFTWARE_DEV", "GAME_DEV"]
        }

        # Build MCMF Graph
        n_students = len(students)
        n_supervisors = len(quotas)
        source = 0
        sink = n_students + n_supervisors + 1
        num_nodes = sink + 1

        adj = [[] for _ in range(num_nodes)]

        def add_edge(u, v, cap, cost):
            forward = cls.Edge(v, cap, 0, cost, len(adj[v]))
            backward = cls.Edge(u, 0, 0, -cost, len(adj[u]))
            adj[u].append(forward)
            adj[v].append(backward)

        # 1. Edges Source -> Student
        for idx, student in enumerate(students, start=1):
            add_edge(source, idx, 1, 0)

        # 2. Edges Student -> Supervisor
        disqualified_pairs = 0
        for s_idx, student in enumerate(students, start=1):
            pref = preferences.get(student.id)
            survey = surveys.get(student.id)
            
            p1_id = pref.preference_1_id if pref else (survey.preferred_supervisor.id if survey and survey.preferred_supervisor else None)
            p2_id = pref.preference_2_id if pref else None
            p3_id = pref.preference_3_id if pref else None
            
            topic_code = ""
            if pref and pref.topic_direction:
                topic_code = pref.topic_direction.code
            elif survey and survey.topic_direction:
                topic_code = survey.topic_direction.code
            else:
                topic_code = "SOFTWARE_DEV"

            is_engineer = (student.education_program == "ENGINEER") or (batch.program_type == "ENGINEER")
            is_viet_anh = student.course_class and student.course_class.program_type == "VIET_ANH"

            for g_idx, q in enumerate(quotas, start=n_students + 1):
                sup = q.supervisor
                
                # Hard Constraint: Kiểm tra chương trình Kỹ sư -> Giảng viên phải đạt học vị tối thiểu (TS trở lên)
                if is_engineer and not sup.is_eligible_for_engineer():
                    disqualified_pairs += 1
                    continue # Bỏ qua cạnh này, không cho phép ghép nối

                dept = q.department or sup.department_name or ""
                cost = 0

                # Trọng số theo thứ tự nguyện vọng NV1 -> NV2 -> NV3
                if p1_id and p1_id == sup.id:
                    cost -= 120
                elif p2_id and p2_id == sup.id:
                    cost -= 70
                elif p3_id and p3_id == sup.id:
                    cost -= 40

                # Độ phù hợp theo hướng đề tài / bộ môn
                aff_topics = dept_topic_affinity.get(dept, [])
                if topic_code in aff_topics:
                    cost -= 30

                # Giảng viên cơ hữu ưu tiên hơn thỉnh giảng
                if dept != "Thỉnh giảng" and not sup.is_external:
                    cost -= 10

                # Ưu tiên lớp Việt - Anh nếu giảng viên có định mức VA
                if is_viet_anh and q.viet_anh_quota > 0:
                    cost -= 25

                add_edge(s_idx, g_idx, 1, cost)

        # 3. Edges Supervisor -> Sink
        for g_idx, q in enumerate(quotas, start=n_students + 1):
            rem_quota = max(0, q.max_total_quota)
            add_edge(g_idx, sink, rem_quota, 0)

        # SPFA / MCMF
        flow = 0
        total_cost = 0
        INF = float('inf')

        while True:
            dist = [INF] * num_nodes
            parent_node = [-1] * num_nodes
            parent_edge = [-1] * num_nodes
            in_queue = [False] * num_nodes

            dist[source] = 0
            queue = collections.deque([source])
            in_queue[source] = True

            while queue:
                u = queue.popleft()
                in_queue[u] = False

                for e_idx, edge in enumerate(adj[u]):
                    if edge.cap - edge.flow > 0 and dist[edge.to] > dist[u] + edge.cost:
                        dist[edge.to] = dist[u] + edge.cost
                        parent_node[edge.to] = u
                        parent_edge[edge.to] = e_idx
                        if not in_queue[edge.to]:
                            queue.append(edge.to)
                            in_queue[edge.to] = True

            if dist[sink] == INF:
                break

            push = INF
            curr = sink
            while curr != source:
                p = parent_node[curr]
                e = parent_edge[curr]
                push = min(push, adj[p][e].cap - adj[p][e].flow)
                curr = p

            curr = sink
            while curr != source:
                p = parent_node[curr]
                e = parent_edge[curr]
                rev_e = adj[p][e].rev
                adj[p][e].flow += push
                adj[curr][rev_e].flow -= push
                curr = p

            flow += push
            total_cost += push * dist[sink]

        # Trích xuất kết quả đề xuất
        matched_results = []
        unassigned_students = []

        with transaction.atomic():
            for s_idx, student in enumerate(students, start=1):
                matched_sup = None
                for edge in adj[s_idx]:
                    if edge.to > n_students and edge.to <= n_students + n_supervisors and edge.flow > 0:
                        q_idx = edge.to - (n_students + 1)
                        matched_sup = quotas[q_idx].supervisor
                        break

                pref = preferences.get(student.id)
                survey = surveys.get(student.id)
                topic_category = (pref.topic_direction if pref else None) or (survey.topic_direction if survey else None)
                tentative_title = (survey.tentative_title if survey else None) or f"Đề tài tốt nghiệp của {student.user.get_full_name() or student.registration_no}"

                if matched_sup:
                    existing_proj = GraduationProject.objects.filter(student=student).first()
                    if existing_proj:
                        # Nếu đồ án đã qua Giai đoạn 2 (đang thực hiện, bảo vệ, duyệt đề tài), bảo toàn trạng thái
                        if existing_proj.status not in ["IN_PROGRESS", "DEFENSE_READY", "DEFENSE_COMPLETED", "COMPLETED", "TOPIC_APPROVED"]:
                            existing_proj.supervisor = matched_sup
                            existing_proj.batch = batch
                            existing_proj.status = "ALLOCATED"
                            if topic_category and not existing_proj.topic_category:
                                existing_proj.topic_category = topic_category
                            if not existing_proj.topic_title_vi:
                                existing_proj.topic_title_vi = tentative_title
                            existing_proj.save()
                        proj = existing_proj
                    else:
                        proj = GraduationProject.objects.create(
                            student=student,
                            supervisor=matched_sup,
                            batch=batch,
                            topic_category=topic_category,
                            topic_title_vi=tentative_title,
                            status="ALLOCATED",
                            topic_review_status="DRAFT"
                        )
                    
                    matched_results.append({
                        "student_id": student.id,
                        "student_name": student.user.get_full_name() or student.user.username,
                        "registration_no": student.registration_no,
                        "education_program": student.education_program,
                        "supervisor_id": matched_sup.id,
                        "supervisor_name": f"{matched_sup.academic_title or ''} {matched_sup.user.get_full_name()}".strip(),
                        "academic_title": matched_sup.academic_title or "",
                        "department": matched_sup.department_name,
                        "project_id": proj.id
                    })
                else:
                    reason = "Vượt quá chỉ tiêu Quota của các Giảng viên phù hợp."
                    if (student.education_program == "ENGINEER" or batch.program_type == "ENGINEER"):
                        reason += " Lưu ý: SV hệ Kỹ sư yêu cầu GVHD có học vị tối thiểu là Tiến sĩ (TS)."

                    unassigned_students.append({
                        "student_id": student.id,
                        "student_name": student.user.get_full_name() or student.user.username,
                        "registration_no": student.registration_no,
                        "education_program": student.education_program,
                        "reason": reason
                    })

            # Cập nhật số lượng đã phân công
            for q in quotas:
                actual_assigned = GraduationProject.objects.filter(batch=batch, supervisor=q.supervisor).count()
                q.current_assigned = actual_assigned
                q.save(update_fields=["current_assigned"])

            # Cập nhật trạng thái đợt sang Giai đoạn 2
            if batch.current_stage == "PHASE_1_SETUP":
                batch.current_stage = "PHASE_2_ALLOCATING"
                batch.save(update_fields=["current_stage"])

        return {
            "success": True,
            "matched_count": len(matched_results),
            "unassigned_count": len(unassigned_students),
            "matched": matched_results,
            "unassigned": unassigned_students,
            "total_students": len(students)
        }

    @classmethod
    def finalize_allocation(cls, batch_id, user=None):
        """Khoa chốt phân công đề tài (Bước 17)"""
        batch = AcademicBatch.objects.get(id=batch_id)
        batch.current_stage = "PHASE_2_LOCKED"
        batch.save(update_fields=["current_stage"])

        if user:
            AuditLog.objects.create(
                user=user,
                action_type="supervisor_request_update",
                description=f"Khoa đã chốt phân công giảng viên hướng dẫn cho Đợt {batch.batch_code}."
            )
        return {"success": True, "message": "Đã chốt danh sách phân công GVHD thành công."}

    @classmethod
    def publish_and_notify_allocation(cls, batch_id, user=None):
        """Công bố và gửi email kết quả phân công (GĐ 1 yeucau.md)"""
        batch = AcademicBatch.objects.get(id=batch_id)
        batch.is_allocation_published = True
        batch.allocation_published_at = timezone.now()
        batch.current_stage = "PHASE_3_TOPIC"
        batch.save(update_fields=["is_allocation_published", "allocation_published_at", "current_stage"])

        # 1. Gửi email thông báo tự động theo quy định GĐ 1
        from .email_service import EmailNotificationService
        email_res = EmailNotificationService.send_assignment_finalized_emails(batch_id)
        emails_sent = email_res.get("emails_sent", 0)

        # 2. Tạo bản ghi Notification thông báo trong hệ thống cho toàn bộ SV và GVHD
        from app.models import Notification, GraduationProject
        projects = GraduationProject.objects.filter(batch=batch).select_related("student__user", "supervisor__user")
        notif_count = 0
        for p in projects:
            if p.student and p.student.user:
                Notification.objects.create(
                    user=p.student.user,
                    title="Thông báo Phân công Giảng viên hướng dẫn",
                    message=f"Bạn đã được phân công Giảng viên hướng dẫn: {p.supervisor}. Vui lòng đăng ký tên và mục tiêu đề tài (Giai đoạn 2).",
                    notification_type="allocation"
                )
                notif_count += 1
            if p.supervisor and p.supervisor.user:
                Notification.objects.create(
                    user=p.supervisor.user,
                    title="Thông báo Danh sách Sinh viên hướng dẫn",
                    message=f"Sinh viên {p.student.user.get_full_name()} (MSSV: {p.student.registration_no}) đã được phân công vào danh sách hướng dẫn của bạn.",
                    notification_type="allocation"
                )
                notif_count += 1

        if user:
            AuditLog.objects.create(
                user=user,
                action_type="group_status_change",
                description=f"Khoa đã công bố và phát lệnh thông báo kết quả phân công cho Đợt {batch.batch_code}. Đã gửi {emails_sent} emails và {notif_count} thông báo."
            )
        return {
            "success": True,
            "emails_sent": emails_sent,
            "notifications_created": notif_count,
            "message": f"Đã công bố và gửi email thông báo kết quả phân công thành công ({emails_sent} email đã phát lệnh, {notif_count} thông báo hệ thống)."
        }

