import React from 'react';
import { PageHeader } from '@/components/shared/PageHeader';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { BookOpen, FileText, CheckCircle2, Calendar, Sparkles, ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useCourses, useSystemStatus } from '@/lib/queries';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';

export default function DashboardPage() {
  const { data: coursesData, isLoading: coursesLoading } = useCourses();
  const { data: systemStatus } = useSystemStatus();

  const courses = Array.isArray(coursesData)
    ? coursesData
    : coursesData?.courses || [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description="Welcome to SemesTrack — your completely offline AI academic study companion."
        actions={
          <Link to="/courses">
            <Button>
              <BookOpen className="mr-2 h-4 w-4" />
              Manage Courses
            </Button>
          </Link>
        }
      />

      {/* Quick Stats Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">Active Courses</CardTitle>
            <BookOpen className="h-4 w-4 text-primary-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-gray-900">{courses.length}</div>
            <p className="text-xs text-gray-500 mt-1">Configured study subjects</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">Indexed Documents</CardTitle>
            <FileText className="h-4 w-4 text-blue-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-gray-900">
              {systemStatus?.storage?.total_documents ?? 0}
            </div>
            <p className="text-xs text-gray-500 mt-1">Course slides & notes</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">Vector Chunks</CardTitle>
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-gray-900">
              {systemStatus?.storage?.total_chunks ?? 0}
            </div>
            <p className="text-xs text-gray-500 mt-1">Embedded into local ChromaDB</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">Model Engine</CardTitle>
            <Sparkles className="h-4 w-4 text-indigo-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-gray-900">
              {systemStatus?.models?.llm_loaded ? 'Loaded' : 'Ready'}
            </div>
            <p className="text-xs text-gray-500 mt-1">Local inference mode</p>
          </CardContent>
        </Card>
      </div>

      {/* Main Sections */}
      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent Courses</CardTitle>
            <CardDescription>Your registered academic courses and syllabus progress</CardDescription>
          </CardHeader>
          <CardContent>
            {coursesLoading ? (
              <LoadingSpinner text="Loading courses..." />
            ) : courses.length === 0 ? (
              <div className="text-center py-6 text-sm text-gray-500">
                No courses added yet.{' '}
                <Link to="/courses" className="text-primary-600 font-medium hover:underline">
                  Add your first course
                </Link>
              </div>
            ) : (
              <div className="space-y-3">
                {courses.slice(0, 4).map((c) => (
                  <Link
                    key={c.id}
                    to="/courses"
                    className="flex items-center justify-between p-3 rounded-lg border border-gray-100 hover:bg-gray-50 transition-colors"
                  >
                    <div>
                      <h4 className="font-medium text-sm text-gray-900">{c.name}</h4>
                      <p className="text-xs text-gray-500">
                        {c.unit_count} Units · {c.document_count} Documents
                      </p>
                    </div>
                    <ArrowRight className="h-4 w-4 text-gray-400" />
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Study Quick Actions</CardTitle>
            <CardDescription>Direct shortcuts to high-priority study workflows</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Link
              to="/documents"
              className="flex items-center gap-3 p-3 rounded-lg border border-gray-100 hover:bg-gray-50 transition-colors"
            >
              <div className="p-2 rounded-md bg-blue-50 text-blue-600">
                <FileText className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">Upload Course Material</p>
                <p className="text-xs text-gray-500">Add slide decks or lecture notes (PDF, PPTX)</p>
              </div>
            </Link>

            <Link
              to="/coverage"
              className="flex items-center gap-3 p-3 rounded-lg border border-gray-100 hover:bg-gray-50 transition-colors"
            >
              <div className="p-2 rounded-md bg-emerald-50 text-emerald-600">
                <CheckCircle2 className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">Analyze Syllabus Coverage</p>
                <p className="text-xs text-gray-500">Verify what concepts are missing before exams</p>
              </div>
            </Link>

            <Link
              to="/schedule"
              className="flex items-center gap-3 p-3 rounded-lg border border-gray-100 hover:bg-gray-50 transition-colors"
            >
              <div className="p-2 rounded-md bg-amber-50 text-amber-600">
                <Calendar className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">Generate Study Schedule</p>
                <p className="text-xs text-gray-500">Topological calendar tailored to exam targets</p>
              </div>
            </Link>

            <Link
              to="/topics"
              className="flex items-center gap-3 p-3 rounded-lg border border-gray-100 hover:bg-gray-50 transition-colors"
            >
              <div className="p-2 rounded-md bg-indigo-50 text-indigo-600">
                <Sparkles className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">AI Topic Teacher</p>
                <p className="text-xs text-gray-500">Generate explanations, analogies, and quizzes</p>
              </div>
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
