import datetime
from django.db import transaction
from app.models import (
    AcademicBatch,
    DefenseCouncil,
    GraduationProject,
    DefenseScheduleSlot,
    AuditLog
)

class DefenseSchedulerEngine:
    """
    Tự động xếp lịch bảo vệ chi tiết (Bước 41):
    Dựa trên tham số Khoa nhập: Ngày bảo vệ, thời lượng mỗi đồ án (phút), ca sáng/chiều, phòng bảo vệ.
    Hệ thống phân bổ thứ tự và khung giờ bảo vệ chi tiết cho từng sinh viên trong mỗi Hội đồng.
    """

    @classmethod
    def schedule_defense_for_batch(
        cls,
        batch_id,
        slot_duration_minutes=40,
        morning_start_str="08:00",
        afternoon_start_str="13:30",
        user=None
    ):
        try:
            batch = AcademicBatch.objects.get(id=batch_id)
        except AcademicBatch.DoesNotExist:
            return {"success": False, "error": f"Không tìm thấy đợt ID {batch_id}."}

        councils = DefenseCouncil.objects.filter(batch=batch).order_by("council_number")
        if not councils.exists():
            return {"success": False, "error": "Chưa có Hội đồng bảo vệ nào được thành lập trong đợt này."}

        scheduled_slots = []
        total_projects = 0

        with transaction.atomic():
            # Xóa các slot cũ trước khi xếp lại
            DefenseScheduleSlot.objects.filter(council__batch=batch).delete()

            for council in councils:
                projects = list(GraduationProject.objects.filter(
                    council=council,
                    is_eligible_for_defense=True
                ).exclude(deferral_status="APPROVED").exclude(status__in=["DEFERRED", "DISQUALIFIED", "FAILED"]).order_by("student__registration_no"))

                if not projects:
                    continue

                session_date = council.session_date or batch.start_date or datetime.date.today()
                is_afternoon = (council.session_time == "AFTERNOON")

                # Khởi tạo giờ bắt đầu
                start_hour_str = afternoon_start_str if is_afternoon else morning_start_str
                cur_h, cur_m = map(int, start_hour_str.split(":"))
                cur_time = datetime.time(hour=cur_h, minute=cur_m)

                for idx, proj in enumerate(projects, start=1):
                    # Tính giờ kết thúc
                    start_dt = datetime.datetime.combine(session_date, cur_time)
                    end_dt = start_dt + datetime.timedelta(minutes=slot_duration_minutes)
                    end_time = end_dt.time()

                    slot = DefenseScheduleSlot.objects.create(
                        council=council,
                        project=proj,
                        order_number=idx,
                        slot_date=session_date,
                        start_time=cur_time,
                        end_time=end_time,
                        room=council.defense_room or f"P.{council.council_number:02d}"
                    )

                    scheduled_slots.append({
                        "council_id": council.id,
                        "council_name": council.council_name,
                        "order": idx,
                        "student_name": proj.student.user.get_full_name(),
                        "registration_no": proj.student.registration_no,
                        "topic_title": proj.topic_title_vi,
                        "slot_date": str(session_date),
                        "start_time": cur_time.strftime("%H:%M"),
                        "end_time": end_time.strftime("%H:%M"),
                        "room": slot.room
                    })

                    # Chuẩn bị cho đồ án tiếp theo
                    cur_time = end_time
                    total_projects += 1

            if user:
                AuditLog.objects.create(
                    user=user,
                    action_type="group_status_change",
                    description=f"Khoa đã chạy thuật toán tự động xếp lịch bảo vệ cho Đợt #{batch_id}: Tổng cộng {total_projects} đồ án."
                )

        return {
            "success": True,
            "total_councils": councils.count(),
            "scheduled_projects_count": total_projects,
            "scheduled_slots_count": total_projects,
            "slots": scheduled_slots
        }
