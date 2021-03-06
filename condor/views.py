#-*- coding:utf-8 -*-

from django.http import HttpResponseRedirect, HttpResponseForbidden, HttpResponse
from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.contrib.auth.models import User

from condor.models import Parent, Student, Attendance, GradeReport, AcademicCalendar, Subject, ClassRoom, Config

from sendsms import api
import re
from decimal import Decimal

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import cm
from reportlab.lib.colors import red, black

def send_message (request):
    """ sends message to the parents with the students name associated included in the message """

    if not "FLAG" in request.POST or not "PARENTS" in request.POST or not "STUDENTS" in request.POST or not "MESSAGE" in request.POST: # making sure the user is not accessing the url directly
        return HttpResponseForbidden ("<title>Code እምቢየው</title><h1 style='font-weight:normal;'>Error: Cannot access this page directly</h1>")

    if request.POST ["FLAG"] == "SMS":
        PARENTS = Parent.objects.filter(id__in = request.POST ["PARENTS"].split("_"))
        STUDENTS = Student.objects.filter(id__in = request.POST ["STUDENTS"].split("_"))

        ERROR_FLAG = False
        for parent in PARENTS:
            MESSAGE = ""
            PARENT_CHILDREN = parent.student_set.all()

            for CHILD in PARENT_CHILDREN:
                if CHILD in STUDENTS:
                    MESSAGE += CHILD.first_name +" "+ CHILD.father_name +", "

            MESSAGE = MESSAGE[:-2] +": "+ request.POST ["MESSAGE"]

            try:
                api.send_sms(body=MESSAGE, from_phone=getattr(settings, 'TWILIO_NUMBER', ''), to=[str(parent.phone_number)])
            except:
                messages.add_message (request, messages.ERROR, "SMS message has not been sent, Please contact your SMS gateway provider")
                ERROR_FLAG = True
                break

        if not ERROR_FLAG:
            messages.add_message (request, messages.INFO, "SMS message has been sent successfully")

        #TODO: Log
        return HttpResponseRedirect ("/TheCondor/condor/student/")

    elif request.POST ["FLAG"] == "EMAIL":
        PARENTS = Parent.objects.filter(id__in = request.POST ["PARENTS"].split("_"))
        STUDENTS = Student.objects.filter(id__in = request.POST ["STUDENTS"].split("_"))

        ERROR_FLAG = False
        for parent in PARENTS:
            MESSAGE = ""

            if len (parent.email) > 3:
                PARENT_CHILDREN = parent.student_set.all()

                for CHILD in PARENT_CHILDREN:
                    if CHILD in STUDENTS:
                        MESSAGE += CHILD.first_name +" "+ CHILD.father_name +", "

                MESSAGE = MESSAGE[:-2] + ": " + request.POST ["MESSAGE"]

                try:
                    send_mail(getattr(settings, 'EMAIL_SUBJECT', ''), MESSAGE, getattr(settings, 'EMAIL_FROM', ''), [parent.email], fail_silently = False)
                except:
                    messages.add_message (request, messages.ERROR, "Email message has not been sent, Please check your email settings")
                    ERROR_FLAG = True
                    break

        if not ERROR_FLAG:
            messages.add_message (request, messages.INFO, "Email message has been sent successfully")

        #TODO: log
        return HttpResponseRedirect ("/TheCondor/condor/student/")

    elif request.POST ["FLAG"] == "BOTH":
        PARENTS = Parent.objects.filter(id__in = request.POST ["PARENTS"].split("_"))
        STUDENTS = Student.objects.filter(id__in = request.POST ["STUDENTS"].split("_"))

        MESSAGE_ADDED = False
        for parent in PARENTS:
            MESSAGE = ""
            PARENT_CHILDREN = parent.student_set.all()

            for CHILD in PARENT_CHILDREN:
                if CHILD in STUDENTS:
                    MESSAGE += CHILD.first_name +" "+ CHILD.father_name +", "

            MESSAGE = MESSAGE[:-2] +": "+ request.POST ["MESSAGE"]

            try:
                api.send_sms(body=MESSAGE, from_phone=getattr(settings, 'TWILIO_NUMBER', ''), to=[str(parent.phone_number)])
                if not MESSAGE_ADDED:
                    messages.add_message (request, messages.INFO, "SMS message has been sent successfully")
                    MESSAGE_ADDED = True
            except:
                messages.add_message (request, messages.ERROR, "Some SMS messages have not been sent, Please contact your SMS gateway provider")
                break

        MESSAGE_ADDED = False
        for parent in PARENTS:
            MESSAGE = ""

            if len (parent.email) > 3:
                PARENT_CHILDREN = parent.student_set.all()

                for CHILD in PARENT_CHILDREN:
                    if CHILD in STUDENTS:
                        MESSAGE += CHILD.first_name +" "+ CHILD.father_name +", "

                MESSAGE = MESSAGE[:-2] + ": " + request.POST ["MESSAGE"]

                try:
                    send_mail(getattr(settings, 'EMAIL_SUBJECT', ''), MESSAGE, getattr(settings, 'EMAIL_FROM', ''), [parent.email], fail_silently = False)
                    if not MESSAGE_ADDED:
                        messages.add_message (request, messages.INFO, "Email message has been sent successfully")
                        MESSAGE_ADDED = True
                except:
                    messages.add_message (request, messages.ERROR, "Email messages have not been sent")
                    break

        #TODO: log
        return HttpResponseRedirect ("/TheCondor/condor/student/")

def notify_parents (request):
    """ Notifies parents on stuff, using the attendance sheet """

    if not "ATTENDANCE_SHEET" in request.POST or not "FLAG" in request.POST or not "MESSAGE" in request.POST: # making sure the user is not accessing the url directly
        return HttpResponseForbidden ("<title>Code እምቢየው</title><h1 style='font-weight:normal;'>Error: Cannot access this page directly</h1>")

    ATTENDANCE_SHEET = Attendance.objects.filter (id__in = request.POST ["ATTENDANCE_SHEET"].split("_"))
    PARENT_LIST = {}
    for A in ATTENDANCE_SHEET:
        for S in A.student.all():
            for P in S.parents.all():
                PARENT_LIST [P.id] = ""

    for P in PARENT_LIST:
        for A in ATTENDANCE_SHEET:
            P_FOUND = False
            for S in A.student.all():
                for PR in S.parents.all():
                    if PR.id == P:
                        P_FOUND = True
                        PARENT_LIST [P] += S.first_name +" "+ S.father_name +", "

            if P_FOUND:
                """
                print ("---------------------------------------------------------------------------")
                print (PARENT_LIST [P])
                print ("---------------------------------------------------------------------------")
                """
                PARENT_LIST [P] = PARENT_LIST [P] +": "+ A.attendance_date.strftime("%A, %B %d") +", "+ A.attendance_type.title() +"\n"

    MESSAGE = request.POST ["MESSAGE"]

    # preparing message to be sent for each parent, depends weather or not a custom message is added or not
    if len(MESSAGE):
        for P in PARENT_LIST:
            PARENT_LIST [P] += MESSAGE

    else:
        for P in PARENT_LIST:
            PARENT_LIST [P] = PARENT_LIST [P][:-1]

    if request.POST ["FLAG"] == "SMS":
        ERROR_FLAG = False

        for P in PARENT_LIST:
            try:
                api.send_sms (body = PARENT_LIST[P], from_phone=getattr(settings, 'TWILIO_NUMBER', ''), to=[Parent.objects.get(pk = P).phone_number])
            except:
                messages.add_message (request, messages.ERROR, "SMS message has not been sent, Please contact your SMS gateway provider")
                ERROR_FLAG = True
                break

        if not ERROR_FLAG:
            messages.add_message (request, messages.INFO, "SMS message has been sent successfully")

    elif request.POST ["FLAG"] == "EMAIL":
        ERROR_FLAG = False

        for P in PARENT_LIST:
            if len (Parent.objects.get(pk = P).email):
                try:
                    send_mail(getattr(settings, 'EMAIL_SUBJECT', ''), PARENT_LIST[P], getattr(settings, 'EMAIL_FROM', ''), [Parent.objects.get(pk = P).email], fail_silently = False)
                except:
                    messages.add_message (request, messages.ERROR, "Email message has not been sent, Please check your email settings")
                    ERROR_FLAG = True
                    break

        if not ERROR_FLAG:
            messages.add_message (request, messages.INFO, "Email message has been sent successfully")

    elif request.POST ["FLAG"] == "BOTH":
        ERROR_FLAG = False

        for P in PARENT_LIST:
            try:
                api.send_sms (body = PARENT_LIST[P], from_phone=getattr(settings, 'TWILIO_NUMBER', ''), to=[Parent.objects.get(pk = P).phone_number])
            except:
                messages.add_message (request, messages.ERROR, "SMS message has not been sent, Please contact your SMS gateway provider")
                ERROR_FLAG = True
                break

        if not ERROR_FLAG:
            messages.add_message (request, messages.INFO, "SMS message has been sent successfully")

        ERROR_FLAG = False

        for P in PARENT_LIST:
            if len (Parent.objects.get(pk = P).email):
                try:
                    send_mail(getattr(settings, 'EMAIL_SUBJECT', ''), PARENT_LIST[P], getattr(settings, 'EMAIL_FROM', ''), [Parent.objects.get(pk = P).email], fail_silently = False)
                except:
                    messages.add_message (request, messages.ERROR, "Email message has not been sent, Please check your email settings")
                    ERROR_FLAG = True
                    break

        if not ERROR_FLAG:
            messages.add_message (request, messages.INFO, "Email message has been sent successfully")

    return HttpResponseRedirect ("/TheCondor/condor/attendance/")

def grade_report (request):
    """ Read the freaken' mode and do what you have to do son """

    if not "GRADE_REPORT" in request.POST or not "MODE" in request.POST or not "SEMISTER" in request.POST: # making sure the user is not accessing the url directly
        return HttpResponseForbidden ("<title>Code እምቢየው</title><h1 style='font-weight:normal;'>Error: Cannot access this page directly</h1>")

    GRADE_REPORT = request.POST["GRADE_REPORT"].split("#")[:-1]
    COUNT_NEW = 0
    COUNT_OR = 0
    COUNT_ADD = 0
    OVER_MAX = False
    REG_X = re.compile (r"^[0-9]+(.{1}[0-9]{2})?$")
    REG_X_ROUNDABLE = re.compile (r"^[0-9]+(\.{1}[0-9]+)?$")

    for GR in GRADE_REPORT:
        # 6_11S_B_Biology_100
        if request.POST ["MODE"] == "A": # we are told to add, your wish is my command
            if not GradeReport.objects.filter (academic_calendar = AcademicCalendar.objects.get (pk = request.POST["SEMISTER"]), student = Student.objects.get (pk = GR.split("_")[0]), subject = Subject.objects.get (name__iexact = GR.split("_")[3].replace ("X", " "))).exists():
                NEW_GP = GradeReport ()
                NEW_GP.academic_calendar = AcademicCalendar.objects.get (pk = request.POST["SEMISTER"])
                NEW_GP.mark = GR.split("_")[4]
                NEW_GP.student = Student.objects.get (pk = GR.split("_")[0])
                NEW_GP.subject = Subject.objects.get (name__iexact = GR.split("_")[3].replace ("X", " "))
                NEW_GP.save()
                COUNT_NEW += 1

            else:
                if (GradeReport.objects.get (academic_calendar = AcademicCalendar.objects.get (pk = request.POST["SEMISTER"]), student = Student.objects.get (pk = GR.split("_")[0]), subject = Subject.objects.get (name__iexact = GR.split("_")[3].replace ("X", " "))).mark) + Decimal (GR.split("_")[4]) < 201:
                    if re.match (REG_X, GR.split("_")[4]) == None: # we know it's not a two decimal point number
                        if re.match (REG_X_ROUNDABLE, GR.split("_")[4]): # testing weather or not it can be rounded or not
                            GradeReport.objects.filter (academic_calendar = AcademicCalendar.objects.get (pk = request.POST["SEMISTER"]), student = Student.objects.get (pk = GR.split("_")[0]), subject = Subject.objects.get (name__iexact = GR.split("_")[3].replace ("X", " "))).update (mark = (GradeReport.objects.get (academic_calendar = AcademicCalendar.objects.get (pk = request.POST["SEMISTER"]), student = Student.objects.get (pk = GR.split("_")[0]), subject = Subject.objects.get (name__iexact = GR.split("_")[3].replace ("X", " "))).mark) + Decimal (GR.split("_")[4][0:GR.split("_")[4].rfind (".")+2]))
                            COUNT_ADD += 1

                    else:
                        GradeReport.objects.filter (academic_calendar = AcademicCalendar.objects.get (pk = request.POST["SEMISTER"]), student = Student.objects.get (pk = GR.split("_")[0]), subject = Subject.objects.get (name__iexact = GR.split("_")[3].replace ("X", " "))).update (mark = (GradeReport.objects.get (academic_calendar = AcademicCalendar.objects.get (pk = request.POST["SEMISTER"]), student = Student.objects.get (pk = GR.split("_")[0]), subject = Subject.objects.get (name__iexact = GR.split("_")[3].replace ("X", " "))).mark) + Decimal (GR.split("_")[4]))
                        COUNT_ADD += 1

                else:
                    OVER_MAX = True

        elif request.POST ["MODE"] == "O": # we are told to override, your wish is my command
            if GradeReport.objects.filter (academic_calendar = AcademicCalendar.objects.get (pk = request.POST["SEMISTER"]), student = Student.objects.get (pk = GR.split("_")[0]), subject = Subject.objects.get (name__iexact = GR.split("_")[3].replace ("X", " "))).exists():
                GradeReport.objects.filter (academic_calendar = AcademicCalendar.objects.get (pk = request.POST["SEMISTER"]), student = Student.objects.get (pk = GR.split("_")[0]), subject = Subject.objects.get (name__iexact = GR.split("_")[3].replace ("X", " "))).update (mark = GR.split("_")[4])
                COUNT_OR += 1
            
            else: # It's a new grade we are supposed to create a new one
                NEW_GP = GradeReport ()
                NEW_GP.academic_calendar = AcademicCalendar.objects.get (pk = request.POST["SEMISTER"])
                NEW_GP.mark = GR.split("_")[4]
                NEW_GP.student = Student.objects.get (pk = GR.split("_")[0])
                NEW_GP.subject = Subject.objects.get (name__iexact = GR.split("_")[3].replace ("X", " "))
                NEW_GP.save()
                COUNT_NEW += 1

    if request.POST["MODE"] == "A":
        messages.add_message (request, messages.INFO, "Grade Report has been saved successfully. New: "+ str (COUNT_NEW) +", Add: "+ str (COUNT_ADD))

        if OVER_MAX: # if the requested mark amount, when added if it exceeds 200 skip the addition and on to the next one
            messages.add_message (request, messages.ERROR, "Some marks were not added because the total sum would exceed 200. No changes will be made in those particular cases.")

    elif request.POST["MODE"] == "O":
        messages.add_message (request, messages.INFO, "Grade Report has been saved successfully. New: "+ str (COUNT_NEW) +", Override: "+ str (COUNT_OR))

    return HttpResponseRedirect ("/TheCondor/condor/student/")

def generate_report_card (request):
    """ well you iz supposed to generate a freakn' report card... """

    if not "AC" in request.POST or not "CONFIG" in request.POST or not "CLASSES" in request.POST: # making sure the user is not accessing the url directly
        return HttpResponseForbidden ("<title>Code እምቢየው</title><h1 style='font-weight:normal;'>Error: Cannot access this page directly</h1>")

    CLASSES = request.POST ["CLASSES"][:-1].split("_") # Splitting...splitting...holds id of classes
    CONFIG = []
    CLASS_SUBJECT_LIST = {} # this will hold ERY subject given in a class i.e. making sure a student has a full grade report before proceeding to make a report card
    ACADEMIC_CALENDARS = request.POST ["AC"][:-1].split("_") # at least one fraken academic calendar is sent...ASS ASS ASS ASS ASS ASS ASS ASS ASS ASS ASS ASS ASS ASS ASS ASS ASS ASS ASS ASS ASS ASS
    CONFIG = []
    MEIN_LIST = {}      # this is suppose to be MëIN LIST...but...........butt!, will be holding student id's who seem to be NERDS!
                        # this is a bit redundant, but the semesters got me fucked so seems this is the only way son!
                        # structure:    <CLASS.id: {STUDENTS WHO HAVE COMPLETE GRADE REPORT ON SELECTED AC's}>

    INCOMPLETES = []    # holds Incomplete--eees
                        # STRUCTURE:
                        #   [Student, Subject, AcademicCalendar]    note it's the OBJECTS them selves not their id's

    JUST_COMPUTE_P_I = False
    JUST_COMPUTE_P_II = False
    JUST_COMPUTE_P_III = False
    JUST_COMPUTE_P_IV = False

    # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    # This block of puppy makes sure that all academic calendars selected belong to the same freaken year
    CHECK_YEAR = {} # we'll be checking to see whether or not the academic calendars selected belong to the same freaken year
    for AC in AcademicCalendar.objects.filter (id__in = ACADEMIC_CALENDARS):
        CHECK_YEAR [AC.academic_year] = "MOE"

    if len (CHECK_YEAR) > 1:
        messages.add_message (request, messages.ERROR, "There seems to be more than one academic calendar year in the selected semesters. Make sure all semesters are from the same year.")
        return HttpResponseRedirect ("/TheCondor/condor/classroom/")
    # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

    if len (request.POST ["CONFIG"]) > 0: # if no configuration is sent, the default settings are: not a master card, won't be emailing to parents and no SMS
        CONFIG = request.POST ["CONFIG"][:-1].split("_")

    for CR in ClassRoom.objects.filter (id__in = CLASSES):
        SUB_LIST = []
        for SUBJECT in CR.grade.subject.all():
            SUB_LIST.append (SUBJECT)

        CLASS_SUBJECT_LIST [CR.id] = SUB_LIST # the subject list will have been already ordered

    # on building ACADEMIC_CALENDARS if either S_I of S_II is selected we have to add the corresponding P's of the S's BEFORE building Mein-List
    # Modifying AC before proceeding is the above commented condition is satisfied ...
    # Please wait...
    for AC in AcademicCalendar.objects.filter (id__in = ACADEMIC_CALENDARS):
        if AC.semester == "S_I": # we should be adding P_I and P_II
            # Checking on P_I -------------------------------------------------------------------------------------------------------------------------------------------------------------------------
            if not AcademicCalendar.objects.filter (semester = "P_I", academic_year = AC.academic_year).exists(): # the insane administrator has created S_I without creating P_I – which is INSAINE
                messages.add_message (request, messages.ERROR, "ERROR! Seems you haven't created the corresponding Period I of {}".format (AC.academic_year))
                return HttpResponseRedirect ("/TheCondor/condor/classroom/")

            else:
                ID = AcademicCalendar.objects.get (semester = "P_I", academic_year = AC.academic_year).id # we know this EXISTS! --- well duhhhhhhhhhh!
                if str (ID) not in ACADEMIC_CALENDARS:
                    JUST_COMPUTE_P_I = True
                    ACADEMIC_CALENDARS.append (ID)
            # DON checking on P_I ---------------------------------------------------------------------------------------------------------------------------------------------------------------------

            # Checking on P_II ------------------------------------------------------------------------------------------------------------------------------------------------------------------------
            if not AcademicCalendar.objects.filter (semester = "P_II", academic_year = AC.academic_year).exists():
                messages.add_message (request, messages.ERROR, "ERROR! Seems you haven't created the corresponding Period II of {}".format (AC.academic_year))
                return HttpResponseRedirect ("/TheCondor/condor/classroom/")

            else:
                ID = AcademicCalendar.objects.get (semester = "P_II", academic_year = AC.academic_year).id
                if str (ID) not in ACADEMIC_CALENDARS:
                    JUST_COMPUTE_P_II = True
                    ACADEMIC_CALENDARS.append (ID)
            # DON checking on P_II --------------------------------------------------------------------------------------------------------------------------------------------------------------------

        if AC.semester == "S_II": # we should be adding P_III and P_IV
            # Checking on P_III -----------------------------------------------------------------------------------------------------------------------------------------------------------------------
            if not AcademicCalendar.objects.filter (semester = "P_III", academic_year = AC.academic_year).exists():
                messages.add_message (request, messages.ERROR, "ERROR! Seems you haven't created the corresponding Period III of {}".format (AC.academic_year))
                return HttpResponseRedirect ("/TheCondor/condor/classroom/")

            else:
                ID = AcademicCalendar.objects.get (semester = "P_III", academic_year = AC.academic_year).id
                if str (ID) not in ACADEMIC_CALENDARS:
                    JUST_COMPUTE_P_III = True
                    ACADEMIC_CALENDARS.append (ID)
            # DON checking on P_III -------------------------------------------------------------------------------------------------------------------------------------------------------------------

            # Checking on P_IV ------------------------------------------------------------------------------------------------------------------------------------------------------------------------
            if not AcademicCalendar.objects.filter (semester = "P_IV", academic_year = AC.academic_year).exists():
                messages.add_message (request, messages.ERROR, "ERROR! Seems you haven't created the corresponding Period IV of {}".format (AC.academic_year))
                return HttpResponseRedirect ("/TheCondor/condor/classroom/")

            else:
                ID = AcademicCalendar.objects.get (semester = "P_IV", academic_year = AC.academic_year).id
                if str (ID) not in ACADEMIC_CALENDARS:
                    JUST_COMPUTE_P_IV = True
                    ACADEMIC_CALENDARS.append (ID)
            # DON checking on P_IV --------------------------------------------------------------------------------------------------------------------------------------------------------------------

    for CR in ClassRoom.objects.filter (id__in = CLASSES):
        MEIN_LIST [CR.id] = []

        for STU in CR.student_set.all():
            if (GradeReport.objects.filter (student = STU, academic_calendar__id__in = ACADEMIC_CALENDARS).count() < (len (CLASS_SUBJECT_LIST [CR.id]) * len (ACADEMIC_CALENDARS))): # grade report MIGHT be missing...
                PREV_COUNT = len (INCOMPLETES) # we'll be using it weather or not to figure out we've added an INCOMPTE to the list or not in the coming loop

                for SUB in CLASS_SUBJECT_LIST [CR.id]:
                    for AC in AcademicCalendar.objects.filter (id__in = ACADEMIC_CALENDARS):
                        if not GradeReport.objects.filter (student = STU, subject = SUB, academic_calendar = AC).exists(): # the greade report does NOT exist -- testing weather or not it should
                            if (AC.semester[0] == "P" and SUB.given_in_semister_only == False): # Checking if the subject is supposed to be given in a period or not, we won't check for semester because it's assumed it is given
                                INCOMPLETES.append ([STU, SUB, AC])

                            elif AC.semester[0] == "S": # academic semester type is --semester-- and there's a subject missing just add it without checking son---duhhhhhhh
                                INCOMPLETES.append ([STU, SUB, AC])

                if PREV_COUNT == len (INCOMPLETES): # clean as whistle students --- NERDS --- We should be storing info in MëIN LIST
                    MEIN_LIST[CR.id].append (STU)

            else: # clean as whistle students --- NERDS++ --- We should be storing info in MëIN LIST
                MEIN_LIST[CR.id].append (STU)

    # Structure on list:
    P_I   = [] # <CLASS_ID, [SUM, GRADE_REPORT_LIST, STUDENT_OBJECT]>
    P_II  = []
    P_III = []
    P_IV  = []
    S_I   = []
    S_II  = []
    S_I_COMPUTED = []
    S_II_COMPUTED = []
    S_AVE_COMPUTED = []

    P_I_FLAG = False    # trust me i need em'
    P_II_FLAG = False
    P_III_FLAG = False
    P_IV_FLAG = False
    S_I_FLAG = False
    S_II_FLAG = False
    S_I_COMPUTE_FLAG = True # will be passed via kwargs on write_mark -- whether or not to compute S_I_COMPUTED or not -- trust me son it's VERY expensive if i don't use this flag
    S_II_COMPUTE_FLAG = True # telling we have to compute S_II_COMPUTED

    # you are going to see unusual number of try: except: clock -- well son that's because the shit is taken to the freaken limit -- tested it as much as i could and were i saw errors
    # i BLOCKED em' -- either passing em' or correcting em' -- what -- what
    #you don't become flexible without breaking some bones in the process...or i'll break em' for you!

    for AC in AcademicCalendar.objects.filter (id__in = ACADEMIC_CALENDARS):
        if AC.semester == "P_I" or AC.semester == "P_II" or AC.semester == "P_III" or AC.semester == "P_IV":
            for CLS in MEIN_LIST:
                CLSX = []   # <[SUM, GRADE_REPORT_LIST, STUDENT_OBJECT]>
                GR_LST = [] # <LIST of GRADE_REPORT OBJECTS OF A STUDENT--NERD>

                for STU in MEIN_LIST [CLS]:
                    SUM = float (0)

                    for SUB in CLASS_SUBJECT_LIST [STU.class_room.id]:
                        if (SUB.given_in_semister_only == False and SUB.use_letter_grading == False):
                            try:
                                GRADE_REP = GradeReport.objects.get (academic_calendar = AC, student = STU, subject = SUB)
                                SUM += int (round (GRADE_REP.mark, 0)) # TODO: check on rounding...
                                GR_LST.append (GRADE_REP)
                            except:
                                try:
                                    MEIN_LIST [CLS].remove(STU)
                                except:
                                    pass

                        elif (SUB.given_in_semister_only == False and SUB.use_letter_grading == True):
                            try:
                                GRADE_REP = GradeReport.objects.get (academic_calendar = AC, student = STU, subject = SUB) # BUG FIX
                                GR_LST.append (GRADE_REP)
                            except:
                                try:
                                    MEIN_LIST [CLS].remove(STU)
                                except:
                                    pass

                    CLSX.append ([SUM, GR_LST, STU]) # <[SUM, GRADE_REPORT_LIST, STUDENT_OBJECT]>

                if AC.semester == "P_I":
                    P_I.append ([CLS, sorted (CLSX, reverse = True)]) # <CLASS_ID, [SUM, GRADE_REPORT_LIST, STUDENT_OBJECT]>
                    P_I_FLAG = True

                elif AC.semester == "P_II":
                    P_II.append ([CLS, sorted (CLSX, reverse = True)])
                    P_II_FLAG = True

                elif AC.semester == "P_III":
                    P_III.append ([CLS, sorted (CLSX, reverse = True)])
                    P_III_FLAG = True

                elif AC.semester == "P_IV":
                    P_IV.append ([CLS, sorted (CLSX, reverse = True)])
                    P_IV_FLAG = True

        elif AC.semester == "S_I":
            """
                we are about to do something hugely redundant--assuming the administrator is sane--i.e. a SINGLE semester is active at a time;
                and if a semester is selected we are going to be calculating it's corresponding periods[eeeeeeeeeeew] and OVERRIDE if other existed;
                won't change anything though--we're just doing it again
            """

            # now we have to calculate P_I and P_II
            # since we have done it above we are going to be very EFFICENT like the Germans and create a fake academic calendar and re-do the above shit son
            # read the academic year of the semester and get the id of the P_I and P_II of that semester


            # before doing any calculation we’ll be checking weather or not P_I and P_II are empty, if they are we have to do it -- if they are not empty we have to re-do it -- insane administrator
            S_I_FLAG = True

            # now we'll start adding shit to S_I's []
            # NOTE: RE_AC is now the new ACADEMIC_CALENDARS -- modified MITCH!

            for AC in AcademicCalendar.objects.filter (id__in = ACADEMIC_CALENDARS):
                if AC.semester == "S_I":
                    for CLS in MEIN_LIST:
                        CLSX = []   # <[SUM, GRADE_REPORT_LIST, STUDENT_OBJECT]>
                        GR_LST = [] # <LIST of GRADE_REPORT OBJECTS OF A STUDENT--NERD>

                        for STU in MEIN_LIST [CLS]:
                            SUM = float (0)

                            for SUB in CLASS_SUBJECT_LIST [STU.class_room.id]:
                                try:
                                    GRADE_REP = GradeReport.objects.get (academic_calendar = AC, student = STU, subject = SUB)
                                    SUM += int (round (GRADE_REP.mark, 0))
                                    GR_LST.append (GRADE_REP)
                                except:
                                    MEIN_LIST[CLS].remove(STU) # FIX: should have been removing student of exception is caught

                            CLSX.append ([SUM, GR_LST, STU]) # <[SUM, GRADE_REPORT_LIST, STUDENT_OBJECT]>

                        S_I.append ([CLS, sorted (CLSX, reverse = True)]) # <CLASS_ID, [SUM, GRADE_REPORT_LIST, STUDENT_OBJECT]>
                        # APPPPPPPPPEEEEEEND it!

        elif AC.semester == "S_II":
            S_II_FLAG = True
            for AC in AcademicCalendar.objects.filter (id__in = ACADEMIC_CALENDARS):
                if AC.semester == "S_II":
                    for CLS in MEIN_LIST:
                        CLSX = []
                        GR_LST = []

                        for STU in MEIN_LIST [CLS]:
                            SUM = float (0)

                            for SUB in CLASS_SUBJECT_LIST [STU.class_room.id]:
                                try:
                                    GRADE_REP = GradeReport.objects.get (academic_calendar = AC, student = STU, subject = SUB)
                                    SUM += int (round (GRADE_REP.mark, 0))
                                    GR_LST.append (GRADE_REP)
                                except:
                                    try: # yep here too
                                        MEIN_LIST[CLS].remove(STU) # FIX: should have been removing student of exception is caught
                                    except:
                                        pass

                            CLSX.append ([SUM, GR_LST, STU])

                        S_II.append ([CLS, sorted (CLSX, reverse = True)])

    # Just because you have S_I or S_II that's not the way you calculate the freaken rank
    # you gonna have to do it again and again and again and again and again and again and again and again --- am sorry was imagining is was having...

    """
    for X in P_I:
        if len (X[1]): # do we have grade reports in the freaken' AC selected?
            RANK = 1
            JUMP = 0
            PREV_MARK = X[1][0][0]
            print (PREV_MARK)

            for i, S in enumerate (X[1]):
                if i > 0:
                    if PREV_MARK == S[0]:
                        JUMP += 1

                    else:
                        PREV_MARK = S[0]
                        RANK += (1 + JUMP)
                        JUMP = 0

                print ("1: {} => {} => {}".format (X[0], S[0], RANK))
    """

    #------------------------------------------------------------------------------------------------------------------------------------------------
    response = HttpResponse (content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="Megan Fox.pdf"' # At the end the file name returned must be associated with the academic calendars, class room and stuff

    CONFIG_OBJ = Config.objects.all()[0] # since there should only exist one config object we're taking the FIRST one to consideration
    p = canvas.Canvas (response, pagesize = A4) # NOTE: MS-Office defaults to letter TODO: test with ACTUAL PAPER, with margins n' all
    # you might have to do a little tweaking on you side to get the fonts --- i know i had to
    pdfmetrics.registerFont (TTFont ('Nyala', 'condor/static/nyala.ttf'))
    pdfmetrics.registerFont (TTFont ('Ubuntu', 'condor/static/Ubuntu-L.ttf'))
    # at initiating a first page is created son...

    def convert_to_grade (**kwargs):
        # we'll be using a fixed grading system -- we'll it's a freaken high school
        if kwargs ["mark"] > 89:
            return "A"

        elif kwargs ["mark"] > 79:
            return "B"

        elif kwargs ["mark"] > 69:
            return "C"

        elif kwargs ["mark"] > 59:
            return "D"

        else:
            return "F"

    def build_front (**kwargs): # BUG FREE
        """ the idea is whenever we call this function we'll have a template to work one with logo and lines and erything... """

        p.rotate(90)
        p.setLineWidth(0.5)

        p.setFont('Ubuntu', 12)
        p.drawString (cm * 29, cm * -0.75, str (kwargs ["number"])) # drawing number ar the corner

        p.setFont('Nyala', 12)
        p.drawString (cm * 16, cm * -13.5, "ስም")
        p.setFont('Ubuntu', 12)
        p.drawString (cm * 16, cm * -14, "Name")
        p.line (cm * 18, cm * -14, cm * 28, cm * -14)
        p.drawString (cm * 18.5, cm * -13.75, kwargs ["student"].upper())

        p.setFont('Nyala', 12)
        p.drawString (cm * 16, cm * -15, "ክፍል")
        p.setFont('Ubuntu', 12)
        p.drawString (cm * 16, cm * -15.5, "Grade")
        p.line (cm * 18, cm * -15.5, cm * 22, cm * -15.5)
        p.drawString (cm * 18.5, cm * -15.25, kwargs ["class_room"].upper())

        p.setFont('Nyala', 12)
        p.drawString (cm * 23, cm * -15, "ዓ.ም.")
        p.setFont('Ubuntu', 12)
        p.drawString (cm * 23, cm * -15.5, "Year")
        p.line (cm * 24.5, cm * -15.5, cm * 28, cm * -15.5)
        p.drawString (cm * 25, cm * -15.25, kwargs ["year"])

        p.setFont('Nyala', 12)
        p.drawString (cm * 16, cm * -16.5, "የክፍሉ ሃላፊ መምህር")
        p.setFont('Ubuntu', 12)
        p.drawString (cm * 16, cm * -17, "Home Room Teacher")
        p.line (cm * 20.5, cm * -17, cm * 28, cm * -17)
        p.drawString (cm * 21, cm * -16.75, kwargs["home_room_teacher"].upper())

        p.setFont('Nyala', 12)
        p.drawString (cm * 16, cm * -18, "ርዕስ መምህር")
        p.setFont('Ubuntu', 12)
        p.drawString (cm * 16, cm * -18.5, "Headmaster")
        p.line (cm * 19, cm * -18.5, cm * 28, cm * -18.5)
        p.drawString (cm * 19.5, cm * -18.25, kwargs["head_master"].upper())

    def build_table (**kwargs): # BUG FREE
        # drawing first row...
        # i know i could have used table of report lab but i don't think i wouldn't be able to control it is i do now -- i.e. with all the functionalities -- this is all ASSUMPTIONS
        p.setLineWidth (0.5)
        p.line (cm * 1, cm * -1, cm * 14.5, cm * -1)
        p.line (cm * 1, cm * -3, cm * 14.5, cm * -3)

        Y1, Y2 = -1, -3
        p.line (cm * 1, cm * Y1, cm * 1, cm * Y2)
        p.line (cm * 14.5, cm * Y1, cm * 14.5, cm * Y2)
        p.line (cm * 4, cm * Y1, cm * 4, cm * Y2)
        p.line (cm * 5.5, cm * Y1, cm * 5.5, cm * Y2)
        p.line (cm * 7, cm * Y1, cm * 7, cm * Y2)
        p.line (cm * 8.5, cm * Y1, cm * 8.5, cm * Y2)
        p.line (cm * 10, cm * Y1, cm * 10, cm * Y2)
        p.line (cm * 11.5, cm * Y1, cm * 11.5, cm * Y2)
        p.line (cm * 13, cm * Y1, cm * 13, cm * Y2)

        p.setFont('Nyala', 12)
        p.drawString (1.25 * cm, -1.85 * cm, "የትምህርት ዓይነት")
        p.setFont('Ubuntu', 11)
        p.drawString (1.25 * cm, -2.35 * cm, "Subject")

        X, Y = 1, -3.85
        for SUBJECT in kwargs["class_room"].grade.subject.all():
            p.line (X * cm, Y * cm, (X + 13.5) * cm, Y * cm)
            p.line (X * cm, Y * cm, X * cm, Y * cm)

            p.setFont('Nyala', 10)
            p.drawString ((X + 30), (Y + 0.5) * cm, SUBJECT.name_a)
            p.setFont('Ubuntu', 9)
            p.drawString ((X + 30), (Y + 0.175) * cm, SUBJECT.name)
            Y = Y - 0.85

        # drawing last box son
        p.line (X * cm, Y * cm, (X + 13.5) * cm, Y * cm)
        p.line (X * cm, Y * cm, X * cm, Y * cm)
        p.setFont('Nyala', 10)
        p.drawString ((X + 30), (Y + 0.5) * cm, "አማካይ ዉጤት")
        p.setFont('Ubuntu', 9)
        p.drawString ((X + 30), (Y + 0.175) * cm, "Average")

        p.line (cm * 1, -3 * cm, cm * 1, Y * cm)
        p.line (cm * 4, -3 * cm, cm * 4, Y * cm)
        p.line (cm * 5.5, -3 * cm, cm * 5.5, Y * cm)
        p.line (cm * 7, -3 * cm, cm * 7, Y * cm)
        p.line (cm * 8.5, -3 * cm, cm * 8.5, Y * cm)
        p.line (cm * 10, -3 * cm, cm * 10, Y * cm)
        p.line (cm * 11.5, -3 * cm, cm * 11.5, Y * cm)
        p.line (cm * 13, -3 * cm, cm * 13, Y * cm)
        p.line (cm * 14.5, -3 * cm, cm * 14.5, Y * cm)

        # building the bottom bitch - building X!
        p.line (cm * 1, cm * -15.75, cm * 14.5, cm * -15.75)
        p.line (cm * 1, cm * -16.6, cm * 14.5, cm * -16.6)
        p.line (cm * 1, cm * -17.45, cm * 14.5, cm * -17.45)
        p.line (cm * 1, cm * -18.3, cm * 14.5, cm * -18.3)
        p.line (cm * 1, cm * -19.15, cm * 14.5, cm * -19.15)
        p.line (cm * 1, cm * -20, cm * 14.5, cm * -20)

        # building Y
        p.line (cm * 1, -15.75 * cm, cm * 1, cm * -20)
        p.line (cm * 4, -15.75 * cm, cm * 4, cm * -20)
        p.line (cm * 5.5, -15.75 * cm, cm * 5.5, cm * -20)
        p.line (cm * 7, -15.75 * cm, cm * 7, cm * -20)
        p.line (cm * 8.5, -15.75 * cm, cm * 8.5, cm * -20)
        p.line (cm * 10, -15.75 * cm, cm * 10, cm * -20)
        p.line (cm * 11.5, -15.75 * cm, cm * 11.5, cm * -20)
        p.line (cm * 13, -15.75 * cm, cm * 13, cm * -20)
        p.line (cm * 14.5, -15.75 * cm, cm * 14.5, cm * -20)

        p.setFont('Nyala', 10)
        p.drawString ((X + 30), -16.075 * cm, "ደረጃ")
        p.setFont('Ubuntu', 9)
        p.drawString ((X + 30), -16.45 * cm, "Rank")

        p.setFont('Nyala', 10)
        p.drawString ((X + 30), -16.95 * cm, "የክፍሉ ቁጥር")
        p.setFont('Ubuntu', 9)
        p.drawString ((X + 30), -17.3 * cm, "Number in Class")

        p.setFont('Nyala', 10)
        p.drawString ((X + 30), -17.75 * cm, "የቀረበት ቀን")
        p.setFont('Ubuntu', 9)
        p.drawString ((X + 30), -18.15 * cm, "Days Absent")

        p.setFont('Nyala', 10)
        p.drawString ((X + 30), -18.65 * cm, "የዘገየበት ጊዜያት")
        p.setFont('Ubuntu', 9)
        p.drawString ((X + 30), -19 * cm, "Times Late")

        p.setFont('Nyala', 10)
        p.drawString ((X + 30), -19.475 * cm, "ዐመል")
        p.setFont('Ubuntu', 9)
        p.drawString ((X + 30), -19.85 * cm, "Conduct")

        # period uno to quatro
        # we're writing the periods last because we're going to be rotating
        # we'll be rotating back through
        p.rotate(90)
        p.setFont('Nyala', 10)
        p.drawString (-2.75 * cm, -4.575 * cm, "፩ኛ ክፋለ ጊዜ")
        p.setFont('Ubuntu', 9)
        p.drawString (-2.5 * cm, -5 * cm, "Period 1")

        p.setFont('Nyala', 10)
        p.drawString (-2.75 * cm, -6.15 * cm, "፪ኛ ክፋለ ጊዜ")
        p.setFont('Ubuntu', 9)
        p.drawString (-2.5 * cm, -6.55 * cm, "Period 2")

        p.setFont('Nyala', 10)
        p.drawString (-2.75 * cm, -7.45 * cm, "፩ኛ ሰሚስተር")
        p.setFont('Ubuntu', 9)
        p.drawString (-2.75 * cm, -7.775 * cm, "Semester 1")
        p.setFont('Ubuntu', 4.3) # fine Print should exist!
        p.drawString (-2.9 * cm, -8.15 * cm, "P1 20% + P2 20% + S1 60%")

        p.setFont('Nyala', 10)
        p.drawString (-2.75 * cm, -9.15 * cm, "፫ኛ ክፋለ ጊዜ")
        p.setFont('Ubuntu', 9)
        p.drawString (-2.5 * cm, -9.55 * cm, "Period 3")

        p.setFont('Nyala', 10)
        p.drawString (-2.75 * cm, -10.65 * cm, "፬ኛ ክፋለ ጊዜ")
        p.setFont('Ubuntu', 9)
        p.drawString (-2.5 * cm, -11.05 * cm, "Period 4")

        p.setFont('Nyala', 10)
        p.drawString (-2.75 * cm, -11.95 * cm, "፪ኛ ሰሚስተር")
        p.setFont('Ubuntu', 9)
        p.drawString (-2.75 * cm, -12.3 * cm, "Semester 2")
        p.setFont('Ubuntu', 4.3) # fine Print should exist!
        p.drawString (-2.9 * cm, -12.7 * cm, "P3 20% + P4 20% + S2 60%")

        p.setFont('Nyala', 10)
        p.drawString (-2.9 * cm, -13.45 * cm, "አማካይ ውጤት")
        p.setFont('Ubuntu', 9)
        p.drawString (-2.55 * cm, -13.75 * cm, "Average")
        p.setFont('Ubuntu', 7) # fine Print should exist!
        p.drawString (-2.65 * cm, -14.15 * cm, "(S1 + S2) / 2")

        # restoring rotation...
        p.rotate(-90)

    def show_class_change (): # BUG FREE
        # two pages are added to kepp the even-odd combination kuuuuuuuuule (Cool with a K -- now that's cool!)

        p.setFont ('Ubuntu', 24)
        p.drawString (cm * 3.75, cm * 15, "Intentionally left blank, Class Change")
        p.showPage ()
        p.setFont ('Ubuntu', 24)
        p.drawString (cm * 2.25, cm * 15, "Left blank intentionally, Even Odd Restoring")
        p.showPage ()

    def write_mark (**kwargs): # BUG ... don't even get me started --- START!
        p.setFont ('Ubuntu', 12)

        # this part is going to be EXPENSIVE: it became expensive to accomodate insane MASTERS!
        #print (JUST_COMPUTE_P_I)
        #if P_I_FLAG: # we'll be drawing on Period UNO
        if not JUST_COMPUTE_P_I: # we'll be drawing on Period UNO
            for BRUCE_WILLS in P_I: # -- don't mess with Bruce Willy son  --
                if len (BRUCE_WILLS[1]): # do we have grade reports in the freaken' AC selected?
                    RANK = 1
                    JUMP = 0
                    PREV_MARK = BRUCE_WILLS[1][0][0]

                    for i, S in enumerate (BRUCE_WILLS[1]):
                        if i > 0:
                            if PREV_MARK == S[0]:
                                JUMP += 1

                            else:
                                PREV_MARK = S[0]
                                RANK += (1 + JUMP)
                                JUMP = 0

                        if S[2] == kwargs["student"]:
                            # find the freaken coordinates and draw son -- ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS
                            SUB_COUNT = 0
                            MESSAGE = kwargs["student"].__unicode__() +"\n"
                            MESSAGE += "-- Period I --\n"

                            for GR in S[1]:
                                if GR.student == kwargs["student"]:
                                    if GR.subject.use_letter_grading: # if using letters...
                                        p.drawString (cm * 4.35, cm * (-3.55 + (-0.85 * kwargs["subject_list_o"].index (GR.subject))), convert_to_grade (mark = int (round (GR.mark, 0)))) # the square brackets are VERY important!
                                        MESSAGE += GR.subject.name +": "+ convert_to_grade (mark = int (round (GR.mark, 0))) + "\n"

                                    else:
                                        SUB_COUNT += 1 # which subjects are ommited out of the -- subject_list_o --

                                        if int (round (GR.mark, 0)) < 50:
                                            p.setFillColor (red)

                                        p.drawString (cm * 4.35, cm * (-3.55 + (-0.85 * kwargs["subject_list_o"].index (GR.subject))), str (int (round (GR.mark, 0))))
                                        MESSAGE += GR.subject.name +": "+ str (int (round (GR.mark, 0))) +"\n"
                                        p.setFillColor (black) # restoring...

                            try:
                                if round ((S[0] / SUB_COUNT), 1) < CONFIG_OBJ.promotion_min: # setting color to red if student has failed
                                    p.setFillColor (red)

                                p.drawString (cm * 4.35, cm * (-3.55 + (-0.85 * len (kwargs["subject_list_o"]))), str (round ((S[0] / SUB_COUNT), 1))) # writing average
                                MESSAGE += "\nAverage: "+ str (round ((S[0] / SUB_COUNT), 1)) +"\n"
                            except:
                                pass
                            p.setFillColor (black)

                            # the bottom box will NOT change coordiantes -- XOXO -- Gossip Girl!
                            p.drawString (cm * 4.35, cm * (-16.35), str (RANK)) # writing rank
                            MESSAGE += "Rank: "+ str (RANK) +"\n"
                            p.drawString (cm * 4.35, cm * (-17.15), str (kwargs["student_count"])) # drawing student count
                            MESSAGE += "Count: "+ str (kwargs["student_count"]) +"\n"

                            try:
                                # drawing LATE days
                                ATTENDACE = Attendance.objects.filter (academic_semester = S[1][0].academic_calendar, attendance_type = "LATE")
                                LATE_DAYS = 0
                                if ATTENDACE.exists(): # we might be drawing LATE days
                                    for ATD in ATTENDACE:
                                        for STUDENT in ATD.student.all():
                                            if STUDENT == kwargs["student"]:
                                                LATE_DAYS += 1

                                if LATE_DAYS: # we are definitely drawing late days
                                    if LATE_DAYS > CONFIG_OBJ.max_late_count:
                                        p.setFillColor (red)

                                    MESSAGE += "Late: "+ str (LATE_DAYS) +"\n"
                                    p.drawString (cm * 4.35, cm * (-18.935), str (LATE_DAYS))
                                    p.setFillColor (black)
                            except:
                                pass

                            try:
                                # drawing FULL days
                                ATTENDACE = Attendance.objects.filter (academic_semester = S[1][0].academic_calendar, attendance_type = "FULL")
                                FULL_DAYS = 0
                                if ATTENDACE.exists(): # we might be drawing LATE days
                                    for ATD in ATTENDACE:
                                        for STUDENT in ATD.student.all():
                                            if STUDENT == kwargs["student"]:
                                                FULL_DAYS += 1

                                if FULL_DAYS: # we are definitely drawing late days
                                    if FULL_DAYS > CONFIG_OBJ.max_late_count:
                                        p.setFillColor (red)

                                    MESSAGE += "Whole: "+ str (FULL_DAYS) +"\n"
                                    p.drawString (cm * 4.35, cm * (-18.05), str (FULL_DAYS))
                                    p.setFillColor (black)
                            except:
                                pass

                            # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------
                            if "EP" in CONFIG or "SR" in CONFIG:
                                for P in kwargs["student"].parents.all():
                                    if "EP" in CONFIG:
                                        if len (P.email):
                                            try: # we won't be having any feedback -- since the PDF is returned...
                                                send_mail (getattr(settings, 'EMAIL_SUBJECT', ''), MESSAGE, getattr (settings, 'EMAIL_FROM', ''), [P.email], fail_silently = True)
                                            except:
                                                pass

                                    if "SR" in CONFIG:
                                        try: # again showing no errors
                                            api.send_sms(body=MESSAGE, from_phone=getattr(settings, 'TWILIO_NUMBER', ''), to=[str(P.phone_number)])
                                        except:
                                            pass
                            # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------

        #if P_II_FLAG: # drawing on Period DOS
        if not JUST_COMPUTE_P_II:
            for BRUCE_WILLS in P_II: # -- don't mess with Bruce Willy son  --
                if len (BRUCE_WILLS[1]): # do we have grade reports in the freaken' AC selected?
                    RANK = 1
                    JUMP = 0
                    PREV_MARK = BRUCE_WILLS[1][0][0]

                    for i, S in enumerate (BRUCE_WILLS[1]):
                        if i > 0:
                            if PREV_MARK == S[0]:
                                JUMP += 1

                            else:
                                PREV_MARK = S[0]
                                RANK += (1 + JUMP)
                                JUMP = 0

                        if S[2] == kwargs["student"]:
                            # find the freaken coordinates and draw son -- ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS
                            SUB_COUNT = 0
                            MESSAGE = kwargs["student"].__unicode__() +"\n"
                            MESSAGE += "-- Period II --\n"

                            for GR in S[1]:
                                if GR.student == kwargs["student"]:
                                    if GR.subject.use_letter_grading: # if using letters...
                                        p.drawString (cm * 5.85, cm * (-3.55 + (-0.85 * kwargs["subject_list_o"].index (GR.subject))), convert_to_grade (mark = int (round (GR.mark, 0)))) # the square brackets are VERY important!
                                        MESSAGE += GR.subject.name +": "+ convert_to_grade (mark = int (round (GR.mark, 0))) + "\n"

                                    else:
                                        SUB_COUNT += 1 # which subjects are ommited out of the -- subject_list_o --

                                        if int (round (GR.mark, 0)) < 50:
                                            p.setFillColor (red)

                                        p.drawString (cm * 5.85, cm * (-3.55 + (-0.85 * kwargs["subject_list_o"].index (GR.subject))), str (int (round (GR.mark, 0))))
                                        MESSAGE += GR.subject.name +": "+ str (int (round (GR.mark, 0))) +"\n"
                                        p.setFillColor (black) # restoring...

                            try:
                                if round ((S[0] / SUB_COUNT), 1) < CONFIG_OBJ.promotion_min: # setting color to red if student has failed
                                    p.setFillColor (red)

                                p.drawString (cm * 5.85, cm * (-3.55 + (-0.85 * len (kwargs["subject_list_o"]))), str (round ((S[0] / SUB_COUNT), 1))) # writing average
                                MESSAGE += "\nAverage: "+ str (round ((S[0] / SUB_COUNT), 1)) +"\n"
                            except:
                                pass
                            p.setFillColor (black)

                            # the bottom box will NOT change coordiantes -- XOXO -- Gossip Girl!
                            p.drawString (cm * 5.85, cm * (-16.35), str (RANK)) # writing rank
                            MESSAGE += "Rank: "+ str (RANK) +"\n"
                            p.drawString (cm * 5.85, cm * (-17.15), str (kwargs["student_count"])) # drawing student count
                            MESSAGE += "Count: "+ str (kwargs["student_count"]) +"\n"

                            # drawing LATE days
                            try:
                                ATTENDACE = Attendance.objects.filter (academic_semester = S[1][0].academic_calendar, attendance_type = "LATE")
                                LATE_DAYS = 0
                                if ATTENDACE.exists(): # we might be drawing LATE days
                                    for ATD in ATTENDACE:
                                        for STUDENT in ATD.student.all():
                                            if STUDENT == kwargs["student"]:
                                                LATE_DAYS += 1

                                if LATE_DAYS: # we are definitely drawing late days
                                    if LATE_DAYS > CONFIG_OBJ.max_late_count:
                                        p.setFillColor (red)

                                    MESSAGE += "Late: "+ str (LATE_DAYS) +"\n"
                                    p.drawString (cm * 5.85, cm * (-18.935), str (LATE_DAYS))
                                    p.setFillColor (black)
                            except:
                                pass

                            # drawing FULL days
                            try:
                                ATTENDACE = Attendance.objects.filter (academic_semester = S[1][0].academic_calendar, attendance_type = "FULL")
                                FULL_DAYS = 0
                                if ATTENDACE.exists(): # we might be drawing LATE days
                                    for ATD in ATTENDACE:
                                        for STUDENT in ATD.student.all():
                                            if STUDENT == kwargs["student"]:
                                                FULL_DAYS += 1

                                if FULL_DAYS: # we are definitely drawing late days
                                    if FULL_DAYS > CONFIG_OBJ.max_late_count:
                                        p.setFillColor (red)

                                    MESSAGE += "Whole: "+ str (FULL_DAYS) +"\n"
                                    p.drawString (cm * 5.85, cm * (-18.05), str (FULL_DAYS))
                                    p.setFillColor (black)
                            except:
                                pass

                            # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------
                            if "EP" in CONFIG or "SR" in CONFIG:
                                for P in kwargs["student"].parents.all():
                                    if "EP" in CONFIG:
                                        if len (P.email):
                                            try: # we won't be having any feedback -- since the PDF is returned...
                                                send_mail (getattr(settings, 'EMAIL_SUBJECT', ''), MESSAGE, getattr (settings, 'EMAIL_FROM', ''), [P.email], fail_silently = True)
                                            except:
                                                pass

                                    if "SR" in CONFIG:
                                        try: # again showing no errors
                                            api.send_sms(body=MESSAGE, from_phone=getattr(settings, 'TWILIO_NUMBER', ''), to=[str(P.phone_number)])
                                        except:
                                            pass
                            # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------

        if S_I_FLAG:
            # LIGHT: how about you build S_I_COMPUTED having similar structure that you can compute is as if it was a P_I or whatever --- whatever i don't care

            # BUILDING STRUCTURE ----------------------------------------------------------------------------------------------------------------------------------------------------------------------
            if kwargs["compute_flag"]:
                if len (S_I):
                    try:
                        S_I_AC = S_I[0][1][0][1][0].academic_calendar
                        P_I_AC = AcademicCalendar.objects.filter (academic_year = S_I[0][1][0][1][0].academic_calendar.academic_year, semester = "P_I")[0] # THESE two should exist!
                        P_II_AC = AcademicCalendar.objects.filter (academic_year = S_I[0][1][0][1][0].academic_calendar.academic_year, semester = "P_II")[0]
    
                        for S_I_X in S_I:
                            if len (S_I_X [1]):
    
                                for CLS in MEIN_LIST:
                                    CLSX = []
                                    GR_LST = []
    
                                    for STU in MEIN_LIST [CLS]:
                                        SUM = float (0)
    
                                        for SUB in CLASS_SUBJECT_LIST [STU.class_room.id]:
                                            if SUB.given_in_semister_only == True and SUB.use_letter_grading == False: # we'll be adding Semester result
                                                GRADE_REP = GradeReport.objects.get (academic_calendar = S_I_AC, student = STU, subject = SUB)
                                                SUM += float (GRADE_REP.mark)
                                                GR_LST.append (GRADE_REP)
    
                                            elif SUB.given_in_semister_only == False and SUB.use_letter_grading == False: # we'll be adding period result p1*20% + p2*20% + s1*60%
                                                GRADE_REP = GradeReport.objects.get (academic_calendar = S_I_AC, student = STU, subject = SUB)
                                                # TODO: check for bugs -- think you have have some here
                                                SUM_X = float (0)
                                                SUM_X += round ((float (GRADE_REP.mark) * 0.6), 0)
    
                                                # BUG FIX
                                                if not GradeReport.objects.filter (academic_calendar = P_I_AC, student = STU, subject = SUB).exists():
                                                    #XX INCOMPLETES.append ([STU, SUB, P_I_AC])
                                                    continue
    
                                                SUM_X += round ((float (GradeReport.objects.get (academic_calendar = P_I_AC, student = STU, subject = SUB).mark) * 0.2), 0)
    
                                                # BUG FIX
                                                if not GradeReport.objects.filter (academic_calendar = P_II_AC, student = STU, subject = SUB).exists():
                                                    #XX INCOMPLETES.append ([STU, SUB, P_II_AC])
                                                    continue
    
                                                SUM_X += round ((float (GradeReport.objects.get (academic_calendar = P_II_AC, student = STU, subject = SUB).mark) * 0.2), 0)
                                                SUM_X = round (SUM_X, 1)
    
                                                SUM += SUM_X
                                                GR_LST.append (GradeReport (academic_calendar = S_I_AC, mark = SUM_X, student = GRADE_REP.student, subject = GRADE_REP.subject))
    
                                            else:
                                                GRADE_REP = GradeReport.objects.get (academic_calendar = S_I_AC, student = STU, subject = SUB)
                                                GR_LST.append (GRADE_REP)
    
                                        CLSX.append ([SUM, GR_LST, STU])
    
                                    S_I_COMPUTED.append ([CLS, sorted (CLSX, reverse = True)])
                    except:
                        pass
            #------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

            for BRUCE_WILLS in S_I_COMPUTED: # -- don't mess with Bruce Willy son  --
                if len (BRUCE_WILLS[1]): # do we have grade reports in the freaken' AC selected?
                    RANK = 1
                    JUMP = 0
                    PREV_MARK = BRUCE_WILLS[1][0][0]

                    for i, S in enumerate (BRUCE_WILLS[1]):
                        if i > 0:
                            if PREV_MARK == S[0]:
                                JUMP += 1

                            else:
                                PREV_MARK = S[0]
                                RANK += (1 + JUMP)
                                JUMP = 0

                        if S[2] == kwargs["student"]:
                            # find the freaken coordinates and draw son -- ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS
                            SUB_COUNT = 0
                            MESSAGE = kwargs["student"].__unicode__() +"\n"
                            MESSAGE += "-- Semester I --\n"

                            for GR in S[1]:
                                if GR.student == kwargs["student"]:
                                    if GR.subject.use_letter_grading: # if using letters...
                                        p.drawString (cm * 7.35, cm * (-3.55 + (-0.85 * kwargs["subject_list_o"].index (GR.subject))), convert_to_grade (mark = int (round (GR.mark, 0)))) # the square brackets are VERY important!
                                        MESSAGE += GR.subject.name +": "+ convert_to_grade (mark = int (round (GR.mark, 0))) + "\n"

                                    else:
                                        # we'll be counting on NON-letters ONLY
                                        # BUG_FIX
                                        SUB_COUNT += 1 # which subjects are ommited out of the -- subject_list_o --

                                        if int (round (GR.mark, 0)) < 50:
                                            p.setFillColor (red)

                                        p.drawString (cm * 7.35, cm * (-3.55 + (-0.85 * kwargs["subject_list_o"].index (GR.subject))), str (int (round (GR.mark, 0))))
                                        MESSAGE += GR.subject.name +": "+ str (int (round (GR.mark, 0))) +"\n"
                                        p.setFillColor (black) # restoring...

                            try:
                                if round ((S[0] / SUB_COUNT), 1) < CONFIG_OBJ.promotion_min: # setting color to red if student has failed
                                    p.setFillColor (red)

                                p.drawString (cm * 7.35, cm * (-3.55 + (-0.85 * len (kwargs["subject_list_o"]))), str (round ((S[0] / SUB_COUNT), 1))) # writing average
                                MESSAGE += "\nAverage: "+ str (round ((S[0] / SUB_COUNT), 1)) +"\n"
                            except:
                                pass
                            p.setFillColor (black)

                            # the bottom box will NOT change coordiantes -- XOXO -- Gossip Girl!
                            p.drawString (cm * 7.35, cm * (-16.35), str (RANK)) # writing rank
                            MESSAGE += "Rank: "+ str (RANK) +"\n"
                            p.drawString (cm * 7.35, cm * (-17.15), str (kwargs["student_count"])) # drawing student count
                            MESSAGE += "Count: "+ str (kwargs["student_count"]) +"\n"

                            # drawing LATE days
                            try:
                                ATTENDACE = Attendance.objects.filter (academic_semester = S[1][0].academic_calendar, attendance_type = "LATE")
                                LATE_DAYS = 0
                                if ATTENDACE.exists(): # we might be drawing LATE days
                                    for ATD in ATTENDACE:
                                        for STUDENT in ATD.student.all():
                                            if STUDENT == kwargs["student"]:
                                                LATE_DAYS += 1

                                if LATE_DAYS: # we are definitely drawing late days
                                    if LATE_DAYS > CONFIG_OBJ.max_late_count:
                                        p.setFillColor (red)

                                    MESSAGE += "Late: "+ str (LATE_DAYS) +"\n"
                                    p.drawString (cm * 7.35, cm * (-18.935), str (LATE_DAYS))
                                    p.setFillColor (black)
                            except:
                                pass

                            # drawing FULL days
                            try:
                                ATTENDACE = Attendance.objects.filter (academic_semester = S[1][0].academic_calendar, attendance_type = "FULL")
                                FULL_DAYS = 0
                                if ATTENDACE.exists(): # we might be drawing LATE days
                                    for ATD in ATTENDACE:
                                        for STUDENT in ATD.student.all():
                                            if STUDENT == kwargs["student"]:
                                                FULL_DAYS += 1

                                if FULL_DAYS: # we are definitely drawing late days
                                    if FULL_DAYS > CONFIG_OBJ.max_late_count:
                                        p.setFillColor (red)

                                    MESSAGE += "Whole: "+ str (FULL_DAYS) +"\n"
                                    p.drawString (cm * 7.35, cm * (-18.05), str (FULL_DAYS))
                                    p.setFillColor (black)
                            except:
                                pass

                            # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------
                            if "EP" in CONFIG or "SR" in CONFIG:
                                for P in kwargs["student"].parents.all():
                                    if "EP" in CONFIG:
                                        if len (P.email):
                                            try: # we won't be having any feedback -- since the PDF is returned...
                                                send_mail (getattr(settings, 'EMAIL_SUBJECT', ''), MESSAGE, getattr (settings, 'EMAIL_FROM', ''), [P.email], fail_silently = True)
                                            except:
                                                pass

                                    if "SR" in CONFIG:
                                        try: # again showing no errors
                                            api.send_sms(body=MESSAGE, from_phone=getattr(settings, 'TWILIO_NUMBER', ''), to=[str(P.phone_number)])
                                        except:
                                            pass
                            # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------

        #if P_III_FLAG: # drawing on Period TRESS
        if not JUST_COMPUTE_P_III:
            for BRUCE_WILLS in P_III: # -- don't mess with Bruce Willy son  --
                if len (BRUCE_WILLS[1]): # do we have grade reports in the freaken' AC selected?
                    RANK = 1
                    JUMP = 0
                    PREV_MARK = BRUCE_WILLS[1][0][0]

                    for i, S in enumerate (BRUCE_WILLS[1]):
                        if i > 0:
                            if PREV_MARK == S[0]:
                                JUMP += 1

                            else:
                                PREV_MARK = S[0]
                                RANK += (1 + JUMP)
                                JUMP = 0

                        if S[2] == kwargs["student"]:
                            # find the freaken coordinates and draw son -- ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS
                            SUB_COUNT = 0
                            MESSAGE = kwargs["student"].__unicode__() +"\n"
                            MESSAGE += "-- Period III --\n"

                            for GR in S[1]:
                                if GR.student == kwargs["student"]:
                                    if GR.subject.use_letter_grading: # if using letters...
                                        p.drawString (cm * 8.85, cm * (-3.55 + (-0.85 * kwargs["subject_list_o"].index (GR.subject))), convert_to_grade (mark = int (round (GR.mark, 0)))) # the square brackets are VERY important!
                                        MESSAGE += GR.subject.name +": "+ convert_to_grade (mark = int (round (GR.mark, 0))) + "\n"

                                    else:
                                        SUB_COUNT += 1 # which subjects are ommited out of the -- subject_list_o --

                                        if int (round (GR.mark, 0)) < 50:
                                            p.setFillColor (red)

                                        p.drawString (cm * 8.85, cm * (-3.55 + (-0.85 * kwargs["subject_list_o"].index (GR.subject))), str (int (round (GR.mark, 0))))
                                        MESSAGE += GR.subject.name +": "+ str (int (round (GR.mark, 0))) +"\n"
                                        p.setFillColor (black) # restoring...

                            try:
                                if round ((S[0] / SUB_COUNT), 1) < CONFIG_OBJ.promotion_min: # setting color to red if student has failed
                                    p.setFillColor (red)

                                p.drawString (cm * 8.85, cm * (-3.55 + (-0.85 * len (kwargs["subject_list_o"]))), str (round ((S[0] / SUB_COUNT), 1))) # writing average
                                MESSAGE += "\nAverage: "+ str (round ((S[0] / SUB_COUNT), 1)) +"\n"
                            except:
                                pass
                            p.setFillColor (black)

                            # the bottom box will NOT change coordiantes -- XOXO -- Gossip Girl!
                            p.drawString (cm * 8.85, cm * (-16.35), str (RANK)) # writing rank
                            MESSAGE += "Rank: "+ str (RANK) +"\n"
                            p.drawString (cm * 8.85, cm * (-17.15), str (kwargs["student_count"])) # drawing student count
                            MESSAGE += "Count: "+ str (kwargs["student_count"]) +"\n"

                            # drawing LATE days
                            try:
                                ATTENDACE = Attendance.objects.filter (academic_semester = S[1][0].academic_calendar, attendance_type = "LATE")
                                LATE_DAYS = 0
                                if ATTENDACE.exists(): # we might be drawing LATE days
                                    for ATD in ATTENDACE:
                                        for STUDENT in ATD.student.all():
                                            if STUDENT == kwargs["student"]:
                                                LATE_DAYS += 1

                                if LATE_DAYS: # we are definitely drawing late days
                                    if LATE_DAYS > CONFIG_OBJ.max_late_count:
                                        p.setFillColor (red)

                                    p.drawString (cm * 8.85, cm * (-18.935), str (LATE_DAYS))
                                    MESSAGE += "Late: "+ str (LATE_DAYS) +"\n"
                                    p.setFillColor (black)
                            except:
                                pass

                            # drawing FULL days
                            try:
                                ATTENDACE = Attendance.objects.filter (academic_semester = S[1][0].academic_calendar, attendance_type = "FULL")
                                FULL_DAYS = 0
                                if ATTENDACE.exists(): # we might be drawing LATE days
                                    for ATD in ATTENDACE:
                                        for STUDENT in ATD.student.all():
                                            if STUDENT == kwargs["student"]:
                                                FULL_DAYS += 1

                                if FULL_DAYS: # we are definitely drawing late days
                                    if FULL_DAYS > CONFIG_OBJ.max_late_count:
                                        p.setFillColor (red)

                                    p.drawString (cm * 8.85, cm * (-18.05), str (FULL_DAYS))
                                    MESSAGE += "Whole: "+ str (FULL_DAYS) +"\n"
                                    p.setFillColor (black)
                            except:
                                pass

                            # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------
                            if "EP" in CONFIG or "SR" in CONFIG:
                                for P in kwargs["student"].parents.all():
                                    if "EP" in CONFIG:
                                        if len (P.email):
                                            try: # we won't be having any feedback -- since the PDF is returned...
                                                send_mail (getattr(settings, 'EMAIL_SUBJECT', ''), MESSAGE, getattr (settings, 'EMAIL_FROM', ''), [P.email], fail_silently = True)
                                            except:
                                                pass

                                    if "SR" in CONFIG:
                                        try: # again showing no errors
                                            api.send_sms(body=MESSAGE, from_phone=getattr(settings, 'TWILIO_NUMBER', ''), to=[str(P.phone_number)])
                                        except:
                                            pass
                            # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------

        #if P_IV_FLAG: # drawing on Period TRESS
        if not JUST_COMPUTE_P_IV:
            for BRUCE_WILLS in P_IV: # -- don't mess with Bruce Willy son  --
                if len (BRUCE_WILLS[1]): # do we have grade reports in the freaken' AC selected?
                    RANK = 1
                    JUMP = 0
                    PREV_MARK = BRUCE_WILLS[1][0][0]

                    for i, S in enumerate (BRUCE_WILLS[1]):
                        if i > 0:
                            if PREV_MARK == S[0]:
                                JUMP += 1

                            else:
                                PREV_MARK = S[0]
                                RANK += (1 + JUMP)
                                JUMP = 0

                        if S[2] == kwargs["student"]:
                            # find the freaken coordinates and draw son -- ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS
                            SUB_COUNT = 0
                            MESSAGE = kwargs["student"].__unicode__() +"\n"
                            MESSAGE += "-- Period IV --\n"

                            for GR in S[1]:
                                if GR.student == kwargs["student"]:
                                    if GR.subject.use_letter_grading: # if using letters...
                                        p.drawString (cm * 10.35, cm * (-3.55 + (-0.85 * kwargs["subject_list_o"].index (GR.subject))), convert_to_grade (mark = int (round (GR.mark, 0)))) # the square brackets are VERY important!
                                        MESSAGE += GR.subject.name +": "+ convert_to_grade (mark = int (round (GR.mark, 0))) + "\n"

                                    else:
                                        SUB_COUNT += 1 # which subjects are ommited out of the -- subject_list_o --

                                        if int (round (GR.mark, 0)) < 50:
                                            p.setFillColor (red)

                                        p.drawString (cm * 10.35, cm * (-3.55 + (-0.85 * kwargs["subject_list_o"].index (GR.subject))), str (int (round (GR.mark, 0))))
                                        MESSAGE += GR.subject.name +": "+ str (int (round (GR.mark, 0))) +"\n"
                                        p.setFillColor (black) # restoring...

                            try:
                                if round ((S[0] / SUB_COUNT), 1) < CONFIG_OBJ.promotion_min: # setting color to red if student has failed
                                    p.setFillColor (red)

                                p.drawString (cm * 10.35, cm * (-3.55 + (-0.85 * len (kwargs["subject_list_o"]))), str (round ((S[0] / SUB_COUNT), 1))) # writing average
                                MESSAGE += "\nAverage: "+ str (round ((S[0] / SUB_COUNT), 1)) +"\n"
                            except:
                                pass
                            p.setFillColor (black)

                            # the bottom box will NOT change coordiantes -- XOXO -- Gossip Girl!
                            p.drawString (cm * 10.35, cm * (-16.35), str (RANK)) # writing rank
                            MESSAGE += "Rank: "+ str (RANK) +"\n"
                            p.drawString (cm * 10.35, cm * (-17.15), str (kwargs["student_count"])) # drawing student count
                            MESSAGE += "Count: "+ str (kwargs["student_count"]) +"\n"

                            # drawing LATE days
                            try:
                                ATTENDACE = Attendance.objects.filter (academic_semester = S[1][0].academic_calendar, attendance_type = "LATE")
                                LATE_DAYS = 0
                                if ATTENDACE.exists(): # we might be drawing LATE days
                                    for ATD in ATTENDACE:
                                        for STUDENT in ATD.student.all():
                                            if STUDENT == kwargs["student"]:
                                                LATE_DAYS += 1

                                if LATE_DAYS: # we are definitely drawing late days
                                    if LATE_DAYS > CONFIG_OBJ.max_late_count:
                                        p.setFillColor (red)

                                    p.drawString (cm * 10.35, cm * (-18.935), str (LATE_DAYS))
                                    MESSAGE += "Late: "+ str (LATE_DAYS) +"\n"
                                    p.setFillColor (black)
                            except:
                                pass

                            # drawing FULL days
                            try:
                                ATTENDACE = Attendance.objects.filter (academic_semester = S[1][0].academic_calendar, attendance_type = "FULL")
                                FULL_DAYS = 0
                                if ATTENDACE.exists(): # we might be drawing LATE days
                                    for ATD in ATTENDACE:
                                        for STUDENT in ATD.student.all():
                                            if STUDENT == kwargs["student"]:
                                                FULL_DAYS += 1

                                if FULL_DAYS: # we are definitely drawing late days
                                    if FULL_DAYS > CONFIG_OBJ.max_late_count:
                                        p.setFillColor (red)

                                    p.drawString (cm * 10.35, cm * (-18.05), str (FULL_DAYS))
                                    MESSAGE += "Whole: "+ str (FULL_DAYS) +"\n"
                                    p.setFillColor (black)
                            except:
                                pass

                            # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------
                            if "EP" in CONFIG or "SR" in CONFIG:
                                for P in kwargs["student"].parents.all():
                                    if "EP" in CONFIG:
                                        if len (P.email):
                                            try: # we won't be having any feedback -- since the PDF is returned...
                                                send_mail (getattr(settings, 'EMAIL_SUBJECT', ''), MESSAGE, getattr (settings, 'EMAIL_FROM', ''), [P.email], fail_silently = True)
                                            except:
                                                pass

                                    if "SR" in CONFIG:
                                        try: # again showing no errors
                                            api.send_sms(body=MESSAGE, from_phone=getattr(settings, 'TWILIO_NUMBER', ''), to=[str(P.phone_number)])
                                        except:
                                            pass
                            # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------
                            # TODO: Send on Semester too --- i am fucking BORED! --- to the front son!

        if S_II_FLAG:
            # let's get it started -- LATER!
            # we're going to do it a little different -- we'll be calculating S_I_COMPUTE if not computed so you see son

            if kwargs["compute_flag_2"]:
                # DONE BUILDING S_II AND S_AVE --------------------------------------------------------------------------------------------------------------------------------------------------------
                if len (S_II):
                    try:
                        S_II_AC = S_II[0][1][0][1][0].academic_calendar
                        S_I_AC = AcademicCalendar.objects.filter (academic_year = S_II[0][1][0][1][0].academic_calendar.academic_year, semester = "S_I")[0]
                        P_I_AC = AcademicCalendar.objects.filter (academic_year = S_II[0][1][0][1][0].academic_calendar.academic_year, semester = "P_I")[0] # THESE two should exist!
                        P_II_AC = AcademicCalendar.objects.filter (academic_year = S_II[0][1][0][1][0].academic_calendar.academic_year, semester = "P_II")[0] # THESE two should exist!
                        P_III_AC = AcademicCalendar.objects.filter (academic_year = S_II[0][1][0][1][0].academic_calendar.academic_year, semester = "P_III")[0] # THESE two should exist!
                        P_IV_AC = AcademicCalendar.objects.filter (academic_year = S_II[0][1][0][1][0].academic_calendar.academic_year, semester = "P_IV")[0]
    
                        for S_II_X in S_II:
                            if len (S_II_X [1]):
    
                                for CLS in MEIN_LIST:
                                    CLSX = []
                                    GR_LST = []
    
                                    CLSX_AVE = []
                                    GR_LST_AVE = []
    
                                    for STU in MEIN_LIST [CLS]:
                                        SUM = float (0)
                                        SUM_I = float (0)
    
                                        for SUB in CLASS_SUBJECT_LIST [STU.class_room.id]:
                                            if SUB.given_in_semister_only == True and SUB.use_letter_grading == False: # we'll be adding Semester result
                                                try:
                                                    GRADE_REP = GradeReport.objects.get (academic_calendar = S_II_AC, student = STU, subject = SUB)
                                                    SUM += float (GRADE_REP.mark)
                                                    GR_LST.append (GRADE_REP)
                                                except:
                                                    #XX INCOMPLETES.append ([STU, SUB, S_II_AC])
                                                    pass
    
                                                # BUG FIX
                                                if not GradeReport.objects.filter (academic_calendar = S_I_AC, student = STU, subject = SUB).exists():
                                                    #XX INCOMPLETES.append ([STU, SUB, S_I_AC])
                                                    continue
    
                                                GRADE_REP_I = GradeReport.objects.get (academic_calendar = S_I_AC, student = STU, subject = SUB)
                                                SUM_I += round ((GRADE_REP_I.mark + GRADE_REP.mark) / 2, 0)
                                                GR_LST_AVE.append (GradeReport (academic_calendar = S_I_AC, student = STU, subject = SUB, mark = round ((GRADE_REP_I.mark + GRADE_REP.mark) / 2, 0)))
    
                                            elif SUB.given_in_semister_only == False and SUB.use_letter_grading == False: # we'll be adding period result p1*20% + p2*20% + s1*60%
                                                SUM_X = float (0)
                                                SUM_X_I = float (0)
    
                                                if not GradeReport.objects.filter (academic_calendar = S_II_AC, student = STU, subject = SUB).exists():
                                                    #XX INCOMPLETES.append ([STU, SUB, S_II_AC])
                                                    continue
                                                GRADE_REP = GradeReport.objects.get (academic_calendar = S_II_AC, student = STU, subject = SUB)
                                                SUM_X += round ((float (GRADE_REP.mark) * 0.6), 0)
    
                                                # BUG FIX
                                                if not GradeReport.objects.filter (academic_calendar = P_III_AC, student = STU, subject = SUB).exists():
                                                    #XX INCOMPLETES.append ([STU, SUB, P_III_AC])
                                                    continue
                                                SUM_X += round ((float (GradeReport.objects.get (academic_calendar = P_III_AC, student = STU, subject = SUB).mark) * 0.2), 0)
    
                                                # BUG FIX
                                                if not GradeReport.objects.filter (academic_calendar = P_IV_AC, student = STU, subject = SUB).exists():
                                                    #XX INCOMPLETES.append ([STU, SUB, P_IV_AC])
                                                    continue
                                                SUM_X += round ((float (GradeReport.objects.get (academic_calendar = P_IV_AC, student = STU, subject = SUB).mark) * 0.2), 0)
    
                                                SUM += round (SUM_X, 1)
                                                GR_LST.append (GradeReport (academic_calendar = S_II_AC, mark = SUM_X, student = GRADE_REP.student, subject = GRADE_REP.subject))
    
                                                GRADE_REP_I = GradeReport.objects.get (academic_calendar = S_I_AC, student = STU, subject = SUB)
                                                SUM_X_I += round ((float (GRADE_REP_I.mark) * 0.6), 0)
                                                # BUG FIX
                                                if not GradeReport.objects.filter (academic_calendar = P_I_AC, student = STU, subject = SUB).exists():
                                                    #XX INCOMPLETES.append ([STU, SUB, P_I_AC])
                                                    continue
                                                SUM_X_I += round ((float (GradeReport.objects.get (academic_calendar = P_I_AC, student = STU, subject = SUB).mark) * 0.2), 0)
    
                                                # BUG FIX
                                                if not GradeReport.objects.filter (academic_calendar = P_I_AC, student = STU, subject = SUB).exists():
                                                    #XX INCOMPLETES.append ([STU, SUB, P_II_AC])
                                                    continue
                                                SUM_X_I += round ((float (GradeReport.objects.get (academic_calendar = P_II_AC, student = STU, subject = SUB).mark) * 0.2), 0)
    
                                                SUM_I += round (((SUM_X_I + SUM_X) / 2), 0) # BIG FIX: this BUG took me 1+ Hour to find...
                                                GR_LST_AVE.append (GradeReport (academic_calendar = S_I_AC, mark = int (round (((SUM_X + SUM_X_I) / 2), 0)), student = GRADE_REP.student, subject = GRADE_REP.subject))
    
                                            else:
                                                try:
                                                    GRADE_REP = GradeReport.objects.get (academic_calendar = S_II_AC, student = STU, subject = SUB)
                                                    GR_LST.append (GRADE_REP)
    
                                                    #XX INCOMPLETES.append ([STU, SUB, S_I_AC])
    
                                                    # this is a last minute fix -- CHECK for errors son!
                                                    GRADE_REP_I = GradeReport.objects.get (academic_calendar = S_I_AC, student = STU, subject = SUB)
                                                    GRADE_REP_II = GradeReport.objects.get (academic_calendar = S_II_AC, student = STU, subject = SUB)
                                                    GR_LST_AVE.append (GradeReport (student = STU, subject = SUB, academic_calendar = S_II_AC, mark = int (round (((GRADE_REP_I.mark + GRADE_REP_II.mark) / 2), 0))))
                                                except:
                                                    pass
    
                                        CLSX.append ([SUM, GR_LST, STU])
                                        CLSX_AVE.append ([SUM_I, GR_LST_AVE, STU])
    
                                    S_II_COMPUTED.append ([CLS, sorted (CLSX, reverse = True)])
                                    S_AVE_COMPUTED.append ([CLS, sorted (CLSX_AVE, reverse = True)])
                    except:
                        pass
                # DONE BUILDING S_II AND S_AVE --------------------------------------------------------------------------------------------------------------------------------------------------------

            for BRUCE_WILLS in S_II_COMPUTED: # -- don't mess with Bruce Willy son  --
                if len (BRUCE_WILLS[1]): # do we have grade reports in the freaken' AC selected?
                    RANK = 1
                    JUMP = 0
                    PREV_MARK = BRUCE_WILLS[1][0][0]

                    for i, S in enumerate (BRUCE_WILLS[1]):
                        if i > 0:
                            if PREV_MARK == S[0]:
                                JUMP += 1

                            else:
                                PREV_MARK = S[0]
                                RANK += (1 + JUMP)
                                JUMP = 0

                        if S[2] == kwargs["student"]:
                            # find the freaken coordinates and draw son -- ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS
                            SUB_COUNT = 0
                            MESSAGE = kwargs["student"].__unicode__() +"\n"
                            MESSAGE += "--Semester II --\n"

                            for GR in S[1]:
                                if GR.student == kwargs["student"]:
                                    if GR.subject.use_letter_grading: # if using letters...
                                        p.drawString (cm * 11.85, cm * (-3.55 + (-0.85 * kwargs["subject_list_o"].index (GR.subject))), convert_to_grade (mark = int (round (GR.mark, 0)))) # the square brackets are VERY important!
                                        MESSAGE += GR.subject.name +": "+ convert_to_grade (mark = int (round (GR.mark, 0))) + "\n"

                                    else:
                                        # we'll be counting on NON-letters ONLY
                                        # BUG_FIX
                                        SUB_COUNT += 1 # which subjects are ommited out of the -- subject_list_o --

                                        if int (round (GR.mark, 0)) < 50:
                                            p.setFillColor (red)

                                        p.drawString (cm * 11.85, cm * (-3.55 + (-0.85 * kwargs["subject_list_o"].index (GR.subject))), str (int (round (GR.mark, 0))))
                                        MESSAGE += GR.subject.name +": "+ str (int (round (GR.mark, 0))) +"\n"
                                        p.setFillColor (black) # restoring...

                            try:
                                if round ((S[0] / SUB_COUNT), 1) < CONFIG_OBJ.promotion_min: # setting color to red if student has failed
                                    p.setFillColor (red)

                                p.drawString (cm * 11.85, cm * (-3.55 + (-0.85 * len (kwargs["subject_list_o"]))), str (round ((S[0] / SUB_COUNT), 1))) # writing average
                                MESSAGE += "\nAverage: "+ str (round ((S[0] / SUB_COUNT), 1)) +"\n"
                            except:
                                pass
                            p.setFillColor (black)

                            # the bottom box will NOT change coordiantes -- XOXO -- Gossip Girl!
                            p.drawString (cm * 11.85, cm * (-16.35), str (RANK)) # writing rank
                            MESSAGE += "Rank: "+ str (RANK) +"\n"
                            p.drawString (cm * 11.85, cm * (-17.15), str (kwargs["student_count"])) # drawing student count
                            MESSAGE += "Count: "+ str (kwargs["student_count"]) +"\n"

                            # drawing LATE days
                            try:
                                ATTENDACE = Attendance.objects.filter (academic_semester = S[1][0].academic_calendar, attendance_type = "LATE")
                                LATE_DAYS = 0
                                if ATTENDACE.exists(): # we might be drawing LATE days
                                    for ATD in ATTENDACE:
                                        for STUDENT in ATD.student.all():
                                            if STUDENT == kwargs["student"]:
                                                LATE_DAYS += 1

                                if LATE_DAYS: # we are definitely drawing late days
                                    if LATE_DAYS > CONFIG_OBJ.max_late_count:
                                        p.setFillColor (red)

                                    p.drawString (cm * 11.85, cm * (-18.935), str (LATE_DAYS))
                                    MESSAGE += "Late: "+ str (LATE_DAYS) +"\n"
                                    p.setFillColor (black)
                            except:
                                pass

                            # drawing FULL days
                            try:
                                ATTENDACE = Attendance.objects.filter (academic_semester = S[1][0].academic_calendar, attendance_type = "FULL")
                                FULL_DAYS = 0
                                if ATTENDACE.exists(): # we might be drawing LATE days
                                    for ATD in ATTENDACE:
                                        for STUDENT in ATD.student.all():
                                            if STUDENT == kwargs["student"]:
                                                FULL_DAYS += 1

                                if FULL_DAYS: # we are definitely drawing late days
                                    if FULL_DAYS > CONFIG_OBJ.max_late_count:
                                        p.setFillColor (red)

                                    p.drawString (cm * 11.85, cm * (-18.05), str (FULL_DAYS))
                                    MESSAGE += "Whole: "+ str (FULL_DAYS) +"\n"
                                    p.setFillColor (black)
                            except:
                                pass

                            # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------
                            if "EP" in CONFIG or "SR" in CONFIG:
                                for P in kwargs["student"].parents.all():
                                    if "EP" in CONFIG:
                                        if len (P.email):
                                            try: # we won't be having any feedback -- since the PDF is returned...
                                                send_mail (getattr(settings, 'EMAIL_SUBJECT', ''), MESSAGE, getattr (settings, 'EMAIL_FROM', ''), [P.email], fail_silently = True)
                                            except:
                                                pass

                                    if "SR" in CONFIG:
                                        try: # again showing no errors
                                            api.send_sms(body=MESSAGE, from_phone=getattr(settings, 'TWILIO_NUMBER', ''), to=[str(P.phone_number)])
                                        except:
                                            pass
                            # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------
                            # TODO: fix redundancy


            for BRUCE_WILLS in S_AVE_COMPUTED: # -- don't mess with Bruce Willy son  --
                if len (BRUCE_WILLS[1]): # do we have grade reports in the freaken' AC selected?
                    RANK = 1
                    JUMP = 0
                    PREV_MARK = BRUCE_WILLS[1][0][0]

                    for i, S in enumerate (BRUCE_WILLS[1]):
                        if i > 0:
                            if PREV_MARK == S[0]:
                                JUMP += 1

                            else:
                                PREV_MARK = S[0]
                                RANK += (1 + JUMP)
                                JUMP = 0

                        if S[2] == kwargs["student"]:
                            # find the freaken coordinates and draw son -- ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS - ASS
                            SUB_COUNT = 0

                            for GR in S[1]:
                                if GR.student == kwargs["student"]:
                                    if GR.subject.use_letter_grading: # if using letters...
                                        p.drawString (cm * 13.35, cm * (-3.55 + (-0.85 * kwargs["subject_list_o"].index (GR.subject))), convert_to_grade (mark = int (round (GR.mark, 0)))) # the square brackets are VERY important!

                                    else:
                                        # we'll be counting on NON-letters ONLY
                                        # BUG_FIX
                                        SUB_COUNT += 1 # which subjects are ommited out of the -- subject_list_o --

                                        if int (round (GR.mark, 0)) < 50:
                                            p.setFillColor (red)

                                        p.drawString (cm * 13.35, cm * (-3.55 + (-0.85 * kwargs["subject_list_o"].index (GR.subject))), str (int (round (GR.mark, 0))))
                                        p.setFillColor (black) # restoring...

                            try:
                                if round ((S[0] / SUB_COUNT), 1) < CONFIG_OBJ.promotion_min: # setting color to red if student has failed
                                    p.setFillColor (red)

                                p.drawString (cm * 13.35, cm * (-3.55 + (-0.85 * len (kwargs["subject_list_o"]))), str (round ((S[0] / SUB_COUNT), 1))) # writing average
                            except:
                                pass
                            p.setFillColor (black)

                            # the bottom box will NOT change coordiantes -- XOXO -- Gossip Girl!
                            p.drawString (cm * 13.35, cm * (-16.35), str (RANK)) # writing rank
                            p.drawString (cm * 13.35, cm * (-17.15), str (kwargs["student_count"])) # drawing student count

                            # drawing LATE days
                            ATTENDACE = Attendance.objects.filter (academic_semester__semester__in = ["P_I", "P_II", "P_III", "P_IV", "S_I", "S_II"], attendance_type = "LATE")
                            LATE_DAYS = 0
                            if ATTENDACE.exists(): # we might be drawing LATE days
                                for ATD in ATTENDACE:
                                    for STUDENT in ATD.student.all():
                                        if STUDENT == kwargs["student"]:
                                            LATE_DAYS += 1

                            if LATE_DAYS: # we are definitely drawing late days
                                if LATE_DAYS > CONFIG_OBJ.max_late_count:
                                    p.setFillColor (red)

                                p.drawString (cm * 13.35, cm * (-18.935), str (LATE_DAYS))
                                p.setFillColor (black)

                            # drawing FULL days
                            ATTENDACE = Attendance.objects.filter (academic_semester__semester__in = ["P_I", "P_II", "P_III", "P_IV", "S_I", "S_II"], attendance_type = "FULL")
                            FULL_DAYS = 0
                            if ATTENDACE.exists(): # we might be drawing LATE days
                                for ATD in ATTENDACE:
                                    for STUDENT in ATD.student.all():
                                        if STUDENT == kwargs["student"]:
                                            FULL_DAYS += 1

                            if FULL_DAYS: # we are definitely drawing late days
                                if FULL_DAYS > CONFIG_OBJ.max_late_count:
                                    p.setFillColor (red)

                                p.drawString (cm * 13.35, cm * (-18.05), str (FULL_DAYS))
                                p.setFillColor (black)

    """
        since all the students will belong to the same freaken class you'll be using first_name, father_name and gf_name to order the freaken query of each student
        and build a freaken awesome structure -- plase this time make it fucking awesome!!!
        scan the top six -- the one that's not empty will be used -- don't forget to ORDER accoring to the freaken sheet -- again first_name, father_name and gf_name

        i just heard DJ Yemi is FAT!
    """

    # <CLASS_ID, [SUM, GRADE_REPORT_LIST, STUDENT_OBJECT]>
    # turns out this whole shit complicates shit! -- SHIT -- SHIT -- SHIT -- SHIT -- SHIT -- SHIT -- SHIT -- SHIT -- SHIT -- SHIT -- SHIT -- SHIT -- SHIT -- SHIT -- SHIT -- SHIT -- SHIT -- 

    # CHOOSING REPORTER!!! -- ya she MUST be HOT!
    # we'll first be giving for Semesters then to PERIODS --- can't say it enough --- SEXY!
    REPORTER = None

    if len (S_I):
        REPORTER = S_I

    elif len (S_II):
        REPORTER = S_II

    elif len (P_I):
        REPORTER = P_I

    elif len (P_II):
        REPORTER = P_II

    elif len (P_III):
        REPORTER = P_III

    elif len (P_IV):
        REPORTER = P_IV

    FX = False  # this will be used for detecting class change in report
    # <CLASS_ID, [SUM, GRADE_REPORT_LIST, STUDENT_OBJECT]>
    # look at all the freaken indexes!
    try:
        YEAR = REPORTER[0][1][0][1][0].academic_calendar.academic_year # pricking the academic_year of the first grade_report since it MUST be the same year ERY DAY
    except:
        YEAR = AcademicCalendar.objects.filter(id__in = ACADEMIC_CALENDARS)[0].academic_year # again another bug fix: CHECK - CHECK and CHECK!

    for REPORT in REPORTER: # we'll be assuming correspondence! -- Megan Fox be with me!
        if FX: # skipping on the first loop -- just like child support!
            show_class_change()

        CLASS_ROOM = ClassRoom.objects.get (pk = REPORT[0])
        HEAD_TEACHER = ""
        NUMBER = 0 # assuming each student is assigned a freaken number like Kunta...i mean TOBBY!
        STUDENT_COUNT = CLASS_ROOM.student_set.count()
        HEAD_MASTER = Config.objects.all()[0].head_master

        # we're going to be reading head teacher for each class -- that makes Sense doesn't it -- that was sarcasm mitch!
        if "PM" in CONFIG: # we'll be reading the user info if PM is requested...
            if User.objects.filter (user_permissions__codename__istartswith = "H_"+ CLASS_ROOM.grade.grade +"_"+ CLASS_ROOM.section).exists(): # we have a head teacher for the freaken class room
                USER = User.objects.filter (user_permissions__codename__istartswith = "H_"+ CLASS_ROOM.grade.grade +"_"+ CLASS_ROOM.section)[0] # am NOBODIES' BITCH! -- The One -- Jet Li
                HEAD_TEACHER = USER.first_name +" "+ USER.last_name

        for STUDENT in CLASS_ROOM.student_set.all().order_by ("first_name", "father_name", "gf_name"): # looking through students accoring to the numbers they are assigned! -- TOBBY!
            NUMBER = NUMBER + 1

            for COMPLETE_STUDENT in REPORT[1]: # Making sure the students we're looping through has complete grade report with the selected calendars
                if COMPLETE_STUDENT[2] == STUDENT: # Huston -- we have CONFIRMATION -- got it from JAMAICA!
                    if "PM" in CONFIG:
                        build_front (head_master = HEAD_MASTER, home_room_teacher = HEAD_TEACHER, student = STUDENT.first_name +" "+ STUDENT.father_name +" "+ STUDENT.gf_name, class_room = CLASS_ROOM.__unicode__(), number = NUMBER, year = YEAR)
                        p.showPage ()

                    # whether or not it's a master we're ALWAYS --like the tampon-- going have to draw the freaken number at the top corner
                    p.rotate(90)
                    p.setFont('Ubuntu', 12)
                    p.drawString (cm * 0.75, cm * -0.75, str(NUMBER)) # drawing number at the corner

                    if "PM" in CONFIG:
                        build_table (class_room = CLASS_ROOM, number = NUMBER)

                    # draw the freakn mark here -- la-de-da!
                    # walla it's magic
                    write_mark (student = STUDENT, student_count = STUDENT_COUNT, class_room = CLASS_ROOM, subject_list_o = list (CLASS_ROOM.grade.subject.all()), compute_flag = S_I_COMPUTE_FLAG, compute_flag_2 = S_II_COMPUTE_FLAG)
                    S_I_COMPUTE_FLAG = False
                    S_II_COMPUTE_FLAG = False
                    p.showPage ()

        S_I_COMPUTE_FLAG = True
        S_II_COMPUTE_FLAG = True
        FX = True # we've finished a class mitch

    # writing INCOMPLETES...
    p.rotate (0)
    p.setFillColor (red)
    Y = 28
    for i, X in enumerate (INCOMPLETES):
        p.drawString (cm * 1, cm * Y, str (i + 1) +": "+ X[0].__unicode__().upper() +" | "+ X[1].__unicode__() +" | "+ X[2].__unicode__())
        Y -= 0.65

        if (i + 1) % 40 == 0:
            p.showPage()
            p.setFillColor (red)
            Y = 28

    p.setAuthor("-- The Condor --")
    p.setTitle ("Django IZ Freaken AWESOME!")
    p.setSubject ("Report Card")
    p.save()
    #------------------------------------------------------------------------------------------------------------------------------------------------

    return response

def student_transfer (request):
    if not "TRANSFER_LIST" in request.POST or not "TRANSFER_TO" in request.POST: # making sure the user is not accessing the url directly
        return HttpResponseForbidden ("<title>Code እምቢየው</title><h1 style='font-weight:normal;'>Error: Cannot access this page directly</h1>")

    if len (request.POST["TRANSFER_LIST"]) > 0:
        #Student.objects.filter (id__in = request.POST ["TRANSFER_LIST"].split("_")).update (class_room = ClassRoom.objects.get (id = request.POST["TRANSFER_TO"]))

        #"""
        # Triple quote this block on deployment, is SLOWER like ethio tele slower, but shows the pretty animation...SNAP!
        for S in request.POST ["TRANSFER_LIST"].split("_"):
            Student.objects.filter (id = S).update (class_room = ClassRoom.objects.get (id = request.POST["TRANSFER_TO"]))
        #"""

    return HttpResponse ("እቴም ሜቴ የሎሚ ሽታ ያ ሰውዬ ምን አለሽ ማታ")

def send_message_p (request):
    """ Sends message to the parents DIRECTLY, no name no nothing just a freaken message """
    if not "P_LIST_SD" in request.POST or not "FLAG" in request.POST or not "MESSAGE" in request.POST: # making sure the user is not accessing the url directly
        return HttpResponseForbidden ("<title>Code እምቢየው</title><h1 style='font-weight:normal;'>Error: Cannot access this page directly</h1>")

    if request.POST ["FLAG"] == "SMS":
        ERROR_FLAG = False

        for P in request.POST ["P_LIST_SD"].split("_"):
            try:
                api.send_sms (body = request.POST ["MESSAGE"], from_phone=getattr (settings, 'TWILIO_NUMBER', ''), to=[Parent.objects.get(pk = P).phone_number])
            except:
                messages.add_message (request, messages.ERROR, "SMS message has not been sent, Please contact your SMS gateway provider")
                ERROR_FLAG = True
                break

        if not ERROR_FLAG:
            messages.add_message (request, messages.INFO, "SMS message has been sent successfully")

    elif request.POST ["FLAG"] == "EMAIL":
        ERROR_FLAG = False

        MAIL_LIST = {}
        for P in request.POST ["P_LIST_SD"].split("_"):
            if len (Parent.objects.get (pk = P).email): # Parent has email
                MAIL_LIST [str (Parent.objects.get (pk = P).email)] = "MOE"

        if len (MAIL_LIST):
            try:
                send_mail (getattr(settings, 'EMAIL_SUBJECT', ''), request.POST["MESSAGE"], getattr(settings, 'EMAIL_FROM', ''), list (MAIL_LIST), fail_silently = False)
            except:
                messages.add_message (request, messages.ERROR, "Email message has not been sent, Please check your email settings")
                ERROR_FLAG = True

            if not ERROR_FLAG:
                messages.add_message (request, messages.INFO, "Email message has been sent successfully")

    elif request.POST ["FLAG"] == "BOTH":
        ERROR_FLAG = False

        for P in request.POST ["P_LIST_SD"].split("_"):
            try:
                api.send_sms (body = request.POST ["MESSAGE"], from_phone=getattr(settings, 'TWILIO_NUMBER', ''), to=[Parent.objects.get(pk = P).phone_number])
            except:
                messages.add_message (request, messages.ERROR, "SMS message has not been sent, Please contact your SMS gateway provider")
                ERROR_FLAG = True
                break

        if not ERROR_FLAG:
            messages.add_message (request, messages.INFO, "SMS message has been sent successfully")

        ERROR_FLAG = False

        MAIL_LIST = {}
        for P in request.POST ["P_LIST_SD"].split("_"):
            if len (Parent.objects.get (pk = P).email): # Parent has email
                MAIL_LIST [str (Parent.objects.get (pk = P).email)] = "MOE"

        if len (MAIL_LIST):
            try:
                send_mail (getattr(settings, 'EMAIL_SUBJECT', ''), request.POST["MESSAGE"], getattr(settings, 'EMAIL_FROM', ''), list (MAIL_LIST), fail_silently = False)
            except:
                messages.add_message (request, messages.ERROR, "Email message has not been sent, Please check your email settings")
                ERROR_FLAG = True

            if not ERROR_FLAG:
                messages.add_message (request, messages.INFO, "Email message has been sent successfully")

    return HttpResponseRedirect ("/TheCondor/condor/parent/")
