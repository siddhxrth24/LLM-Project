import React, { useState } from 'react';
import { PageHeader } from '@/components/shared/PageHeader';
import { useCourses, useSchedule, useGenerateSchedule } from '@/lib/queries';
import { Select } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Calendar, Sparkles } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';
import { Badge } from '@/components/ui/badge';

export default function SchedulePage() {
  const { data: coursesData } = useCourses();
  const courses = Array.isArray(coursesData) ? coursesData : coursesData?.courses || [];
  const [selectedCourseId, setSelectedCourseId] = useState<number | undefined>(
    courses[0]?.id
  );

  const { data: schedule, isLoading } = useSchedule(selectedCourseId);
  const generateMutation = useGenerateSchedule();

  const handleGenerate = () => {
    if (selectedCourseId) {
      generateMutation.mutate({ courseId: selectedCourseId });
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Study Schedule"
        description="Topologically sorted revision schedule respecting prerequisite topics and exam deadlines."
        actions={
          <Button
            onClick={handleGenerate}
            disabled={generateMutation.isPending || !selectedCourseId}
          >
            <Sparkles className="mr-2 h-4 w-4" />
            {generateMutation.isPending ? 'Generating...' : 'Generate Schedule'}
          </Button>
        }
      />

      <div className="w-full sm:w-64">
        <label className="block text-xs font-medium text-gray-500 mb-1">Select Course</label>
        <Select
          value={selectedCourseId}
          onChange={(e) => setSelectedCourseId(Number(e.target.value))}
        >
          {courses.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>
      </div>

      {isLoading ? (
        <LoadingSpinner text="Loading study schedule..." fullHeight />
      ) : schedule ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-3">
            <Card>
              <CardContent className="pt-6">
                <div className="text-2xl font-bold">{schedule.total_sessions}</div>
                <p className="text-xs text-gray-500">Planned Sessions</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-2xl font-bold">{schedule.total_hours} hrs</div>
                <p className="text-xs text-gray-500">Total Study Time</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-2xl font-bold">
                  {schedule.is_feasible ? (
                    <span className="text-emerald-600">Feasible</span>
                  ) : (
                    <span className="text-red-600">Tight Schedule</span>
                  )}
                </div>
                <p className="text-xs text-gray-500">Target Exam Timeline</p>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Timeline Sessions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="divide-y divide-gray-100">
                {schedule.sessions?.map((session) => (
                  <div
                    key={session.id}
                    className="flex items-center justify-between py-3 text-sm"
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-50 text-primary-600 shrink-0">
                        <Calendar className="h-4 w-4" />
                      </div>
                      <div>
                        <p className="font-medium text-gray-900">
                          {session.topic_name || `Session #${session.order_index}`}
                        </p>
                        <p className="text-xs text-gray-500">
                          {session.scheduled_date} · {session.duration_hours} hrs
                        </p>
                      </div>
                    </div>
                    <Badge variant={session.session_type === 'revision' ? 'warning' : 'secondary'}>
                      {session.session_type}
                    </Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      ) : (
        <div className="text-center py-12 text-sm text-gray-500">
          No schedule found for this course. Click "Generate Schedule" to compute optimal dates.
        </div>
      )}
    </div>
  );
}
