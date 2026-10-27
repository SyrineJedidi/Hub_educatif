from django.urls import path
from . import views as v
from . import subject_views as m
from . import student_views as s
from . import shared_views as x
urlpatterns = [
    path('subjects/', m.SubjectsView.as_view()),
    path('subjects/<str:uid>/', m.SubjectDetailView.as_view()),
    path('courses/search/', x.SearchView.as_view()),
    path('courses/processing/', x.ProcessingStatusView.as_view()),
    path('courses/resources/<str:resource_id>/file/', x.ResourceFileView.as_view()),
    path('courses/', v.CoursesView.as_view()),
    path('courses/<str:uid>/', v.CourseDetailView.as_view()),
    path('courses/<str:uid>/publish/', v.CourseActionView.as_view(transition='publish')),
    path('courses/<str:uid>/unpublish/', v.CourseActionView.as_view(transition='unpublish')),
    path('courses/<str:uid>/archive/', v.CourseActionView.as_view(transition='archive')),
    path('courses/<str:uid>/restore/', v.CourseActionView.as_view(transition='restore')),
    path('courses/<str:uid>/chapters/', v.ChaptersView.as_view()),
    path('courses/<str:uid>/chapters/reorder/', v.ChapterReorderView.as_view()),
    path('courses/<str:uid>/chapters/<str:chapter_id>/', v.ChapterDetailView.as_view()),
    path('courses/<str:uid>/chapters/<str:chapter_id>/resources/reorder/', v.ResourceReorderView.as_view()),
    path('courses/<str:uid>/resources/', v.ResourcesView.as_view()),
    path('courses/<str:uid>/resources/<str:resource_id>/', v.ResourceDetailView.as_view()),
    path('courses/<str:uid>/resources/<str:resource_id>/reprocess/', v.ReprocessView.as_view()),
    path('courses/<str:uid>/resources/<str:resource_id>/segments/', v.SegmentsView.as_view()),
    path('courses/<str:uid>/resources/<str:resource_id>/segments/<str:segment_id>/', v.SegmentDetailView.as_view()),
    path('courses/<str:uid>/statistics/', v.StatisticsView.as_view()),
    path('student/courses/', s.StudentCoursesView.as_view()),
    path('student/courses/<str:uid>/', s.StudentCourseDetailView.as_view()),
    path('student/courses/<str:uid>/resources/<str:resource_id>/', s.StudentResourceView.as_view()),
    path('student/courses/<str:uid>/resources/<str:resource_id>/segments/', s.StudentSegmentsView.as_view()),
    path('student/courses/<str:uid>/resources/<str:resource_id>/views/', s.ResourceViewTrackingView.as_view()),
]
