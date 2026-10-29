import React, { useState } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Sidebar } from '@/components/layout/Sidebar';
import Dashboard from '@/pages/Dashboard';
import CourseSetup, { CourseForm } from '@/pages/CourseSetup';
import UnitUploads from '@/pages/UnitUploads';
import CoverageAnalysis from '@/pages/CoverageAnalysis';
import StudyTimeline from '@/pages/StudyTimeline';
import TopicLearning from '@/pages/TopicLearning';
import Settings from '@/pages/Settings';
import { Menu, ShieldCheck } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

export default function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-gray-50 text-gray-900 font-sans">
      {/* Desktop Sidebar */}
      <div className="hidden md:flex shrink-0">
        <Sidebar
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed((prev) => !prev)}
        />
      </div>

      {/* Mobile Sidebar Overlay */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div
            className="fixed inset-0 bg-black/40 backdrop-blur-xs"
            onClick={() => setMobileMenuOpen(false)}
          />
          <div className="fixed inset-y-0 left-0 z-50 w-64 bg-white shadow-xl">
            <Sidebar onToggleCollapse={() => setMobileMenuOpen(false)} />
          </div>
        </div>
      )}

      {/* Main Layout Area */}
      <div className="flex flex-1 flex-col min-w-0">
        {/* Top Header Bar */}
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-gray-200/80 bg-white/95 px-4 backdrop-blur-sm sm:px-6">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(true)}
              className="p-1.5 text-gray-500 hover:text-gray-900 rounded-lg md:hidden"
              aria-label="Open navigation menu"
            >
              <Menu className="h-5 w-5" />
            </button>
            <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">
              Offline Workspace
            </span>
          </div>

          <div className="flex items-center gap-3">
            <Badge
              variant="outline"
              className="hidden sm:inline-flex items-center gap-1.5 bg-emerald-50 text-emerald-700 border-emerald-200 text-xs font-medium"
            >
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
              <span>Offline Guaranteed</span>
            </Badge>
          </div>
        </header>

        {/* Page Content Viewport */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto animate-in fade-in duration-200">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/courses" element={<CourseSetup />} />
            <Route path="/courses/new" element={<CourseForm />} />
            <Route path="/courses/:id/edit" element={<CourseForm />} />
            <Route path="/documents" element={<UnitUploads />} />
            <Route path="/documents/:courseId" element={<UnitUploads />} />
            <Route path="/coverage" element={<CoverageAnalysis />} />
            <Route path="/coverage/:courseId" element={<CoverageAnalysis />} />
            <Route path="/schedule" element={<StudyTimeline />} />
            <Route path="/schedule/:courseId" element={<StudyTimeline />} />
            <Route path="/topics" element={<TopicLearning />} />
            <Route path="/topics/:courseId" element={<TopicLearning />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
