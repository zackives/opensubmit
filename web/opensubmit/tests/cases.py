'''
    Base functionality for OpenSubmit test suite.
'''
import datetime
import logging
import json
import os
import shutil

from django import http

from django.conf import settings
from django.utils import timezone

from django.test import TransactionTestCase, LiveServerTestCase
from django.test.utils import override_settings
from django.test.client import Client
from django.core.files import File as DjangoFile


from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password, PBKDF2SHA1PasswordHasher

from opensubmit.models import Course, Assignment, Submission, SubmissionFile, SubmissionTestResult
from opensubmit.models import Grading, GradingScheme, TestMachine
from opensubmit.models import UserProfile

rootdir=os.getcwd()

# Unicode crap, to be added to all test suite string input
# Ensures proper handling of unicode content everywhere, as reaction to #154
uccrap = u'\u1234\u2345\u3456'

class AnonStruct(object):
    def __init__(self, entries):
        self.__dict__.update(entries)

@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher',])
@override_settings(MEDIA_ROOT='/tmp/')
class SubmitTestCase(LiveServerTestCase):
    '''
        A test case base class with several resources being prepared:

        Users:
        - self.admin
        - self.teacher
        - self.another_teacher
        - self.tutor
        - self.enrolled_students
        - self.not_enrolled_students
        - self.current_user (the one currently logged-in)

        No user is logged-in after setup.

        Courses:
        - self.course (by self.teacher)
        - self.anotherCourse (by self.another_teacher)
        - self.inactiveCourse
        - self.all_courses

        Assignments:
        - self.openAssignment (in self.course)
        - self.validatedAssignment (in self.course)
        - self.softDeadlinePassedAssignment (in self.course)
        - self.hardDeadlinePassedAssignment (in self.course)
        - self.unpublishedAssignment (in self.course)
        - self.allAssignments

        Gradings:
        - self.passGrade
        - self.failGrade
        - self.passFailGrading

        The class offers some convinience functions:
        - createTestMachine(self, test_host)
        - createSubmissionFile(self)
        - createTestedSubmissionFile(self, test_machine)
        - createValidatableSubmission(self, user)
        - createValidatedSubmission(self, user, test_host='127.0.0.1')
        - createSubmission(self, user, assignment)
    '''
    current_user = None

    def setUp(self):
        settings.MAIN_URL=self.live_server_url
        super(SubmitTestCase, self).setUp()
        # How much do you want to see from the OpenSubmit web code
        self.logger = logging.getLogger('OpenSubmit')
        self.logger.setLevel(logging.ERROR)
        # How much do you want to see from the OpenSubmit executor
        self.logger = logging.getLogger('OpenSubmitExecutor')
        self.logger.setLevel(logging.ERROR)
        self.setUpUsers()
        self.setUpCourses()
        self.setUpGradings()
        self.setUpAssignments()

    def createUser(self, user_dict):
        args = dict(user_dict)
        args['password'] = make_password(args['password'])
        user_obj = User(**args)
        user_obj.save()

        user_profile = UserProfile(user=user_obj)
        user_profile.save()

        user_dict['user'] = user_obj
        user_dict['profile'] = user_profile
        user_struct = AnonStruct(user_dict)
        return user_struct

    def loginUser(self, user_struct):
        assert(self.c.login(username=user_struct.username, password=user_struct.password))
        uid = self.c.session['_auth_user_id']
        user_struct.user = User.objects.get(pk=uid)
        self.current_user = user_struct

    def setUpUsers(self):
        self.c = Client()

        self.admin_dict = {
            'username': uccrap+'testrunner_admin',
            'password': uccrap+'PNZabhExaL6H',
            'email': uccrap+'testrunner_admin@django.localhost.local',
            'is_staff': True,
            'is_superuser': True
        }
        self.admin = self.createUser(self.admin_dict)

        self.teacher_dict = {
            'username': uccrap+'testrunner_teacher',
            'password': uccrap+'2tVvWzdknP56',
            'email': uccrap+'testrunner_teacher@django.localhost.local',
            'is_staff': True,
            'is_superuser': False
        }
        self.teacher = self.createUser(self.teacher_dict)

        self.another_teacher_dict = {
            'username': uccrap+'testrunner_anotherTeacher',
            'password': uccrap+'LW8vhgQWz5kT',
            'email': uccrap+'testrunner_anotherTeacher@django.localhost.local',
            'is_staff': True,
            'is_superuser': False
        }
        self.another_teacher = self.createUser(self.another_teacher_dict)

        self.tutor_dict = {
            'username': uccrap+'testrunner_tutor',
            'password': uccrap+'2tVP56vMadkn',
            'email': uccrap+'testrunner_tutor@django.localhost.local',
            'is_staff': True,
            'is_superuser': False
        }
        self.tutor = self.createUser(self.tutor_dict)

        self.enrolled_students = list()
        for i in range(0, 5):
            enrolled_student_dict = {
                'username': uccrap+'testrunner_enrolled_student{}'.format(i),
                'password': uccrap+'very{}secret'.format(i),
                'email': uccrap+'testrunner_enrolled_student{}@django.localhost.local'.format(i),
                'is_staff': False,
                'is_superuser': False,
                'first_name': uccrap+'Harold',
                'last_name': uccrap+'Finch'
            }
            self.enrolled_students.append(self.createUser(enrolled_student_dict))

        self.not_enrolled_students = list()
        for i in range(0, 5):
            not_enrolled_student_dict = {
                'username': uccrap+'testrunner_not_enrolled_student{}'.format(i),
                'password': uccrap+'not.very{}secret'.format(i),
                'email': uccrap+'testrunner_not_enrolled_student{}@django.localhost.local'.format(i),
                'is_staff': False,
                'is_superuser': False
            }
            self.not_enrolled_students.append(self.createUser(not_enrolled_student_dict))

    def setUpCourses(self):
        self.all_courses = []

        self.course = Course(
            title=uccrap+'Active test course',
            active=True,
            owner=self.teacher.user,
            max_authors=3,
        )
        self.course.save()
        self.course.tutors.add(self.tutor.user)
        for student in self.enrolled_students:
            self.course.participants.add(student.profile)
        self.all_courses.append(self.course)

        self.anotherCourse = Course(
            title=uccrap+'Another active test course',
            active=True,
            owner=self.another_teacher.user,
            max_authors=1,
        )
        self.anotherCourse.save()
        self.all_courses.append(self.anotherCourse)

        self.inactiveCourse = Course(
            title=uccrap+'Inactive test course',
            active=False,
            owner=self.another_teacher.user,
            max_authors=1,
        )
        self.inactiveCourse.save()
        self.all_courses.append(self.inactiveCourse)

    def setUpGradings(self):
        self.passGrade = Grading(title=uccrap+'passed', means_passed=True)
        self.passGrade.save()
        self.failGrade = Grading(title=uccrap+'failed', means_passed=False)
        self.failGrade.save()

        self.passFailGrading = GradingScheme(title=uccrap+'Pass/Fail Grading Scheme')
        self.passFailGrading.save()
        self.passFailGrading.gradings.add(self.passGrade)
        self.passFailGrading.gradings.add(self.failGrade)
        self.passFailGrading.save()

    def setUpAssignments(self):
        today = timezone.now()
        last_week = today - datetime.timedelta(weeks=1)
        yesterday = today - datetime.timedelta(days=1)
        tomorrow = today + datetime.timedelta(days=1)
        next_week = today + datetime.timedelta(weeks=1)

        # List of all assignments being assigned to the "self.course" course
        self.allAssignments = []

        self.openAssignment = Assignment(
            title=uccrap+'Open assignment',
            course=self.course,
            download=u'http://example.org/assignments/1/download'+uccrap,
            gradingScheme=self.passFailGrading,
            publish_at=last_week,
            soft_deadline=tomorrow,
            hard_deadline=next_week,
            has_attachment=False
        )
        self.openAssignment.save()
        self.allAssignments.append(self.openAssignment)

        self.anotherAssignment = Assignment(
            title=uccrap+'Another open assignment',
            course=self.anotherCourse,
            download=u'http://example.org/assignments/1/download'+uccrap,
            gradingScheme=self.passFailGrading,
            publish_at=last_week,
            soft_deadline=tomorrow,
            hard_deadline=next_week,
            has_attachment=False
        )
        self.anotherAssignment.save()

        self.fileAssignment = Assignment(
            title=uccrap+'File assignment',
            course=self.course,
            download=u'http://example.org/assignments/1/download'+uccrap,
            gradingScheme=self.passFailGrading,
            publish_at=last_week,
            soft_deadline=tomorrow,
            hard_deadline=next_week,
            has_attachment=True
        )
        self.fileAssignment.save()
        self.allAssignments.append(self.fileAssignment)

        # Move test files to current MEDIA_ROOT, otherwise Django security complains
        working_zip=settings.MEDIA_ROOT+"working.zip"
        supportfiles_zip=settings.MEDIA_ROOT+"supportfiles.zip"
        single_file=settings.MEDIA_ROOT+"validator.py"
        shutil.copyfile(rootdir+'/opensubmit/tests/validators/working.zip', working_zip)
        shutil.copyfile(rootdir+'/opensubmit/tests/validators/supportfiles.zip', supportfiles_zip)
        shutil.copyfile(rootdir+'/opensubmit/tests/validators/validator.py', single_file)

        self.validatedAssignment = Assignment(
            title=uccrap+'Validated assignment',
            course=self.course,
            download=u'http://example.org/assignments/1/download'+uccrap,
            gradingScheme=self.passFailGrading,
            publish_at=last_week,
            soft_deadline=tomorrow,
            hard_deadline=next_week,
            has_attachment=True,
            validity_script_download=True,
            attachment_test_validity=DjangoFile(open(working_zip)),
            attachment_test_full=DjangoFile(open(working_zip))
        )
        self.validatedAssignment.save()
        self.allAssignments.append(self.validatedAssignment)

        self.singleFileValidatorAssignment = Assignment(
            title=uccrap+'Validated assignment with single file validator',
            course=self.course,
            download=u'http://example.org/assignments/1/download'+uccrap,
            gradingScheme=self.passFailGrading,
            publish_at=last_week,
            soft_deadline=tomorrow,
            hard_deadline=next_week,
            has_attachment=True,
            validity_script_download=True,
            attachment_test_validity=DjangoFile(open(single_file)),
            attachment_test_full=DjangoFile(open(single_file))
        )
        self.singleFileValidatorAssignment.save()
        self.allAssignments.append(self.singleFileValidatorAssignment)

        self.validatedWithSupportFilesAssignment = Assignment(
            title=uccrap+'Validated assignment with support files',
            course=self.course,
            download=u'http://example.org/assignments/1/download'+uccrap,
            gradingScheme=self.passFailGrading,
            publish_at=last_week,
            soft_deadline=tomorrow,
            hard_deadline=next_week,
            has_attachment=True,
            validity_script_download=True,
            attachment_test_validity=DjangoFile(open(working_zip)),
            attachment_test_full=DjangoFile(open(working_zip)),
            attachment_test_support=DjangoFile(open(supportfiles_zip))
        )
        self.validatedWithSupportFilesAssignment.save()
        self.allAssignments.append(self.validatedWithSupportFilesAssignment)

        self.softDeadlinePassedAssignment = Assignment(
            title=uccrap+'Soft deadline passed assignment',
            course=self.course,
            download=u'http://example.org/assignments/2/download'+uccrap,
            gradingScheme=self.passFailGrading,
            publish_at=last_week,
            soft_deadline=yesterday,
            hard_deadline=tomorrow,
            has_attachment=False,
        )
        self.softDeadlinePassedAssignment.save()
        self.allAssignments.append(self.softDeadlinePassedAssignment)

        self.hardDeadlinePassedAssignment = Assignment(
            title=uccrap+'Hard deadline passed assignment',
            course=self.course,
            download=u'http://example.org/assignments/3/download'+uccrap,
            gradingScheme=self.passFailGrading,
            publish_at=last_week,
            soft_deadline=yesterday,
            hard_deadline=yesterday,
            has_attachment=False,
        )
        self.hardDeadlinePassedAssignment.save()
        self.allAssignments.append(self.hardDeadlinePassedAssignment)        

        self.unpublishedAssignment = Assignment(
            title=uccrap+'Unpublished assignment',
            course=self.course,
            download=u'http://example.org/assignments/4/download'+uccrap,
            gradingScheme=self.passFailGrading,
            publish_at=tomorrow,
            soft_deadline=next_week,
            hard_deadline=next_week,
            has_attachment=False,
        )
        self.unpublishedAssignment.save()
        self.allAssignments.append(self.unpublishedAssignment)        

    def createTestMachine(self, test_host):
        '''
            Create test machine entry. The configuration information
            is expected to be some JSON dictionary, since this is
            normally directly rendered in the machine details view.
        '''
        self.machine = TestMachine(
            last_contact=datetime.datetime.now(),
            host = test_host,
            config=json.dumps({'Operating system':uccrap+'Plan 9'}))
        self.machine.save()
        return self.machine

    def createSubmissionFile(self, relpath="/opensubmit/tests/submfiles/working_withsubdir.zip"):
        fname=relpath[relpath.rfind(os.sep)+1:]
        shutil.copyfile(rootdir+relpath, settings.MEDIA_ROOT+fname)
        sf = SubmissionFile(attachment=DjangoFile(open(rootdir+relpath), unicode(fname)))
        sf.save()
        return sf

    def createCompileBrokenSubmissionFile(self, relpath="/opensubmit/tests/submfiles/reverse_submission.zip"):
        fname=relpath[relpath.rfind(os.sep)+1:]
        shutil.copyfile(rootdir+relpath, settings.MEDIA_ROOT+fname)
        sf = SubmissionFile(attachment=DjangoFile(open(settings.MEDIA_ROOT+fname), unicode(fname)))
        sf.save()
        return sf

    def createNoArchiveSubmissionFile(self, relpath="/opensubmit/tests/submfiles/noarchive.txt"):
        fname=relpath[relpath.rfind(os.sep)+1:]
        shutil.copyfile(rootdir+relpath, settings.MEDIA_ROOT+fname)
        sf = SubmissionFile(attachment=DjangoFile(open(settings.MEDIA_ROOT+fname), unicode(fname)))
        sf.save()
        return sf


    def createTestedSubmissionFile(self, test_machine):
        '''
            Create finalized test result in the database.
        '''
        sf = self.createSubmissionFile()
        result_compile  = SubmissionTestResult(
            kind=SubmissionTestResult.COMPILE_TEST,
            result=uccrap+"Compilation ok.",
            machine=test_machine,
            submission_file=sf
            ).save()
        result_validity = SubmissionTestResult(
            kind=SubmissionTestResult.VALIDITY_TEST,
            result=uccrap+"Validation ok.",
            machine=self.machine,
            perf_data = uccrap+";41;42;43",
            submission_file=sf).save()
        result_full     = SubmissionTestResult(
            kind=SubmissionTestResult.FULL_TEST,
            result=uccrap+"Full test ok.",
            perf_data = uccrap+";77;88;99",
            machine=self.machine,
            submission_file=sf).save()
        return sf

    def createValidatableSubmission(self, user):
        '''
            Create a submission that can be validated by executor.
        '''
        sf = self.createSubmissionFile()
        sub = Submission(
            assignment=self.validatedAssignment,
            submitter=user.user,
            notes=uccrap+"This is a validatable submission.",
            state=Submission.TEST_COMPILE_PENDING,
            file_upload=sf
        )
        sub.save()
        return sub

    def createCompileBrokenSubmission(self, user):
        '''
            Create a submission that cannot be compiled.
        '''
        sf = self.createCompileBrokenSubmissionFile()
        sub = Submission(
            assignment=self.validatedAssignment,
            submitter=user.user,
            notes=uccrap+"This is a non-compilable submission.",
            state=Submission.TEST_COMPILE_PENDING,
            file_upload=sf
        )
        fname="reverse_support_files.zip"
        shutil.copyfile(rootdir+'/opensubmit/tests/submfiles/'+fname, settings.MEDIA_ROOT+fname)
        sub.assignment.attachment_test_support=DjangoFile(open(settings.MEDIA_ROOT+fname))
        sub.assignment.save()
        sub.save()
        return sub


    def createSingleFileValidatorSubmission(self, user):
        '''
            Create a submission that can be validated by executor,
            where the validator is a single file and not an archive.
        '''
        sf = self.createSubmissionFile()
        sub = Submission(
            assignment=self.singleFileValidatorAssignment,
            submitter=user.user,
            notes=uccrap+"This is a validatable submission.",
            state=Submission.TEST_COMPILE_PENDING,
            file_upload=sf
        )
        sub.save()
        return sub

    def createValidatableWithSupportFilesSubmission(self, user):
        '''
            Create a submission that can be validated by executor,
            which as support files in the assignment.
        '''
        sf = self.createSubmissionFile()
        sub = Submission(
            assignment=self.validatedWithSupportFilesAssignment,
            submitter=user.user,
            notes=uccrap+"This is a validatable submission for an assignment with support files.",
            state=Submission.TEST_COMPILE_PENDING,
            file_upload=sf
        )
        sub.save()
        return sub

    def createValidatableNoArchiveSubmission(self, user):
        '''
            Create a submission that can be validated by executor.
            It is not an archive and cant be compiled. This tests special
            executor cases, e.g. PDF report submission.
        '''
        sf = self.createNoArchiveSubmissionFile()
        sub = Submission(
            assignment=self.validatedAssignment,
            submitter=user.user,
            notes=uccrap+"This is a validatable submission with a non-archive.",
            state=Submission.TEST_VALIDITY_PENDING,
            file_upload=sf
        )
        sub.save()
        return sub

    def createValidatedSubmission(self, user, test_host='127.0.0.1'):
        '''
            Create a submission that already has test results in the database.
        '''
        machine = self.createTestMachine(test_host)
        sf = self.createTestedSubmissionFile(machine)
        sub = Submission(
            assignment=self.validatedAssignment,
            submitter=user.user,
            notes=uccrap+"This is an already validated submission.",
            state=Submission.SUBMITTED_TESTED,
            file_upload=sf
        )
        sub.save()
        return sub

    def createSubmission(self, user, assignment):
        sub = Submission(
            assignment=assignment,
            submitter=user.user,
            notes=uccrap+"This is a submission.",
            state=Submission.SUBMITTED
        )
        sub.save()
        return sub

class MockRequest(http.HttpRequest):
    def __init__(self, user):
        self.user = user
        # Needed for mocking a functioning messaging middleware
        # see https://code.djangoproject.com/ticket/17971
        self.session = 'session'
        self._messages = FallbackStorage(self)

class SubmitAdminTestCase(SubmitTestCase):
    '''
        Test case with an admin logged-in.
    '''
    def setUp(self):
        super(SubmitAdminTestCase, self).setUp()
        self.loginUser(self.admin)
        self.request = MockRequest(self.admin.user)
        # Test for amok-running post_save handlers (we had such a case)
        assert(self.current_user.user.is_active)
        assert(self.current_user.user.is_superuser)
        assert(self.current_user.user.is_staff)

class SubmitTeacherTestCase(SubmitTestCase):
    '''
        Test case with an teacher (course owner) logged-in.
    '''
    def setUp(self):
        super(SubmitTeacherTestCase, self).setUp()
        self.loginUser(self.teacher)
        self.request = MockRequest(self.teacher.user)
        # Test for amok-running post_save handlers (we had such a case)
        assert(self.current_user.user.is_active)
        assert(self.current_user.user.is_staff)


class SubmitTutorTestCase(SubmitTestCase):
    '''
        Test case with a tutor logged-in.
    '''
    def setUp(self):
        super(SubmitTutorTestCase, self).setUp()
        self.loginUser(self.tutor)
        self.request = MockRequest(self.tutor.user)
        # Test for amok-running post_save handlers (we had such a case)
        assert(self.current_user.user.is_active)
        assert(not self.current_user.user.is_superuser)
        assert(self.current_user.user.is_staff)

class StudentTestCase(SubmitTestCase):
    '''
        Test case with a student logged-in.
    '''
    def setUp(self):
        super(StudentTestCase, self).setUp()
        self.loginUser(self.enrolled_students[0])
        self.request = MockRequest(self.enrolled_students[0].user)

