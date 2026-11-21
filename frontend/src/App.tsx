import React, { useEffect, useRef, useState } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Sidebar } from '@/components/layout/Sidebar';
import Dashboard from '@/pages/Dashboard';
import CourseSetup, { CourseForm } from '@/pages/CourseSetup';
import UnitUploads from '@/pages/UnitUploads';
import CoverageAnalysis from '@/pages/CoverageAnalysis';
import StudyTimeline from '@/pages/StudyTimeline';
import TopicLearning from '@/pages/TopicLearning';
import Settings from '@/pages/Settings';
import { Menu, Moon, ShieldCheck, Sun } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

export default function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    () => localStorage.getItem('semestrack-sidebar-collapsed') === 'true'
  );
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const mobileMenuRef = useRef<HTMLDivElement>(null);
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const savedTheme = localStorage.getItem('semestrack-theme');
    if (savedTheme === 'light' || savedTheme === 'dark') return savedTheme;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  });

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.classList.toggle('dark', theme === 'dark');
    localStorage.setItem('semestrack-theme', theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem('semestrack-sidebar-collapsed', String(sidebarCollapsed));
  }, [sidebarCollapsed]);

  useEffect(() => {
    mobileMenuRef.current?.toggleAttribute('inert', !mobileMenuOpen);
    if (!mobileMenuOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMobileMenuOpen(false);
    };
    document.addEventListener('keydown', closeOnEscape);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', closeOnEscape);
      document.body.style.overflow = '';
    };
  }, [mobileMenuOpen]);

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
      <div
        ref={mobileMenuRef}
        className={`fixed inset-0 z-50 transition-opacity duration-300 md:hidden ${
          mobileMenuOpen ? 'pointer-events-auto opacity-100' : 'pointer-events-none opacity-0'
        }`}
        style={{
          visibility: mobileMenuOpen ? 'visible' : 'hidden',
          transition: mobileMenuOpen
            ? 'opacity 300ms ease'
            : 'opacity 300ms ease, visibility 0s linear 300ms',
        }}
        aria-hidden={!mobileMenuOpen}
      >
        <button
          type="button"
          tabIndex={mobileMenuOpen ? 0 : -1}
          onClick={() => setMobileMenuOpen(false)}
          className={`absolute inset-0 h-full w-full bg-black/45 backdrop-blur-[2px] transition-opacity duration-300 ${
            mobileMenuOpen ? 'opacity-100' : 'opacity-0'
          }`}
          aria-label="Close navigation menu"
        />
        <div
          className={`absolute inset-y-0 left-0 z-10 w-72 max-w-[85vw] shadow-2xl transition-transform duration-300 ease-out ${
            mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'
          }`}
        >
          <Sidebar mobile onClose={() => setMobileMenuOpen(false)} />
        </div>
      </div>

      {/* Main Layout Area */}
      <div className="flex flex-1 flex-col min-w-0">
        {/* Top Header Bar */}
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-gray-200/80 bg-white/95 px-4 backdrop-blur-sm sm:px-6">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(true)}
              aria-expanded={mobileMenuOpen}
              aria-controls="mobile-navigation"
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
            <button
              type="button"
              onClick={() => setTheme((current) => current === 'light' ? 'dark' : 'light')}
              className="inline-flex h-9 items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 text-xs font-medium text-gray-700 shadow-sm transition-colors hover:bg-gray-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
              aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`}
              title={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`}
            >
              {theme === 'light' ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
              <span className="hidden sm:inline">{theme === 'light' ? 'Dark mode' : 'Light mode'}</span>
            </button>
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
