import React from 'react';
import { PageHeader } from '@/components/shared/PageHeader';
import { Button } from '@/components/ui/button';
import { Plus, BookOpen } from 'lucide-react';
import { useCourses } from '@/lib/queries';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';
import { EmptyState } from '@/components/shared/EmptyState';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';

export default function CoursesPage() {
  const { data, isLoading } = useCourses();
  const courses = Array.isArray(data) ? data : data?.courses || [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Courses"
        description="Manage your academic subjects, syllabus outlines, and exam milestones."
        actions={
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            Add Course
          </Button>
        }
      />

      {isLoading ? (
        <LoadingSpinner text="Loading courses..." fullHeight />
      ) : courses.length === 0 ? (
        <EmptyState
          icon={BookOpen}
          title="No courses yet"
          description="Create your first course and provide its syllabus to start tracking study materials."
          actionLabel="Create Course"
          onAction={() => {}}
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {courses.map((course) => (
            <Card key={course.id} className="hover:shadow-md transition-shadow">
              <CardHeader>
                <CardTitle>{course.name}</CardTitle>
                <CardDescription>
                  {course.exam_date ? `Exam: ${course.exam_date}` : 'No exam date set'}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-gray-600">
                <div className="flex justify-between">
                  <span>Units:</span>
                  <span className="font-medium text-gray-900">{course.unit_count}</span>
                </div>
                <div className="flex justify-between">
                  <span>Documents:</span>
                  <span className="font-medium text-gray-900">{course.document_count}</span>
                </div>
                <div className="flex justify-between">
                  <span>Daily Study:</span>
                  <span className="font-medium text-gray-900">{course.daily_study_hours} hrs</span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
