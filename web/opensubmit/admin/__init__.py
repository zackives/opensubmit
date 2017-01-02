from django.contrib.auth.models import User, Permission, Group
from opensubmit.models import Course, Grading, GradingScheme, Assignment, SubmissionFile, Submission, TestMachine
from opensubmit import settings
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.views import redirect_to_login
from django.contrib import messages
from django.shortcuts import redirect
from django.core.exceptions import PermissionDenied

from user import UserAdmin
from course import CourseAdmin
from grading import GradingAdmin
from gradingscheme import GradingSchemeAdmin
from assignment import AssignmentAdmin
from submissionfile import SubmissionFileAdmin
from submission import SubmissionAdmin

def _social_auth_login(self, request, **kwargs):
    '''
        View function that redirects to social auth login,
        in case the user is not logged in.
    '''
    if request.user.is_authenticated():
        if not request.user.is_active or not request.user.is_staff:
            raise PermissionDenied()
    else:
        messages.add_message(request, messages.WARNING, 'Please authenticate first.')
        return redirect_to_login(request.get_full_path())

class AdminBackend(AdminSite):
    site_header = "OpenSubmit"
    site_url = settings.MAIN_URL
    index_title = "Administrator Backend"

    def app_index(self, request, app_label, extra_context=None):
        return redirect('admin:index')


admin_backend = AdminBackend(name="admin")
admin_backend.register(User, UserAdmin)
admin_backend.register(Permission)
admin_backend.register(Group)
admin_backend.register(TestMachine)


class TeacherBackend(AdminSite):
    site_header = "OpenSubmit"
    site_url = settings.MAIN_URL
    index_title = "Teacher Backend"
    login = _social_auth_login

    def app_index(self, request, app_label, extra_context=None):
        return redirect('teacher:index')

teacher_backend = TeacherBackend(name="teacher")
teacher_backend.register(Grading, GradingAdmin)
teacher_backend.register(GradingScheme, GradingSchemeAdmin)
teacher_backend.register(Assignment, AssignmentAdmin)
teacher_backend.register(SubmissionFile, SubmissionFileAdmin)
teacher_backend.register(Submission, SubmissionAdmin)
teacher_backend.register(Course, CourseAdmin)
