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
  ChevronRight,
  GraduationCap,
  HardDrive,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Tooltip } from '@/components/ui/tooltip';

interface SidebarProps {
  collapsed?: boolean;
  onToggleCollapse?: () => void;
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

export function Sidebar({ collapsed = false, onToggleCollapse }: SidebarProps) {
  return (
    <aside
      className={cn(
        'relative flex flex-col border-r border-gray-200 bg-white transition-all duration-300 select-none z-30 shrink-0 h-screen sticky top-0',
        collapsed ? 'w-18' : 'w-64'
      )}
    >
      {/* Brand Header */}
      <div className="flex h-16 items-center border-b border-gray-100 px-4 justify-between">
        <NavLink
          to="/"
          className={cn(
            'flex items-center gap-2.5 font-bold tracking-tight text-gray-900 transition-opacity',
            collapsed ? 'justify-center w-full' : ''
          )}
        >
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary-600 text-white shadow-sm shrink-0">
            <GraduationCap className="h-5 w-5" />
          </div>
          {!collapsed && (
            <div className="flex flex-col">
              <span className="text-base font-semibold leading-tight text-gray-900">
                SemesTrack
              </span>
              <span className="text-[10px] font-medium tracking-wide uppercase text-primary-600">
                Offline AI Study
              </span>
            </div>
          )}
        </NavLink>
      </div>

      {/* Navigation Items */}
      <nav className="flex-1 space-y-1.5 p-3 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          const linkNode = (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors cursor-pointer',
                  isActive
                    ? 'bg-primary-50 text-primary-700 font-semibold shadow-xs'
                    : 'text-gray-600 hover:bg-gray-100/80 hover:text-gray-900',
                  collapsed && 'justify-center px-2'
                )
              }
            >
              <Icon className="h-5 w-5 shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          );

          if (collapsed) {
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
        {!collapsed ? (
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
        {onToggleCollapse && (
          <button
            type="button"
            onClick={onToggleCollapse}
            className={cn(
              'flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-800 transition-colors cursor-pointer',
              collapsed && 'justify-center px-0'
            )}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <>
                <ChevronLeft className="h-4 w-4" />
                <span>Collapse Sidebar</span>
              </>
            )}
          </button>
        )}
      </div>
    </aside>
  );
}
