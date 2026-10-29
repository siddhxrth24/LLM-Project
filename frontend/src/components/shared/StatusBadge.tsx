import * as React from 'react';
import {
  CheckCircle2,
  AlertCircle,
  XCircle,
  HelpCircle,
  Clock,
  Loader2,
  AlertOctagon,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

export type StatusType =
  | 'covered'
  | 'partially_covered'
  | 'not_found'
  | 'needs_review'
  | 'pending'
  | 'processing'
  | 'completed'
  | 'failed'
  | string;

export interface StatusBadgeProps {
  status: StatusType;
  className?: string;
  showIcon?: boolean;
  label?: string;
}

const statusConfig: Record<
  string,
  {
    label: string;
    variant: 'default' | 'secondary' | 'destructive' | 'outline' | 'success' | 'warning';
    badgeClass: string;
    icon: React.ComponentType<{ className?: string }>;
    iconClass: string;
  }
> = {
  covered: {
    label: 'Covered',
    variant: 'success',
    badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100',
    icon: CheckCircle2,
    iconClass: 'text-emerald-600',
  },
  partially_covered: {
    label: 'Partially Covered',
    variant: 'secondary',
    badgeClass: 'bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100',
    icon: AlertCircle,
    iconClass: 'text-blue-600',
  },
  not_found: {
    label: 'Not Found',
    variant: 'destructive',
    badgeClass: 'bg-red-50 text-red-700 border-red-200 hover:bg-red-100',
    icon: XCircle,
    iconClass: 'text-red-600',
  },
  needs_review: {
    label: 'Needs Review',
    variant: 'warning',
    badgeClass: 'bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100',
    icon: HelpCircle,
    iconClass: 'text-amber-600',
  },
  pending: {
    label: 'Pending',
    variant: 'secondary',
    badgeClass: 'bg-gray-100 text-gray-700 border-gray-200 hover:bg-gray-200',
    icon: Clock,
    iconClass: 'text-gray-500',
  },
  processing: {
    label: 'Processing',
    variant: 'secondary',
    badgeClass: 'bg-indigo-50 text-indigo-700 border-indigo-200 hover:bg-indigo-100',
    icon: Loader2,
    iconClass: 'text-indigo-600 animate-spin',
  },
  completed: {
    label: 'Completed',
    variant: 'success',
    badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100',
    icon: CheckCircle2,
    iconClass: 'text-emerald-600',
  },
  failed: {
    label: 'Failed',
    variant: 'destructive',
    badgeClass: 'bg-red-50 text-red-700 border-red-200 hover:bg-red-100',
    icon: AlertOctagon,
    iconClass: 'text-red-600',
  },
};

export function StatusBadge({
  status,
  className,
  showIcon = true,
  label: customLabel,
}: StatusBadgeProps) {
  const normalizedKey = status?.toLowerCase().trim() || 'pending';
  const config = statusConfig[normalizedKey] || {
    label: status || 'Unknown',
    variant: 'secondary' as const,
    badgeClass: 'bg-gray-100 text-gray-700 border-gray-200',
    icon: AlertCircle,
    iconClass: 'text-gray-500',
  };

  const Icon = config.icon;
  const displayLabel = customLabel || config.label;

  return (
    <Badge
      variant="outline"
      className={cn(
        'inline-flex items-center gap-1.5 font-medium px-2.5 py-0.5 border text-xs transition-colors',
        config.badgeClass,
        className
      )}
    >
      {showIcon && <Icon className={cn('h-3.5 w-3.5 shrink-0', config.iconClass)} />}
      <span>{displayLabel}</span>
    </Badge>
  );
}
