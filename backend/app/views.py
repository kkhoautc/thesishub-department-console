import logging
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.cache import cache

from django.conf import settings

BATCHES_CACHE_KEY = "admin_academic_batches_list"
USER_SUMMARY_CACHE_KEY = "admin_users_summary_cache"
SECURITY_METRICS_CACHE_KEY = "admin_security_metrics_cache"

def invalidate_user_summary_cache():
    cache.delete(USER_SUMMARY_CACHE_KEY)
    cache.delete(SECURITY_METRICS_CACHE_KEY)
from .models import (
    CustomUser,
    AuditLog,
    AcademicBatch,
    CourseClass,
    Department,
    Student,
    Supervisor,
    SupervisorQuota,
    ProjectTopicArea,
    StudentPreference,
    GraduationProject,
    DefenseCouncil,
    CouncilMember,
    DefenseScheduleSlot,
    FinalGradeSummary,
    EvaluationPolicy
)
from .permissions import IsAdminUserRole
from .serializers import (
    AdminUserSerializer,
    AdminRegisterSerializer,
    AdminCreateUserSerializer,
    AdminResetPasswordSerializer,
    AuditLogSerializer,
    AcademicBatchSerializer,
    CourseClassSerializer,
    DepartmentSerializer,
    SupervisorQuotaSerializer,
    SupervisorDetailSerializer,
    DefenseCouncilSerializer,
    DefenseScheduleSlotSerializer,
    GraduationProjectAdminSerializer
)
from .services.excel_importer import ExcelImportService, generate_random_password
from .services.allocation_engine import MinCostMaxFlowAllocationEngine
from .services.reviewer_engine import ReviewerAndCouncilAllocationEngine
from .services.document_generator import DocumentGenerationService
from .services.defense_scheduler import DefenseSchedulerEngine

logger = logging.getLogger(__name__)

def set_refresh_cookie(response, refresh_token):
    is_production = not getattr(settings, "DEBUG", True)
    is_secure = is_production and getattr(settings, "SESSION_COOKIE_SECURE", True)
    response.set_cookie(
        key="refresh_token",
        value=str(refresh_token),
        httponly=True,
        secure=is_secure,
        samesite="None" if is_secure else "Lax",
        path="/",
        max_age=7 * 24 * 3600,
    )
    return response


def delete_refresh_cookie(response):
    is_production = not getattr(settings, "DEBUG", True)
    is_secure = is_production and getattr(settings, "SESSION_COOKIE_SECURE", True)
    response.delete_cookie(
        key="refresh_token",
        path="/",
        samesite="None" if is_secure else "Lax",
    )
    return response


from .utils.db_helpers import safe_create_user, fix_all_postgres_sequences


class AdminRegisterAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AdminRegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        admin_secret = serializer.validated_data["admin_secret"]
        configured_secret = getattr(settings, "ADMIN_REGISTRATION_SECRET", "")
        if not configured_secret or admin_secret != configured_secret:
            return Response(
                {"detail": "Forbidden: Invalid Admin Registration Secret Key."},
                status=status.HTTP_403_FORBIDDEN
            )

        username = serializer.validated_data["username"].strip()
        email = serializer.validated_data["email"].strip().lower()

        if CustomUser.objects.filter(username=username).exists():
            return Response({"username": ["A user with that username already exists."]}, status=status.HTTP_400_BAD_REQUEST)
        if CustomUser.objects.filter(email=email).exists():
            return Response({"email": ["A user with that email already exists."]}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = safe_create_user(
                username=username,
                email=email,
                password=serializer.validated_data["password"],
                first_name="",
                last_name="",
                user_type="admin",
                is_staff=True,
                is_superuser=True,
                is_active=True
            )

            try:
                AuditLog.objects.create(
                    user=user,
                    action_type="admin_user_update",
                    description=f"Admin registered user '{username}'."
                )
            except Exception as log_err:
                logger.warning(f"Could not create audit log on registration: {log_err}")

            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)

            response = Response({
                "access": access_token,
                "user": AdminUserSerializer(user).data,
                "message": "Admin registration successful."
            }, status=status.HTTP_201_CREATED)

            return set_refresh_cookie(response, refresh)
        except Exception as ex:
            logger.exception("Admin registration failed")
            return Response({
                "detail": f"Đăng ký tài khoản Admin thất bại: {str(ex)}",
                "error": str(ex)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdminLoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        from django.core.cache import cache
        identifier = (request.data.get("username") or request.data.get("email") or "").strip()
        password = request.data.get("password", "")

        if not identifier or not password:
            return Response({"detail": "Username/email and password are required."}, status=status.HTTP_400_BAD_REQUEST)

        lock_key = f"login_lock_{identifier}"
        if cache.get(lock_key):
            return Response({"detail": "Tài khoản tạm khóa 15 phút do nhập sai mật khẩu quá 3 lần."}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        fail_key = f"login_fail_{identifier}"
        fail_count = cache.get(fail_key, 0)

        user = CustomUser.objects.filter(Q(username__iexact=identifier) | Q(email__iexact=identifier)).first()
        if not user or not user.check_password(password):
            fail_count += 1
            if fail_count >= 3:
                cache.set(lock_key, True, 15 * 60)  # 15 minutes
                cache.delete(fail_key)
                if user:
                    AuditLog.objects.create(
                        user=user,
                        action_type="SECURITY_ALERT",
                        description=f"Tài khoản bị khóa 15 phút do nhập sai mật khẩu 3 lần."
                    )
                return Response({"detail": "Tài khoản tạm khóa 15 phút do nhập sai mật khẩu quá 3 lần."}, status=status.HTTP_429_TOO_MANY_REQUESTS)
            
            cache.set(fail_key, fail_count, 15 * 60)
            return Response({"detail": f"Sai thông tin đăng nhập. Bạn còn {3 - fail_count} lần thử trước khi bị khóa."}, status=status.HTTP_401_UNAUTHORIZED)

        # Successful login, reset fail count
        cache.delete(fail_key)

        # Upgrade legacy MD5 hash to standard PBKDF2 on successful login
        if user.password.startswith('md5$'):
            user.set_password(password)
            user.save(update_fields=['password'])

        if not user.is_active:
            return Response({"detail": "Account is disabled."}, status=status.HTTP_403_FORBIDDEN)

        if not (user.is_staff or user.is_superuser or user.user_type in ["admin", "academic_staff"]):
            return Response({"detail": "Forbidden: You do not have admin or academic staff access privileges."}, status=status.HTTP_403_FORBIDDEN)

        if user.user_type not in ["admin", "academic_staff"] and (user.is_staff or user.is_superuser):
            user.user_type = "admin"
            user.save(update_fields=["user_type"])

        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        AuditLog.objects.create(
            user=user,
            action_type="admin_user_update",
            description=f"Admin '{user.username}' logged in successfully."
        )

        response = Response({
            "access": access_token,
            "user_type": user.user_type,
            "user": AdminUserSerializer(user).data
        }, status=status.HTTP_200_OK)

        return set_refresh_cookie(response, refresh)



class AdminCookieTokenRefreshAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.COOKIES.get("refresh_token")
        if not refresh_token:
            return Response({"detail": "No refresh token cookie found."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            refresh = RefreshToken(refresh_token)
            user_id = refresh.payload.get("user_id")
            user = CustomUser.objects.filter(id=user_id).first()

            if not user or not user.is_active or not (user.is_staff or user.is_superuser or user.user_type in ["admin", "academic_staff"]):
                response = Response({"detail": "Invalid session or unauthorized."}, status=status.HTTP_403_FORBIDDEN)
                return delete_refresh_cookie(response)

            access_token = str(refresh.access_token)
            return Response({
                "access": access_token,
                "user_type": user.user_type,
                "user": AdminUserSerializer(user).data
            }, status=status.HTTP_200_OK)
        except Exception:
            response = Response({"detail": "Token expired or invalid."}, status=status.HTTP_401_UNAUTHORIZED)
            return delete_refresh_cookie(response)


class AdminCookieLogoutAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        response = Response({"message": "Logged out successfully."}, status=status.HTTP_200_OK)
        return delete_refresh_cookie(response)


class AdminUserManagementAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def get(self, request):
        summary_only = str(request.query_params.get("summary_only", "")).lower() in ["true", "1"]
        if summary_only:
            cached_summary = cache.get(USER_SUMMARY_CACHE_KEY)
            if cached_summary is not None:
                res = Response(cached_summary, status=status.HTTP_200_OK)
                res["Cache-Control"] = "private, max-age=60"
                return res

        # Fast aggregated counts in a single query (10x faster over network)
        user_counts = CustomUser.objects.aggregate(
            total_students=Count('id', filter=Q(user_type="student")),
            total_supervisors=Count('id', filter=Q(user_type="supervisor")),
            total_committee=Count('id', filter=Q(user_type="committee_member")),
            total_external=Count('id', filter=Q(user_type="external_examiner")),
            total_admins=Count('id', filter=Q(user_type="admin")),
            total_academic_staff=Count('id', filter=Q(user_type="academic_staff")),
            total_active=Count('id', filter=Q(is_active=True)),
            total_deactivated=Count('id', filter=Q(is_active=False)),
        )
        total_students = user_counts["total_students"] or 0
        total_supervisors = user_counts["total_supervisors"] or 0
        total_committee = user_counts["total_committee"] or 0
        total_external = user_counts["total_external"] or 0
        total_admins = user_counts["total_admins"] or 0
        total_academic_staff = user_counts["total_academic_staff"] or 0
        total_active = user_counts["total_active"] or 0
        total_deactivated = user_counts["total_deactivated"] or 0

        # Major counts
        khmt_students_count = Student.objects.filter(
            Q(course_class__program_type="KHMT") | Q(department__icontains="Khoa học máy tính") | Q(department__icontains="KHMT")
        ).count()
        cntt_students_count = max(0, total_students - khmt_students_count)

        all_total = total_students + total_supervisors + total_committee + total_external + total_admins + total_academic_staff

        if summary_only:
            summary_data = {
                "users": [],
                "total": all_total,
                "counts": {
                    "total": all_total,
                    "active": total_active,
                    "deactivated": total_deactivated,
                    "students": total_students,
                    "supervisors": total_supervisors,
                    "committee": total_committee,
                    "external": total_external,
                    "admins": total_admins,
                    "academic_staff": total_academic_staff,
                    "cntt_students": cntt_students_count,
                    "khmt_students": khmt_students_count,
                }
            }
            cache.set(USER_SUMMARY_CACHE_KEY, summary_data, 60)
            res = Response(summary_data, status=status.HTTP_200_OK)
            res["Cache-Control"] = "private, max-age=60"
            return res

        users = CustomUser.objects.all().select_related(
            "student_profile",
            "student_profile__course_class",
            "student_profile__academic_batch",
            "student_profile__graduation_project",
            "student_profile__graduation_project__supervisor",
            "student_profile__graduation_project__supervisor__user",
            "supervisor_profile",
            "academic_staff_profile",
            "academic_staff_profile__department"
        ).prefetch_related(
            "council_roles",
            "supervisor_profile__quotas"
        ).order_by("-id")

        # Filters
        user_type = request.query_params.get("user_type") or request.query_params.get("role")
        major = request.query_params.get("major")
        program_type = request.query_params.get("program_type")
        class_id = request.query_params.get("class_id")
        batch_id = request.query_params.get("batch_id")
        supervisor_id = request.query_params.get("supervisor_id")
        has_supervisor = request.query_params.get("has_supervisor")
        is_active = request.query_params.get("is_active")
        search = (request.query_params.get("search") or request.query_params.get("q") or "").strip()

        if user_type:
            users = users.filter(user_type=user_type)

        if major:
            if major.upper() == "KHMT":
                users = users.filter(
                    Q(student_profile__course_class__program_type="KHMT") |
                    Q(student_profile__department__icontains="Khoa học máy tính") |
                    Q(student_profile__department__icontains="KHMT")
                )
            elif major.upper() == "CNTT":
                users = users.exclude(
                    Q(student_profile__course_class__program_type="KHMT") |
                    Q(student_profile__department__icontains="Khoa học máy tính") |
                    Q(student_profile__department__icontains="KHMT")
                )

        if program_type:
            users = users.filter(student_profile__course_class__program_type=program_type)

        if class_id:
            users = users.filter(student_profile__course_class_id=class_id)

        if batch_id:
            users = users.filter(
                Q(student_profile__academic_batch_id=batch_id) |
                Q(supervisor_profile__quotas__batch_id=batch_id)
            ).distinct()

        if supervisor_id:
            if supervisor_id == "unassigned":
                users = users.filter(student_profile__graduation_project__supervisor__isnull=True)
            else:
                users = users.filter(student_profile__graduation_project__supervisor_id=supervisor_id)

        if has_supervisor is not None and has_supervisor != "":
            if str(has_supervisor).lower() in ["true", "1"]:
                users = users.filter(student_profile__graduation_project__supervisor__isnull=False)
            elif str(has_supervisor).lower() in ["false", "0"]:
                users = users.filter(student_profile__graduation_project__supervisor__isnull=True)

        if is_active is not None and is_active != "":
            if str(is_active).lower() in ["true", "1"]:
                users = users.filter(is_active=True)
            elif str(is_active).lower() in ["false", "0"]:
                users = users.filter(is_active=False)

        if search:
            users = users.filter(
                Q(username__icontains=search) |
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(student_profile__registration_no__icontains=search) |
                Q(student_profile__department__icontains=search) |
                Q(student_profile__phone_number__icontains=search) |
                Q(supervisor_profile__supervisor_id__icontains=search) |
                Q(supervisor_profile__department_name__icontains=search) |
                Q(supervisor_profile__academic_title__icontains=search) |
                Q(council_roles__external_institution__icontains=search) |
                Q(council_roles__council__council_name__icontains=search)
            ).distinct()

        sort_by = request.query_params.get("sort_by") or request.query_params.get("sort")
        order = request.query_params.get("order") or request.query_params.get("dir", "asc")

        users_list = list(users)
        if sort_by in ["name", "vietnamese_name", "full_name"]:
            from .utils.vietnamese_sort import sort_by_vietnamese_name
            def extract_sort_name(u):
                if u.last_name and u.first_name:
                    return f"{u.last_name} {u.first_name}".strip()
                return u.get_full_name() or u.username or ""
            users_list = sort_by_vietnamese_name(users_list, key_extractor=extract_sort_name)
            if order.lower() == "desc":
                users_list.reverse()

        total_matched = len(users_list)
        serializer = AdminUserSerializer(users_list, many=True)
        return Response({
            "users": serializer.data,
            "total": total_matched,
            "counts": {
                "total": total_students + total_supervisors + total_committee + total_external + total_admins,
                "active": total_active,
                "deactivated": total_deactivated,
                "students": total_students,
                "supervisors": total_supervisors,
                "committee": total_committee,
                "external": total_external,
                "admins": total_admins,
                "cntt_students": cntt_students_count,
                "khmt_students": khmt_students_count,
            }
        }, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = AdminCreateUserSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        user_type = data["user_type"]
        username = data["username"].strip()
        first_name = data.get("first_name", "").strip()
        last_name = data.get("last_name", "").strip()
        phone_number = data.get("phone_number", "").strip()
        is_active = data.get("is_active", True)
        password_strategy = data.get("password_strategy", "MSSV")
        custom_password = data.get("custom_password", "").strip()

        # Check duplicate username
        if CustomUser.objects.filter(username=username).exists():
            return Response({"username": ["Tên đăng nhập này đã tồn tại."]}, status=status.HTTP_400_BAD_REQUEST)

        # Determine password
        if password_strategy == "FIXED" and custom_password:
            plain_password = custom_password
        elif password_strategy == "CUSTOM" and custom_password:
            plain_password = custom_password
        elif password_strategy == "RANDOM":
            plain_password = generate_random_password(8)
        elif data.get("password"):
            plain_password = data["password"]
        else:
            # Default MSSV or username
            plain_password = data.get("registration_no") or username

        # Determine email
        email = data.get("email", "").strip().lower()
        if not email:
            if user_type == "student":
                reg_no = data.get("registration_no") or username
                email = f"{reg_no.lower()}@lms.utc.edu.vn"
            else:
                email = f"{username.lower()}@utc.edu.vn"

        if CustomUser.objects.filter(email=email).exists():
            return Response({"email": ["Email này đã được sử dụng bởi tài khoản khác."]}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            user = safe_create_user(
                username=username,
                email=email,
                password=plain_password,
                first_name=first_name,
                last_name=last_name,
                user_type=user_type,
                is_active=is_active,
                is_staff=True if user_type == "admin" else False,
                is_superuser=True if user_type == "admin" else False
            )

            # Handle Student Profile
            if user_type == "student":
                reg_no = data.get("registration_no") or username
                class_name = data.get("class_name", "").strip()
                program_type = data.get("program_type", "DAI_TRA")
                course_class_id = data.get("course_class_id")
                academic_batch_id = data.get("academic_batch_id")

                course_class = None
                if course_class_id:
                    course_class = CourseClass.objects.filter(id=course_class_id).first()

                batch = None
                if academic_batch_id:
                    batch = AcademicBatch.objects.filter(id=academic_batch_id).first()
                elif course_class:
                    batch = course_class.batch
                else:
                    batch = AcademicBatch.objects.filter(is_active=True).first()

                edu_prog = data.get("education_program")
                if not edu_prog:
                    if course_class and course_class.education_program:
                        edu_prog = course_class.education_program
                    elif batch and batch.program_type in ["BACHELOR", "ENGINEER"]:
                        edu_prog = batch.program_type
                    else:
                        edu_prog = "BACHELOR"

                student = Student.objects.create(
                    user=user,
                    registration_no=reg_no,
                    department=class_name or (course_class.class_name if course_class else ""),
                    education_program=edu_prog,
                    course_class=course_class,
                    academic_batch=batch,
                    batch_no=class_name,
                    phone_number=phone_number
                )

            # Handle Supervisor Profile
            elif user_type == "supervisor":
                spv_id = data.get("supervisor_id") or username
                academic_title = data.get("academic_title", "").strip()
                department_name = data.get("department_name", "Khoa CNTT - ĐHGTVT").strip()
                is_external = data.get("is_external", False)

                spv = Supervisor.objects.create(
                    user=user,
                    supervisor_id=spv_id,
                    academic_title=academic_title,
                    department_name=department_name,
                    phone_number=phone_number,
                    is_external=is_external
                )

                # Initialize Quota for active batch
                active_batch = AcademicBatch.objects.filter(is_active=True).first()
                if active_batch:
                    SupervisorQuota.objects.create(
                        supervisor=spv,
                        batch=active_batch,
                        department=department_name,
                        viet_anh_quota=data.get("viet_anh_quota", 2),
                        general_cntt_quota=data.get("general_cntt_quota", 3),
                        max_total_quota=data.get("max_total_quota", 5),
                        current_assigned=0
                    )

            AuditLog.objects.create(
                user=request.user,
                action_type="admin_user_update",
                description=f"Admin created {user_type} account '{username}' ({last_name} {first_name})."
            )

        serialized_user = AdminUserSerializer(user).data
        invalidate_user_summary_cache()
        return Response({
            "message": f"Tạo người dùng '{user.username}' thành công.",
            "user": AdminUserSerializer(user).data,
            "plain_password": plain_password
        }, status=status.HTTP_201_CREATED)

    def patch(self, request, pk=None):
        if not pk:
            return Response({"detail": "User ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        user = get_object_or_404(CustomUser, pk=pk)

        is_active = request.data.get("is_active")
        user_type = request.data.get("user_type")
        first_name = request.data.get("first_name")
        last_name = request.data.get("last_name")
        email = request.data.get("email")

        if is_active is not None:
            user.is_active = bool(is_active)
        if user_type:
            user.user_type = user_type
            if user_type == "admin":
                user.is_staff = True
            elif user.id != request.user.id:
                user.is_staff = False
        if first_name is not None:
            user.first_name = first_name.strip()
        if last_name is not None:
            user.last_name = last_name.strip()
        if email:
            user.email = email.strip().lower()

        user.save()

        # Update associated Student profile if any
        std = getattr(user, "student_profile", None)
        if std:
            phone_number = request.data.get("phone_number")
            class_name = request.data.get("class_name")
            course_class_id = request.data.get("course_class_id")
            academic_batch_id = request.data.get("academic_batch_id")

            if phone_number is not None:
                std.phone_number = phone_number.strip()
            if class_name is not None:
                std.department = class_name.strip()
                std.batch_no = class_name.strip()
            if course_class_id:
                std.course_class_id = course_class_id
            if academic_batch_id:
                std.academic_batch_id = academic_batch_id
            std.save()

        # Update associated Supervisor profile if any
        spv = getattr(user, "supervisor_profile", None)
        if spv:
            academic_title = request.data.get("academic_title")
            department_name = request.data.get("department_name")
            phone_number = request.data.get("phone_number")
            is_external = request.data.get("is_external")

            if academic_title is not None:
                spv.academic_title = academic_title.strip()
            if department_name is not None:
                spv.department_name = department_name.strip()
            if phone_number is not None:
                spv.phone_number = phone_number.strip()
            if is_external is not None:
                spv.is_external = bool(is_external)
            spv.save()

        AuditLog.objects.create(
            user=request.user,
            action_type="admin_user_update",
            description=f"Admin updated user '{user.username}' status/profile."
        )
        invalidate_user_summary_cache()
        return Response({
            "message": "Cập nhật người dùng thành công.",
            "user": AdminUserSerializer(user).data
        }, status=status.HTTP_200_OK)

    def delete(self, request, pk=None):
        if not pk:
            return Response({"detail": "User ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        user = get_object_or_404(CustomUser, pk=pk)

        if user.id == request.user.id:
            return Response({"detail": "Không thể xóa tài khoản Admin đang đăng nhập."}, status=status.HTTP_400_BAD_REQUEST)

        username = user.username
        user.delete()

        AuditLog.objects.create(
            user=request.user,
            action_type="admin_user_update",
            description=f"Admin deleted user '{username}'."
        )
        invalidate_user_summary_cache()
        return Response({"message": f"Đã xóa người dùng {username}."}, status=status.HTTP_200_OK)


class AdminImportExcelAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file_obj = request.FILES.get("file")
        batch_id = request.data.get("batch_id")
        password_strategy = request.data.get("password_strategy", "MSSV")
        custom_fixed_password = request.data.get("custom_fixed_password", "")
        default_major = request.data.get("default_major", "CNTT")

        if not file_obj:
            return Response({"detail": "Vui lòng chọn file Excel để import."}, status=status.HTTP_400_BAD_REQUEST)
        if not batch_id:
            active_batch = AcademicBatch.objects.filter(is_active=True).first() or AcademicBatch.objects.order_by("-id").first()
            if not active_batch:
                active_batch = AcademicBatch.objects.create(
                    batch_code=f"K{timezone.now().year}",
                    batch_name=f"Đợt Đồ Án {timezone.now().year}",
                    is_active=True
                )
            batch_id = active_batch.id

        res = ExcelImportService.import_students_from_excel(
            file_obj=file_obj,
            batch_id=batch_id,
            password_strategy=password_strategy,
            custom_fixed_password=custom_fixed_password,
            default_major=default_major
        )

        AuditLog.objects.create(
            user=request.user,
            action_type="admin_user_update",
            description=f"Imported Excel students for Batch #{batch_id}: Total={res.get('total')}, Created={res.get('created')}, Strategy={password_strategy}"
        )
        invalidate_user_summary_cache()
        cache.delete(BATCHES_CACHE_KEY)
        cache.delete(SECURITY_METRICS_CACHE_KEY)

        return Response(res, status=status.HTTP_200_OK if res.get("success") else status.HTTP_400_BAD_REQUEST)


class AdminDownloadTemplateAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def get(self, request):
        buffer = ExcelImportService.generate_student_template()
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = 'attachment; filename="Mau_Import_Sinh_Vien_UTC.xlsx"'
        return response


class AdminExportUsersExcelAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def get(self, request):
        users = CustomUser.objects.all().select_related(
            "student_profile",
            "student_profile__course_class",
            "student_profile__academic_batch",
            "student_profile__graduation_project",
            "student_profile__graduation_project__supervisor",
            "student_profile__graduation_project__supervisor__user",
            "supervisor_profile"
        ).order_by("-id")

        user_type = request.query_params.get("user_type") or request.query_params.get("role")
        major = request.query_params.get("major")
        program_type = request.query_params.get("program_type")
        class_id = request.query_params.get("class_id")
        batch_id = request.query_params.get("batch_id")
        supervisor_id = request.query_params.get("supervisor_id")
        search = (request.query_params.get("search") or request.query_params.get("q") or "").strip()

        if user_type:
            users = users.filter(user_type=user_type)
        if major:
            if major.upper() == "KHMT":
                users = users.filter(
                    Q(student_profile__course_class__program_type="KHMT") |
                    Q(student_profile__department__icontains="Khoa học máy tính") |
                    Q(student_profile__department__icontains="KHMT")
                )
            elif major.upper() == "CNTT":
                users = users.exclude(
                    Q(student_profile__course_class__program_type="KHMT") |
                    Q(student_profile__department__icontains="Khoa học máy tính") |
                    Q(student_profile__department__icontains="KHMT")
                )
        if program_type:
            users = users.filter(student_profile__course_class__program_type=program_type)
        if class_id:
            users = users.filter(student_profile__course_class_id=class_id)
        if batch_id:
            users = users.filter(
                Q(student_profile__academic_batch_id=batch_id) |
                Q(supervisor_profile__quotas__batch_id=batch_id)
            ).distinct()
        if supervisor_id:
            if supervisor_id == "unassigned":
                users = users.filter(student_profile__graduation_project__supervisor__isnull=True)
            else:
                users = users.filter(student_profile__graduation_project__supervisor_id=supervisor_id)
        if search:
            users = users.filter(
                Q(username__icontains=search) |
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(student_profile__registration_no__icontains=search) |
                Q(student_profile__department__icontains=search) |
                Q(supervisor_profile__supervisor_id__icontains=search)
            ).distinct()

        buffer = ExcelImportService.export_users_to_excel(users, role=user_type or "all")
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = 'attachment; filename="Danh_Sach_Nguoi_Dung_UTC.xlsx"'
        return response


class AdminResetUserPasswordAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def post(self, request, pk=None):
        if not pk:
            return Response({"detail": "User ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        user = get_object_or_404(CustomUser, pk=pk)

        serializer = AdminResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        strategy = serializer.validated_data.get("password_strategy", "MSSV")
        custom_pwd = serializer.validated_data.get("custom_password", "").strip()

        if strategy == "MSSV":
            if hasattr(user, "admin_student_profile") and user.admin_student_profile.registration_no:
                new_pwd = user.admin_student_profile.registration_no
            elif hasattr(user, "admin_supervisor_profile") and user.admin_supervisor_profile.supervisor_id:
                new_pwd = user.admin_supervisor_profile.supervisor_id
            else:
                new_pwd = user.username
        elif strategy in ["FIXED", "CUSTOM"] and custom_pwd:
            new_pwd = custom_pwd
        elif strategy == "RANDOM":
            new_pwd = generate_random_password(8)
        else:
            new_pwd = user.username

        user.set_password(new_pwd)
        user.save()

        AuditLog.objects.create(
            user=request.user,
            action_type="admin_user_update",
            description=f"Admin reset password for user '{user.username}' (Strategy: {strategy})."
        )
        invalidate_user_summary_cache()

        return Response({
            "message": f"Đặt lại mật khẩu thành công cho tài khoản '{user.username}'.",
            "username": user.username,
            "new_password": new_pwd
        }, status=status.HTTP_200_OK)


class AdminSecurityCenterAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def get(self, request):
        cached_sec = cache.get(SECURITY_METRICS_CACHE_KEY)
        if cached_sec is not None:
            res = Response(cached_sec, status=status.HTTP_200_OK)
            res["Cache-Control"] = "private, max-age=30"
            return res

        total_users = CustomUser.objects.count()
        active_users = CustomUser.objects.filter(is_active=True).count()
        deactivated_users = CustomUser.objects.filter(is_active=False).count()
        admin_count = CustomUser.objects.filter(user_type="admin").count()
        student_count = Student.objects.count()
        supervisor_count = Supervisor.objects.count()
        batches_count = AcademicBatch.objects.count()
        projects_count = GraduationProject.objects.count()
        councils_count = DefenseCouncil.objects.count()
        recent_audits = AuditLogSerializer(AuditLog.objects.all().order_by("-created_at")[:10], many=True).data

        sec_data = {
            "metrics": {
                "total_users": total_users,
                "active_users": active_users,
                "deactivated_users": deactivated_users,
                "admin_count": admin_count,
                "student_count": student_count,
                "supervisor_count": supervisor_count,
                "batches_count": batches_count,
                "projects_count": projects_count,
                "councils_count": councils_count,
            },
            "security_headers": {
                "httponly_cookies": True,
                "content_security_policy": True,
                "hsts_production": True,
                "cors_credentials": True,
                "magic_bytes_file_inspection": True,
                "websocket_one_time_tickets": True,
                "jwt_access_expiry_minutes": 15,
                "rate_limiting_active": True,
            },
            "recent_audits": recent_audits
        }
        cache.set(SECURITY_METRICS_CACHE_KEY, sec_data, 30)
        res = Response(sec_data, status=status.HTTP_200_OK)
        res["Cache-Control"] = "private, max-age=30"
        return res


class AdminAuditLogListAPIView(ListAPIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]
    serializer_class = AuditLogSerializer
    queryset = AuditLog.objects.all().order_by("-created_at")


class AdminAuditLogStatsAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def get(self, request):
        total = AuditLog.objects.count()
        admin_actions = AuditLog.objects.filter(action_type="admin_user_update").count()
        eval_actions = AuditLog.objects.filter(action_type="evaluation_update").count()
        return Response({
            "total_audit_logs": total,
            "admin_actions_count": admin_actions,
            "evaluation_actions_count": eval_actions
        }, status=status.HTTP_200_OK)


# ==============================================================================
# ACADEMIC BATCH & EXCEL IMPORT VIEWS
# ==============================================================================

class AcademicBatchListCreateAPIView(ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]
    serializer_class = AcademicBatchSerializer
    queryset = AcademicBatch.objects.all().order_by("-created_at")
    pagination_class = None

    def list(self, request, *args, **kwargs):
        cached_data = cache.get(BATCHES_CACHE_KEY)
        if cached_data is not None:
            res = Response(cached_data, status=status.HTTP_200_OK)
            res["Cache-Control"] = "private, max-age=120"
            return res

        response = super().list(request, *args, **kwargs)
        if response.status_code == 200:
            cache.set(BATCHES_CACHE_KEY, response.data, 600)
            response["Cache-Control"] = "private, max-age=120"
        return response

    def create(self, request, *args, **kwargs):
        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        # Normalize fields for flexible callers
        if "name" in data and not data.get("batch_name"):
            data["batch_name"] = data["name"]
        if "time" in data and not data.get("start_date"):
            data["start_date"] = data["time"]
        if "start_time" in data and not data.get("start_date"):
            data["start_date"] = data["start_time"]
        if "end_time" in data and not data.get("end_date"):
            data["end_date"] = data["end_time"]
        if not data.get("batch_code"):
            name = str(data.get("batch_name", "BATCH"))
            clean = "".join(ch for ch in name if ch.isalnum())
            prefix = clean[:8].upper() if clean else "BATCH"
            timestamp = timezone.now().strftime("%y%m%d%H%M%S")
            data["batch_code"] = f"{prefix}_{timestamp}"

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        cache.delete(BATCHES_CACHE_KEY)
        invalidate_user_summary_cache()
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class AcademicBatchDetailAPIView(RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]
    serializer_class = AcademicBatchSerializer
    queryset = AcademicBatch.objects.all()

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        cache.delete(BATCHES_CACHE_KEY)
        invalidate_user_summary_cache()
        return response

    def destroy(self, request, *args, **kwargs):
        response = super().destroy(request, *args, **kwargs)
        cache.delete(BATCHES_CACHE_KEY)
        invalidate_user_summary_cache()
        return response


class ExcelStudentImportAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file_obj = (
            request.FILES.get("file")
            or request.FILES.get("excel")
            or request.FILES.get("excel_file")
            or request.FILES.get("student_file")
            or (next(iter(request.FILES.values())) if request.FILES else None)
        )
        batch_id = request.data.get("batch_id")

        if not file_obj:
            return Response({"detail": "Vui lòng chọn file Excel để import."}, status=status.HTTP_400_BAD_REQUEST)
        if not batch_id:
            active_batch = AcademicBatch.objects.filter(is_active=True).first() or AcademicBatch.objects.order_by("-id").first()
            if not active_batch:
                active_batch = AcademicBatch.objects.create(
                    batch_code=f"K{timezone.now().year}",
                    batch_name=f"Đợt Đồ Án {timezone.now().year}",
                    is_active=True
                )
        password_strategy = request.data.get("password_strategy", "MSSV")
        custom_fixed_password = request.data.get("custom_fixed_password", "")
        default_major = request.data.get("default_major", "CNTT")

        res = ExcelImportService.import_students_from_excel(
            file_obj=file_obj,
            batch_id=batch_id,
            password_strategy=password_strategy,
            custom_fixed_password=custom_fixed_password,
            default_major=default_major
        )

        AuditLog.objects.create(
            user=request.user,
            action_type="admin_user_update",
            description=f"Imported Excel students for Batch #{batch_id}: Total={res.get('total')}, Created={res.get('created')}"
        )
        invalidate_user_summary_cache()
        cache.delete(BATCHES_CACHE_KEY)
        cache.delete(SECURITY_METRICS_CACHE_KEY)

        return Response(res, status=status.HTTP_200_OK if res.get("success") else status.HTTP_400_BAD_REQUEST)


class ExcelStudentExportAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def get(self, request):
        batch_id = request.query_params.get("batch_id")
        if batch_id:
            try:
                batch = AcademicBatch.objects.get(id=batch_id)
            except AcademicBatch.DoesNotExist:
                batch = AcademicBatch.objects.filter(is_active=True).first()
        else:
            batch = AcademicBatch.objects.filter(is_active=True).first() or AcademicBatch.objects.order_by("-id").first()

        if not batch:
            return Response({"detail": "Chưa có đợt đồ án nào để xuất danh sách sinh viên."}, status=status.HTTP_404_NOT_FOUND)

        buffer = ExcelImportService.export_students_import_format(batch.id)
        filename = f"Danh_Sach_Sinh_Vien_Dot_{batch.batch_code}.xlsx"

        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


# ==============================================================================
# SUPERVISOR QUOTA & ALLOCATION VIEWS
# ==============================================================================

class SupervisorQuotaListUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def get(self, request):
        batch_id = request.query_params.get("batch_id")
        if batch_id:
            batch = AcademicBatch.objects.filter(id=batch_id).first()
            if batch and not SupervisorQuota.objects.filter(batch=batch).exists():
                active_supervisors = Supervisor.objects.filter(user__is_active=True).select_related('user')
                for sup in active_supervisors:
                    mult = sup.academic_rank_multiplier or 1.0
                    base_quota = 5
                    max_q = int(round(base_quota * mult))
                    SupervisorQuota.objects.get_or_create(
                        supervisor=sup,
                        batch=batch,
                        defaults={
                            "department": sup.department_name or "",
                            "base_quota": base_quota,
                            "rank_multiplier": mult,
                            "max_total_quota": max_q,
                            "general_cntt_quota": max_q,
                            "viet_anh_quota": 2 if sup.is_eligible_for_engineer() else 0,
                            "current_assigned": 0
                        }
                    )
        quotas = SupervisorQuota.objects.all().select_related("supervisor__user")
        if batch_id:
            quotas = quotas.filter(batch_id=batch_id)
        serializer = SupervisorQuotaSerializer(quotas, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        quotas_data = request.data
        if not isinstance(quotas_data, list):
            return Response({"detail": "Dữ liệu phải là danh sách quota cập nhật."}, status=status.HTTP_400_BAD_REQUEST)

        updated_count = 0
        for item in quotas_data:
            quota_id = item.get("id")
            if quota_id:
                q = SupervisorQuota.objects.filter(id=quota_id).first()
                if q:
                    q.viet_anh_quota = item.get("viet_anh_quota", q.viet_anh_quota)
                    q.general_cntt_quota = item.get("general_cntt_quota", q.general_cntt_quota)
                    q.max_total_quota = item.get("max_total_quota", q.max_total_quota)
                    q.save()
                    updated_count += 1

        AuditLog.objects.create(
            user=request.user,
            action_type="admin_user_update",
            description=f"Updated quotas for {updated_count} supervisors."
        )

        return Response({"message": f"Cập nhật thành công {updated_count} giảng viên."}, status=status.HTTP_200_OK)


class AutoSupervisorAllocationAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def post(self, request):
        batch_id = request.data.get("batch_id")
        if not batch_id:
            return Response({"detail": "batch_id is required.", "error": "batch_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        res = MinCostMaxFlowAllocationEngine.allocate_supervisors_for_batch(batch_id)

        AuditLog.objects.create(
            user=request.user,
            action_type="supervisor_request_update",
            description=f"Ran MCMF auto-allocation for Batch #{batch_id}: Matched={res.get('matched_count')}, Unassigned={res.get('unassigned_count')}"
        )

        if not res.get("success") and "detail" not in res:
            res["detail"] = res.get("error")

        return Response(res, status=status.HTTP_200_OK if res.get("success") else status.HTTP_400_BAD_REQUEST)


class ManualSupervisorAllocationAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def patch(self, request):
        student_id = request.data.get("student_id")
        supervisor_id = request.data.get("supervisor_id")
        batch_id = request.data.get("batch_id")

        if not student_id or not supervisor_id:
            return Response({"detail": "student_id and supervisor_id are required."}, status=status.HTTP_400_BAD_REQUEST)

        student = get_object_or_404(Student, id=student_id)
        supervisor = get_object_or_404(Supervisor, id=supervisor_id)
        batch = AcademicBatch.objects.filter(id=batch_id).first() or student.academic_batch

        if not batch:
            return Response({"detail": "Sinh viên chưa thuộc đợt đào tạo nào."}, status=status.HTTP_400_BAD_REQUEST)

        proj, created = GraduationProject.objects.update_or_create(
            student=student,
            defaults={
                "supervisor": supervisor,
                "batch": batch,
                "topic_title_vi": f"Đồ án tốt nghiệp của {student.user.get_full_name()}",
                "status": "ALLOCATED"
            }
        )

        # Update quota count
        quota = SupervisorQuota.objects.filter(supervisor=supervisor, batch=batch).first()
        if quota:
            quota.current_assigned = GraduationProject.objects.filter(batch=batch, supervisor=supervisor).count()
            quota.save(update_fields=["current_assigned"])

        AuditLog.objects.create(
            user=request.user,
            action_type="supervisor_request_update",
            description=f"Manual assign student {student.registration_no} to supervisor {supervisor.user.get_full_name()}."
        )

        return Response({
            "message": "Phân công thủ công thành công.",
            "project": GraduationProjectAdminSerializer(proj).data
        }, status=status.HTTP_200_OK)


# ==============================================================================
# DEFENSE COUNCIL & REVIEWER VIEWS
# ==============================================================================

class DefenseCouncilListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def get(self, request):
        batch_id = request.query_params.get("batch_id")
        councils = DefenseCouncil.objects.all().prefetch_related("members__user", "members__supervisor")
        if batch_id:
            councils = councils.filter(batch_id=batch_id)
        serializer = DefenseCouncilSerializer(councils, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        data = request.data
        batch_id = data.get("batch_id")
        council_number = data.get("council_number", 1)
        council_name = data.get("council_name", f"Hội đồng {council_number}")
        defense_room = data.get("defense_room", "")
        session_date = data.get("session_date")
        session_time = data.get("session_time", "MORNING")
        members_data = data.get("members", [])

        if not batch_id:
            return Response({"detail": "batch_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        batch = get_object_or_404(AcademicBatch, id=batch_id)
        council = DefenseCouncil.objects.create(
            batch=batch,
            council_number=council_number,
            council_name=council_name,
            defense_room=defense_room,
            session_date=session_date if session_date else None,
            session_time=session_time
        )

        for m in members_data:
            user_id = m.get("user_id")
            role = m.get("role", "MEMBER")
            ext = m.get("external_institution", "")
            if user_id:
                user = CustomUser.objects.filter(id=user_id).first()
                if user:
                    sup = getattr(user, "admin_supervisor_profile", None) or getattr(user, "supervisor_profile", None)
                    CouncilMember.objects.create(
                        council=council,
                        user=user,
                        supervisor=sup,
                        role=role,
                        external_institution=ext
                    )

        return Response(DefenseCouncilSerializer(council).data, status=status.HTTP_201_CREATED)

    def delete(self, request, pk=None):
        council_id = pk or request.query_params.get("id") or request.data.get("id")
        if not council_id:
            return Response({"detail": "Council ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        council = get_object_or_404(DefenseCouncil, id=council_id)
        if council.is_finalized:
            return Response({"detail": "Không thể xóa Hội đồng đã khóa / chốt điểm."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Reset projects and schedule slots associated with this council
        GraduationProject.objects.filter(council=council).update(council=None, reviewer=None)
        DefenseScheduleSlot.objects.filter(council=council).delete()
        council_name = council.council_name
        council.delete()

        AuditLog.objects.create(
            user=request.user,
            action_type="group_status_change",
            description=f"Admin đã xóa {council_name}."
        )

        return Response({"message": f"Đã xóa thành công {council_name}."}, status=status.HTTP_200_OK)



class AutoReviewerAllocationAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def post(self, request):
        batch_id = request.data.get("batch_id")
        if not batch_id:
            return Response({"detail": "batch_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        res = ReviewerAndCouncilAllocationEngine.assign_councils_and_reviewers(batch_id)

        AuditLog.objects.create(
            user=request.user,
            action_type="admin_user_update",
            description=f"Ran No-Conflict Reviewer Allocation for Batch #{batch_id}: Assigned={res.get('assigned_count')}"
        )

        return Response(res, status=status.HTTP_200_OK if res.get("success") else status.HTTP_400_BAD_REQUEST)


class GraduationProjectsAdminListAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def get(self, request):
        batch_id = request.query_params.get("batch_id")
        council_id = request.query_params.get("council_id")
        status_filter = request.query_params.get("status")

        projects = GraduationProject.objects.all().select_related(
            "student__user",
            "supervisor__user",
            "reviewer__user",
            "council",
            "topic_category",
            "final_grade_summary"
        )

        if batch_id:
            projects = projects.filter(batch_id=batch_id)
        if council_id:
            projects = projects.filter(council_id=council_id)
        if status_filter:
            projects = projects.filter(status=status_filter)

        from .utils.vietnamese_sort import sort_by_vietnamese_name
        projects_list = list(projects)
        projects_list = sort_by_vietnamese_name(
            projects_list,
            key_extractor=lambda p: p.student.user.get_full_name() or p.student.user.username
        )

        serializer = GraduationProjectAdminSerializer(projects_list, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ==============================================================================
# DOCUMENT EXPORT API VIEWS (Word .docx & Excel .xlsx)
# ==============================================================================

class ExportToTrinhWordAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def get(self, request):
        council_id = request.query_params.get("council_id")
        if not council_id:
            return Response({"detail": "council_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            buffer = DocumentGenerationService.generate_to_trinh_docx(council_id)
            response = HttpResponse(
                buffer.getvalue(),
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            response["Content-Disposition"] = f'attachment; filename="To_trinh_Hoi_dong_{council_id}.docx"'
            return response
        except Exception as ex:
            return Response({"detail": f"Error generating document: {str(ex)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ExportBienBanExcelAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def get(self, request):
        council_id = request.query_params.get("council_id")
        if not council_id:
            return Response({"detail": "council_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            buffer = DocumentGenerationService.generate_bien_ban_excel(council_id)
            response = HttpResponse(
                buffer.getvalue(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            response["Content-Disposition"] = f'attachment; filename="Bien_ban_cham_diem_HD_{council_id}.xlsx"'
            return response
        except Exception as ex:
            return Response({"detail": f"Error generating document: {str(ex)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class HealthCheckAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok", "service": "Smart-Fyp-Admin API"}, status=status.HTTP_200_OK)


class FinalizeAndNotifyAllocationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .services.email_service import EmailNotificationService
        batch_id = request.data.get("batch_id")
        if not batch_id:
            return Response({"error": "Missing batch_id"}, status=status.HTTP_400_BAD_REQUEST)

        result = EmailNotificationService.send_assignment_finalized_emails(batch_id)
        if result.get("success"):
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

# ==============================================================================
# OUTLINE MANAGEMENT API VIEWS
# ==============================================================================

class OutlineGroupListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def get(self, request):
        batch_id = request.query_params.get("batch_id")
        from app.models import OutlineReviewGroup
        from app.serializers import OutlineReviewGroupSerializer
        qs = OutlineReviewGroup.objects.all().prefetch_related("members__user")
        if batch_id:
            qs = qs.filter(batch_id=batch_id)
        serializer = OutlineReviewGroupSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        data = request.data
        batch_id = data.get("batch_id")
        name = data.get("name")
        department = data.get("department")
        members = data.get("members", [])

        if not batch_id or not name:
            return Response({"error": "batch_id and name are required"}, status=status.HTTP_400_BAD_REQUEST)

        from app.models import OutlineReviewGroup, AcademicBatch
        batch = get_object_or_404(AcademicBatch, id=batch_id)
        group = OutlineReviewGroup.objects.create(batch=batch, name=name, department=department)
        
        if members:
            group.members.set(members)
        
        from app.serializers import OutlineReviewGroupSerializer
        return Response(OutlineReviewGroupSerializer(group).data, status=status.HTTP_201_CREATED)


class OutlineGroupDetailAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def put(self, request, pk):
        from app.models import OutlineReviewGroup
        from app.serializers import OutlineReviewGroupSerializer
        group = get_object_or_404(OutlineReviewGroup, pk=pk)
        data = request.data
        if "name" in data:
            group.name = data["name"]
        if "department" in data:
            group.department = data["department"]
        group.save()
        if "members" in data:
            group.members.set(data["members"])
            
        return Response(OutlineReviewGroupSerializer(group).data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        from app.models import OutlineReviewGroup
        group = get_object_or_404(OutlineReviewGroup, pk=pk)
        group.delete()
        return Response({"success": True}, status=status.HTTP_204_NO_CONTENT)


class OutlineReviewListAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def get(self, request):
        batch_id = request.query_params.get("batch_id")
        verdict_filter = request.query_params.get("verdict")
        group_id = request.query_params.get("group_id")
        search = (request.query_params.get("search") or request.query_params.get("q") or "").strip()

        from app.models import OutlineReview, GraduationProject, AcademicBatch
        from app.serializers import OutlineReviewSerializer
        from app.utils.vietnamese_sort import sort_by_vietnamese_name

        if not batch_id:
            first_batch = AcademicBatch.objects.first()
            batch_id = first_batch.id if first_batch else None

        if not batch_id:
            return Response([], status=status.HTTP_200_OK)

        projects = GraduationProject.objects.filter(batch_id=batch_id).select_related("student__user")

        # Ensure OutlineReview exists for all projects
        for p in projects:
            if not hasattr(p, 'outline_review'):
                OutlineReview.objects.create(project=p)

        reviews = OutlineReview.objects.filter(project__batch_id=batch_id).select_related(
            "project__student__user",
            "project__student__course_class",
            "project__supervisor__user",
            "review_group",
            "reviewer__user"
        )

        if verdict_filter and verdict_filter != "ALL":
            reviews = reviews.filter(verdict=verdict_filter)

        if group_id:
            if group_id == "unassigned":
                reviews = reviews.filter(review_group__isnull=True)
            else:
                reviews = reviews.filter(review_group_id=group_id)

        if search:
            reviews = reviews.filter(
                Q(project__student__user__first_name__icontains=search) |
                Q(project__student__user__last_name__icontains=search) |
                Q(project__student__registration_no__icontains=search) |
                Q(project__topic_title_vi__icontains=search) |
                Q(project__topic_title_en__icontains=search)
            )

        # Sort by Vietnamese name collation
        reviews_list = list(reviews)
        reviews_list = sort_by_vietnamese_name(
            reviews_list,
            key_extractor=lambda r: (f"{r.project.student.user.last_name} {r.project.student.user.first_name}".strip() if (r.project.student.user.last_name or r.project.student.user.first_name) else (r.project.student.user.get_full_name() or r.project.student.user.username))
        )

        serializer = OutlineReviewSerializer(reviews_list, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class OutlineReviewDetailAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def patch(self, request, pk):
        from app.models import OutlineReview, Supervisor
        from app.serializers import OutlineReviewSerializer
        from django.utils import timezone

        review = get_object_or_404(OutlineReview, pk=pk)
        data = request.data

        if "verdict" in data:
            review.verdict = data["verdict"]
            review.reviewed_at = timezone.now()
            # Sync project status
            project = review.project
            if review.verdict == "APPROVED":
                project.status = "OUTLINE_APPROVED"
            elif review.verdict == "REVISION_REQUIRED":
                project.status = "OUTLINE_REVISION"
            elif review.verdict == "REJECTED":
                project.status = "FAILED"
            elif review.verdict == "PENDING":
                project.status = "OUTLINE_PENDING"
            project.save()

        if "comments" in data:
            review.comments = data["comments"]

        if "review_group_id" in data:
            review.review_group_id = data["review_group_id"] or None

        if "reviewer_id" in data:
            review.reviewer_id = data["reviewer_id"] or None

        review.save()
        return Response(OutlineReviewSerializer(review).data, status=status.HTTP_200_OK)


class OutlineReviewAssignAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def post(self, request):
        from app.models import OutlineReview, OutlineReviewGroup, GraduationProject
        from django.utils import timezone

        action = request.data.get("action", "assign_group")
        batch_id = request.data.get("batch_id")

        if action == "auto_assign":
            # Distribute unassigned projects across groups in the batch
            groups = list(OutlineReviewGroup.objects.filter(batch_id=batch_id)) if batch_id else list(OutlineReviewGroup.objects.all())
            if not groups:
                return Response({"error": "Cần tạo ít nhất một nhóm xét duyệt đề cương trước khi phân nhóm tự động."}, status=status.HTTP_400_BAD_REQUEST)

            projects = GraduationProject.objects.filter(batch_id=batch_id) if batch_id else GraduationProject.objects.all()
            assigned_count = 0
            for idx, p in enumerate(projects):
                review, _ = OutlineReview.objects.get_or_create(project=p)
                review.review_group = groups[idx % len(groups)]
                review.save()
                assigned_count += 1

            return Response({
                "success": True,
                "assigned_count": assigned_count,
                "message": f"Đã tự động phân bổ {assigned_count} đề cương vào {len(groups)} nhóm thẩm định."
            }, status=status.HTTP_200_OK)

        elif action == "bulk_approve":
            project_ids = request.data.get("project_ids", [])
            query = OutlineReview.objects.all()
            if project_ids:
                query = query.filter(project_id__in=project_ids)
            elif batch_id:
                query = query.filter(project__batch_id=batch_id)

            updated = 0
            now = timezone.now()
            for r in query:
                r.verdict = "APPROVED"
                r.reviewed_at = now
                if not r.comments:
                    r.comments = "Đề cương đạt chuẩn yêu cầu bảo vệ ĐATN."
                r.save()
                r.project.status = "OUTLINE_APPROVED"
                r.project.save()
                updated += 1

            return Response({
                "success": True,
                "updated_count": updated,
                "message": f"Đã duyệt đạt yêu cầu cho {updated} đề cương."
            }, status=status.HTTP_200_OK)

        else:
            project_ids = request.data.get("project_ids", [])
            group_id = request.data.get("group_id")
            
            if not project_ids or not group_id:
                return Response({"error": "project_ids and group_id are required"}, status=status.HTTP_400_BAD_REQUEST)
                
            group = get_object_or_404(OutlineReviewGroup, id=group_id)
            updated_count = 0
            for pid in project_ids:
                review, created = OutlineReview.objects.get_or_create(project_id=pid)
                review.review_group = group
                review.save()
                updated_count += 1
                
            return Response({"success": True, "updated_count": updated_count}, status=status.HTTP_200_OK)



class DatabaseHealthCheckAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            user_count = CustomUser.objects.count()
            return Response({"status": "healthy", "database": "connected", "total_users": user_count}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"status": "unhealthy", "database": "error", "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==============================================================================
# DEPARTMENT MANAGEMENT (BỘ MÔN CHUYÊN MÔN - GIAI ĐOẠN 1)
# ==============================================================================

class DepartmentListCreateAPIView(ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]
    serializer_class = DepartmentSerializer
    queryset = Department.objects.all().order_by("code")
    pagination_class = None


class DepartmentDetailAPIView(RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsAdminUserRole]
    serializer_class = DepartmentSerializer
    queryset = Department.objects.all()


class SupervisorProfileUpdateAPIView(APIView):
    """Cập nhật thông tin học vị, bộ môn, hệ số, hướng nghiên cứu của GV (Bước 7)"""
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def patch(self, request, pk):
        supervisor = get_object_or_404(Supervisor, pk=pk)
        academic_title = request.data.get("academic_title")
        department_id = request.data.get("department_id")
        rank_multiplier = request.data.get("academic_rank_multiplier")
        research_interest = request.data.get("research_interest")

        if academic_title is not None:
            supervisor.academic_title = academic_title
        if department_id is not None:
            supervisor.department_obj = Department.objects.filter(id=department_id).first()
            if supervisor.department_obj:
                supervisor.department_name = supervisor.department_obj.name
        if rank_multiplier is not None:
            try:
                supervisor.academic_rank_multiplier = float(rank_multiplier)
            except:
                pass
        if research_interest is not None:
            supervisor.research_interest = research_interest

        supervisor.save()

        # Tự động cập nhật hệ số sang SupervisorQuota trong các đợt hiện có
        for q in supervisor.quotas.all():
            q.rank_multiplier = supervisor.academic_rank_multiplier
            q.calculate_capacity()
            q.save()

        AuditLog.objects.create(
            user=request.user,
            action_type="admin_user_update",
            description=f"Cập nhật hồ sơ học vị/bộ môn của GV {supervisor.user.get_full_name()} (Hệ số={supervisor.academic_rank_multiplier})."
        )

        return Response(SupervisorDetailSerializer(supervisor).data, status=status.HTTP_200_OK)


# ==============================================================================
# ALLOCATION WORKFLOW (CHỐT PHÂN CÔNG & CÔNG BỐ - GIAI ĐOẠN 2 & 3)
# ==============================================================================

class FinalizeAllocationAPIView(APIView):
    """Khoa chốt phân công đề tài (Bước 17)"""
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def post(self, request):
        batch_id = request.data.get("batch_id")
        if not batch_id:
            return Response({"detail": "batch_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        res = MinCostMaxFlowAllocationEngine.finalize_allocation(batch_id, user=request.user)
        return Response(res, status=status.HTTP_200_OK if res.get("success") else status.HTTP_400_BAD_REQUEST)


class PublishAllocationAPIView(APIView):
    """Công bố và gửi email kết quả phân công (Bước 18 & 19)"""
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def post(self, request):
        batch_id = request.data.get("batch_id")
        if not batch_id:
            return Response({"detail": "batch_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        res = MinCostMaxFlowAllocationEngine.publish_and_notify_allocation(batch_id, user=request.user)
        return Response(res, status=status.HTTP_200_OK if res.get("success") else status.HTTP_400_BAD_REQUEST)


# ==============================================================================
# TOPIC APPROVAL & OUTLINE DOWNLOAD (DUYỆT ĐỀ TÀI - GIAI ĐOẠN 3)
# ==============================================================================

class TopicApprovalAPIView(APIView):
    """Khoa/Ban duyệt đề tài (Bước 22): APPROVE hoặc REQUEST_REVISION"""
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def patch(self, request, pk):
        project = get_object_or_404(GraduationProject, pk=pk)
        decision = request.data.get("decision")  # "APPROVE" hoặc "REQUEST_REVISION"
        notes = request.data.get("notes", "")

        if decision == "APPROVE":
            project.topic_review_status = "APPROVED"
            project.status = "OUTLINE_APPROVED"
            project.topic_revision_notes = ""
            project.save()

            AuditLog.objects.create(
                user=request.user,
                action_type="document_status_change",
                description=f"Khoa phê duyệt đề tài cho SV {project.student.registration_no} ({project.topic_title_vi})."
            )
            return Response({"message": "Phê duyệt đề tài thành công.", "status": "APPROVED"}, status=status.HTTP_200_OK)

        elif decision == "REQUEST_REVISION":
            project.topic_review_status = "REVISION_REQUIRED"
            project.status = "OUTLINE_REVISION"
            project.topic_revision_notes = notes
            project.save()

            AuditLog.objects.create(
                user=request.user,
                action_type="document_status_change",
                description=f"Khoa yêu cầu sửa đề tài của SV {project.student.registration_no}: {notes}"
            )
            return Response({"message": "Đã gửi yêu cầu chỉnh sửa đề tài về Draft.", "status": "REVISION_REQUIRED"}, status=status.HTTP_200_OK)

        return Response({"detail": "Quyết định không hợp lệ (APPROVE hoặc REQUEST_REVISION)."}, status=status.HTTP_400_BAD_REQUEST)


class DownloadProjectOutlineAPIView(APIView):
    """Giai đoạn 3 (Bước 23): Tải Phiếu giao đề tài & Đề cương đồ án tốt nghiệp"""
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def get(self, request, pk):
        try:
            buffer = DocumentGenerationService.generate_outline_docx(pk)
            project = GraduationProject.objects.get(id=pk)
            response = HttpResponse(
                buffer.getvalue(),
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            filename = f"Phieu_giao_de_tai_{project.student.registration_no}.docx"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response
        except Exception as ex:
            return Response({"detail": f"Error generating document: {str(ex)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==============================================================================
# ELIGIBILITY & FORCE APPROVE (GIAI ĐOẠN 4)
# ==============================================================================

class ExcelEligibilityImportAPIView(APIView):
    """Import điểm / danh sách xét điều kiện làm đồ án (Bước 25 & 26)"""
    permission_classes = [IsAuthenticated, IsAdminUserRole]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file_obj = request.FILES.get("file")
        batch_id = request.data.get("batch_id")

        if not file_obj or not batch_id:
            return Response({"detail": "File Excel và batch_id là bắt buộc."}, status=status.HTTP_400_BAD_REQUEST)

        res = ExcelImportService.import_eligibility_from_excel(file_obj, batch_id)

        AuditLog.objects.create(
            user=request.user,
            action_type="admin_user_update",
            description=f"Imported eligibility for Batch #{batch_id}: Processed={res.get('total_processed')}, Eligible={res.get('eligible_count')}"
        )

        return Response(res, status=status.HTTP_200_OK if res.get("success") else status.HTTP_400_BAD_REQUEST)


class EligibilityDecisionAPIView(APIView):
    """Quyết định Force Approve hoặc Loại khỏi đợt (Bước 27)"""
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def patch(self, request, pk):
        return self.handle_decision(request, pk)

    def post(self, request, pk):
        return self.handle_decision(request, pk)

    def handle_decision(self, request, pk):
        project = GraduationProject.objects.filter(Q(pk=pk) | Q(student_id=pk) | Q(student__user_id=pk)).first()
        if not project:
            return Response({"detail": "Không tìm thấy hồ sơ đồ án hoặc sinh viên tương ứng."}, status=status.HTTP_404_NOT_FOUND)
        decision = (request.data.get("decision") or "FORCE_APPROVE").strip().upper()
        reason = request.data.get("reason", "")

        if decision in ("FORCE_APPROVE", "FORCE_APPROVED", "APPROVE", "APPROVED"):
            project.initial_eligibility = "FORCE_APPROVED"
            project.final_academic_eligibility = "ELIGIBLE"
            project.is_eligible_for_defense = True
            if project.supervisor_defense_confirmed or (project.supervisor_score is not None and str(project.supervisor_score) != ""):
                project.status = "DEFENSE_READY"
            else:
                project.status = "IN_PROGRESS"
            project.deferral_status = "NONE"
            project.force_approved_by = request.user
            project.force_approved_at = timezone.now()
            project.ineligibility_reason = f"Đặc cách: {reason}" if reason else (project.ineligibility_reason or "Khoa phê duyệt đặc cách theo đơn giải trình")
            project.save()

            AuditLog.objects.create(
                user=request.user,
                action_type="evaluation_update",
                description=f"Khoa Force Approve cho SV {project.student.registration_no}: {reason}"
            )
            return Response({"message": "Khoa đã đặc cách cho phép bảo vệ đồ án (Force Approve).", "status": "DEFENSE_READY"}, status=status.HTTP_200_OK)

        elif decision in ("DEFER", "DEFERRED"):
            project.initial_eligibility = "INELIGIBLE"
            project.final_academic_eligibility = "INELIGIBLE"
            project.status = "DEFERRED"
            project.deferral_status = "APPROVED"
            project.is_eligible_for_defense = False
            project.deferral_reason = reason or "Khoa xác nhận bảo lưu đồ án do nợ tín chỉ"
            project.deferral_decided_at = timezone.now()
            project.save()

            AuditLog.objects.create(
                user=request.user,
                action_type="evaluation_update",
                description=f"Khoa chuyển bảo lưu đồ án cho SV {project.student.registration_no}: {reason}"
            )
            return Response({"message": "Đã chuyển sinh viên sang trạng thái bảo lưu đồ án.", "status": "DEFERRED"}, status=status.HTTP_200_OK)

        elif decision in ("DISQUALIFY", "DISQUALIFIED", "REJECT", "REJECTED"):
            project.initial_eligibility = "DISQUALIFIED"
            project.status = "DISQUALIFIED"
            project.is_eligible_for_defense = False
            project.ineligibility_reason = reason or "Không đủ điều kiện làm đồ án tốt nghiệp"
            project.save()

            AuditLog.objects.create(
                user=request.user,
                action_type="evaluation_update",
                description=f"Khoa loại SV {project.student.registration_no} khỏi đợt đồ án: {reason}"
            )
            return Response({"message": "Đã loại sinh viên khỏi đợt đồ án.", "status": "DISQUALIFIED"}, status=status.HTTP_200_OK)

        return Response({"detail": "Quyết định không hợp lệ (FORCE_APPROVE, DEFER, hoặc DISQUALIFY)."}, status=status.HTTP_400_BAD_REQUEST)



class SupervisorListAPIView(ListAPIView):
    """Danh sách giảng viên nâng cao đầy đủ học vị, hướng nghiên cứu, quota"""
    permission_classes = [IsAuthenticated, IsAdminUserRole]
    serializer_class = SupervisorDetailSerializer
    queryset = Supervisor.objects.all().select_related("user", "department_obj").prefetch_related("quotas")
    pagination_class = None


# ==============================================================================
# DEFENSE READINESS, DEFERRAL & SCHEDULING (GIAI ĐOẠN 6 & BẢO LƯU)
# ==============================================================================

class ExcelFinalAcademicImportAPIView(APIView):
    """Import kiểm tra điều kiện học vụ cuối (Bước 36 & 37)"""
    permission_classes = [IsAuthenticated, IsAdminUserRole]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file_obj = request.FILES.get("file")
        batch_id = request.data.get("batch_id")

        if not file_obj or not batch_id:
            return Response({"detail": "File Excel và batch_id là bắt buộc."}, status=status.HTTP_400_BAD_REQUEST)

        res = ExcelImportService.import_final_academic_status(file_obj, batch_id)

        AuditLog.objects.create(
            user=request.user,
            action_type="admin_user_update",
            description=f"Imported final academic status for Batch #{batch_id}: Eligible={res.get('eligible_count')}, Ineligible={res.get('ineligible_count')}"
        )

        return Response(res, status=status.HTTP_200_OK if res.get("success") else status.HTTP_400_BAD_REQUEST)


class DeferralDecisionAPIView(APIView):
    """Xử lý Nhánh Bảo lưu (Bước 43): Khoa duyệt bảo lưu hoặc loại khỏi đợt"""
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def patch(self, request, pk):
        project = get_object_or_404(GraduationProject, pk=pk)
        decision = request.data.get("decision")  # "APPROVE_DEFERRAL" hoặc "REJECT_DEFERRAL"
        reason = request.data.get("reason", "")

        if decision == "APPROVE_DEFERRAL":
            project.deferral_status = "APPROVED"
            project.status = "DEFERRED"
            project.deferral_reason = reason or project.deferral_reason or "Bảo lưu theo quy định học vụ"
            project.deferral_decided_at = timezone.now()
            project.is_eligible_for_defense = False
            project.save()

            AuditLog.objects.create(
                user=request.user,
                action_type="group_status_change",
                description=f"Khoa phê duyệt đơn bảo lưu đồ án cho SV {project.student.registration_no}."
            )
            return Response({"message": "Khoa đã duyệt bảo lưu thành công.", "status": "DEFERRED"}, status=status.HTTP_200_OK)

        elif decision == "REJECT_DEFERRAL":
            project.deferral_status = "REJECTED"
            project.status = "FAILED"
            project.is_eligible_for_defense = False
            project.deferral_reason = reason or "Khoa từ chối đơn bảo lưu -> Không đạt"
            project.deferral_decided_at = timezone.now()
            project.save()

            AuditLog.objects.create(
                user=request.user,
                action_type="group_status_change",
                description=f"Khoa từ chối đơn bảo lưu của SV {project.student.registration_no} -> Loại khỏi đợt."
            )
            return Response({"message": "Đã từ chối đơn bảo lưu và loại khỏi đợt đồ án.", "status": "FAILED"}, status=status.HTTP_200_OK)

        return Response({"detail": "Quyết định không hợp lệ."}, status=status.HTTP_400_BAD_REQUEST)


class AutoDefenseScheduleAPIView(APIView):
    """Xếp lịch bảo vệ tự động (Bước 41)"""
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def post(self, request):
        batch_id = request.data.get("batch_id")
        slot_duration = int(request.data.get("slot_duration", 40))
        morning_start = request.data.get("morning_start", "08:00")
        afternoon_start = request.data.get("afternoon_start", "13:30")

        if not batch_id:
            return Response({"detail": "batch_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        res = DefenseSchedulerEngine.schedule_defense_for_batch(
            batch_id=batch_id,
            slot_duration_minutes=slot_duration,
            morning_start_str=morning_start,
            afternoon_start_str=afternoon_start,
            user=request.user
        )

        return Response(res, status=status.HTTP_200_OK if res.get("success") else status.HTTP_400_BAD_REQUEST)


class ManualReviewerOverrideAPIView(APIView):
    """Khoa điều chỉnh thủ công Hội đồng & Giảng viên phản biện (Bước 40)"""
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def patch(self, request):
        project_id = request.data.get("project_id")
        council_id = request.data.get("council_id")
        reviewer_id = request.data.get("reviewer_id")

        if not project_id:
            return Response({"detail": "project_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        res = ReviewerAndCouncilAllocationEngine.manual_override_reviewer(
            project_id=project_id,
            council_id=council_id,
            reviewer_id=reviewer_id,
            user=request.user
        )

        return Response(res, status=status.HTTP_200_OK if res.get("success") else status.HTTP_400_BAD_REQUEST)


class FinalizeCouncilScoresAPIView(APIView):
    """Hội đồng xác nhận chốt điểm (Bước 43)"""
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def post(self, request, pk):
        council = get_object_or_404(DefenseCouncil, pk=pk)
        council.is_finalized = True
        council.save()

        # Finalize all summaries
        for proj in council.projects.all():
            summary = getattr(proj, "final_grade_summary", None)
            if summary:
                summary.is_finalized = True
                summary.save(update_fields=["is_finalized"])

        AuditLog.objects.create(
            user=request.user,
            action_type="evaluation_update",
            description=f"Hội đồng {council.council_name} đã xác nhận chốt toàn bộ điểm bảo vệ."
        )

        return Response({"message": f"Đã chốt điểm thành công cho {council.council_name}."}, status=status.HTTP_200_OK)


class CouncilMinutesPdfExportAPIView(APIView):
    """
    Giai đoạn 6: Xuất Biên bản họp Hội đồng bảo vệ ĐATN ra định dạng PDF chuẩn UTC.
    Gồm đầy đủ: Thành phần Hội đồng (1CT-2TK-2UV), Điểm từng thành viên, Điểm TB HĐ, Điểm tổng kết và chữ ký.
    """
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def get(self, request, council_id):
        council = get_object_or_404(
            DefenseCouncil.objects.select_related("batch"),
            id=council_id
        )

        import io
        import os
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        font_name = "Helvetica"
        if os.path.exists("C:\\Windows\\Fonts\\arial.ttf"):
            try:
                pdfmetrics.registerFont(TTFont("Arial", "C:\\Windows\\Fonts\\arial.ttf"))
                font_name = "Arial"
            except Exception:
                pass

        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        # Header
        p.setFont(font_name, 10)
        p.drawString(45, height - 45, "TRƯỜNG ĐẠI HỌC GIAO THÔNG VẬN TẢI")
        p.drawString(45, height - 60, "KHOA CÔNG NGHỆ THÔNG TIN")
        p.drawString(width - 230, height - 45, "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM")
        p.drawString(width - 190, height - 60, "Độc lập - Tự do - Hạnh phúc")

        p.setFont(font_name, 14)
        p.drawCentredString(width / 2, height - 100, f"BIÊN BẢN HỌP HỘI ĐỒNG BẢO VỆ ĐỒ ÁN TỐT NGHIỆP #{council.council_number}")

        p.setFont(font_name, 9)
        y = height - 128
        session_time_disp = council.get_session_time_display()
        p.drawString(45, y, f"Hội đồng: {council.council_name} | Phòng: {council.defense_room or 'TBA'} | Ngày: {council.session_date or 'TBA'} ({session_time_disp})")
        y -= 22

        p.setFont(font_name, 10)
        p.drawString(45, y, "I. THÀNH PHẦN HỘI ĐỒNG (Cơ cấu chuẩn UTC: 1 Chủ tịch - 2 Thư ký - 2 Ủy viên):")
        y -= 16
        p.setFont(font_name, 9)
        members = list(council.members.select_related("user", "supervisor").all())
        for idx, m in enumerate(members, 1):
            deg = m.supervisor.academic_title if m.supervisor else ""
            p.drawString(65, y, f"{idx}. {m.get_role_display()}: {deg} {m.user.get_full_name()} ({m.user.email})")
            y -= 15

        y -= 12
        p.setFont(font_name, 10)
        p.drawString(45, y, "II. KẾT QUẢ ĐÁNH GIÁ VÀ ĐIỂM BẢO VỆ:")
        y -= 18
        p.setFont(font_name, 8)
        p.drawString(45, y, "STT | MSSV | Họ và tên SV | Điểm GVHD | Điểm GVPB | Điểm TB HĐ | Điểm TK (Hệ 10 / Chữ / Xếp loại)")
        y -= 14

        projects = council.projects.select_related("student__user", "final_grade_summary").all()
        for idx, proj in enumerate(projects, 1):
            summary = getattr(proj, "final_grade_summary", None)
            sup_s = f"{proj.supervisor_score:.1f}" if proj.supervisor_score is not None else "--"
            rev_s = f"{proj.reviewer_score:.1f}" if proj.reviewer_score is not None else "--"
            cou_s = f"{summary.council_avg_score:.2f}" if summary and summary.council_avg_score is not None else "--"
            fin_s = f"{summary.final_score_10:.2f} ({summary.final_letter_grade} - {summary.classification})" if summary and summary.final_score_10 is not None else "--"
            s_name = proj.student.user.get_full_name() if proj.student and proj.student.user else ""
            p.drawString(45, y, f"{idx}. {proj.student.registration_no} - {s_name} | {sup_s}đ | {rev_s}đ | {cou_s}đ | {fin_s}")
            y -= 15
            if y < 90:
                p.showPage()
                y = height - 50

        y -= 30
        p.setFont(font_name, 9)
        p.drawString(65, y, "CHỦ TỊCH HỘI ĐỒNG")
        p.drawString(width - 200, y, "THƯ KÝ HỘI ĐỒNG")
        p.drawString(65, y - 14, "(Ký và ghi rõ họ tên)")
        p.drawString(width - 200, y - 14, "(Ký và ghi rõ họ tên)")

        p.showPage()
        p.save()

        buffer.seek(0)
        filename = f"Bien_ban_HD_{council.council_number}.pdf"
        response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class CloseBatchAPIView(APIView):
    """Khoa kết thúc đợt đồ án (Bước 46)"""
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def post(self, request, pk):
        batch = get_object_or_404(AcademicBatch, pk=pk)
        batch.current_stage = "COMPLETED"
        batch.is_closed = True
        batch.save(update_fields=["current_stage", "is_closed"])

        AuditLog.objects.create(
            user=request.user,
            action_type="group_status_change",
            description=f"Khoa đã chính thức kết thúc Đợt đồ án {batch.batch_code}."
        )

        return Response({"message": f"Đợt {batch.batch_code} đã hoàn tất và kết thúc thành công."}, status=status.HTTP_200_OK)


class ExportFinalSummaryExcelAPIView(APIView):
    """Xuất dữ liệu cuối kỳ - ký (Bước 45)"""
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def get(self, request):
        batch_id = request.query_params.get("batch_id")
        if not batch_id:
            return Response({"detail": "batch_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            buffer = DocumentGenerationService.generate_final_summary_excel(batch_id)
            response = HttpResponse(
                buffer.getvalue(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            response["Content-Disposition"] = f'attachment; filename="Du_lieu_cuoi_ky_Dot_{batch_id}.xlsx"'
            return response
        except Exception as ex:
            return Response({"detail": f"Error generating document: {str(ex)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==============================================================================
# PHÂN HỆ GIÁO VỤ (ACADEMIC STAFF MODULE) - TỔNG HỢP & XUẤT ĐIỂM THEO LỚP
# ==============================================================================

class AcademicStaffFinalGradesAPIView(APIView):
    """
    Chức năng cuối kỳ cho Giáo vụ:
    - Nhận dữ liệu tổng hợp điểm cuối kỳ theo từng lớp hoặc toàn đợt.
    - Trả về thống kê số lượng đạt, trượt, bảo lưu, điểm trung bình.
    """
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def get(self, request):
        batch_id = request.query_params.get("batch_id")
        class_id = request.query_params.get("class_id")
        search = (request.query_params.get("search") or "").strip().lower()

        if not batch_id:
            batch = AcademicBatch.objects.filter(is_active=True).first() or AcademicBatch.objects.first()
            if not batch:
                return Response({"detail": "Chưa có đợt đồ án nào trong hệ thống."}, status=status.HTTP_404_NOT_FOUND)
            batch_id = batch.id
        else:
            batch = get_object_or_404(AcademicBatch, id=batch_id)

        # Lấy danh sách các lớp học phần trong đợt
        classes_qs = CourseClass.objects.filter(batch=batch).order_by("class_code")
        classes_data = []
        for c in classes_qs:
            st_count = Student.objects.filter(course_class=c).count()
            classes_data.append({
                "id": c.id,
                "class_code": c.class_code,
                "class_name": c.class_name,
                "program_type": c.program_type,
                "program_display": c.get_program_type_display(),
                "student_count": st_count,
            })

        # Lấy danh sách đồ án tốt nghiệp
        projects_qs = GraduationProject.objects.filter(batch=batch).select_related(
            "student__user",
            "student__course_class",
            "supervisor__user",
            "reviewer__user",
            "council",
            "final_grade_summary"
        ).order_by("student__course_class__class_code", "student__registration_no")

        if class_id:
            projects_qs = projects_qs.filter(student__course_class_id=class_id)

        if search:
            projects_qs = projects_qs.filter(
                Q(student__registration_no__icontains=search) |
                Q(student__user__first_name__icontains=search) |
                Q(student__user__last_name__icontains=search) |
                Q(topic_title_vi__icontains=search)
            )

        grades_list = []
        passed_count = 0
        failed_count = 0
        deferred_count = 0
        scores_10 = []

        for p in projects_qs:
            std = p.student
            usr = std.user
            summary = getattr(p, "final_grade_summary", None)
            is_deferred = (p.deferral_status == "APPROVED")

            # Auto calculate if missing
            if not summary and (p.supervisor_score is not None or p.reviewer_score is not None):
                summary, _ = FinalGradeSummary.objects.get_or_create(project=p)
                summary.supervisor_score = p.supervisor_score
                summary.reviewer_score = p.reviewer_score
                scores = list(CouncilLiveScore.objects.filter(project=p))
                if scores:
                    summary.council_avg_score = round(sum(s.total_score for s in scores) / len(scores), 2)
                summary.calculate_and_save()

            if is_deferred:
                deferred_count += 1
                verdict = "Bảo lưu"
            elif summary and summary.is_passed:
                passed_count += 1
                verdict = "Đạt"
                if summary.final_score_10 is not None:
                    scores_10.append(summary.final_score_10)
            else:
                failed_count += 1
                verdict = "Không đạt"
                if summary and summary.final_score_10 is not None:
                    scores_10.append(summary.final_score_10)

            c_code = std.course_class.class_code if std.course_class else ""
            c_name = std.course_class.class_name if std.course_class else (std.department or "CNTT")

            grades_list.append({
                "project_id": p.id,
                "student_id": std.id,
                "registration_no": std.registration_no,
                "student_name": usr.get_full_name() or usr.username,
                "course_class_id": std.course_class_id,
                "class_code": c_code,
                "class_name": c_name,
                "education_program": std.education_program,
                "education_program_display": std.get_education_program_display(),
                "topic_title_vi": p.topic_title_vi,
                "supervisor_name": f"{p.supervisor.academic_title or ''} {p.supervisor.user.get_full_name()}".strip() if p.supervisor else "",
                "reviewer_name": f"{p.reviewer.academic_title or ''} {p.reviewer.user.get_full_name()}".strip() if p.reviewer else "",
                "council_name": p.council.council_name if p.council else "",
                "supervisor_score": summary.supervisor_score if summary else p.supervisor_score,
                "reviewer_score": summary.reviewer_score if summary else p.reviewer_score,
                "council_avg_score": summary.council_avg_score if summary else None,
                "final_score_10": summary.final_score_10 if (summary and not is_deferred) else None,
                "final_score_4": summary.final_score_4 if (summary and not is_deferred) else None,
                "final_letter_grade": summary.final_letter_grade if (summary and not is_deferred) else "",
                "classification": summary.classification if (summary and not is_deferred) else "",
                "is_passed": summary.is_passed if (summary and not is_deferred) else False,
                "is_deferred": is_deferred,
                "deferral_reason": p.deferral_reason or "",
                "verdict": verdict,
                "debt_credits": p.debt_credits,
                "status": p.status,
            })

        total_st = len(grades_list)
        avg_score = round(sum(scores_10) / len(scores_10), 2) if scores_10 else 0.0
        pass_rate = round((passed_count / total_st) * 100, 1) if total_st > 0 else 0.0

        return Response({
            "batch": {
                "id": batch.id,
                "batch_code": batch.batch_code,
                "batch_name": batch.batch_name,
                "program_type": batch.program_type,
                "current_stage": batch.current_stage,
                "is_closed": batch.is_closed,
            },
            "classes": classes_data,
            "selected_class_id": int(class_id) if class_id else None,
            "grades": grades_list,
            "stats": {
                "total_students": total_st,
                "passed_count": passed_count,
                "failed_count": failed_count,
                "deferred_count": deferred_count,
                "pass_rate": pass_rate,
                "average_score": avg_score,
            }
        }, status=status.HTTP_200_OK)


class AcademicStaffExportClassGradesExcelAPIView(APIView):
    """
    Xuất danh sách điểm đồ án tốt nghiệp theo từng lớp (hoặc toàn đợt) ra file Excel.
    """
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def get(self, request):
        batch_id = request.query_params.get("batch_id")
        class_id = request.query_params.get("class_id")

        if not batch_id:
            batch = AcademicBatch.objects.filter(is_active=True).first() or AcademicBatch.objects.first()
            if not batch:
                return Response({"detail": "batch_id is required."}, status=status.HTTP_400_BAD_REQUEST)
            batch_id = batch.id

        try:
            buffer = DocumentGenerationService.generate_class_grades_excel(batch_id, class_id)
            batch = AcademicBatch.objects.get(id=batch_id)
            c_tag = f"_Lop_{class_id}" if class_id else "_Toan_Dot"
            filename = f"Bang_Diem_Do_An_{batch.batch_code}{c_tag}.xlsx"

            response = HttpResponse(
                buffer.getvalue(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response
        except Exception as ex:
            return Response({"detail": f"Lỗi tạo file bảng điểm: {str(ex)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AcademicStaffExportEligibilityReportExcelAPIView(APIView):
    """
    Giai đoạn 4: Xuất báo cáo danh sách sinh viên đủ điều kiện và không đủ điều kiện (bảo lưu) ra file Excel.
    """
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def get(self, request):
        batch_id = request.query_params.get("batch_id")
        if not batch_id:
            batch = AcademicBatch.objects.filter(is_active=True).first() or AcademicBatch.objects.first()
            if not batch:
                return Response({"detail": "batch_id is required."}, status=status.HTTP_400_BAD_REQUEST)
            batch_id = batch.id

        try:
            buffer = DocumentGenerationService.generate_eligibility_report_excel(batch_id)
            batch = AcademicBatch.objects.get(id=batch_id)
            filename = f"Bao_Cao_Hau_Kiem_Hoc_Vu_Dot_{batch.batch_code}.xlsx"

            response = HttpResponse(
                buffer.getvalue(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response
        except Exception as ex:
            return Response({"detail": f"Lỗi tạo báo cáo hậu kiểm học vụ: {str(ex)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AcademicStaffCompleteBatchAPIView(APIView):
    """
    Giáo vụ / Ban Chủ nhiệm Khoa hoàn tất và đóng đợt đồ án tốt nghiệp.
    """
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def post(self, request):
        batch_id = request.data.get("batch_id")
        if not batch_id:
            return Response({"detail": "batch_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        batch = get_object_or_404(AcademicBatch, id=batch_id)
        batch.current_stage = "COMPLETED"
        batch.is_closed = True
        batch.save(update_fields=["current_stage", "is_closed"])

        AuditLog.objects.create(
            user=request.user,
            action_type="group_status_change",
            description=f"Giáo vụ Khoa hoàn tất và đóng đợt đồ án {batch.batch_code}."
        )

        return Response({
            "message": f"Đợt đồ án '{batch.batch_name}' ({batch.batch_code}) đã được Giáo vụ hoàn tất và khóa sổ thành công.",
            "batch_id": batch.id,
            "current_stage": "COMPLETED",
            "is_closed": True
        }, status=status.HTTP_200_OK)


class AdminSeedDataAPIView(APIView):
    """
    Khôi phục và nạp bộ dữ liệu mẫu UTC cho Admin Portal
    (Bao gồm Admin, Giảng viên, Sinh viên, Đợt đồ án, Bộ môn, Hội đồng)
    """
    permission_classes = [IsAuthenticated, IsAdminUserRole]

    def post(self, request):
        from django.core.management import call_command
        reset = str(request.data.get("reset", "")).lower() in ["true", "1"]
        try:
            if reset:
                call_command("seed_admin_data", reset=True)
            else:
                call_command("seed_admin_data")

            invalidate_user_summary_cache()
            cache.delete(BATCHES_CACHE_KEY)

            user_counts = CustomUser.objects.aggregate(
                total_students=Count('id', filter=Q(user_type="student")),
                total_supervisors=Count('id', filter=Q(user_type="supervisor")),
                total_committee=Count('id', filter=Q(user_type="committee_member")),
                total_external=Count('id', filter=Q(user_type="external_examiner")),
                total_admins=Count('id', filter=Q(user_type="admin")),
            )

            return Response({
                "success": True,
                "message": "Nạp bộ dữ liệu mẫu UTC thành công!",
                "stats": {
                    "total_students": user_counts["total_students"] or 0,
                    "total_supervisors": user_counts["total_supervisors"] or 0,
                    "total_committee": user_counts["total_committee"] or 0,
                    "total_external": user_counts["total_external"] or 0,
                    "total_admins": user_counts["total_admins"] or 0,
                    "total_batches": AcademicBatch.objects.count(),
                    "total_projects": GraduationProject.objects.count(),
                    "total_councils": DefenseCouncil.objects.count(),
                }
            }, status=status.HTTP_200_OK)
        except Exception as ex:
            logger.exception("Error running seed_admin_data")
            return Response({
                "success": False,
                "error": f"Lỗi khi nạp dữ liệu mẫu: {str(ex)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



