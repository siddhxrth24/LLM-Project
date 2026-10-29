import React, { useState } from 'react';
import { PageHeader } from '@/components/shared/PageHeader';
import { FileUploadZone } from '@/components/shared/FileUploadZone';
import { useCourses, useDocuments, useUploadDocument } from '@/lib/queries';
import { Select } from '@/components/ui/select';
import { EmptyState } from '@/components/shared/EmptyState';
import { FileText } from 'lucide-react';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';

export default function DocumentsPage() {
  const { data: coursesData } = useCourses();
  const courses = Array.isArray(coursesData) ? coursesData : coursesData?.courses || [];

  const [selectedCourseId, setSelectedCourseId] = useState<number | undefined>(
    courses[0]?.id
  );
  const [selectedUnit, setSelectedUnit] = useState<number>(1);

  const { data: docs = [], isLoading } = useDocuments(selectedCourseId);
  const uploadMutation = useUploadDocument();

  const handleUpload = async (files: File[]) => {
    if (!selectedCourseId) return;
    const formData = new FormData();
    files.forEach((f) => formData.append('files', f));
    await uploadMutation.mutateAsync({
      courseId: selectedCourseId,
      unitNumber: selectedUnit,
      formData,
    });
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Documents"
        description="Upload course lecture notes and presentation slides (PDF/PPTX) organized by unit."
      />

      <div className="flex flex-col sm:flex-row gap-4 items-center">
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

        <div className="w-full sm:w-40">
          <label className="block text-xs font-medium text-gray-500 mb-1">Target Unit</label>
          <Select
            value={selectedUnit}
            onChange={(e) => setSelectedUnit(Number(e.target.value))}
          >
            {[1, 2, 3, 4, 5].map((u) => (
              <option key={u} value={u}>
                Unit {u}
              </option>
            ))}
          </Select>
        </div>
      </div>

      <FileUploadZone
        onUpload={handleUpload}
        isLoading={uploadMutation.isPending}
      />

      <Card>
        <CardHeader>
          <CardTitle>Uploaded Documents</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-6 text-sm text-gray-500">Loading documents...</div>
          ) : docs.length === 0 ? (
            <EmptyState
              icon={FileText}
              title="No documents uploaded"
              description="Drop lecture slides or chapter notes above to extract and index syllabus concepts."
            />
          ) : (
            <div className="divide-y divide-gray-100">
              {docs.map((doc) => (
                <div key={doc.id} className="flex items-center justify-between py-3">
                  <div>
                    <h4 className="font-medium text-sm text-gray-900">{doc.original_filename}</h4>
                    <p className="text-xs text-gray-500">
                      Unit {doc.unit_id} · {doc.page_count} pages · {doc.chunk_count} chunks
                    </p>
                  </div>
                  <StatusBadge status={doc.status} />
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
