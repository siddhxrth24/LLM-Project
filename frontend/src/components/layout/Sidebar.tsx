import * as React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  BookOpen,
  FileText,
  CheckCircle2,
  Calendar,
  Sparkles,
  Settings,
  ChevronLeft,
  GraduationCap,
  HardDrive,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Tooltip } from '@/components/ui/tooltip';

interface SidebarProps {
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  mobile?: boolean;
  onClose?: () => void;
}

interface NavItem {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const navItems: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/courses', label: 'Courses', icon: BookOpen },
  { to: '/documents', label: 'Documents', icon: FileText },
  { to: '/coverage', label: 'Coverage', icon: CheckCircle2 },
  { to: '/schedule', label: 'Schedule', icon: Calendar },
  { to: '/topics', label: 'Topics & Tutor', icon: Sparkles },
  { to: '/settings', label: 'Settings', icon: Settings },
];

export function Sidebar({ collapsed = false, onToggleCollapse, mobile = false, onClose }: SidebarProps) {
  return (
    <aside
      className={cn(
        'relative flex h-screen shrink-0 select-none flex-col border-r border-gray-200 bg-white transition-[width] duration-300 ease-in-out',
        mobile ? 'w-full' : 'sticky top-0 z-30',
        !mobile && (collapsed ? 'w-[4.5rem]' : 'w-64')
      )}
    >
      {/* Brand Header */}
      <div className={cn('flex h-16 items-center justify-between overflow-hidden border-b border-gray-100 transition-[padding] duration-300', collapsed && !mobile ? 'px-3' : 'px-4')}>
        <NavLink
          to="/"
          aria-label="SemesTrack home"
          onClick={onClose}
          className={cn(
            'flex min-w-0 items-center gap-2.5 overflow-hidden font-bold tracking-tight text-gray-900',
            collapsed && !mobile ? 'w-full justify-center' : 'flex-1'
          )}
        >
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary-600 text-white shadow-sm shrink-0">
            <GraduationCap className="h-5 w-5" />
          </div>
          <div className={cn('flex min-w-0 flex-col overflow-hidden whitespace-nowrap transition-all duration-200', collapsed && !mobile ? 'max-w-0 -translate-x-2 opacity-0' : 'max-w-44 translate-x-0 opacity-100')} aria-hidden={collapsed && !mobile}>
              <span className="text-base font-semibold leading-tight text-gray-900">
                SemesTrack
              </span>
              <span className="text-[10px] font-medium tracking-wide uppercase text-primary-600">
                Offline AI Study
              </span>
          </div>
        </NavLink>
        {mobile && onClose && (
          <button
            type="button"
            onClick={onClose}
            className="ml-2 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-900"
            aria-label="Close navigation menu"
          >
            <X className="h-5 w-5" />
          </button>
        )}
      </div>

      {/* Navigation Items */}
      <nav id={mobile ? 'mobile-navigation' : 'desktop-navigation'} className="flex-1 space-y-1.5 overflow-y-auto p-3">
        {navItems.map((item) => {
          const Icon = item.icon;
          const linkNode = (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              onClick={onClose}
              className={({ isActive }) =>
                cn(
                  'flex min-h-10 items-center gap-3 overflow-hidden rounded-lg px-3 py-2.5 text-sm font-medium transition-[color,background-color,padding] duration-200 cursor-pointer',
                  isActive
                    ? 'bg-primary-50 text-primary-700 font-semibold shadow-xs'
                    : 'text-gray-600 hover:bg-gray-100/80 hover:text-gray-900',
                  collapsed && !mobile && 'justify-center gap-0 px-2'
                )
              }
            >
              <Icon className="h-5 w-5 shrink-0" />
              <span
                className={cn('overflow-hidden whitespace-nowrap transition-all duration-200', collapsed && !mobile ? 'max-w-0 -translate-x-2 opacity-0' : 'max-w-40 translate-x-0 opacity-100')}
                aria-hidden={collapsed && !mobile}
              >
                {item.label}
              </span>
            </NavLink>
          );

          if (collapsed && !mobile) {
            return (
              <Tooltip key={item.to} content={item.label} side="right">
                {linkNode}
              </Tooltip>
            );
          }

          return linkNode;
        })}
      </nav>

      {/* Offline Status Badge & Collapse Toggle */}
      <div className="p-3 border-t border-gray-100 space-y-2">
        {(!collapsed || mobile) ? (
          <div className="flex items-center gap-2 rounded-lg bg-emerald-50/70 p-2 text-xs text-emerald-800 border border-emerald-100">
            <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse shrink-0" />
            <div className="min-w-0">
              <p className="font-medium truncate">100% Offline</p>
              <p className="text-[10px] text-emerald-600 truncate">Local LLM & Embeddings</p>
            </div>
          </div>
        ) : (
          <Tooltip content="100% Local & Offline" side="right">
            <div className="flex justify-center p-2 rounded-lg bg-emerald-50 text-emerald-700">
              <HardDrive className="h-4 w-4" />
            </div>
          </Tooltip>
        )}

        {/* Collapse Button */}
        {mobile && onClose ? (
          <button
            type="button"
            onClick={onClose}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-800"
          >
            <X className="h-4 w-4" />
            <span>Close navigation</span>
          </button>
        ) : onToggleCollapse && (
          <button
            type="button"
            onClick={onToggleCollapse}
            aria-expanded={!collapsed}
            aria-controls="desktop-navigation"
            className={cn(
              'flex w-full items-center gap-2 overflow-hidden rounded-lg px-3 py-2 text-xs font-medium text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-800 cursor-pointer',
              collapsed && 'justify-center gap-0 px-0'
            )}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            title={collapsed ? 'Expand sidebar' : undefined}
          >
            <ChevronLeft className={cn('h-4 w-4 shrink-0 transition-transform duration-300', collapsed && 'rotate-180')} />
            <span className={cn('overflow-hidden whitespace-nowrap transition-all duration-200', collapsed ? 'max-w-0 opacity-0' : 'max-w-32 opacity-100')}>Collapse sidebar</span>
          </button>
        )}
      </div>
    </aside>
  );
}
