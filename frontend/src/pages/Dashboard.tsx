import * as React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  BookOpen,
  FileText,
  BarChart3,
  Calendar,
  Plus,
  ArrowRight,
  Sparkles,
  Clock,
  CheckCircle2,
  AlertCircle,
  GraduationCap,
  HardDrive,
  UploadCloud,
} from 'lucide-react';
import { format, differenceInCalendarDays, isValid, parseISO } from 'date-fns';

import { useCourses, Course } from '@/lib/queries';
import { PageHeader } from '@/components/shared/PageHeader';
import { EmptyState } from '@/components/shared/EmptyState';
import { ErrorDisplay } from '@/components/shared/ErrorDisplay';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';

export default function Dashboard() {
  const navigate = useNavigate();
  const { data, isLoading, isError, error, refetch } = useCourses();

  // Normalize courses data (can be array or { courses, total })
  const courses: Course[] = React.useMemo(() => {
    if (!data) return [];
    if (Array.isArray(data)) return data;
    if ('courses' in data && Array.isArray(data.courses)) return data.courses;
    return [];
  }, [data]);

  // Derived stats
  const totalCourses = courses.length;
  const totalDocuments = courses.reduce((sum, c) => sum + (c.document_count || 0), 0);
  const totalTopics = courses.reduce((sum, c) => sum + (c.topic_count || 0), 0);

  // Approximate overall coverage rate from topic counts & docs
  const averageCoverage = React.useMemo(() => {
    if (totalCourses === 0) return 0;
    // Calculate based on courses having documents/topics
    let totalScore = 0;
    courses.forEach((c) => {
      if (c.topic_count > 0 && c.document_count > 0) {
        totalScore += Math.min(100, Math.round((c.document_count / Math.max(1, c.unit_count || 5)) * 100));
      } else if (c.document_count > 0) {
        totalScore += 25;
      }
    });
    return Math.round(totalScore / totalCourses);
  }, [courses, totalCourses]);

  const formatExamDate = (dateString?: string | null) => {
    if (!dateString) return null;
    try {
      const parsed = parseISO(dateString);
      if (!isValid(parsed)) return null;
      const daysLeft = differenceInCalendarDays(parsed, new Date());
      return {
        formatted: format(parsed, 'MMM dd, yyyy'),
        daysLeft,
      };
    } catch {
      return null;
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-8 animate-in fade-in duration-200">
        <div className="space-y-2">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-4 w-96" />
        </div>

        {/* Stats Skeleton */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="p-5">
              <div className="flex items-center justify-between">
                <div className="space-y-2">
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-7 w-14" />
                </div>
                <Skeleton className="h-11 w-11 rounded-lg" />
              </div>
            </Card>
          ))}
        </div>

        {/* Course Cards Skeleton */}
        <div className="space-y-4">
          <Skeleton className="h-6 w-36" />
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {Array.from({ length: 3 }).map((_, i) => (
              <Card key={i} className="p-6 space-y-4">
                <Skeleton className="h-5 w-3/4" />
                <Skeleton className="h-4 w-1/2" />
                <Skeleton className="h-2.5 w-full" />
                <div className="flex justify-between pt-2">
                  <Skeleton className="h-8 w-24" />
                  <Skeleton className="h-8 w-20" />
                </div>
              </Card>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="py-8">
        <ErrorDisplay
          title="Failed to load dashboard data"
          message="Could not retrieve your courses from the local backend."
          error={error as Error}
          onRetry={() => refetch()}
          fullHeight
        />
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-12">
      {/* Welcome Header */}
      <PageHeader
        title="Semester Dashboard"
        description="Track your academic syllabus, inspect material coverage, and follow your offline AI study plan."
        actions={
          <Button onClick={() => navigate('/courses/new')} className="gap-2 shadow-sm">
            <Plus className="h-4 w-4" />
            New Course
          </Button>
        }
      />

      {/* Top Banner Guide for Offline AI Mode */}
      <div className="relative overflow-hidden rounded-xl border border-primary-200 bg-gradient-to-r from-primary-50 via-white to-primary-50/50 p-5 shadow-xs">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary-600 text-white shadow-sm shrink-0">
              <GraduationCap className="h-6 w-6" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-gray-900">
                100% Offline AI Learning Platform Active
              </h2>
              <p className="text-xs text-gray-600 mt-0.5">
                All syllabus extraction, document embeddings, and AI tutoring run entirely locally on your hardware.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/settings')}
              className="text-xs bg-white text-gray-700 hover:text-gray-900 shadow-xs"
            >
              <HardDrive className="mr-1.5 h-3.5 w-3.5 text-gray-500" />
              Model Status
            </Button>
          </div>
        </div>
      </div>

      {/* Stats Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Courses */}
        <Card className="hover:shadow-md transition-shadow">
          <CardContent className="p-5 flex items-center justify-between">
            <div className="space-y-1">
              <p className="text-xs font-medium uppercase tracking-wider text-gray-500">
                Total Courses
              </p>
              <p className="text-2xl font-bold text-gray-900">{totalCourses}</p>
              <p className="text-xs text-gray-500">Registered this semester</p>
            </div>
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary-50 text-primary-600">
              <BookOpen className="h-6 w-6" />
            </div>
          </CardContent>
        </Card>

        {/* Documents Uploaded */}
        <Card className="hover:shadow-md transition-shadow">
          <CardContent className="p-5 flex items-center justify-between">
            <div className="space-y-1">
              <p className="text-xs font-medium uppercase tracking-wider text-gray-500">
                Documents Uploaded
              </p>
              <p className="text-2xl font-bold text-gray-900">{totalDocuments}</p>
              <p className="text-xs text-gray-500">PDFs & lecture slide decks</p>
            </div>
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-50 text-blue-600">
              <FileText className="h-6 w-6" />
            </div>
          </CardContent>
        </Card>

        {/* Topics Extracted */}
        <Card className="hover:shadow-md transition-shadow">
          <CardContent className="p-5 flex items-center justify-between">
            <div className="space-y-1">
              <p className="text-xs font-medium uppercase tracking-wider text-gray-500">
                Syllabus Topics
              </p>
              <p className="text-2xl font-bold text-gray-900">{totalTopics}</p>
              <p className="text-xs text-gray-500">Structured syllabus units</p>
            </div>
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
              <BarChart3 className="h-6 w-6" />
            </div>
          </CardContent>
        </Card>

        {/* Average Material Coverage */}
        <Card className="hover:shadow-md transition-shadow">
          <CardContent className="p-5 flex items-center justify-between">
            <div className="space-y-1">
              <p className="text-xs font-medium uppercase tracking-wider text-gray-500">
                Material Coverage
              </p>
              <p className="text-2xl font-bold text-gray-900">{averageCoverage}%</p>
              <div className="w-24 mt-1.5">
                <Progress value={averageCoverage} className="h-1.5" />
              </div>
            </div>
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
              <Calendar className="h-6 w-6" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Courses Section */}
      <div className="space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-gray-900">Your Enrolled Courses</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              Select a course to inspect notes, audit coverage, or jump into study sessions.
            </p>
          </div>
          {totalCourses > 0 && (
            <Link
              to="/courses"
              className="text-xs font-semibold text-primary-600 hover:text-primary-700 flex items-center gap-1 group"
            >
              <span>Manage all</span>
              <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
            </Link>
          )}
        </div>

        {totalCourses === 0 ? (
          <EmptyState
            icon={BookOpen}
            title="No courses registered yet"
            description="Get started by creating your first course. Paste your syllabus and set your exam date to let SemesTrack build your timeline."
            actionLabel="Create your first course"
            onAction={() => navigate('/courses/new')}
            className="py-16 bg-white border-dashed border-gray-300"
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {courses.map((course) => {
              const examInfo = formatExamDate(course.exam_date);
              const coverageEstimate = course.topic_count > 0
                ? Math.min(100, Math.round(((course.document_count || 1) / Math.max(1, course.unit_count || 5)) * 100))
                : 0;

              return (
                <Card
                  key={course.id}
                  className="flex flex-col justify-between border-gray-200/90 hover:border-primary-300 hover:shadow-md transition-all duration-200"
                >
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="space-y-1">
                        <CardTitle className="text-base line-clamp-1">
                          {course.name}
                        </CardTitle>
                        <CardDescription className="text-xs">
                          {course.unit_count || 5} Units &bull; {course.topic_count || 0} Topics
                        </CardDescription>
                      </div>
                      <Badge
                        variant="secondary"
                        className="capitalize text-[11px] font-medium shrink-0"
                      >
                        {course.difficulty_preference || 'Balanced'}
                      </Badge>
                    </div>
                  </CardHeader>

                  <CardContent className="space-y-4 pb-4">
                    {/* Exam Date pill */}
                    {examInfo ? (
                      <div className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2 text-xs border border-gray-100">
                        <span className="flex items-center gap-1.5 text-gray-600">
                          <Calendar className="h-3.5 w-3.5 text-gray-400 shrink-0" />
                          <span>Exam: {examInfo.formatted}</span>
                        </span>
                        <span
                          className={`font-semibold ${
                            examInfo.daysLeft <= 7
                              ? 'text-red-600 font-bold'
                              : examInfo.daysLeft <= 30
                              ? 'text-amber-600'
                              : 'text-primary-700'
                          }`}
                        >
                          {examInfo.daysLeft < 0
                            ? 'Past'
                            : examInfo.daysLeft === 0
                            ? 'Today'
                            : `${examInfo.daysLeft}d left`}
                        </span>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1.5 text-xs text-gray-400 py-1">
                        <Calendar className="h-3.5 w-3.5 shrink-0" />
                        <span>No exam date specified</span>
                      </div>
                    )}

                    {/* Progress details */}
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-gray-500 font-medium">Estimated Coverage</span>
                        <span className="font-semibold text-gray-900">{coverageEstimate}%</span>
                      </div>
                      <Progress value={coverageEstimate} className="h-2" />
                    </div>

                    {/* Quick counts */}
                    <div className="grid grid-cols-2 gap-2 text-center pt-1 text-xs">
                      <div className="rounded-md bg-gray-50 p-2 border border-gray-100">
                        <p className="text-gray-500 text-[10px] uppercase font-medium">Documents</p>
                        <p className="text-sm font-bold text-gray-800">{course.document_count || 0}</p>
                      </div>
                      <div className="rounded-md bg-gray-50 p-2 border border-gray-100">
                        <p className="text-gray-500 text-[10px] uppercase font-medium">Pacing</p>
                        <p className="text-sm font-bold text-gray-800">{course.daily_study_hours || 2}h/day</p>
                      </div>
                    </div>
                  </CardContent>

                  <CardFooter className="pt-2 border-t border-gray-100 flex items-center justify-between gap-2 bg-gray-50/50 rounded-b-xl">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-xs h-8 text-gray-600 hover:text-primary-600"
                      onClick={() => navigate(`/documents?courseId=${course.id}`)}
                    >
                      <UploadCloud className="mr-1.5 h-3.5 w-3.5" />
                      Upload
                    </Button>
                    <Button
                      variant="default"
                      size="sm"
                      className="text-xs h-8 gap-1"
                      onClick={() => navigate(`/schedule?courseId=${course.id}`)}
                    >
                      <span>Study Plan</span>
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Button>
                  </CardFooter>
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {/* Quick Actions & Guidance Section */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-4">
        {/* Step 1: Upload Documents */}
        <Card className="bg-white border-gray-200">
          <CardContent className="p-5 space-y-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-100 text-primary-700">
              <UploadCloud className="h-5 w-5" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900 text-sm">1. Upload Materials</h3>
              <p className="text-xs text-gray-500 mt-1 leading-relaxed">
                Add lecture slides (PPTX) and textbook chapters (PDF) for each unit to build your offline vector index.
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="w-full text-xs"
              onClick={() => navigate('/documents')}
            >
              Go to Document Manager
            </Button>
          </CardContent>
        </Card>

        {/* Step 2: Topic Coverage */}
        <Card className="bg-white border-gray-200">
          <CardContent className="p-5 space-y-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-100 text-emerald-700">
              <CheckCircle2 className="h-5 w-5" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900 text-sm">2. Audit Syllabus Coverage</h3>
              <p className="text-xs text-gray-500 mt-1 leading-relaxed">
                Discover which syllabus topics are fully explained in your slides and highlight uncovered exam items.
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="w-full text-xs"
              onClick={() => navigate('/coverage')}
            >
              Analyze Coverage
            </Button>
          </CardContent>
        </Card>

        {/* Step 3: AI Tutor */}
        <Card className="bg-white border-gray-200">
          <CardContent className="p-5 space-y-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-100 text-amber-700">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900 text-sm">3. Study with Local AI</h3>
              <p className="text-xs text-gray-500 mt-1 leading-relaxed">
                Generate high-retention lessons, analogies, worked examples, and practice questions from your syllabus.
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="w-full text-xs"
              onClick={() => navigate('/topics')}
            >
              Open Topic Tutor
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
