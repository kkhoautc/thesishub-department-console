from django.db import transaction
from django.db.models import Q
from app.models import (
    GraduationProject,
    DefenseCouncil,
    CouncilMember,
    Supervisor,
    AcademicBatch,
    AuditLog
)

class ReviewerAndCouncilAllocationEngine:
    """
    Phân bổ Đề tài vào Hội đồng bảo vệ và gán Giảng viên phản biện (Bước 40)
    
    RÀNG BUỘC CỨNG (Hard Constraints):
    1. Giảng viên phản biện != Giảng viên hướng dẫn (so sánh cả Supervisor ID và CustomUser ID).
    2. Giảng viên hướng dẫn TUYỆT ĐỐI KHÔNG được là thành viên của Hội đồng chấm sinh viên của mình.
    3. Giảng viên phản biện BẮT BUỘC phải là thành viên trong Hội đồng được phân công.
    4. Chỉ phân bổ vào các Hội đồng hợp lệ (đã được thêm thành viên và có giảng viên đủ điều kiện làm phản biện).
    
    RÀNG BUỘC MỀM (Soft Constraints - Tối ưu hóa đa mục tiêu):
    1. Cân bằng tải số lượng sinh viên giữa các Hội đồng hợp lệ.
    2. Cân bằng tải số lượng bài phản biện giữa các thành viên trong Hội đồng.
    3. Heuristic Most-Constrained First: Đồ án có GVHD nằm trong nhiều Hội đồng nhất được ưu tiên xếp trước để tránh bế tắc.
    """

    @classmethod
    def assign_councils_and_reviewers(cls, batch_id):
        try:
            batch = AcademicBatch.objects.get(id=batch_id)
        except AcademicBatch.DoesNotExist:
            return {"success": False, "error": f"Không tìm thấy đợt ID {batch_id}."}

        from django.db.models import Q
        # 1. Điều kiện đầu vào (GĐ 5 yeucau.md): Chỉ những SV Đủ điều kiện bảo vệ (ở GĐ 4: nợ 0 TC hoặc đặc cách) mới được đưa vào danh sách lập HĐ
        projects = list(
            GraduationProject.objects.filter(batch=batch)
            .filter(
                Q(is_eligible_for_defense=True) |
                Q(status="DEFENSE_READY") |
                (Q(debt_credits=0) & ~Q(initial_eligibility="INELIGIBLE") & ~Q(final_academic_eligibility="INELIGIBLE"))
            )
            .exclude(deferral_status="APPROVED")
            .exclude(status__in=["DEFERRED", "DISQUALIFIED", "FAILED"])
            .select_related("student__user", "supervisor__user", "topic_category")
        )

        if not projects:
            return {"success": False, "error": "Không có đề tài đồ án nào đủ điều kiện bảo vệ (ở Giai đoạn 4) để phân hội đồng trong đợt này."}

        # 2. Lấy danh sách tất cả Hội đồng trong đợt
        all_councils = list(
            DefenseCouncil.objects.filter(batch=batch)
            .prefetch_related("members__supervisor__user", "members__user")
            .order_by("council_number")
        )

        if not all_councils:
            return {"success": False, "error": "Chưa thành lập bất kỳ Hội đồng bảo vệ nào cho đợt này."}

        # 3. Lọc các Hội đồng HỢP LỆ (có ít nhất 1 thành viên và có ít nhất 1 giảng viên phản biện)
        valid_councils = []
        ignored_councils = []

        council_member_sup_ids = {}
        council_member_user_ids = {}
        council_reviewers = {}

        for c in all_councils:
            members = list(c.members.all())
            if not members:
                ignored_councils.append(f"{c.council_name} (chưa có thành viên)")
                continue

            sup_ids = set()
            user_ids = set()
            rev_candidates = []

            for m in members:
                user_ids.add(m.user_id)
                # Tìm supervisor tương ứng (hỗ trợ cả liên kết trực tiếp và ngược từ User)
                spv = m.supervisor or getattr(m.user, "supervisor_profile", None)
                if spv:
                    sup_ids.add(spv.id)
                    user_ids.add(spv.user_id)
                    if spv not in rev_candidates:
                        rev_candidates.append(spv)

            if not rev_candidates:
                ignored_councils.append(f"{c.council_name} (chưa có giảng viên có thể phản biện)")
                continue

            council_member_sup_ids[c.id] = sup_ids
            council_member_user_ids[c.id] = user_ids
            council_reviewers[c.id] = rev_candidates
            valid_councils.append(c)

        if not valid_councils:
            ignored_desc = ", ".join(ignored_councils)
            return {
                "success": False,
                "error": f"Không có Hội đồng nào đủ điều kiện hoạt động ({ignored_desc}). Vui lòng bổ sung thành viên trước khi phân bổ."
            }

        # 4. Xác định các Hội đồng đã bị khóa (is_finalized)
        locked_council_ids = {c.id for c in valid_councils if c.is_finalized}

        council_assigned_projects = {c.id: [] for c in valid_councils}
        reviewer_load = {}

        projects_to_assign = []
        for proj in projects:
            if proj.council_id in locked_council_ids:
                council_assigned_projects[proj.council_id].append(proj)
                if proj.reviewer_id:
                    reviewer_load[proj.reviewer_id] = reviewer_load.get(proj.reviewer_id, 0) + 1
            else:
                projects_to_assign.append(proj)

        # 5. Heuristic Most-Constrained First: Ưu tiên xếp các đồ án có ít lựa chọn Hội đồng trước
        def count_available_councils(proj):
            spv_id = proj.supervisor_id
            spv_user_id = proj.supervisor.user_id if proj.supervisor else None
            count = 0
            for c in valid_councils:
                has_conflict = False
                if spv_id and spv_id in council_member_sup_ids[c.id]:
                    has_conflict = True
                elif spv_user_id and spv_user_id in council_member_user_ids[c.id]:
                    has_conflict = True
                if not has_conflict:
                    if any(r.id != spv_id and r.user_id != spv_user_id for r in council_reviewers[c.id]):
                        count += 1
            return count

        projects_to_assign.sort(key=count_available_councils)

        # 6. Tiến hành phân bổ từng đồ án vào Hội đồng và chọn GVPB tối ưu
        assigned_count = 0
        unassigned_count = 0
        conflicts = []
        assignments = []

        for proj in projects_to_assign:
            spv_id = proj.supervisor_id
            spv_user_id = proj.supervisor.user_id if proj.supervisor else None
            spv_name = proj.supervisor.user.get_full_name() if proj.supervisor else "Chưa gán GVHD"

            eligible_councils_with_reviewers = []
            for c in valid_councils:
                # Ràng buộc cứng: GVHD không được là thành viên của Hội đồng
                is_spv_in_council = False
                if spv_id and spv_id in council_member_sup_ids[c.id]:
                    is_spv_in_council = True
                elif spv_user_id and spv_user_id in council_member_user_ids[c.id]:
                    is_spv_in_council = True

                if is_spv_in_council:
                    continue

                # Ràng buộc cứng: Giảng viên phản biện != GVHD và nằm trong Hội đồng này
                valid_revs = [
                    r for r in council_reviewers[c.id]
                    if r.id != spv_id and (spv_user_id is None or r.user_id != spv_user_id)
                ]

                if not valid_revs:
                    continue

                # Chọn phản biện có tải thấp nhất trong Hội đồng
                valid_revs.sort(key=lambda r: reviewer_load.get(r.id, 0))
                best_rev_for_c = valid_revs[0]
                min_rev_load = reviewer_load.get(best_rev_for_c.id, 0)

                eligible_councils_with_reviewers.append({
                    "council": c,
                    "reviewer": best_rev_for_c,
                    "council_load": len(council_assigned_projects[c.id]),
                    "reviewer_load": min_rev_load
                })

            if eligible_councils_with_reviewers:
                # Sắp xếp chọn Hội đồng ít tải nhất, sau đó đến Reviewer ít tải nhất
                eligible_councils_with_reviewers.sort(
                    key=lambda x: (x["council_load"], x["reviewer_load"])
                )

                chosen = eligible_councils_with_reviewers[0]
                chosen_council = chosen["council"]
                chosen_rev = chosen["reviewer"]

                council_assigned_projects[chosen_council.id].append(proj)
                reviewer_load[chosen_rev.id] = reviewer_load.get(chosen_rev.id, 0) + 1

                proj.council = chosen_council
                proj.reviewer = chosen_rev
                assigned_count += 1

                assignments.append({
                    "project_id": proj.id,
                    "student_name": proj.student.user.get_full_name(),
                    "registration_no": proj.student.registration_no,
                    "topic_title": proj.topic_title_vi,
                    "supervisor": spv_name,
                    "council_name": chosen_council.council_name,
                    "reviewer": f"{chosen_rev.academic_title or ''} {chosen_rev.user.get_full_name()}".strip()
                })
            else:
                # Không có Hội đồng nào hợp lệ -> Reset sạch để không giữ tàn dư xung đột cũ
                proj.council = None
                proj.reviewer = None
                unassigned_count += 1

                councils_with_spv = [
                    c.council_name for c in valid_councils
                    if (spv_id and spv_id in council_member_sup_ids[c.id]) or
                       (spv_user_id and spv_user_id in council_member_user_ids[c.id])
                ]

                if len(councils_with_spv) == len(valid_councils):
                    reason = (
                        f"GVHD ({spv_name}) là thành viên của tất cả {len(valid_councils)} Hội đồng hiện có "
                        f"({', '.join(councils_with_spv)}). Cần thành lập thêm Hội đồng khác hoặc hoán đổi thành viên để chấm chéo."
                    )
                elif councils_with_spv:
                    reason = (
                        f"GVHD ({spv_name}) tham gia các Hội đồng: {', '.join(councils_with_spv)}. "
                        f"Các Hội đồng còn lại không có Giảng viên phản biện hợp lệ."
                    )
                else:
                    reason = "Không có Hội đồng nào còn Giảng viên phản biện hợp lệ cho đề tài này."

                conflicts.append({
                    "project_id": proj.id,
                    "student_name": proj.student.user.get_full_name(),
                    "registration_no": proj.student.registration_no,
                    "supervisor_name": spv_name,
                    "reason": reason
                })

        # 7. Lưu tất cả thay đổi vào CSDL trong một transaction
        with transaction.atomic():
            for proj in projects_to_assign:
                proj.save(update_fields=["council", "reviewer"])

        return {
            "success": True,
            "total_projects": len(projects),
            "assigned_count": assigned_count,
            "unassigned_count": unassigned_count,
            "valid_councils_count": len(valid_councils),
            "ignored_councils": ignored_councils,
            "conflicts": conflicts,
            "assignments": assignments
        }

    @classmethod
    def manual_override_reviewer(cls, project_id, council_id, reviewer_id, user=None):
        """Khoa điều chỉnh thủ công Hội đồng & Giảng viên phản biện cho sinh viên"""
        project = GraduationProject.objects.get(id=project_id)
        council = DefenseCouncil.objects.filter(id=council_id).first() if council_id else None
        reviewer = Supervisor.objects.filter(id=reviewer_id).first() if reviewer_id else None

        if reviewer and project.supervisor_id == reviewer.id:
            return {"success": False, "error": "Giảng viên phản biện không được trùng với Giảng viên hướng dẫn!"}

        if council:
            # Kiểm tra ràng buộc cứng: GVHD không được là thành viên của Hội đồng
            if project.supervisor:
                is_spv_in_council = (
                    council.members.filter(supervisor=project.supervisor).exists() or
                    council.members.filter(user=project.supervisor.user).exists()
                )
                if is_spv_in_council:
                    return {
                        "success": False,
                        "error": f"Xung đột lợi ích: GVHD ({project.supervisor.user.get_full_name()}) là thành viên của {council.council_name}!"
                    }

            if reviewer:
                # Kiểm tra xem GV phản biện có nằm trong hội đồng này không
                is_member = (
                    council.members.filter(supervisor=reviewer).exists() or
                    council.members.filter(user=reviewer.user).exists()
                )
                if not is_member:
                    return {
                        "success": False,
                        "error": f"Giảng viên phản biện {reviewer.user.get_full_name()} không thuộc {council.council_name}."
                    }

        project.council = council
        project.reviewer = reviewer
        project.save(update_fields=["council", "reviewer"])

        if user:
            AuditLog.objects.create(
                user=user,
                action_type="evaluation_update",
                description=f"Khoa đã điều chỉnh thủ công HĐ/Phản biện cho SV {project.student.registration_no}."
            )

        return {"success": True, "message": "Điều chỉnh thủ công Hội đồng & Phản biện thành công."}
